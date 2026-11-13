# Estado del proyecto / pendientes

## Deploy hecho el 12/11/2026

Commit `1d60308a` pusheado a `main` y deployado en producción
(`erp.multiliderestech.online` → VPS `148.230.73.167`):

- SSH: `ssh -i ~/.ssh/tbot_vps root@148.230.73.167` (clave instalada vía paramiko,
  usuario root — `ubuntu` no acepta password).
- Sitio: `/home/ubuntu/www/SitioMTCRM`, venv `/home/ubuntu/DJENV` (NO el DJENV del repo).
- Web: lighttpd → scgi :4600 → vassal `/etc/uwsgi/vassals/uwsgi13.ini` (uWSGI Emperor).
- Deploy: `git pull` → `manage.py collectstatic --noinput` (como root, staticfiles es
  root-owned) → `touch /etc/uwsgi/vassals/uwsgi13.ini` (el Emperor recarga el vassal).
- Migraciones 0022/0023 ya estaban aplicadas en la DB vía conexión `remote`.
- Verificado: workers respawned, GET / → 200.

## Qué se implementó (rama de trabajo actual)

- Modelo `StockMovement` + servicio `core/erp/services/stock_service.py`
  (`adjust_stock` / `log_stock_movement`). Toda mutación de `Product.stock` queda
  auditada: ventas, fiados, anulaciones, ediciones, remitos, transferencias,
  importaciones, ajustes manuales y syncs.
- `stock` removido del `ProductForm` (ya no se edita a mano). Se agregó botón
  "Ajustar stock" (modal con motivo obligatorio) y botón "Historial" en
  `product/list.html`/`list.js`; acciones `adjust_stock` y `stock_history`
  en `ProductListView.post`.
- Stock negativo permitido: se eliminaron los pisos `Greatest(F('stock')-cant, 0)`
  y la validación `stock < 0` de `Product.clean()`. Remitos de salida y
  anulaciones ya no bloquean (dejan warning en log).
- Migración `erp.0022_stockmovement` aplicada en `default` y `remote`.
- Migración `erp.0023_employeeaccountpayment` aplicada en `default` y `remote`.
- Pagos parciales (abonos) en cuentas corrientes: modelo `EmployeeAccountPayment`
  (monto, forma de pago, nota, usuario, fecha) + helpers `amount_paid()`/`balance()`
  en `EmployeeAccountSale`. Botón "Abonar" (monedas) en
  `employee_account_list.html` con modal; columnas Abonado/Saldo; historial en el
  detalle. Los abonos NO crean venta ni tocan caja (el ingreso lo hace el usuario
  con movimiento de caja manual). `mark_as_paid` con abonos solo marca paga sin
  crear Sale (evita duplicar el ingreso). `total_debt` del listado ahora descuenta
  los abonos. Pedido por Pablo (Don Julio Pereiro, empresa 7).
- Alta rápida de cliente desde el modal de Cuenta Corriente del POS: action
  `add_client` en `sale/views.py` + botón "Nuevo cliente" con mini-form inline
  en `pos.html` + handlers en `sale/js/pos.js` (bump `?v=20261112`). Antes el
  modal solo permitía elegir clientes existentes (el viejo "agregar empleado"
  está comentado) y el botón tenía un `"` de más en el HTML — corregido.

## Cambios 13/11/2026 (listado de movimientos + fix de fechas UTC→local)

Commit `3d11bbc1` pusheado a `main` y deployado (GET / → 200, ruta nueva
responde 302→login).

- `StockMovementListView` (`/erp/stock-movement/list/`): listado global de
  movimientos de stock con filtros por fecha, tipo, usuario y producto
  (hasta 500 filas). Template `stock_movement/list.html`, entrada en el
  menú Inventario. Permite auditar "qué ajustes manuales hizo X usuario".
