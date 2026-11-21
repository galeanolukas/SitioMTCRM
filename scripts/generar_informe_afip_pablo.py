#!/usr/bin/env python
"""Genera informe_afip_djp.pdf (informe Nro 9, en criollo):
que le falta a Pablo para emitir factura electronica con CAE."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'videos_tutoriales', 'informe_afip_djp.pdf')

ACCENT = colors.HexColor('#1a5276')
LIGHT = colors.HexColor('#eaf2f8')
GREEN = colors.HexColor('#1e8449')
RED = colors.HexColor('#b03a2e')
AMBER = colors.HexColor('#9a7d0a')

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
ok_st = ParagraphStyle('ok', parent=cell, textColor=GREEN,
                       fontName='Helvetica-Bold')
no_st = ParagraphStyle('no', parent=cell, textColor=RED,
                       fontName='Helvetica-Bold')
war_st = ParagraphStyle('war', parent=cell, textColor=AMBER,
                        fontName='Helvetica-Bold')


def T(rows, widths, header=True):
    data = []
    for i, r in enumerate(rows):
        line = []
        for x in r:
            if isinstance(x, Paragraph):
                line.append(x)
            else:
                style = cellw if (header and i == 0) else cell
                line.append(Paragraph(str(x), style))
        data.append(line)
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


def ok(t):
    return Paragraph(t, ok_st)


def no(t):
    return Paragraph(t, no_st)


def war(t):
    return Paragraph(t, war_st)


E = [
    Paragraph('INFORME Nro 9: QUE FALTA PARA FACTURAR ELECTRONICO (CAE)', title_st),
    Paragraph('Don Julio Pereiro - 21/11/2026', sub_st),

    Paragraph('1. Resumen en una frase', h_st),
    Paragraph(
        'El sistema YA sabe emitir factura electronica, pero a la empresa '
        '<b>Don Julio Pereiro nunca se le cargo la configuracion AFIP</b>. '
        'Por eso hasta hoy salen tickets internos, no facturas con CAE. '
        'Para habilitarlo hay que juntar unas cosas de ARCA y cargarlas '
        'en una pantalla del sistema. La mayoria las gestiona el contador '
        'en un dia.', body),

    Paragraph('2. Estado actual (revisado el 21/11/2026)', h_st),
    T([
        ['Item', 'Estado', 'Detalle'],
        ['CUIT', ok('OK'), '20409378472 (cargado en la empresa)'],
        ['Condicion IVA', ok('OK'), 'Responsable Inscripto (RI) - verificar con el contador que sea la real'],
        ['Domicilio', ok('OK'), 'Padre Patino 15, Formosa'],
        ['Inicio de actividades', ok('OK'), '20/10/1985'],
        ['Ingresos Brutos (IIBB)', no('FALTA'), 'El campo esta vacio. El contador debe pasar el numero/CM de Formosa.'],
        ['Config AFIP en el sistema', no('FALTA'), 'No existe ninguna configuracion cargada para la empresa.'],
        ['Punto de venta AFIP', no('FALTA'), 'No hay punto de venta electronico creado (ni en el sistema ni, probablemente, en ARCA).'],
        ['Certificado + clave (WSFE)', no('FALTA'), 'Sin certificado no hay CAE. Se genera automatico con la clave fiscal, o se sube manual.'],
        ['Ventas ya emitidas con CAE', no('0'), 'Ninguna venta de la empresa tiene CAE todavia.'],
        ['Ventas esperando CAE', war('695'), 'Hay 695 ventas marcadas "pendiente de autorizacion AFIP".'],
    ], [3.6*cm, 2.4*cm, 10.4*cm]),

    Paragraph('3. Lo que hay que conseguir del lado de ARCA (lo hace el contador)', h_st),
    T([
        ['#', 'Tramite', 'Para que sirve'],
        ['1', 'Clave fiscal nivel 3', 'Es el usuario+contrasena de ARCA. Con nivel 3 se pueden delegar '
         'servicios web. El sistema la usa UNA vez para generar el certificado solo.'],
        ['2', 'Punto de venta electronico (tipo Web Service / RECE)', 'En ARCA: Administracion de '
         'Puntos de Venta y Domicilios -> dar de alta un PV electronico. El numero que quede '
         '(ej: 4) es el que va en el sistema.'],
        ['3', 'Adherirse al servicio WSFE (Facturacion Electronica)', 'En ARCA: Administrador de '
         'Relaciones -> habilitar el web service wsfe. El sistema intenta hacerlo automatico '
         'con la clave fiscal, pero si falla hay que darlo de alta manual.'],
        ['4', 'Alta/confirmar IIBB en Formosa', 'Para que figure bien el encabezado de la factura '
         'y no haya problema provincial.'],
        ['5', 'Confirmar la condicion IVA real', 'Define el tipo de factura: si es RI emite '
         'Factura B (o A a otro RI); si es Monotributo emite Factura C. Esto lo define el contador.'],
    ], [0.7*cm, 5.6*cm, 10.1*cm]),

    Paragraph('4. Lo que se carga en el sistema (5 minutos, lo hacemos nosotros con vos)', h_st),
    Paragraph(
        'Menu AFIP -> Crear configuracion. Campos:', body),
    T([
        ['Campo', 'Que va'],
        ['Empresa / CUIT', 'Don Julio Pereiro - 20409378472'],
        ['Access Token', 'Ya hay uno global cargado en el servidor (afipsdk.com).'],
        ['Usuario y contrasena Clave Fiscal', 'Se usan solo para generar el certificado y autorizar '
         'WSFE automaticamente. No quedan expuestos en ninguna factura.'],
        ['Ambiente', 'prod (produccion). Ojo: hoy el CUIT esta en modo dev/homologacion, '
         'o sea que las pruebas no emiten CAE real.'],
        ['Tipo de comprobante', 'Factura B si es RI / Factura C si es Monotributo (punto 3.5).'],
        ['Punto de venta', 'El numero electronico que de ARCA (punto 3.2). El sistema crea '
         'el registro interno solo, hay que ponerle el numero correcto.'],
    ], [5.4*cm, 11.0*cm]),
    Paragraph(
        'Al guardar, el sistema genera el certificado, autoriza WSFE y crea el punto de '
        'venta interno. Despues conviene emitir UNA factura de prueba a Consumidor Final '
        'por poco monto y verificar el CAE antes de facturar en serio.', body),

    Paragraph('5. Ojo con las 695 ventas pendientes', h_st),
    Paragraph(
        'Todas las ventas hechas hasta hoy quedaron como "pendiente de autorizacion" '
        'porque no habia CAE. Cuando este habilitado hay que decidir con el contador '
        'cuales se facturan (las de este periodo fiscal, normalmente) y cuales se dejan '
        'asentadas como ticket interno. <b>No se emiten todas automaticamente</b> - '
        'se factura a partir de la habilitacion y, si hace falta, se recuperan las de '
        'noviembre que correspondan.', body),

    Paragraph('6. Checklist para Pablo (imprimilo y tachemos juntos)', h_st),
    T([
        ['', 'Paso'],
        ['[ ]', 'Pedirle al contador: clave fiscal nivel 3 + numero de IIBB + confirmar si soy RI o Monotributo'],
        ['[ ]', 'Pedirle al contador (o hacerlo en ARCA): punto de venta electronico WSFE dado de alta - anotar el numero'],
        ['[ ]', 'Avisar a Lukas con esos datos -> cargamos la config AFIP en el sistema'],
        ['[ ]', 'Emitir factura de prueba por poco monto y verificar que sale con CAE'],
        ['[ ]', 'Definir con el contador que hacer con las ventas pendientes de noviembre'],
    ], [1.2*cm, 15.2*cm], header=False),
]


def main():
    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=1.6*cm,
                            rightMargin=1.6*cm, topMargin=1.5*cm,
                            bottomMargin=1.5*cm)
    doc.build(E)
    print('Generado:', OUT)


if __name__ == '__main__':
    main()
