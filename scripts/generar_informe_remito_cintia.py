#!/usr/bin/env python
"""Genera informe_carga_remito_cintia.pdf (informe Nro 6).

Explica en criollo el error al cargar el remito de la factura
A00114-00004081 (Avicola Santa Ana -> Acro Activo, 12/11/2026): se uso
la columna $P.U.Lista (con IVA, sin bonif.) en vez de $P.U.Neto
(costo real sin IVA, con bonif. aplicada).
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'videos_tutoriales', 'informe_carga_remito_cintia.pdf')

ACCENT = colors.HexColor('#1a5276')
LIGHT = colors.HexColor('#eaf2f8')
WARN = colors.HexColor('#fdf2e9')
OK = colors.HexColor('#e8f6ef')

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
    Paragraph('INFORME Nro 6: COMO CARGAR UN REMITO DESDE LA FACTURA DEL PROVEEDOR', title_st),
    Paragraph('Para Cintia - Distribuidora Acro Activo - caso remito A00114-00004081 (Avicola Santa Ana, 12/11/2026) - 13/11/2026', sub_st),

    Paragraph('1. Que paso, en criollo', h_st),
    Paragraph(
        'Cargaste el remito con la columna <b>$P.U.Lista</b> de la factura. Esa columna es el '
        '"precio de vidriera" del proveedor: <b>trae el IVA adentro y no le descontaron las '
        'bonificaciones</b>. Como el remito quedo en modo "IVA agregado", el sistema tomo ese '
        'numero tal cual como costo de compra.', body),
    Paragraph(
        'Resultado: el costo quedaba cargado entre un <b>15% y un 26% mas caro</b> de lo que '
        'realmente se pago. Si se procesaba asi, el sistema recalculaba los precios de venta '
        'con ese costo inflado y los PVP quedaban altos.', body),

    Paragraph('2. Como se lee la factura del proveedor', h_st),
    T([
        ['Columna de la factura', 'Que es', 'Va al remito?'],
        ['<b>$P.U.Lista</b>', 'Precio de lista del proveedor: CON IVA y SIN descuentos.', '<b>NO</b>'],
        ['<b>%Bonif.</b>', 'Descuento que te hacen por ese renglon (4%, 1,5%, 5%...).', 'Ya esta adentro del neto'],
        ['<b>$P.U.Neto</b>', '<b>Lo que te cobran de verdad por unidad</b>: sin IVA y con el descuento ya restado.', '<b>SI - esta es la que va</b>'],
        ['Subtotal / Subt c/IMP', 'Totales por renglon (el c/IMP vuelve a sumar el IVA).', 'NO'],
    ], [3.2 * cm, 9.3 * cm, 3.5 * cm]),

    Paragraph('3. Item por item: lo cargado vs lo que iba', h_st),
    T([
        ['Item (cant.)', 'Cargaste (lista c/IVA)', 'Correcto (neto)', 'Diferencia'],
        ['Milanesa pollo 6kg x20', '44.830,00', '<b>35.567,60</b>', '+26%'],
        ['Patitas crunch 6kg x5', '47.370,00', '<b>38.561,53</b>', '+23%'],
        ['Medallon JyQ 5kg x5', '47.880,00', '<b>38.976,69</b>', '+23%'],
        ['Soy alas 15kg x35', '37.500,00', '<b>32.579,19</b>', '+15%'],
        ['Carne mecanica 20kg x12', '27.500,00', '<b>23.891,40</b>', '+15%'],
        ['Carcasa Opt 15kg x12', '17.550,00', '<b>15.247,06</b>', '+15%'],
        ['Pata muslo 15kg x80', '38.640,00', '<b>33.219,91</b>', '+16%'],
        ['Suprema bloque x30', '115.000,00', '<b>99.909,50</b>', '+15%'],
        ['Bifecito 12kg x3', '119.830,00', '<b>104.105,70</b>', '+15%'],
        ['<b>Neto total</b>', '<b>10.126.640 (con tu carga)</b>', '<b>8.676.171,15 (factura)</b>', ''],
    ], [5.6 * cm, 4.2 * cm, 4.0 * cm, 2.2 * cm]),
    Paragraph(
        'La prueba facil: el neto del remito tiene que dar <b>igual al "Subtotal $" de la '
        'factura</b> (8.676.171,15). Si da mas, es porque se cargaron precios con IVA o sin '
        'bonificacion.', body),

    Paragraph('4. Regla para la proxima (una sola frase)', h_st),
    Paragraph(
        '<b>En el remito va siempre la columna "$P.U.Neto" de la factura</b> - esa ya trae el '
        'descuento restado y el IVA afuera. No hay que calcular nada: se copia el numero '
        'tal cual, con dos decimales.', body),
    Paragraph(
        'Si la factura NO trae columna neto (algunas solo muestran lista + %bonif), el neto '
        'se saca asi: <b>lista x (1 - %bonif) / (1 + IVA)</b>. Ejemplo: 44.830 x 0,96 / 1,21 '
        '= 35.567,60. Ante la duda, avisanos y lo verificamos.', body),

    Paragraph('5. Como quedo este remito', h_st),
    Paragraph(
        'Ya corregimos los 9 precios con los netos de la factura. El remito quedo '
        '<b>PENDIENTE a proposito</b>: no movio stock ni costos. Entra a Remitos, abrilo, '
        'revisa los precios contra la factura y, si cierra, procesalo.', body),

    Paragraph('6. Dos cosas para revisar antes de procesar', h_st),
    T([
        ['Item', 'Aviso'],
        ['SSEBA Pata muslo x80',
         'La factura dice SSEBA pero se cargo en el registro "CAJA SOY DE PATA MUSLO". '
         'Si todo el pata muslo se junta ahi a proposito, ok. Si no, falta crear el producto SSEBA.'],
        ['Soy Alas x35',
         'Se cargo en "CAJA SOY ALAS". Si fisicamente entraron cajas AVEGUAY, el stock va a '
         'quedar en el registro equivocado otra vez (es el problema de siempre). Verificar '
         'que hay en la heladera.'],
    ], [3.6 * cm, 12.4 * cm]),

    Paragraph('7. Lo que la factura tiene y el remito hoy no muestra', h_st),
    Paragraph(
        'No es error tuyo: el remito <b>no tiene campo</b> para bonificacion por renglon ni '
        'para la percepcion de IIBB ($173.523,42 en esta factura). Por eso la unica forma '
        'correcta de cargar es con el $P.U.Neto. Estamos evaluando mejorar la pantalla para '
        'que esto no pueda pasar de nuevo.', small),
    Paragraph(
        'El IVA de esta factura es mixto (21% en milanesa/patitas/medallon, 10,5% en el '
        'resto). El remito maneja un % global; si hace falta el detalle impositivo lo '
        'registra contaduria, no el remito.', small),

    HRFlowable(width='100%', color=ACCENT, thickness=1, spaceBefore=10, spaceAfter=6),
    Paragraph(
        'Resumen: columna "$P.U.Neto" = la que va. Las cantidades y los productos estaban '
        'bien. El remito quedo corregido y pendiente para que lo revises y proceses.',
        body),
]

doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=2 * cm, rightMargin=2 * cm,
                        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                        title='Informe carga de remito - Acro Activo')
doc.build(E)
print('Generado:', OUT)
