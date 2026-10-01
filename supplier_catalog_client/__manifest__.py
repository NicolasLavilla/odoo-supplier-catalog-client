{
    "name": "Supplier Catalog Client",
    "version": "19.0.1.1.4",
    "summary": "Sincroniza catálogos y precios tipados desde Catalog Hub",
    "description": """
Client Odoo module for Catalog Hub v3. It keeps supplier net purchase prices
in Odoo vendor pricelists, stores recommended retail prices separately, and
queues catalog rows without a usable purchase price for human review. The Hub
continues to enforce supplier entitlements server-side.
""",
    "category": "Technical",
    "author": "Ataraxial",
    "license": "LGPL-3",
    "depends": ["base", "product", "purchase"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/catalog_sync_log_views.xml",
        "views/catalog_price_review_views.xml",
        "views/product_supplierinfo_views.xml",
        "views/catalog_access_status_views.xml",
        "data/ir_cron_data.xml",
    ],
    "installable": True,
    "application": False,
}
