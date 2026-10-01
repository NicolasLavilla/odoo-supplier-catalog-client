# Supplier Catalog Client

Sincroniza en Odoo los productos y precios de proveedor entregados por una API Catalog Hub. La sincronización crea o actualiza productos y registros de proveedor en la base local.

## Requisitos

- Odoo 19.0.
- Aplicaciones Odoo `Product` y `Purchase` instaladas.
- Python package `requests` instalado en el mismo entorno Python que ejecuta Odoo. En este repositorio se instala desde `docker/odoo/requirements.txt`; en otra instalación hay que instalarlo en el entorno del servidor Odoo antes de instalar el addon.
- Una instancia de Catalog Hub accesible por HTTPS que implemente el contrato paginado `GET /api/v3/catalog/sync`, envía la clave como `Authorization: Bearer ...` y responde con `generated_at`, `products` y `next_cursor`.

## Instalación

1. Copia la carpeta `supplier_catalog_client` en una ruta incluida en `addons_path`.
2. Instala `requests` en el entorno Python de Odoo.
3. Reinicia Odoo, actualiza la lista de aplicaciones e instala **Supplier Catalog Client**.
4. Abre Ajustes y configura `Supplier Catalog` con la URL base del Hub y la clave de API emitida para esta instalación.
5. Ejecuta **Supplier Catalog → Sync Now** y revisa **Sync History** antes de confiar en los datos importados.

El addon programa una sincronización mensual. Ajusta el intervalo de la acción planificada según el contrato de servicio y la carga acordados.

## Comportamiento y límites conocidos

- La primera ejecución sin cursor sincroniza el catálogo completo; las siguientes solicitan cambios desde el último cursor satisfactorio.
- Solo el precio neto de compra actualiza la tarifa del proveedor en Odoo. Tarifa bruta, descuentos y PVP recomendado se conservan por separado; el PVP no modifica automáticamente el precio de venta.
- Los productos nuevos con precio neto se crean y vinculan al proveedor por código. Los productos sin precio de compra aparecen en **Supplier Catalog → Precios pendientes de revisar**; no se crea una tarifa de compra cero ni se borra el último precio válido del producto existente.
- Un descuento ausente se marca para revisión solo cuando la tarifa disponible requiere ese dato para calcular el coste. Si el proveedor entrega un neto, la ausencia de descuento es normal.
- Al revocar un proveedor, el Hub comunica el estado al módulo; los productos, tarifas y demás datos locales permanecen en Odoo. **Estado de proveedores** muestra el último estado recibido. Si se reactiva el acceso, la siguiente sincronización vuelve a actualizar el catálogo.
- La lógica de permisos y proveedores incluidos corresponde al Hub y a la clave configurada. No compartas esa clave entre clientes.
- Los datos resultantes se guardan en la base de datos Odoo del cliente. Una revocación de acceso al Hub no debe borrar esos registros locales.
- El Hub y su operación son servicios externos y no se incluyen en este addon. La disponibilidad comercial del addon depende de que el servicio Hub esté operativo y contratado/configurado.
- No se ha validado este proceso contra una base de datos Odoo en esta revisión. No usar como procedimiento de producción hasta completar la etapa de pruebas autorizadas.

## Licencia y contacto

El manifiesto declara LGPL-3. La revisión de procedencia/copyright y los datos del editor aún están pendientes. No hay correo de soporte publicado en esta guía; añadir el contacto oficial antes de cualquier publicación.
