# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductSupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    catalog_purchase_list_price = fields.Float(
        string="Tarifa de compra del catálogo", digits="Product Price", copy=False
    )
    catalog_purchase_list_price_available = fields.Boolean(copy=False)
    catalog_purchase_discounts = fields.Text(string="Descuentos del catálogo", copy=False)
    catalog_recommended_retail_price = fields.Float(
        string="PVP recomendado por proveedor", digits="Product Price", copy=False
    )
    catalog_recommended_retail_price_available = fields.Boolean(copy=False)
