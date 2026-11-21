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
- **Revertido parcial (commit `df1b01e2`, pedido por Yasmin/AcroActivo):**
  `stock` volvió al `ProductForm` para cargar stock al crear/editar, pero
  las vistas loguean `StockMovement` (alta con stock != 0 → 'Alta de
  producto'; edición con delta → 'Edicion de producto'), así el movimiento
  sigue auditado. El modal "Ajustar stock" sigue existiendo para ajustes
  con motivo obligatorio.
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

## REVISAR MAÑANA — Yasmin (usuario AcroActivo) editó precios a mano

Después de mi ajuste ×1,10, ella editó los productos por
`/erp/product/update/` (ActivityLog 23:30–23:53 UTC del 13/11) y puso
precios **redondos**:

| Prod | ×1,10 que dejé | PVP final actual (manual) |
|---|---|---|
| 90216 milanesa | 49313 | **50000** |
| 90289 medallón | 52668 | **52000** |
| 90351 soy alas | 41250 | **42000** |
| 90297 carne mec. | 30250 | **31000** |
| 90338 carcasa | 19305 | **22000** |
| 90236 bifecito | 131813 | **132000** |
| 90348 pata muslo | 42504 | **43000** |
| 90227? patitas | 52107 | **52000** |
| 90367 suprema | 126500 | 126500 (sin cambio) |

- **Inconsistencia:** los `margin_percentage` quedaron con MIS valores
  implícitos (38,65 / 35,13 / 26,61 / 27,95%) → ya no matchean el PVP.
  Si se procesa un remito o recalcula por margen, el precio vuelve al
  valor ×1,10, no al redondo. Decidir: ¿corregir margen para que
  coincida con el PVP redondo, o restaurar precios ×1,10?
- También creó productos: `CAJA PATA MUSLO SSEBA X15KG` (23:25),
  `CAJA SSEBA PATA MUSLO X15KG` (23:42), `CAJA OPT SUPREMA X20KG`
  (23:43) y **borró el producto 90368**. Verificar si resolvió
  duplicados por su cuenta y qué producto usa el remito/POS ahora.
- Remito 147 sigue `pending` (updated 19:53 UTC).

## Fix 14/11 — productos Acro con IVA que el POS sumaba encima

Yasmin carga **precio final** (costo + PVP final, no usa IVA). Tenía 6
productos con `iva_rate=0.21` → el POS cobraba `pvp × 1.21` (ej. pata
muslo tipeado a 43000 → cobraba 52030). Se corrigió en producción:
`iva_rate=0`, `pvp=pvp_final`=precio que ella quiso cobrar, margen
recomputado (90367 suprema quedó 126500, margen 26,61%).
Después del fix, `emp10` tiene `pvp == pvp_final` en todos los
productos (verificado: 0 diferencias).

**Regla para ella:** en el form de producto dejar **IVA 0%** — si pone
21% el POS le suma IVA al precio que tipea. Las otras empresas (4/7)
trabajan al revés (pvp neto + IVA) y NO se tocaron: tienen 1200+
productos con `pvp_final = pvp×1.21` a propósito.

## Hallazgo conocido sin corregir

- `core/erp/views/transfer/views.py`: al recibir transferencia suma stock al
  producto de ORIGEN (`detail.product`) aunque el destino ya fue acreditado al
  crearla → fabrica stock en destino y restaura origen. Quedó auditado por
  StockMovement; decidir si se corrige la lógica.
- Acro Activo vende "CAJA SOY ALAS" (114 en 35 días) con stock 0 mientras
  despacha cajas físicas AVEGUAY → el stock se desfasa por uso del registro
  equivocado. Sugerir unificar productos duplicados SOY/AVEGUAY o revisar
  qué registro se usa al cobrar.

## Fix 14/11 — venta combinada con plan de cuotas no se registraba (Pablo, DJP)

Síntoma: POS avisaba "se aplicó el recargo" pero la venta no aparecía y
no mostraba error. Causa (uwsgi.log): `UnboundLocalError` —
`CardInstallmentPlan` se importaba solo dentro del bloque
`payment_method=='card'`; con `combined` + `card_plan_id` en
`combined_payments` el nombre quedaba sin ligar → `{'error'}` con
status 200 → el `.done` de jQuery lo tragaba en silencio y limpiaba el
carrito.

Commit `93401607`:
- views/sale: imports locales redundantes eliminados; action `invoice`
  ahora también persiste `combined_payments` (antes perdía el detalle).
- pos.js (`?v=20261114`): `.done` de `create_sale`/`invoice` (flujo
  normal y combinado) muestran `resp.error` y NO limpian el carrito si
  el server devolvió error JSON — patrón de fallo silencioso corregido.

## Venta manual registrada #6766 (DJP, 14/11)

La venta combinada que Pablo no pudo cargar por el bug se registró a
mano vía shell en producción (mismo flujo que `create_sale`):

- Items: #912 guitarra Stagg (467702,51), #5002 ampli NUX con lista 6%
  (649309,81), #827 funda con lista 10% (44116,48), #783 correa (6026,90),
  #1605 cable (24576,31), #1509 limpiador (42358,47) — cantidad 1 c/u.
- Neto 1.019.909,49 + IVA 21% 214.180,99 = 1.234.090,48 + redondeo
  +10.909,52 → **total $1.245.000**.
- `payment_method='combined'`, `payment_details`: transferencia $750.000
  + tarjeta $495.000 (Naranja X 6 cuotas, plan 56, `card_plan`/`card_installments` seteados).
- Stock descontado en los 6 productos vía `adjust_stock` (auditado,
  user=djp), `SaleVatBreakdown` 21% y `LibroIvaRegistro` creados (1 reg).
- Cliente CF anónimo, ticket (no factura AFIP).

## Informes generados

- `videos_tutoriales/informe_desfasaje_stock_2_acroactivo.pdf` (informe Nro 5,
  diagnóstico + guía del ranking). Script: `scripts/generar_informe_desfasaje_v2.py`.

## Carga de factura/remito con IA (commit 999172d4, deployado 17/11)

Portado del repo de referencia ERPOutlet + adaptado a nuestro flujo:

- `core/erp/services/factura_vision.py`: PDF→PNG (pymupdf) → OpenRouter
  (modelo `nvidia/nemotron-3.5-super-vl:free`, gratis; configurable con
  `FACTURA_VISION_MODELO`) → JSON con proveedor/CUIT/fecha/nro/tipo/IVA
  y por ítem: codigo, cod_barras, descripcion, cantidad, **precio_neto**
  y **precio_lista** por separado, bonif_pct por renglón.
  - OJO: el prompt original pedía "precio de lista SIN IVA" (ambiguo) y
    devolvía los precios CON IVA. Se corrigió para pedir ambas columnas
    por separado — verificado con la factura real A00114-00004081:
    netos exactos (milanesa 35567.60, no 44830).
- `escanear_remito` (`/erp/remito/escanear/`): POST con el archivo →
  matchea proveedor por CUIT→nombre, ítems por codigo_proveedor/barras/
  SKU, y por similitud de nombre devuelve hasta 5 `candidatos` por ítem
  sin match. Devuelve `prod_data` (toJSON completo) para que funcionen
  el lápiz de edición y la tabla "Qué pasará al procesar".
- Template: botón "Escanear factura/remito" + alerta "ítems sin match"
  con select de candidatos. Las líneas entran DIRECTO a la tabla (no
  abre el modal por línea — el operador revisa con el lápiz). Ítems con
  solo precio de lista: el JS calcula el neto con el IVA del producto o
  del comprobante y lo avisa en el estado.
- **API key en `/etc/uwsgi/vassals/uwsgi13.ini` como `env = OPENROUTER_API_KEY=...`
  (fuera del repo)**. Si falta, el endpoint devuelve 422 con mensaje claro.
- Verificado en producción con la factura real: 9/9 ítems con el
  producto correcto como primer candidato (esta factura no trae códigos,
  todo fue por similitud de nombre — muy buena precisión).
- Pendiente: nada se guarda solo — es un borrador; el operador confirma.

## Conteo físico 18/11 — AVEGUAY 90328 (6→4)

Yasmin reportó 2 cajas de menos vs sistema. Auditoría completa del libro de
movimientos: TODO cuadra — conteo nocturno 12/11=20, −11 ventas 13-16/11,
hoy +2 restauradas (cta.cte. #334 eliminada y venta #6883 anulada, ambas
re-registradas enseguida) y −5 entregadas → 6. Las 2 cajas faltantes no
tienen movimiento: salida física no registrada o cobrada como SOY ALAS
(90351). Normalizado 6→4 vía adjust_stock (ref conteo-fisico).

**Sospecha nueva descubierta:** al eliminar cta.cte. #334 se restauró +1 a
pata muslo SOY 90348 (0→1) pero el re-registro #350 descontó SSEBA 90370 —
Yasmin cambió el SKU al re-cargar. 90348 quedó con +1 fantasma y 90370 con
−1 de más. Verificar con ella en el próximo conteo.

## SSL renovado 18/11

`erp.multiliderestech.online` vencía hoy → renovado hasta 16/02/2027 con
`/home/ubuntu/DJENV/bin/certbot renew` (authenticator standalone: parar
lighttpd → renew → start). El deploy-hook rebuilda combined.pem solo.
Fallaron 9 certs por NXDOMAIN en `*.multilideres.com` (DNS caído) y
shoppingformosa.online apunta a otra IP — revisar DNS o limpiar esos certs.

## Fix 19/11 — pvp_final corrupto en productos con iva_rate=0 (DJP, emp 7)

Reporte de Pablo: el POS le mostraba el precio "con el IVA sumando" en
productos que siempre vendió planos. Caso disparador: BATERIA 9V DURACELL
(cod. interno 672, prod 89143) saltó de ~$9.494 a $11.488,95 tras procesar
el remito R-008914 (12/11) — Pablo la vendió 2 veces anuladas y terminó
vendiendo a $9.000 manual (ventas 6900/6902/6911).

- **Bug:** `prod.iva_rate or Decimal('0.21')` en 7 puntos — trataba IVA 0
  como "sin dato" y recalculaba `pvp_final = pvp × 1.21`. El POS muestra
  `pvp_final` → cobraba 21% de más. Corregido a
  `iva_rate if iva_rate is not None else 0.21` en: `procesar_remito`,
  proyección de impacto, datos del modal de margen,
  `actualizar_margen_remito` (remito/views.py), `adjust_margin`,
  `increase_cost` (product/views.py) y apply de costo (models.py).
  OJO: `_line_iva_rate` se dejó igual a propósito — para EXTRAER el neto
  de un precio con IVA sí corresponde caer al % del remito.
- **Dato:** 50 productos emp7 con `iva_rate=0` quedaron con
  `pvp_final = pvp × 1.21` (corruptos por ajustes de margen del 3/11 y
  17/11 y remitos R-000010/R-000015/R-008913/A0004-88675/R-088676).
  Snapshots de MarginAdjustmentHistory prueban que antes tenían
  `pvp_final == pvp`. Corregidos en producción: `pvp_final = pvp`,
  `synced_to_server=False`. Incluye las guitarras del remito R-088676
  (90374/90375): ahora $120.000 plano, no $145.200.
- Empresas 4 y 10 verificadas: 0 productos afectados.
- Regla de lectura: en DJP conviven productos `iva_rate=0.21` (neto+IVA,
  pvp_final=pvp×1.21) y `iva_rate=0` (precio plano, pvp_final=pvp).
  Cualquier cálculo de pvp_final debe respetar el 0.
- Commit `f8777061` pusheado y deployado (GET / → 200).

## 21/11 — Stock fantasma por carga rápida del POS (DJP)

Pablo reportó guitarra 90197 (7 cuerdas Solar) con stock 1 debiendo ser 0.
Auditoría: venta 6714 (13/11 21:22) la dejó en 0; 3 min después un
`quick_add` +1 ("Carga rápida desde la venta", user djp) la volvió a 1 —
clic accidental en el botón "+1" de las sugerencias del buscador del POS,
que sumaba stock SIN confirmación (el Enter por código sí preguntaba).
- Stock corregido a 0 vía adjust_stock (manual, auditado).
- Commit `4c72692f`: el botón "+1" ahora pide `confirm()` igual que el
  camino por Enter. Bump `?v=20261121`. Deployado (GET / → 200).
