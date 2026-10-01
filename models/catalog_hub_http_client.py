# -*- coding: utf-8 -*-
"""Pure-Python client for the central catalog hub API — no Odoo import here
on purpose, so it can be unit-tested with plain pytest + a mocked `requests`
session, without any Odoo runtime.

API contract (hub side, versioned so both sides can evolve independently):

    GET {hub_url}/api/v3/catalog/sync?since=<ISO8601 or omitted for full sync>&limit=500
    Header: Authorization: Bearer <api_key>

    200 response (next_cursor is null on the last page):
    {
      "generated_at": "2026-09-23T10:00:00Z",
      "next_cursor": "opaque-token-or-null",
      "products": [
        {
          "supplier_code": "PROV001",
          "supplier_name": "Ferreteria XYZ",
          "product_code": "TORN-8X40",
          "name": "Tornillo M8x40",
          "price": 0.12,
          "purchase_price_available": true,
          "purchase_list_price": 0.15,
          "purchase_discounts": [20],
          "recommended_retail_price": 0.25,
          "currency": "EUR",
          "uom": "unit",
          "updated_at": "2026-09-20T00:00:00Z"
        }
      ]
    }

Which suppliers/products a given API key is entitled to see (billing /
entitlements) is decided entirely hub-side — this client never filters or
assumes anything about that.
"""
import logging

import requests

_logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60
PAGE_SIZE = 500
MAX_PAGES = 10000


class CatalogHubError(Exception):
    """Raised for any hub-level failure (bad config, timeout, HTTP error,
    unexpected response shape)."""


class CatalogHubClient:
    """Independent from the ORM, so it is trivially mockable/injectable in
    unit tests (no Odoo registry needed) — pass a fake `session` with a
    `.get()` method."""

    def __init__(self, hub_url, api_key, timeout=None, session=None):
        self.hub_url = (hub_url or "").rstrip("/")
        self.api_key = api_key
        self.timeout = timeout or DEFAULT_TIMEOUT
        self._session = session or requests
        self.generated_at = None

    def iter_update_pages(self, since=None, timeout=None):
        """Yield (products, generated_at) for pages of one stable sync.

        Send `since` only on the first request; continuation requests use the
        Hub's opaque cursor. All pages must belong to the same snapshot.
        """
        if not self.hub_url:
            raise CatalogHubError(
                "Catalog hub URL is not configured. Set it in Settings."
            )
        if not self.api_key:
            raise CatalogHubError(
                "Catalog hub API key is not configured. Set it in Settings."
            )

        self.generated_at = None
        headers = {"Authorization": "Bearer %s" % self.api_key}
        cursor = None
        seen_cursors = set()
        for _page_number in range(MAX_PAGES):
            params = {"limit": PAGE_SIZE}
            if cursor:
                params["cursor"] = cursor
            elif since:
                params["since"] = since
            try:
                response = self._session.get(
                    "%s/api/v3/catalog/sync" % self.hub_url,
                    params=params,
                    headers=headers,
                    timeout=timeout or self.timeout,
                )
            except requests.exceptions.Timeout as exc:
                _logger.error("Catalog hub request timed out")
                raise CatalogHubError("Catalog hub request timed out") from exc
            except requests.exceptions.RequestException as exc:
                # Never log the API key or request headers.
                _logger.error("Catalog hub request failed: %s", type(exc).__name__)
                raise CatalogHubError("Catalog hub request failed") from exc

            if response.status_code >= 400:
                _logger.error("Catalog hub returned HTTP %s", response.status_code)
                raise CatalogHubError("Catalog hub returned HTTP %s" % response.status_code)

            try:
                data = response.json()
            except ValueError as exc:
                raise CatalogHubError("Unexpected catalog hub response shape") from exc
            if not isinstance(data, dict):
                raise CatalogHubError("Unexpected catalog hub response shape")
            products = data.get("products")
            generated_at = data.get("generated_at")
            next_cursor = data.get("next_cursor")
            if (
                not isinstance(products, list)
                or not isinstance(generated_at, str)
                or not generated_at
                or (next_cursor is not None and (not isinstance(next_cursor, str) or not next_cursor))
            ):
                raise CatalogHubError("Unexpected catalog hub response shape")
            if self.generated_at is None:
                self.generated_at = generated_at
            elif self.generated_at != generated_at:
                raise CatalogHubError("Catalog Hub changed the snapshot during pagination")

            yield products, generated_at
            if next_cursor is None:
                return
            if next_cursor in seen_cursors:
                raise CatalogHubError("Catalog Hub repeated a pagination cursor")
            seen_cursors.add(next_cursor)
            cursor = next_cursor

        raise CatalogHubError("Catalog Hub exceeded the maximum number of pages")

    def fetch_updates(self, since=None, timeout=None):
        """Compatibility helper that collects all pages into one list."""
        products = []
        for page, _generated_at in self.iter_update_pages(since=since, timeout=timeout):
            products.extend(page)
        return products

    def fetch_supplier_access(self, timeout=None):
        """Fetch current access states; local products are never deleted."""
        if not self.hub_url or not self.api_key:
            raise CatalogHubError("Catalog hub URL and API key must be configured")
        headers = {"Authorization": "Bearer %s" % self.api_key}
        try:
            response = self._session.get(
                "%s/api/v3/catalog/access" % self.hub_url,
                headers=headers,
                timeout=timeout or self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise CatalogHubError("Catalog hub access status request timed out") from exc
        except requests.exceptions.RequestException as exc:
            _logger.error("Catalog hub access status request failed: %s", type(exc).__name__)
            raise CatalogHubError("Catalog hub access status request failed") from exc
        if response.status_code >= 400:
            raise CatalogHubError("Catalog hub access status returned HTTP %s" % response.status_code)
        try:
            data = response.json()
        except ValueError as exc:
            raise CatalogHubError("Unexpected catalog hub access response shape") from exc
        if not isinstance(data, dict) or not isinstance(data.get("suppliers"), list):
            raise CatalogHubError("Unexpected catalog hub access response shape")
        validated = []
        seen = set()
        for index, item in enumerate(data["suppliers"], 1):
            if not isinstance(item, dict):
                raise CatalogHubError("Supplier access row %s is not an object" % index)
            code = item.get("supplier_code")
            name = item.get("supplier_name")
            state = item.get("status")
            changed_at = item.get("changed_at")
            if not all(isinstance(value, str) and value.strip() for value in (code, name, changed_at)):
                raise CatalogHubError("Supplier access row %s has invalid text fields" % index)
            if state not in ("active", "revoked"):
                raise CatalogHubError("Supplier access row %s has an invalid status" % index)
            if code in seen:
                raise CatalogHubError("Catalog Hub returned duplicate supplier access code: %s" % code)
            seen.add(code)
            validated.append(
                {
                    "supplier_code": code.strip(),
                    "supplier_name": name.strip(),
                    "state": state,
                    "changed_at": changed_at,
                }
            )
        return validated
