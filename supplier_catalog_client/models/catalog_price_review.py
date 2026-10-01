# -*- coding: utf-8 -*-
import json

from odoo import fields, models


class CatalogPriceReview(models.Model):
    _name = "supplier.catalog.price.review"
    _description = "Catalog Price Review"
    _order = "write_date desc, id desc"
    _rec_name = "product_name"

    supplier_code = fields.Char(required=True, index=True)
    supplier_name = fields.Char(required=True)
    product_code = fields.Char(required=True, index=True)
    product_name = fields.Char(required=True)
    currency = fields.Char()
    uom = fields.Char()
    purchase_price_available = fields.Boolean()
    purchase_list_price = fields.Float(digits="Product Price")
    purchase_list_price_available = fields.Boolean()
    purchase_discounts_json = fields.Text()
    recommended_retail_price = fields.Float(digits="Product Price")
    recommended_retail_price_available = fields.Boolean()
    issue = fields.Selection(
        [
            ("no_purchase_price", "Falta el precio de compra"),
            ("retail_only", "Solo se ha recibido el PVP"),
            ("discount_missing", "Falta el descuento para calcular el coste"),
            ("discount_without_price", "Hay descuento, pero falta la tarifa base"),
        ],
        required=True,
    )
    state = fields.Selection(
        [("open", "Pendiente de revisar"), ("resolved", "Resuelto")],
        default="open",
        required=True,
        index=True,
    )
    source_updated_at = fields.Char()

    _sql_constraints = [
        (
            "supplier_product_code_unique",
            "unique(supplier_code, product_code)",
            "A supplier catalog item can only have one open review record per product code.",
        )
    ]

    def discounts(self):
        self.ensure_one()
        try:
            value = json.loads(self.purchase_discounts_json or "[]")
            return value if isinstance(value, list) else []
        except (TypeError, ValueError):
            return []