- Fix de timezone: los `DateTimeField` se guardan en UTC (USE_TZ=True) pero
  varios puntos usaban `.date()`/`strftime()`/`date.today()` que devuelven
  fecha UTC o del SO → ventas después de las 21:00 AR (00:00 UTC) caían en
  el día siguiente en Libro IVA, cuenta corriente, asientos contables, QR
  de AFIP, informes y exportaciones. Se agregó `local_date()` en models.py
  y se migró todo a `timezone.localdate()`/`timezone.localtime()`:
  - models.py: `fecha` de LibroIvaRegistro, CuentaCorrienteCliente,
    AsientoContable, `fecha_cbte` del QR AFIP, validación date_birthday,
    `__str__` de ActivityLog y EmployeeAccountSale.
  - `sync_sales_api` (sale/views.py): `make_aware(fromisoformat(...))`
    explotaba con fechas aware (`+00:00`/`Z`) → caía al `except` y la venta
    quedaba con fecha de sync, no de venta. Ahora parsea aware/naive.
  - Display: afip issue_date, pdf_utils, exports CSV/Excel de reports,
    export_iva_digital, dashboard export, operator_reports (ya usaba
    localtime), activity_log, cash_register, profit_views, forms (fecha
    inicial remitos), undo_views, history de ajustes de margen.
- `__date` del ORM ya era correcto (Django convierte al TZ activo).

## Cambios 13/11/2026 tarde (remito A00114-00004081 + carga guiada)

- Remito #147 (empresa 10, Avícola Santa Ana): Cintia cargó `$P.U.Lista`
  (con IVA, sin bonif.) en vez de `$P.U.Neto`. Corregidos los 9
  `precio_unitario` a los netos del PDF; quedó **pending** con nota en
  observaciones para que ella revise y procese. Informe PDF:
  `videos_tutoriales/informe_carga_remito_cintia.pdf`
  (`scripts/generar_informe_remito_cintia.py`).
- `remito/create.html`: campos Bonif% + IVA% por línea, radio
  "precio neto / precio de lista" (con modo `agregado`+lista el neto se
  calcula solo), etiqueta dinámica del precio, columna Neto siempre
  visible. Sin migración — solo template/JS.
- Fix `_line_iva_rate` (remito/views.py) y el `lineRate` del JS: producto
  con `iva_rate=0` ahora cae al % del remito. OJO: los productos de Acro
  tienen `iva_rate=0.0000` (dato, no "exento") — definir alícuotas reales
  con el contador antes de cargarlas (afecta desglose de IVA en ventas).
- Pendiente con Cintia: "SSEBA Pata muslo" se cargó en registro SOY
  (90348); "Soy Alas" en 90351 (duplicado conflictivo — verificar si
  físicamente entró AVEGUAY → correspondería 90328).
- Commit `eda6cac2`: modal "Nuevo Producto" alineado al flujo — radio
  neto/lista + Bonif% (calcula `cost_price` neto), al crear precarga
  `ivaPctLinea` con el `iva_rate` del producto y llena `precioUnitario`
  según el modo de la fila (antes volcaba siempre el costo neto → doble
  descuento en modo lista). Guía PDF para Cintia:
  `videos_tutoriales/guia_carga_remito.pdf`
  (`scripts/generar_guia_remito_cintia.py` + capturas en
  `videos_tutoriales/guia_remito/`).
- Commit `845e97e6`: detalle de remito pendiente muestra tabla "Impacto
  al procesar" por línea (stock actual→resultante, costo actual→nuevo,
  P. venta actual→nuevo, alerta si queda negativo) con la misma fórmula
  que `procesar_remito`. El modal "Ajustar precios" ahora previsualiza
  el PVP sobre el costo que va a quedar al procesar, no el viejo.
- Commit `f3b745c0`: el modal "Ajustar precios" es bidireccional — se
  puede tipear el PVP final directamente (el margen muestra el implícito)
  o el margen (recalcula el PVP). Al guardar con PVP manual persiste el
  `pvp_final` exacto y el `margin_percentage` implícito para que futuros
  recalculos de remito no pisen el precio acordado. Endpoint
  `actualizar-margen` acepta `{items:[{id, margin|pvp_final}]}` +
  formato viejo `{margins:{}}`.
