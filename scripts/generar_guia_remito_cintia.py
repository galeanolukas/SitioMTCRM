#!/usr/bin/env python
"""Genera guia_carga_remito.pdf — tutorial paso a paso para Cintia.

Usa las capturas de scripts/screenshots_guia_remito.py (videos_tutoriales/
guia_remito/*.png) y los datos de la factura real A00114-00004081.
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, HRFlowable, PageBreak)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, 'videos_tutoriales', 'guia_remito')
OUT = os.path.join(BASE, 'videos_tutoriales', 'guia_carga_remito.pdf')

ACCENT = colors.HexColor('#1a5276')
LIGHT = colors.HexColor('#eaf2f8')

title_st = ParagraphStyle('t', fontName='Helvetica-Bold', fontSize=16,
                          textColor=ACCENT, spaceAfter=2)
sub_st = ParagraphStyle('s', fontName='Helvetica', fontSize=9.5,
                        textColor=colors.HexColor('#555555'), spaceAfter=10)
h_st = ParagraphStyle('h', fontName='Helvetica-Bold', fontSize=11.5,
                      textColor=ACCENT, spaceBefore=10, spaceAfter=4)
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


def img(name, width=16.5 * cm):
    path = os.path.join(IMG, name)
    from PIL import Image as PILImage
    w, h = PILImage.open(path).size
    return Image(path, width=width, height=width * h / w)


E = [
    Paragraph('GUIA: COMO CARGAR UN REMITO DE ENTRADA DESDE LA FACTURA', title_st),
    Paragraph('Para Cintia - Distribuidora Acro Activo - ejemplo real: factura A00114-00004081 '
              '(Avicola Santa Ana, 12/11/2026) - 13/11/2026', sub_st),

    Paragraph('Menu: Inventario > Remitos > Nuevo registro. Ejemplo con una factura tipo A '
              'del proveedor (precios de lista con IVA, bonificacion por renglon e IVA mixto).', body),

    Paragraph('PASO 1 - Cabecera del remito', h_st),
    T([
        ['Campo', 'Que poner'],
        ['Tipo', 'Entrada (estamos recibiendo mercaderia)'],
        ['Proveedor', 'El de la factura (ej: AVICOLA SANTA ANA S.A.)'],
        ['Numero de Remito', 'El numero de la factura tal cual: A00114-00004081'],
        ['Fecha', 'La fecha de la factura'],
        ['IVA (%)', 'El IVA mas comun de la factura (en el ejemplo 10.5). Es solo el default; cada renglon puede tener otro.'],
        ['Modo de IVA', '"IVA adicional sobre el neto" para facturas A/B (los netos no traen IVA).'],
        ['Ajuste de costo (%)', '0, salvo que el proveedor haya aumentado la lista despues de emitir la factura.'],
    ], [4.2 * cm, 12.0 * cm]),
    img('paso1_cabecera.png'),

    Paragraph('PASO 2 - Cada renglon: tipear lo que dice la factura', h_st),
    Paragraph(
        'La fila de carga ahora copia las columnas de la factura tal cual vienen. '
        'Para cada item:', body),
    T([
        ['Campo', 'Que tipear (columna de la factura)'],
        ['Producto (buscador)', 'El producto del inventario que corresponde'],
        ['Cantidad', 'La columna "Unidades" (ej: 20 cajas)'],
        ['Precio', 'La columna "$P.U.Lista" TAL CUAL (con IVA)'],
        ['Bonif%', 'La columna "%Bonif." del renglon (4, 1.5, 5...)'],
        ['IVA%', 'La columna "%IVA" del renglon (21 o 10.5)'],
    ], [4.2 * cm, 12.0 * cm]),
    Paragraph(
        '<b>Clave: marcar la opcion "Precio de LISTA"</b> (radio azul). El sistema solo '
        'calcula el neto: descuenta la bonificacion y saca el IVA. Se ve en verde '
        '"Neto calculado: $35.567,60" antes de apretar Agregar.', body),
    img('paso2_fila_lista.png'),
    Paragraph(
        'Ejemplo del primer renglon: MILANESA 6KG, 20 unidades, lista $44.830, '
        'bonif 4%, IVA 21% -> el sistema guarda el neto <b>$35.567,60</b>, que es lo '
        'que se pago de verdad por caja.', body),

    PageBreak(),

    Paragraph('PASO 3 - La tabla se llena sola', h_st),
    Paragraph(
        'Cada "Agregar" suma un renglon con Precio Unitario = neto ya calculado, '
        'la columna Bonif muestra el descuento aplicado y las columnas IVA/Neto '
        'muestran el desglose de cada item.', body),
    img('paso3_tabla.png'),
    img('paso4_totales.png', width=16.5 * cm),

    Paragraph('EXTRA - Si el producto no existe: boton "Nuevo Producto"', h_st),
    Paragraph(
        'Si un item de la factura no esta en el sistema, se crea ahi mismo con el boton verde '
        '"Nuevo Producto" (no hay que salir del remito). El formulario ahora copia la misma '
        'logica de la fila:', body),
    T([
        ['Campo', 'Que poner'],
        ['Nombre del Producto', 'El nombre tal cual figura en la factura/empaque'],
        ['Categoria', 'La que corresponda (ej: CONGELADOS)'],
        ['Precio neto / Precio de lista', 'Misma regla que la fila: si vas a tipear la '
         'columna "$P.U.Lista" de la factura, marca "Precio de lista"'],
        ['Precio', 'Segun el modo elegido: el neto o el "$P.U.Lista" tal cual'],
        ['Bonificacion (%)', 'La columna "%Bonif." del renglon (solo aparece en modo lista)'],
        ['Margen de ganancia (%)', 'El margen para armar el precio de venta'],
        ['IVA (%)', 'La columna "%IVA" del renglon (21 o 10.5)'],
        ['Unidad de medida', 'Unidad, Caja, Kg, etc.'],
    ], [4.8 * cm, 11.4 * cm]),
    img('paso5_nuevo_producto.png', width=15.5 * cm),
    Paragraph(
        'El cartel gris de abajo muestra el <b>Costo neto</b> calculado (en el ejemplo '
        '$35.567,60 - el mismo que da la factura) y el precio de venta sugerido. '
        '<b>Verificar ese "Costo neto" contra el "$P.U.Neto" de la factura ANTES de apretar '
        'Crear</b>: si no coincide, algo se tipeo mal. Al crear, la fila del remito queda '
        'precargada con el precio, el IVA y la bonif del producto nuevo - solo falta poner '
        'la cantidad y Agregar.', body),
    Paragraph(
        '<b>Importante:</b> si se tipea el "$P.U.Lista" habiendo dejado "Precio neto" marcado, '
        'el producto nace con costo inflado (~25% mas caro) y el precio de venta tambien '
        'queda alto. Es el mismo chequeo de siempre, pero aca ademas queda grabado en la '
        'ficha del producto.', body),

    Paragraph('PASO 4 - VERIFICACION (hacer siempre antes de guardar/procesar)', h_st),
    Paragraph('Checklist rapido para saber que la carga esta bien:', body),
    T([
        ['#', 'Que verificar', 'Como'],
        ['1', '<b>El "Neto" total del remito = "Subtotal $" de la factura</b>',
         'En el ejemplo: remito Neto tiene que dar 8.676.171,15 (unos centavos de diferencia '
         'por redondeo es normal). Si da mucho mas -> cargaron precios con IVA o sin '
         'bonificacion. Si da menos -> falto un item o se duplico el descuento.'],
        ['2', '<b>Cantidad de renglones = renglones de la factura</b>',
         'La factura tiene 9 items -> la tabla tiene 9 items.'],
        ['3', '<b>Cantidades correctas por item</b>',
         'Cotejar "Unidades" de cada renglon contra la factura (20, 5, 5, 35, 12, 12, 80, 30, 3).'],
        ['4', '<b>Neto por item razonable</b>',
         'El neto tiene que ser MENOR que la lista (le saco bonif e IVA). Si el "Precio '
         'Unitario" de la tabla es igual a la lista -> falto marcar "Precio de LISTA" o la bonif.'],
        ['5', '<b>IVA por item correcto</b>',
         'La columna IVA muestra el % de cada item (21% en elaborados, 10.5% en el resto). '
         'La suma de IVA tiene que acercar a la suma de las lineas IVA de la factura '
         '(230.799,07 + 795.598,44 = 1.026.397,51 en el ejemplo).'],
        ['6', '<b>Producto correcto</b>',
         'OJO con los duplicados: "Soy Alas" vs "Alas Aveguay", "Soy pata muslo" vs Aveguay. '
         'Verificar que hay fisicamente en la heladera antes de elegir el registro.'],
    ], [0.8 * cm, 6.2 * cm, 9.2 * cm]),

    Paragraph('Los errores mas comunes (y como se ven)', h_st),
    T([
        ['Sintoma', 'Causa'],
        ['Neto total mucho mas alto que el Subtotal de la factura',
         'Se cargo "$P.U.Lista" como si fuera neto (el error de esta factura: daba +$1.4M).'],
        ['Neto total MENOR que el Subtotal de la factura',
         'Se aplico la bonificacion dos veces (bonif cargada + precio ya neto).'],
        ['Un item con precio igual a la lista', 'Falto Bonif% o IVA% en esa fila.'],
        ['Falta mercaderia en stock despues de procesar',
         'El remito quedo "Pendiente" y nunca se proceso -> hay que procesarlo para que sume stock.'],
    ], [7.0 * cm, 9.2 * cm]),

    HRFlowable(width='100%', color=ACCENT, thickness=1, spaceBefore=10, spaceAfter=6),
    Paragraph(
        'Regla de oro: <b>tipear tal cual dice la factura (Lista, %Bonif, %IVA) con la opcion '
        '"Precio de LISTA" marcada, y que el Neto total cierre con el "Subtotal $" de la factura.</b> '
        'Si no cierra, NO procesar - avisar antes.', body),
    Paragraph(
        'Nota: la percepcion de IIBB (ej: $173.523,42) no se carga en el remito; la registra '
        'contaduria. El "Total" del remito (neto + IVA) va a quedar un poco por debajo del '
        'total de la factura por esa percepcion - es normal.', small),
]

doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=2 * cm, rightMargin=2 * cm,
                        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                        title='Guia carga de remito - Acro Activo')
doc.build(E)
print('Generado:', OUT)
