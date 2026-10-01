# Supplier Catalog Client — Catálogo de Proveedores para Odoo 19

![Odoo 19](https://img.shields.io/badge/Odoo-19.0-purple)
![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue)

Sincroniza automáticamente los catálogos y precios de proveedor desde el **Catalog Hub** directamente en Odoo. Mantén siempre actualizados los precios de compra, el PVP recomendado y las referencias de proveedor.

---

## Funcionalidades

- Sincronización automática de tarifas de proveedor desde el Hub centralizado
- Actualización de listas de precio de compra (`product.supplierinfo`) en Odoo
- Almacenamiento del PVP recomendado por separado (sin mezclar con precio de compra)
- Cola de revisión para filas sin precio de compra utilizable
- Log de sincronización con fecha, proveedor y resultado
- Panel de estado de acceso por proveedor (entitlements)
- Sincronización manual o automática (cron configurable)

---

## Instalación

### Requisitos

- Odoo 19.0
- Python `requests`
- Acceso al Catalog & OCR Hub (URL + clave API `chub_...`)

### Pasos

1. Copia la carpeta `supplier_catalog_client/` en tu directorio de addons
2. Actualiza la lista de módulos y activa **Supplier Catalog Client**
3. Ve a **Ajustes → Supplier Catalog** e introduce la URL del Hub y tu clave API

---

## Licencia

LGPL-3 — Libre para uso comercial y modificación, con atribución.
