# -*- coding: utf-8 -*-
from odoo import fields, models


class CatalogAccessStatus(models.Model):
    _name = "supplier.catalog.access.status"
    _description = "Estado del acceso a catálogos"
    _order = "supplier_name, supplier_code"
    _rec_name = "supplier_name"

    supplier_code = fields.Char(required=True, index=True)
    supplier_name = fields.Char(required=True)
    state = fields.Selection(
        [("active", "Activo"), ("revoked", "Revocado")],
        required=True,
        index=True,
    )
    changed_at = fields.Char(string="Último cambio comunicado por el Hub")

    _sql_constraints = [
        (
            "supplier_code_unique",
            "unique(supplier_code)",
            "Only one access status can exist per supplier code.",
        )
    ]
