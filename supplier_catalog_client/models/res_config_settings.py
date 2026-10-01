# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    catalog_hub_url = fields.Char(
        string="Catalog Hub URL",
        config_parameter="supplier_catalog_client.hub_url",
        help="Base URL of the central catalog hub API, e.g. "
        "https://hub.example.com (no trailing slash needed).",
    )
    catalog_hub_api_key = fields.Char(
        string="Catalog Hub API Key",
        config_parameter="supplier_catalog_client.api_key",
        help="Issued by the hub; determines which suppliers' catalogs this "
        "installation is entitled to sync.",
    )
