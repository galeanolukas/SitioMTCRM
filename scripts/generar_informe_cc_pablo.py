#!/usr/bin/env python
"""Genera informe_cuentas_corrientes_pablo.pdf (informe Nro 8, en criollo)."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'videos_tutoriales', 'informe_cuentas_corrientes_pablo.pdf')

ACCENT = colors.HexColor('#1a5276')
LIGHT = colors.HexColor('#eaf2f8')
GREEN = colors.HexColor('#1e8449')

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
    Paragraph('INFORME Nro 8: CUENTA CORRIENTE QUE "SIGUE DEBIENDO"', title_st),
    Paragraph('Don Julio Pereiro - explicado en criollo - 12/11/2026', sub_st),

    Paragraph('1. El problema, en una frase', h_st),
    Paragraph(
        'Pablo cobro plata de clientes que debian en cuenta corriente y la cargo como '
        '"movimiento de caja" (ingreso). La plata entro bien a la caja, pero la cuenta '
        'corriente sigue marcando la deuda completa. <b>No es un error del sistema: '
        'son dos botones distintos que hacen cosas distintas.</b>', body),

    Paragraph('2. Por que pasa: hay DOS caminos y hacen cosas distintas', h_st),
    T([
        ['', 'Movimiento de caja (ingreso/egreso)', 'Boton "Registrar Pago" en la Cta. Cte.'],
        ['Que hace', 'Anota que entro o salio plata del cajon. Punto.',
         'Marca la cuenta como PAGADA y aparte crea el ingreso en caja solo.'],
        ['La deuda', 'No la toca. La cuenta sigue debiendo todo.',
         'La cancela. La cuenta queda en cero.'],
        ['Sirve para', 'Ingresos que no son ventas: aportes, prestamos, '
         'retiros, caja chica, etc.', 'Cobrar fiados/cuentas corrientes de clientes.'],
    ], [2.2*cm, 7.0*cm, 7.2*cm]),
    Paragraph(
        'O sea: el movimiento de caja es como anotar en la libreta "entro tanta plata". '
        'El boton de la cuenta corriente es el que ademas tacha la deuda del cuaderno.', body),

    Paragraph('3. Lo importante: NO hagas las dos cosas a la vez', h_st),
    Paragraph(
        '<b>Si cargas el ingreso como movimiento de caja Y despues tocas "Registrar Pago" '
        'en la cuenta, la plata se cuenta DOS VECES en el cierre de caja.</b> '
        'Es una u otra, nunca las dos.', body),

    Paragraph('4. Como hacerlo bien, segun el caso', h_st),
    T([
        ['Situacion', 'Que hacer'],
        ['<b>El cliente paga TODO lo que debe</b>',
         'Ir a Cuentas Corrientes -> buscar al cliente -> tocar el boton de cobro/pago '
         '-> elegir como pago (efectivo, MP, etc.) -> confirmar. La deuda se borra y la '
         'plata entra a caja automaticamente. NO cargar movimiento de caja aparte.'],
        ['<b>El cliente paga UNA PARTE</b> (abono/entrega)',
         'Hoy el sistema no tiene "pago parcial". Mientras tanto: cargar el ingreso como '
         'movimiento de caja con descripcion clara ("CUENTA CORRIENTE NOMBRE - abono") '
         'y anotar en las notas de la cuenta cuanto pago y cuanto queda debiendo. '
         'Cuando termine de pagar todo, ahi si se toca "Registrar Pago" — pero ojo: '
         'en ese caso NO cargar el ultimo pago como movimiento de caja, o se duplica.'],
    ], [4.6*cm, 11.8*cm]),

    Paragraph('5. El truco del ultimo pago (para no duplicar)', h_st),
    Paragraph(
        'Cuando un cliente que venia pagando de a partes hace el ULTIMO pago, lo correcto es: '
        'tocar "Registrar Pago" en la cuenta (eso ingresa el total a caja) y '
        '<b>borrar o compensar los movimientos de caja que ya habias cargado</b> por los abonos '
        'anteriores — si no, la caja cuenta los abonos dos veces. La forma simple de no '
        'enredarse: anota los abonos en la descripcion del movimiento y en las notas de la '
        'cuenta, y el dia del pago final revisa que la suma de movimientos + pago final = '
        'deuda total.', body),

    Paragraph('6. Tus cuentas hoy (para que revises)', h_st),
    T([
        ['Cliente', 'Debe en total', 'Ya pago (por mov. de caja)', 'Le queda debiendo'],
        ['EMMANUEL', '$431.779', '$200.000 (9/11)', '~$231.779'],
        ['RODRIGO VERA', '$502.858', '$120.000 (hoy)', '~$382.858'],
        ['GUSTAVO GALEANO', '$104.630', '$104.000 + $4.000', '~$0* (revisar, casi cancelada)'],
        ['MARTIN ORTIZ', '$9.079', 'nota "$14.000"', 'revisar: figura cobrado de mas'],
        ['LAUTARO', '$125.504', 'sin pagos visibles', '$125.504'],
        ['WILLIAM', '$146.060', 'sin pagos visibles', '$146.060'],
        ['LOS ARANDITAS', '$41.728', 'sin pagos visibles', '$41.728'],
        ['MONCHO', '$49.541', 'sin pagos visibles', '$49.541'],
    ], [3.4*cm, 3.4*cm, 5.0*cm, 4.6*cm]),

    Paragraph('7. Lo que viene (mejora del sistema)', h_st),
    Paragraph(
        'Estamos preparando la funcion de <b>pago parcial (abono)</b>: un boton en la cuenta '
        'corriente para cargar "pago $X" que descuente del saldo, quede registrado con fecha '
        'y entre a caja solo. Asi no hace falta mas el truco del movimiento + la nota. '
        'Va a salir junto con la proxima actualizacion del sistema.', body),

    Spacer(1, 8),
    HRFlowable(width='100%', thickness=0.6, color=ACCENT),
    Paragraph('Datos verificados en el servidor el 12/11/2026: cuentas corrientes y '
              'movimientos de caja de Don Julio Pereiro. Los saldos "le queda debiendo" '
              'son estimados segun los movimientos cargados — confirmar con el cliente.', small),
]

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=1.6*cm, rightMargin=1.6*cm,
                        topMargin=1.4*cm, bottomMargin=1.4*cm,
                        title='Informe 8 - Cuentas corrientes Don Julio Pereiro')
doc.build(E)
print('OK ->', OUT)
