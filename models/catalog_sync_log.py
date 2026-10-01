# -*- coding: utf-8 -*-
import logging
import math
import json

from odoo import api, fields, models

from .catalog_hub_http_client import CatalogHubClient, CatalogHubError

_logger = logging.getLogger(__name__)


class CatalogSyncLog(models.Model):
    """One record per sync attempt (manual or cron), for visibility/audit —
    never overwrites, so you can see the history and diagnose a failed
    month's sync."""

    _name = "supplier.catalog.sync.log"
    _description = "Supplier Catalog Sync Log"
    _order = "create_date desc"

    name = fields.Char(default="Catalog sync", required=True)
    state = fields.Selection(
        [("running", "Running"), ("done", "Done"), ("error", "Error")],
        default="running",
        required=True,
    )
    started_at = fields.Datetime(default=fields.Datetime.now)
    finished_at = fields.Datetime()
    hub_cursor = fields.Char(help="Hub snapshot cursor used for the next incremental sync.")
    products_received = fields.Integer()
    products_created = fields.Integer()
    products_updated = fields.Integer()
    suppliers_created = fields.Integer()
    price_review_items = fields.Integer(string="Items needing price review")
    revoked_suppliers = fields.Integer(string="Revoked supplier accesses")
    error_message = fields.Text()

    @api.model
    def _get_client(self):
        """Delegates to a thin factory so tests can inject a fake client
        instead of making a real HTTP call. Falls back to hub_client_base
        parameters and HUB_* environment variables for seamless unified configuration."""
        import os

        icp = self.env["ir.config_parameter"].sudo()
        hub_url = (
            os.environ.get("HUB_URL")
            or icp.get_param("supplier_catalog_client.hub_url")
            or icp.get_param("hub_client_base.hub_url")
            or "http://localhost:8000"
        ).strip()
        api_key = (
            os.environ.get("HUB_API_KEY")
            or icp.get_param("supplier_catalog_client.api_key")
            or icp.get_param("hub_client_base.api_key")
            or ""
        ).strip()
        return CatalogHubClient(hub_url=hub_url, api_key=api_key)

    @api.model
    def run_sync(self, full=False):
        """Entry point for both the scheduled cron and the manual 'Sync Now'
        button. `full=True` ignores the last successful sync timestamp and
        re-pulls everything (useful the first time, or to recover from a
        gap)."""
        log = self.create({})
        try:
            since = None if full else self._last_successful_sync_timestamp()
            client = self._get_client()
            stats = {
                "products_created": 0,
                "products_updated": 0,
                "suppliers_created": 0,
                "price_review_items": 0,
                "revoked_suppliers": 0,
            }
            products_received = 0
            with self.env.cr.savepoint():
                for products, _generated_at in client.iter_update_pages(since=since):
                    validated_products = self._validate_products(products)
                    page_stats = self._apply_products(validated_products)
                    products_received += len(products)
                    for key in stats:
                        stats[key] += page_stats[key]
                access_states = client.fetch_supplier_access()
                stats["revoked_suppliers"] = self._apply_supplier_access(access_states)
            log.write(
                {
                    "state": "done",
                    "finished_at": fields.Datetime.now(),
                    "hub_cursor": client.generated_at,
                    "products_received": products_received,
                    **stats,
                }
            )
        except CatalogHubError as exc:
            _logger.error("Catalog sync failed: %s", exc)
            log.write(
                {
                    "state": "error",
                    "finished_at": fields.Datetime.now(),
                    "error_message": str(exc),
                }
            )
        except Exception as exc:  # noqa: BLE001 - persist any unexpected failure
            _logger.exception("Catalog sync failed unexpectedly")
            log.write(
                {
                    "state": "error",
                    "finished_at": fields.Datetime.now(),
                    "error_message": str(exc),
                }
            )
        return log

    def _apply_supplier_access(self, statuses):
        Access = self.env["supplier.catalog.access.status"]
        revoked = 0
        for item in statuses:
            existing = Access.search([("supplier_code", "=", item["supplier_code"])], limit=1)
            values = {
                "supplier_code": item["supplier_code"],
                "supplier_name": item["supplier_name"],
                "state": item["state"],
                "changed_at": item["changed_at"],
            }
            if existing:
                existing.write(values)
            else:
                Access.create(values)
            if item["state"] == "revoked":
                revoked += 1
        return revoked

    def _last_successful_sync_timestamp(self):
        last = self.search([("state", "=", "done"), ("hub_cursor", "!=", False)], order="finished_at desc", limit=1)
        return last.hub_cursor if last else None

    @api.model
    def _validate_products(self, products):
        """Reject malformed snapshots before changing any live catalog data."""
        if not isinstance(products, list):
            raise CatalogHubError("The catalog snapshot must contain a products list")
        validated = []
        seen = set()
        for index, item in enumerate(products, 1):
            if not isinstance(item, dict):
                raise CatalogHubError("Catalog row %s is not an object" % index)
            required = ("supplier_code", "supplier_name", "product_code", "name", "purchase_price_available", "currency", "uom")
            missing = [key for key in required if item.get(key) in (None, "")]
            if missing:
                raise CatalogHubError("Catalog row %s is missing: %s" % (index, ", ".join(missing)))
            for key in ("supplier_code", "supplier_name", "product_code", "name", "currency", "uom"):
                item[key] = str(item[key]).strip()
                if not item[key]:
                    raise CatalogHubError("Catalog row %s has an empty %s" % (index, key))
            if not isinstance(item["purchase_price_available"], bool):
                raise CatalogHubError("Catalog row %s has an invalid purchase price status" % index)
            for field_name in ("price", "purchase_list_price", "recommended_retail_price"):
                value = item.get(field_name)
                if value is None:
                    continue
                try:
                    value = float(value)
                except (TypeError, ValueError) as exc:
                    raise CatalogHubError("Catalog row %s has an invalid %s" % (index, field_name)) from exc
                if not math.isfinite(value) or value < 0:
                    raise CatalogHubError("Catalog row %s has an invalid %s" % (index, field_name))
                item[field_name] = value
            if item["purchase_price_available"] != (item.get("price") is not None):
                raise CatalogHubError("Catalog row %s has inconsistent purchase price fields" % index)
            discounts = item.get("purchase_discounts", [])
            if discounts is None:
                discounts = []
            if not isinstance(discounts, list):
                raise CatalogHubError("Catalog row %s has invalid purchase discounts" % index)
            try:
                discounts = [float(value) for value in discounts]
            except (TypeError, ValueError) as exc:
                raise CatalogHubError("Catalog row %s has invalid purchase discounts" % index) from exc
            if any(not math.isfinite(value) or value < 0 or value > 100 for value in discounts):
                raise CatalogHubError("Catalog row %s has invalid purchase discounts" % index)
            item["purchase_discounts"] = discounts
            item["currency"] = item["currency"].upper()
            key = (item["supplier_code"], item["product_code"])
            if key in seen:
                raise CatalogHubError("Catalog snapshot contains duplicate supplier/product code: %s / %s" % key)
            seen.add(key)
            validated.append(item)
        return validated

    def _apply_products(self, products):
        """Unlike ai_document_processor's vendor-bill lines (deliberately
        free-text, never auto-creating products from arbitrary invoice
        wording), THIS module's entire purpose is to maintain a clean
        product/supplier catalog from curated hub data — creating/updating
        product.product + product.supplierinfo here is the intended
        behaviour, not a shortcut."""
        Partner = self.env["res.partner"]
        Product = self.env["product.product"]
        SupplierInfo = self.env["product.supplierinfo"]
        Currency = self.env["res.currency"]
        Uom = self.env["uom.uom"]

        stats = {
            "products_created": 0,
            "products_updated": 0,
            "suppliers_created": 0,
            "price_review_items": 0,
            "revoked_suppliers": 0,
        }
        supplier_cache = {}

        for item in products:
            if not item["purchase_price_available"]:
                self._upsert_price_review(item)
                stats["price_review_items"] += 1
                continue

            currency = Currency.search([("name", "=", item["currency"]), ("active", "=", True)], limit=1)
            if not currency:
                raise CatalogHubError("Unknown or inactive currency: %s" % item["currency"])
            uom = self._resolve_uom(Uom, item["uom"])
            supplier_code = item.get("supplier_code")
            partner = supplier_cache.get(supplier_code)
            if partner is None:
                matches = Partner.search([("ref", "=", supplier_code)], limit=2)
                if len(matches) > 1:
                    raise CatalogHubError(
                        "Supplier reference %s matches multiple Odoo contacts; resolve it before syncing." % supplier_code
                    )
                partner = matches
                if partner and not partner.supplier_rank:
                    raise CatalogHubError(
                        "Supplier reference %s belongs to a contact not marked as a supplier; resolve it before syncing." % supplier_code
                    )
                if not partner:
                    partner = Partner.create(
                        {
                            "name": item.get("supplier_name") or supplier_code,
                            "ref": supplier_code,
                            "supplier_rank": 1,
                        }
                    )
                    stats["suppliers_created"] += 1
                supplier_cache[supplier_code] = partner

            # A supplier's product_code is not a globally unique Odoo SKU.
            # Resolve catalog identity by the supplier's own info record so
            # two vendors can use the same code for unrelated products.
            infos = SupplierInfo.search(
                [("partner_id", "=", partner.id), ("product_code", "=", item["product_code"])],
                limit=2,
            )
            if len(infos) > 1:
                raise CatalogHubError(
                    "Supplier %s has multiple Odoo mappings for vendor product code %s; resolve the duplicates before syncing."
                    % (supplier_code, item["product_code"])
            )
            info = infos
            if info:
                product = info.product_id
                if not product:
                    variants = info.product_tmpl_id.product_variant_ids
                    if len(variants) != 1:
                        raise CatalogHubError(
                            "Supplier %s product code %s maps to a multi-variant template without a specific variant. Resolve it before syncing."
                            % (supplier_code, item["product_code"])
                        )
                    product = variants
            else:
                product = Product.create(
                    {
                        "name": item["name"],
                    }
                )
                stats["products_created"] += 1

            info_vals = {
                "partner_id": partner.id,
                "product_id": product.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_code": item.get("product_code"),
                "product_name": item.get("name"),
                "price": item["price"],
                "catalog_purchase_list_price": item.get("purchase_list_price") or 0,
                "catalog_purchase_list_price_available": item.get("purchase_list_price") is not None,
                "catalog_purchase_discounts": json.dumps(item.get("purchase_discounts") or []),
                "catalog_recommended_retail_price": item.get("recommended_retail_price") or 0,
                "catalog_recommended_retail_price_available": item.get("recommended_retail_price") is not None,
            }
            if "currency_id" in SupplierInfo._fields:
                info_vals["currency_id"] = currency.id
            if "product_uom" in SupplierInfo._fields:
                info_vals["product_uom"] = uom.id
            elif "product_uom_id" in SupplierInfo._fields:
                info_vals["product_uom_id"] = uom.id
            if info:
                info.write(info_vals)
                stats["products_updated"] += 1
            else:
                SupplierInfo.create(info_vals)
            review = self.env["supplier.catalog.price.review"].search(
                [("supplier_code", "=", supplier_code), ("product_code", "=", item["product_code"])], limit=1
            )
            if review:
                review.write({"state": "resolved", "source_updated_at": item.get("updated_at")})

        return stats

    def _upsert_price_review(self, item):
        Review = self.env["supplier.catalog.price.review"]
        has_list = item.get("purchase_list_price") is not None
        has_retail = item.get("recommended_retail_price") is not None
        discounts = item.get("purchase_discounts") or []
        if has_retail and not has_list and not discounts:
            issue = "retail_only"
        elif has_list and not discounts:
            issue = "discount_missing"
        elif discounts and not has_list:
            issue = "discount_without_price"
        else:
            issue = "no_purchase_price"
        values = {
            "supplier_code": item["supplier_code"],
            "supplier_name": item["supplier_name"],
            "product_code": item["product_code"],
            "product_name": item["name"],
            "currency": item["currency"],
            "uom": item["uom"],
            "purchase_price_available": False,
            "purchase_list_price": item.get("purchase_list_price") or 0,
            "purchase_list_price_available": has_list,
            "purchase_discounts_json": json.dumps(discounts),
            "recommended_retail_price": item.get("recommended_retail_price") or 0,
            "recommended_retail_price_available": has_retail,
            "issue": issue,
            "state": "open",
            "source_updated_at": item.get("updated_at"),
        }
        existing = Review.search(
            [("supplier_code", "=", item["supplier_code"]), ("product_code", "=", item["product_code"])],
            limit=1,
        )
        if existing:
            existing.write(values)
        else:
            Review.create(values)

    @api.model
    def _resolve_uom(self, Uom, uom_code):
        aliases = {
            "unit": "uom.product_uom_unit",
            "units": "uom.product_uom_unit",
            "unidad": "uom.product_uom_unit",
            "unidades": "uom.product_uom_unit",
            "kg": "uom.product_uom_kgm",
            "kilogram": "uom.product_uom_kgm",
            "kilograms": "uom.product_uom_kgm",
            "m": "uom.product_uom_meter",
            "meter": "uom.product_uom_meter",
            "meters": "uom.product_uom_meter",
        }
        xmlid = aliases.get(uom_code.strip().casefold())
        if xmlid:
            uom = self.env.ref(xmlid, raise_if_not_found=False)
            if uom:
                return uom
        candidates = Uom.search([("name", "=", uom_code.strip())], limit=2)
        if len(candidates) == 1:
            return candidates
        raise CatalogHubError("Unknown or ambiguous unit of measure: %s" % uom_code)