- Commit `c06c8490`: modal de producto compartido (alta/edición) con
  dto. proveedor, flete, IVA, margen, PVP neto y PVP final bidireccional.
  `ProductUpdateView` action `quick_update` actualiza solo esos campos
  (verifica empresa). Flujo de remito: al elegir producto existente y
  apretar Agregar, el modal de edición se abre con datos de la DB + el
  costo tipeado; la línea se confirma recién al Guardar (`_pendingLinea`).
  Si cancela el modal, la línea NO se agrega. Lápices junto al buscador
  y en cada fila para editar sin agregar.
- Commit `b5d20d59`: proyección "Qué pasará al procesar" también en el
  formulario de carga (tabla live con stock→queda, costo→nuevo,
  PVP→nuevo por línea, misma fórmula que `procesar_remito`). El
  detalle usa el mismo formato compacto "antes → nuevo". El buscador
  viaja con snapshot completo vía `toJSON` + nuevo campo
  `supplier_default_discount`. Fix autocompletado de precio: en modo
  lista/incluido sugiere `costo×(1+IVA)` (el campo espera con IVA).

## Normalización aplicada (12/11, conteo físico Acro Activo, empresa 10)

Ajustes `manual` ya escritos en el servidor con `adjust_stock(using='remote')`:
90348 pata muslo 36→41 (+5), 90216 milanesas 6kg 1→4 (+3), 90328 alas AVEGUAY 21→22 (+1),
90332 cogote 5→6 (+1), 90276 milanesa 1kg 7→8 (+1). Resto del conteo: exacto.

## Pendiente al retomar (estado remito #147 / factura A00114-00004081)

Hecho directo en producción vía `manage.py shell` (simulando el modal nuevo):

- Los 9 productos del remito quedaron con `cost_price` = neto factura y
  `pvp_final` = **precio de lista × 1,10** (valores exactos que pidió el
  usuario, ref. imagen "Con 10% agregado"): milanesa 49313, patitas 52107,
  medallón 52668, soy alas 41250, carne mecánica 30250, carcasa 19305,
  suprema 126500, bifecito 131813, pata muslo 42504. En cada uno se
  guardó el `margin_percentage` implícito (4,64%–38,65%) para que el
  recálculo al procesar no pise el precio.
- **La línea PATA MUSLO x80 (neto 33219.91) había desaparecido del remito**
  (quedaban 8 de 9 renglones) — se re-agregó como `DetalleRemito` 510.
  Avisar a Cintia: posiblemente se borró al re-editar el remito.
- Neto total remito: 8.676.171,17 vs factura 8.676.171,15 (2¢ redondeo). OK.
- Remito sigue `pending` con nota en observaciones; al procesar solo debe
  impactar stock (costos/PVP ya quedaron como corresponde).
- OJO: solo `OPT SUPREMA BLOQUE` (90367) tiene `iva_rate=0.21` real; el
  resto sigue en 0 → su `pvp` = `pvp_final`. Pendiente con contador.
- Duplicados sin resolver: línea "SOY ALAS" sigue en prod 90351 (si
  entró AVEGUAY físico corresponde 90328); pata muslo todo en SOY 90348.

## Hallazgo conocido sin corregir

- `core/erp/views/transfer/views.py`: al recibir transferencia suma stock al
  producto de ORIGEN (`detail.product`) aunque el destino ya fue acreditado al
  crearla → fabrica stock en destino y restaura origen. Quedó auditado por
  StockMovement; decidir si se corrige la lógica.
- Acro Activo vende "CAJA SOY ALAS" (114 en 35 días) con stock 0 mientras
  despacha cajas físicas AVEGUAY → el stock se desfasa por uso del registro
  equivocado. Sugerir unificar productos duplicados SOY/AVEGUAY o revisar
  qué registro se usa al cobrar.

## Informes generados

- `videos_tutoriales/informe_desfasaje_stock_2_acroactivo.pdf` (informe Nro 5,
  diagnóstico + guía del ranking). Script: `scripts/generar_informe_desfasaje_v2.py`.
