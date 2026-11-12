#!/usr/bin/env python
"""Genera informe_normalizacion_stock_acroactivo.pdf (informe Nro 6)."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'videos_tutoriales', 'informe_normalizacion_stock_acroactivo.pdf')

ACCENT = colors.HexColor('#1a5276')
GREEN = colors.HexColor('#1e8449')
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
    Paragraph('INFORME Nro 6: CONTEO FISICO Y NORMALIZACION DE STOCK', title_st),
    Paragraph('Distribuidora Acro Activo - conteo fisico completo del frio vs sistema - 12/11/2026', sub_st),

    Paragraph('1. Que se hizo', h_st),
    Paragraph(
        'Se tomo el conteo fisico completo de la mercaderia de frio (15 productos, '
        'valorizado en <b>$6.132.500</b>) y se comparo item por item contra el stock '
        'del sistema en el servidor. Las diferencias reales se corrigieron dejando '
        'registro auditable de cada ajuste.', body),

    Paragraph('2. Resultado: el sistema esta mas sano de lo que parecia', h_st),
    Paragraph(
        '<b>10 de los 15 items cuadraban exacto</b>, incluida la SUPREMA que motivo '
        'todo el reclamo: el sistema decia 15 cajas y en la heladera hay 15 cajas. '
        'Las "4 cajas faltantes" del informe anterior eran historia vieja (ventas '
        'borradas/anuladas de antes del arreglo), no un error actual del sistema.', body),
    T([
        ['Conteo fisico', 'Fisico', 'Sistema decia', 'Resultado'],
        ['Higado (caja Aveguay x15kg)', '4', '4', 'EXACTO'],
        ['Carcasa', '1', '1', 'EXACTO'],
        ['Alas (caja Aveguay A x15kg)', '22', '21', '+1 ajustado'],
        ['Pollo N8 (Enercop)', '11', '11', 'EXACTO'],
        ['Suprema (Aveguay x15kg IQF)', '15', '15', 'EXACTO'],
        ['Milanesa x15 6kg (Noelma)', '4', '1', '+3 ajustado'],
        ['Cogote x15', '6', '5', '+1 ajustado'],
        ['Pata Muslo x15 (Soy)', '41', '36', '+5 ajustado'],
        ['Milanesa x 1kg (clasica)', '8', '7', '+1 ajustado'],
        ['Patitas (crunch rebozadas)', '1', '1', 'EXACTO'],
        ['Finger (chichen finger)', '2', '2', 'EXACTO'],
        ['Pollo suelto', '4', '4', 'EXACTO'],
        ['Medallones IQF', '6', '6', 'EXACTO'],
        ['Alas oregano y pimenton', '1', '1', 'EXACTO'],
        ['Tulipas (Noelma x1kg)', '5', '5', 'EXACTO'],
    ], [6.4 * cm, 2.2 * cm, 3.2 * cm, 4.2 * cm]),
    Spacer(1, 6),
    Paragraph(
        'Total corregido: <b>+11 cajas</b> repartidas en 5 productos. El desfasaje '
        'grande fue pata muslo (+5, la misma diferencia de 5 del conteo anterior: '
        'un faltante que se repite y habria que vigilar: mermas sin anotar o '
        'anulaciones respondidas al reves).', body),

    Paragraph('3. Que quedo implementado para que no vuelva a pasar', h_st),
    T([
        ['Cambio', 'Que hace'],
        ['Registro de movimientos de stock',
         'Toda vez que cambia el stock de un producto queda asentado: tipo '
         '(venta, fiado, anulacion, remito, transferencia, ajuste manual, '
         'importacion, sync), cantidad, stock antes/despues, usuario, motivo '
         'y fecha. Terminaron las investigaciones a ciegas.'],
        ['Boton "Ajustar stock" (icono de cajas) en el listado de productos',
         'Corrige el stock con motivo obligatorio (conteo fisico, merma, carga '
         'sin remito, correccion). El campo stock ya NO se puede editar a mano '
         'en el producto: era la via de las cargas invisibles.'],
        ['Boton "Historial" (icono de reloj) en cada producto',
         'Muestra todos los movimientos del producto: quien, cuando, cuanto '
         'y por que. Cualquiera puede auditar un producto en un minuto.'],
        ['Stock negativo permitido',
         'Antes el sistema no dejaba bajar de 0 y las ventas "contra piso" se '
         'evaporaban (ej: las alas Soy vendieron 114 cajas con stock 0 sin que '
         'baje nada). Ahora el faltante queda visible en vez de esconderse.'],
    ], [5.4 * cm, 10.6 * cm]),

    Paragraph('4. Advertencia: vender por un registro y despachar otro', h_st),
    Paragraph(
        '<b>CAJA SOY ALAS X15KG vendio 114 cajas en 35 dias con stock 0</b>. Como el '
        'conteo fisico confirmo que las alas reales son AVEGUAY, significa que al '
        'cobrar alas a veces usan el registro "SOY ALAS" y despachan cajas de la '
        'otra marca. Si eso sigue, el stock de alas se vuelve a desfasar solo, sin '
        'ningun error del sistema.', body),
    Paragraph(
        'Recomendacion: revisar que producto se selecciona al vender alas (son casi '
        'identicos en la lista). A mediano plazo conviene unificar o renombrar los '
        'productos duplicados SOY/AVEGUAY para que no haya dos registros para la '
        'misma caja fisica.', body),

    Paragraph('5. Reglas de oro (las mismas, ahora con dientes)', h_st),
    T([
        ['Regla', 'Por que'],
        ['Mercaderia que entra de proveedor = remito de entrada',
         'Actualiza stock Y costo. Nunca editar el numero del producto.'],
        ['Correcciones = boton Ajustar stock con motivo',
         'Queda firmada con usuario y motivo, auditable.'],
        ['No borrar ventas: anularlas y responder bien la pregunta',
         '"La mercaderia volvio?" decide si el stock se devuelve.'],
        ['Mermas y roturas = remito de salida (o ajuste con motivo)',
         'La heladera pierde cajas que el sistema no sabe si no se anotan.'],
        ['Conteo fisico semanal de los 10 productos que mas rotan',
         'Este conteo demostro que funciona: agarro 5 diferencias chicas '
         'antes de que sean grandes. Repetirlo es la garantia.'],
    ], [7.2 * cm, 8.8 * cm]),

    Paragraph('6. Pendiente tecnico', h_st),
    Paragraph(
        'El registro de movimientos ya esta operativo en la base del servidor y los '
        'ajustes de este informe ya quedaron asentados. Falta publicar el codigo '
        'nuevo en el servidor al cierre del local para que los botones de '
        'ajuste/historial aparezcan en el listado y cada venta se registre sola '
        'de ahora en adelante.', body),
    Spacer(1, 10),
    HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#b0b0b0')),
    Spacer(1, 4),
    Paragraph(
        'Anexo - trazabilidad: los 5 ajustes se aplicaron directo en el servidor '
        '(base gayozolibreria, empresa 10) el 12/11 ~14:34-14:41hs como movimientos '
        'tipo "manual" con motivo "Conteo fisico 12/11 (stock valorizado)", visibles '
        'en erp_stockmovement y en el boton Historial de cada producto una vez '
        'publicado el codigo.', small),
]

doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=1.7 * cm, rightMargin=1.7 * cm,
                        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                        title='Informe Nro 6 - Conteo Fisico y Normalizacion - Acro Activo')
doc.build(E)
print(OUT)
