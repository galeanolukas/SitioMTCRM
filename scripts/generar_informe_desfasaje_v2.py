#!/usr/bin/env python
"""Genera informe_desfasaje_stock_2_acroactivo.pdf (informe Nro 5)."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'videos_tutoriales', 'informe_desfasaje_stock_2_acroactivo.pdf')

ACCENT = colors.HexColor('#1a5276')
LIGHT = colors.HexColor('#eaf2f8')

title_st = ParagraphStyle('t', fontName='Helvetica-Bold', fontSize=16,
                          textColor=ACCENT, spaceAfter=2)
sub_st = ParagraphStyle('s', fontName='Helvetica', fontSize=9.5,
                        textColor=colors.HexColor('#555555'), spaceAfter=10)
h_st = ParagraphStyle('h', fontName='Helvetica-Bold', fontSize=11.5,
                      textColor=ACCENT, spaceBefore=12, spaceAfter=4)
body = ParagraphStyle('b', fontName='Helvetica', fontSize=9.5, leading=13,
                      spaceAfter=5)
small = ParagraphStyle('sm', parent=body, fontSize=8.5, leading=11,
                       textColor=colors.HexColor('#444444'))
cell = ParagraphStyle('c', fontName='Helvetica', fontSize=8.5, leading=10.5)
cellb = ParagraphStyle('cb', parent=cell, fontName='Helvetica-Bold')
cellw = ParagraphStyle('cw', parent=cell, fontName='Helvetica-Bold',
                       textColor=colors.white)


def T(rows, widths, header=True):
    data = []
    for i, r in enumerate(rows):
        style = cellw if (header and i == 0) else cell
        data.append([Paragraph(str(x), style) for x in r])
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#b0b0b0')),
          ('VALIGN', (0, 0), (-1, -1), 'TOP'),
          ('TOPPADDING', (0, 0), (-1, -1), 3),
          ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
          ('LEFTPADDING', (0, 0), (-1, -1), 5),
          ('RIGHTPADDING', (0, 0), (-1, -1), 5)]
    if header:
        st += [('BACKGROUND', (0, 0), (-1, 0), ACCENT)]
        for i in range(1, len(rows)):
            if i % 2 == 0:
                st.append(('BACKGROUND', (0, i), (-1, i), LIGHT))
    t.setStyle(TableStyle(st))
    return t


E = [
    Paragraph('INFORME Nro 5: DESFASAJE DE STOCK (segunda vuelta)', title_st),
    Paragraph('Distribuidora Acro Activo - verificado en el servidor y en el codigo - 12/11/2026', sub_st),

    Paragraph('1. El reclamo, en criollo', h_st),
    Paragraph(
        'Yasmin cuenta mercaderia de verdad en la heladera y no le cierra con el sistema. '
        'El viernes 6/11 a la noche (~20:11) cargo stock directo por producto: <b>60 cajas de '
        'SUPREMA AVEGUAY X15KG IQF</b> y un monto de <b>PATA MUSLO</b>. Dice que cuando las '
        'cargo el stock figuraba en 0. Hoy el "stock actual" que muestra el ranking de '
        'productos no coincide ni con lo vendido ni con lo que hay en la heladera.', body),
    Paragraph(
        'Importante: esta vez <b>no fue el mismo error de antes</b>. El fix de las '
        'anulaciones esta deployado y anda (la venta 6634 quedo anulada con traza, no '
        'borrada). Lo que encontramos es que hay varios agujeros mas, chicos pero '
        'acumulativos, y uno de concepto: el "stock actual" del reporte no es '
        '"carga menos vendidas".', body),

    Paragraph('2. Primero lo primero: el "local_pos" es un espejismo', h_st),
    Paragraph(
        'Pregunta que surgio: ¿hay un POS local sincronizando con el servidor? '
        'Respuesta: <b>no</b>. Todo el trabajo de Acro Activo pasa en el servidor. '
        'Dos cosas confunden:', body),
    T([
        ['Lo que se ve', 'Que es en realidad'],
        ["Ventas con origen 'local_pos' (~5.500)",
         'Es el default del sistema: toda venta nueva se etiqueta "local_pos" aunque se haya '
         'cargado en la web del servidor. No viene de ningun POS.'],
        ['POST /erp/sync/data/ en el registro de actividad',
         'Es el boton "Sincronizar" del menu de la web. En el servidor ese boton no hace '
         'nada (esta pensado para los POS locales). Tocarlo no rompe nada.'],
    ], [4.6 * cm, 11.4 * cm]),

    Paragraph('3. Los numeros, producto por producto (6/11 a hoy)', h_st),
    Paragraph('CAJA DE SUPREMA AVEGUAY X15KG IQF - el caso mas claro:', body),
    T([
        ['Concepto', 'Cajas'],
        ['Carga del vie 6/11 ~20:12 (edicion directa del campo stock)', '+60'],
        ['Ventas confirmadas del periodo', '-40'],
        ['Fiada sin cobrar (cuenta corriente, 10/11)', '-1'],
        ['Lo que deberia dar', '19'],
        ['Lo que muestra el sistema', '15'],
        ['Cajas que "faltan"', '4'],
    ], [11 * cm, 4 * cm]),
    Spacer(1, 6),
    Paragraph('CAJA SOY DE PATA MUSLO IQF X 15KG - aca casi cierra: del 63 que media el '
              'informe anterior (10/11) se vendieron ~17 el 10/11 y ~4 el 11 y 12/11: da '
              '~42 esperado contra 41-42 que muestra. Diferencia: ~1 caja. '
              'SOY CARNE MECANICA: era 3, se vendieron 7 y figura 0: ajustada por '
              'edicion durante el periodo.', body),

    Paragraph('4. De donde se fueron las ~4 supremas (y el resto del ruido)', h_st),
    T([
        ['Evento entre la carga y hoy', 'Efecto en el stock'],
        ['5 ventas BORRADAS (6492, 6548, 6557, 6609) antes del deploy del fix',
         'Cada borrado devolvio sus items al stock Y saco la venta del ranking: doble '
         'descuadre. Sus productos son irrecuperables, si alguna tenia supremas ahi esta '
         'parte del faltante.'],
        ['5 ventas ANULADAS sin detalles (6601, 6615, 6618, 6637, 6652)',
         'Si se anularon con "la mercaderia no volvio", sus cajas quedaron descontadas '
         'pero invisibles para el ranking.'],
        ['La carga misma es invisible',
         'Se hizo editando el campo "stock" del producto. No queda registro del numero '
         'cargado: si fue 56 en vez de 60, supremas cierra exacto (56-41=15).'],
        ['Fiados (cuentas corrientes)',
         'Descuentan stock sin ser "venta". En el ranking nuevo si entran a "vendido", '
         'pero si la cuenta se hace a mano con las ventas, descuadran '
         '(1 suprema + 3 pata en el periodo).'],
        ['Ventas con stock en 0',
         'El sistema no permite stock negativo: una venta contra stock 0 "descuenta" '
         'contra un piso y la merma queda escondida.'],
    ], [7.2 * cm, 8.8 * cm]),

    Paragraph('5. Cosas descartadas esta vuelta', h_st),
    T([
        ['Sospechoso', 'Veredicto'],
        ['Productos duplicados (otra "suprema" registrando las ventas)',
         'ABSUELTO: todas las ventas cayeron en el producto correcto. Los otros '
         'productos suprema/pata no tuvieron movimientos.'],
        ['Cobros de cuentas corrientes descontando stock dos veces',
         'ABSUELTO: el cobro crea la venta de cobro sin tocar stock (verificado en '
         'codigo y datos).'],
        ['El fix de anulacion de ventas no deployado',
         'ABSUELTO: esta deployado. Las anulaciones nuevas quedan "cancelled" con traza '
         'y preguntan si la mercaderia volvio.'],
        ['Un POS externo tocando el stock',
         'ABSUELTO: no hay ninguno activo; el stock del server solo se mueve por '
         'operaciones hechas en el server.'],
    ], [7.2 * cm, 8.8 * cm]),

    Paragraph('6. GUIA: como leer el "ranking de productos" sin volverse loco', h_st),
    Paragraph('Que significa cada columna:', body),
    T([
        ['Columna', 'Que muestra'],
        ['Cantidad vendida',
         'Unidades que SALIERON en el periodo: ventas de mostrador + fiados de cuenta '
         'corriente no anulados. No incluye: ventas anuladas/borradas.'],
        ['Total $', 'Plata facturada por ese producto en el periodo (mismo criterio).'],
        ['Stock actual',
         'El numero ABSOLUTO de hoy: arrastra toda la historia del producto, no '
         '"carga menos vendidas del periodo". Cualquier error viejo queda adentro.'],
    ], [4 * cm, 12 * cm]),
    Spacer(1, 6),
    Paragraph('La cuenta que SI tiene que cerrar (hacerla por producto):', cellb),
    T([
        ['Paso', 'Dato'],
        ['Stock esperado = carga - vendidas - fiadas - anuladas "no volvio"',
         'Carga: lo que se cargo por remito o ajuste. Vendidas: columna del ranking. '
         'Fiadas: solapa Cuenta Corriente impagas. Anuladas "no volvio": ventas '
         'canceladas donde la mercaderia ya se habia entregado.'],
        ['Si esperado != "stock actual"',
         'El faltante esta en: ventas borradas/anuladas del periodo, mermas/roturas sin '
         'anotar, o una carga con numero distinto al recordado.'],
    ], [7.2 * cm, 8.8 * cm]),
    Spacer(1, 6),
    Paragraph('Reglas de oro:', cellb),
    T([
        ['Regla', 'Por que'],
        ['NUNCA cargar stock editando el producto',
         'No deja registro: despues nadie puede reconstruir la cuenta. Usar remito de '
         'entrada (o remito de ajuste).'],
        ['No borrar ventas: anularlas y responder la pregunta',
         '"¿La mercaderia volvio a la heladera?" es lo que decide si el stock se '
         'devuelve o no.'],
        ['Mermas y roturas = remito de salida',
         'La heladera pierde cajas que el sistema no sabe si no se anotan.'],
        ['Conteo fisico semanal de los 10 productos que mas rotan',
         'Agarrar el desfasaje chico antes de que sea un numero grande.'],
    ], [7.2 * cm, 8.8 * cm]),

    Paragraph('7. SOLUCION PROPUESTA (para aprobar)', h_st),
    T([
        ['#', 'Cambio', 'Para que'],
        ['1', 'Ajuste de stock ahora por conteo fisico, con remito de ajuste (entrada/salida), no por edicion de producto',
         'Arrancar parejo Y dejar traza del ajuste.'],
        ['2', 'Tabla de movimientos de stock: toda mutacion deja registro (venta, anulacion, remito, ajuste manual, fiado) con usuario, fecha y motivo',
         'Que el proximo desfasaje se audite en 5 minutos, no en una investigacion.'],
        ['3', 'Sacar el campo "stock" del formulario de producto (o convertirlo en ajuste firmado)',
         'Cerrar la via de cargas invisibles.'],
        ['4', 'Permitir stock negativo (o al menos registrar el deficit)',
         'Un stock que no puede ser negativo es un stock que miente: las ventas contra '
         'piso 0 desaparecen.'],
        ['5', 'Las anulaciones ya preguntan si la mercaderia volvio: reforzar capacitacion',
         'Si se responde "no volvio" cuando si volvio (o al reves) el stock miente '
         'igual.'],
    ], [0.8 * cm, 8.4 * cm, 6.8 * cm]),
    Spacer(1, 10),
    HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#b0b0b0')),
    Spacer(1, 4),
    Paragraph(
        'Anexo - evidencia: base gayozolibreria en 148.230.73.167 (empresa 10), '
        'consultada el 12/11/2026. Sin remitos de empresa 10 en el servidor. '
        'ActivityLog: edicion masiva de productos el 6/11 ~20:11-20:12 (ids 90339, '
        '90348, 90297 entre otros). Ventas borradas en el periodo: 6492 (7/11), '
        '6548 y 6557 (9/11), 6609 (10/11, fisica pre-fix). Anuladas sin detalles: '
        '6601, 6615, 6618, 6637, 6652. Fiadas en el periodo: 1 suprema '
        '(cuenta 332) y 3 pata muslo. Codigo verificado en SaleDeleteView '
        '(anula con pregunta de devolucion), create_employee_account_sale '
        '(descuenta al fiar), ProductForm (campo stock editable) y '
        'get_product_ranking_data (incluye fiados, excluye cobros).', small),
]

doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=1.7 * cm, rightMargin=1.7 * cm,
                        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                        title='Informe Nro 5 - Desfasaje de Stock - Acro Activo')
doc.build(E)
print(OUT)
