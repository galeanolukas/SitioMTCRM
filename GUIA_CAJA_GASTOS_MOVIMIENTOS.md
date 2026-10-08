# Guía de funcionamiento: Gastos, Movimientos y Cierres de Caja

## 1. Los tres conceptos (y cuándo usar cada uno)

| Concepto | Qué es | Cuándo usarlo |
|---|---|---|
| **Gasto** (`/erp/expense/add/`) | Plata que sale del negocio para siempre: proveedores, servicios, alquiler, transporte | Cuando pagás algo real — queda en reportes de gastos, dashboard y libro |
| **Movimiento de caja** (botón "Agregar Movimiento" en el detalle de la caja) | Entrada/salida física del cajón que **no es venta ni gasto**: retiro a caja de ahorro, ingreso de clases, vuelto de caja chica | Cuando la plata se mueve entre cajas/cuentas o entra sin ser una venta |
| **Cierre de caja** (`/erp/cash-register/`) | La foto del día: saldo inicial + ventas − gastos ± movimientos = saldo esperado vs lo que contaste | Al final del día (o período) para controlar el efectivo |

**Regla de oro**: una misma plata va en **un solo lugar**. Un retiro a caja chica es *movimiento* (sale del cajón pero no es gasto); el pago del alquiler es *gasto* (sale del negocio). Si cargás el retiro como movimiento Y como gasto, el sistema lo descuenta dos veces.

## 2. La caja abierta: cómo acumula en tiempo real

- Al **abrir** una caja se guarda `fecha = hoy` (la fecha del POS en ese momento) + saldo inicial.
- Mientras esté **abierta**, cada consulta calcula **en vivo** (no queda guardado):

```
Saldo esperado = Saldo inicial
               + Ventas en efectivo (desde la fecha de la caja hasta HOY)
               − Gastos en efectivo (mismo rango)
               + Movimientos de ingreso en efectivo
               − Movimientos de egreso en efectivo
```

- Los resúmenes por medio de pago (tarjeta, Mercado Pago, transferencia, cheque) también se calculan en vivo, pero **solo el efectivo** entra en el saldo esperado — el resto es informativo.
- ⚠️ **Importante**: la caja arrastra desde su fecha hasta el día de cierre. Si se abre un lunes a la noche y se cierra el miércoles, suma 3 días. Y si se abre una segunda caja con una fecha ya usada, **las dos suman las mismas ventas**.

## 3. El cierre

Al cerrar (botón "Cerrar Caja"), el sistema **congela** los totales: ventas por medio de pago, gastos por medio de pago, saldo esperado y el conteo real (`Saldo final`). Después muestra:

- **Diferencia** = lo que contaste − lo esperado. `+$X` = sobra plata; `−$X` = falta.
- Una vez cerrada ya no se pueden agregar ni borrar movimientos, y los números quedan fijos.

## 4. Flujo recomendado diario

1. **Mañana**: Abrir caja con el saldo real del cajón (lo que quedó del cierre anterior, si no se retiró nada).
2. **Durante el día**:
   - Ventas → POS (se suman solas).
   - Pagos reales → **Gastos**, con su método de pago.
   - Retiros/devoluciones del cajón → **Movimiento** (egreso/ingreso).
   - Si sale plata para caja chica/ahorro → egreso. Si vuelve → ingreso al día siguiente. El sistema lo entiende.
3. **Noche**: Cerrar caja → el "Saldo Esperado" debería coincidir con el efectivo físico. La diferencia indica si falta o sobra.

## 5. Cuidados y casos conocidos

- **No enviar el formulario de movimiento dos veces**: el bug del "error al guardar" (corregido en v2.2.02) podía grabar duplicados. Conviene verificar en el detalle de la caja que no haya movimientos repetidos.
- **Abrir la caja el mismo día que corresponde**: si se abre a la noche "para mañana", queda con la fecha de hoy y arrastra ventas del día anterior.
- **Una plata, un registro**: si un retiro va a volver (caja chica), registrar egreso al salir e ingreso al volver — así el saldo esperado siempre refleja el cajón real. No registrarlo también como gasto.
- **El estado "Abierto" acumula todo el rango**: gastos y ventas de días posteriores a la fecha de la caja se siguen sumando hasta que se cierra. Si una caja queda abierta varios días, revisar qué rango está sumando antes de cerrar.

## 6. Detalle técnico (para referencia)

- `CashRegister.date` se asigna con `date.today()` del sistema al crear la apertura.
- Las consultas de ventas/gastos para una caja abierta usan `date__range=(fecha_caja, hoy)`; para una cerrada solo su fecha.
- El saldo esperado solo considera movimientos y gastos con método **efectivo**; los demás medios de pago no afectan el efectivo del cajón.
- Una empresa puede tener una sola caja abierta por usuario a la vez (bloqueado al crear).
- Al cerrar se guardan los totales en la caja (`cash_sales`, `expenses`, `cash_expenses`, etc.) — la vista de detalle de una caja cerrada muestra esos valores fijos.
