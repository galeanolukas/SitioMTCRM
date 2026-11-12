#!/usr/bin/env python
"""Genera informe_pata_muslo_12_11_acroactivo.pdf (informe Nro 7, en criollo)."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'videos_tutoriales', 'informe_pata_muslo_12_11_acroactivo.pdf')

ACCENT = colors.HexColor('#1a5276')
RED = colors.HexColor('#a93226')
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
    Paragraph('INFORME Nro 7: FALTANTE DE PATA MUSLO (38 vs 41)', title_st),
    Paragraph('Distribuidora Acro Activo - reclamo del 12/11/2026 - verificado directo en el servidor', sub_st),

    Paragraph('1. El reclamo, en criollo', h_st),
    Paragraph(
        'Yasmin conto la pata muslo en la heladera y tiene <b>38 cajas</b>, '
        'pero el sistema dice <b>41</b>. Faltan 3 cajas. La pregunta es: '
        'se las llevo el sistema o se fueron por otro lado?', body),

    Paragraph('2. Las pruebas: que paso hoy, hora por hora', h_st),
    Paragraph(
        'Esto esta sacado directo de la base de datos del servidor, no es una '
        'suposicion. Todas las horas son de Argentina:', body),
    T([
        ['Hora', 'Que paso', 'Stock en sistema'],
        ['09:34 a 11:11', 'Se vendieron <b>8 cajas</b> y se cargaron bien: 6 ventas confirmadas '
         '(6659, 6660, 6661, 6663, 6665 x3 y 6667), todas cobradas a $43.000', '44 → 36'],
        ['~11:30', 'Yasmin hizo el conteo fisico de la mañana: <b>41 cajas</b>. Como el sistema '
         'decia 36, se aplico la correccion +5 (quedo guardada con fecha y motivo '
         '"Conteo fisico 12/11")', '36 → 41'],
        ['11:30 → ahora', '<b>NADA. CERO movimientos.</b> No hubo ni una venta, ni un fiado, '
         'ni un remito, ni una anulacion, ni una edicion del producto. El sistema '
         'sigue marcando 41 porque nadie le aviso que salio mercaderia.', '41 (sin tocar)'],
        ['ahora', 'Conteo fisico nuevo: <b>38 cajas</b> en la heladera', '41 ≠ 38'],
    ], [2.0*cm, 11.2*cm, 3.2*cm]),

    Paragraph('3. Lo que dice el servidor, sin vueltas', h_st),
    Paragraph(
        'El sistema <b>no se comio nada</b>. Desde que quedo en 41 al mediodia, no registro '
        'NI UNA salida de pata muslo. Si el sistema hubiera vendido o descontado cajas, '
        'quedaria el registro — y no hay nada.', body),
    Paragraph(
        'Ademas se revisaron <b>las 19 variantes de "pata muslo"</b> que hay en el catalogo '
        '(SOY, AVEGUAY, Tres Arroyos, x3kg, x4kg, x12kg, etc): hoy solo se vendio por '
        'la ficha correcta (CAJA SOY DE PATA MUSLO). Nadie vendio por la ficha '
        'equivocada ni por otro producto parecido.', body),
    Paragraph(
        '<b>Conclusion: las 3 cajas salieron de la heladera sin pasar por la caja.</b> '
        'No es un error del sistema — es mercaderia que se fue sin registrarse.', body),

    Paragraph('4. Donde pueden haberse ido las 3 cajas', h_st),
    Paragraph(
        'Hay 4 caminos posibles para que salga mercaderia. Hay que preguntarle a '
        'Yasmin cual paso, porque la correccion correcta es distinta en cada caso:', body),
    T([
        ['Que paso con las 3 cajas', 'Como se arregla'],
        ['<b>Se vendieron y no se cargaron</b> (se cobro plata pero no se registro)',
         'Cargar las ventas en el POS AHORA → el stock baja solo y queda registrada la plata'],
        ['<b>Fue un fiado</b> (anotado en cuaderno o de palabra)',
         'Cargarla como Cuenta Corriente en el POS → queda el cliente debiendo y el stock baja'],
        ['<b>Se mando a otro local o a un repartidor</b> sin hacer remito',
         'Cargar el remito de salida → queda trazado a donde fue'],
        ['<b>Merma o caja rota</b> (rota, descongelada, caida)',
         'Ajuste de stock con motivo "merma" → queda firmado quien y por que'],
    ], [8.0*cm, 8.4*cm]),

    Paragraph('5. La regla de oro para que esto no se repita', h_st),
    Paragraph(
        '<b>Toda caja que sale de la heladera tiene que pasar por el sistema</b> — como '
        'venta, como fiado, como remito o como merma. Si alguien saca una caja "despues '
        'la cargo" o "ya la anoto en la libreta", el stock no cierra nunca mas. Es la '
        'misma causa que el desfasaje original de las supremas: no es el sistema, es '
        'mercaderia que sale sin registrarse.', body),
    Paragraph(
        'Despues del cierre se instala la version nueva que obliga a que TODO movimiento '
        'de stock quede firmado con usuario, hora y motivo — ahi va a ser todavia mas '
        'facil ver quien saco que y cuando.', small),

    Paragraph('6. Recomendacion inmediata', h_st),
    Paragraph(
        '1. Preguntar en el local si alguien vendio, fio o mando 3 cajas de pata muslo '
        'esta tarde (despues de las 11:30).<br/>'
        '2. Si aparece la venta: cargarla y listo — el sistema queda en 38 solo.<br/>'
        '3. Si nadie sabe donde fueron: se ajusta 41 → 38 con motivo "faltante en '
        'conteo 12/11" y queda anotado. Pero ojo: si se repite, hay que revisar el '
        'procedimiento del local, porque las cajas no se evaporan.', body),

    Spacer(1, 8),
    HRFlowable(width='100%', thickness=0.6, color=ACCENT),
    Paragraph('Verificado en base de datos de produccion el 12/11/2026. '
              'Ventas revisadas: erp_detsale/erp_sale. Fiados: erp_employeeaccountsale. '
              'Sin remitos ni ediciones del producto en el dia. '
              'Ajuste de las 11:30 registrado en erp_stockmovement (movimiento Nro 1).', small),
]

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=1.6*cm, rightMargin=1.6*cm,
                        topMargin=1.4*cm, bottomMargin=1.4*cm,
                        title='Informe 7 - Faltante pata muslo Acro Activo')
doc.build(E)
print('OK ->', OUT)
