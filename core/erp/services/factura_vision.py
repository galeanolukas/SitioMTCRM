"""Lee facturas/remitos escaneados con un modelo de visión (OpenRouter).

El comprobante llega como PDF (digital o del escáner) o como imagen. Se convierte
a PNG y se la manda a un modelo que "ve" el papel y devuelve un JSON con todo lo
relevante: proveedor (con CUIT), fecha, número, tipo, renglones con código de
proveedor y código de barras, descuento, IVA y total.

Después la vista `escanear_remito` cruza cada código con el catálogo
(codigo_proveedor / code / external_code) y devuelve el borrador precargado
para la pantalla de carga de remito — nada se guarda sin revisión del usuario.

La clave se lee de `OPENROUTER_API_KEY`. El modelo se puede cambiar con
`FACTURA_VISION_MODELO` (por defecto Nemotron VL, gratis en OpenRouter).
"""
import base64
import json
import os
import re
import urllib.request
from decimal import Decimal, InvalidOperation

import pymupdf

MODELO = os.getenv('FACTURA_VISION_MODELO', 'nvidia/nemotron-3.5-super-vl:free')
OPENROUTER = os.getenv('OPENROUTER_API_KEY', '')

PROMPT = (
    "Leé esta factura o remito de un proveedor y extraé TODOS los datos. "
    "Devolvé SOLO un JSON válido, sin texto antes ni después, con esta estructura exacta:\n"
    '{\n'
    '  "proveedor": "razón social del EMISOR (quien emite el comprobante, no el cliente)",\n'
    '  "cuit_proveedor": "CUIT del emisor, solo dígitos",\n'
    '  "fecha": "DD/MM/AAAA",\n'
    '  "numero": "número completo del comprobante (punto de venta + número, ej: A00004-00134828)",\n'
    '  "tipo": "FACTURA_A" (o FACTURA_B, FACTURA_C, REMITO, NOTA_CREDITO),\n'
    '  "items": [{"codigo": "código de artículo del proveedor (columna ARTICULO/CODIGO)", '
    '"cod_barras": "código de barras/EAN si hay columna, si no null", '
    '"descripcion": "...", "cantidad": 1, '
    '"precio_neto": 0.0, "precio_lista": 0.0, "bonif_pct": 0.0}],\n'
    '  "descuento": 0.0,\n'
    '  "iva_porcentaje": 21,\n'
    '  "total": 0.0\n'
    '}\n'
    "Transcribí códigos y números exactos, tal cual están impresos — NO omitas dígitos "
    "en el número de comprobante (el punto de venta suele tener 4 a 5 dígitos). "
    "En cada ítem: precio_neto es el precio unitario SIN IVA y CON bonificación ya "
    "descontada (columna '$P.U.Neto', 'P.Unit.Neto', 'Neto' o similar). "
    "precio_lista es el precio unitario CON IVA y sin bonificar (columna '$P.U.Lista', "
    "'P.Unit.Lista' o similar). Si solo hay una columna de precio unitario, completá "
    "precio_neto con ese valor y dejá precio_lista en null. "
    "bonif_pct es la bonificación porcentual del renglón si figura por columna, si no null. "
    "Nunca pongas el importe total del renglón como precio. "
    "descuento es el porcentaje de bonificación general del comprobante "
    "(ej: la leyenda DESCUENTO:0.00 %). "
    "Si el documento trae páginas repetidas (ORIGINAL y DUPLICADO/COPIA del mismo "
    "comprobante), leé solo una copia — NO dupliques los ítems. "
    "Si un campo no figura en el papel, poné null."
)


def _a_png(ruta):
    """Un PNG (bytes) por página si es PDF; la imagen tal cual si es foto."""
    if ruta.lower().endswith('.pdf'):
        doc = pymupdf.open(ruta)
        return [pagina.get_pixmap(dpi=200).tobytes('png') for pagina in doc]
    return [open(ruta, 'rb').read()]


def _pedir_vision(pngs):
    if not OPENROUTER:
        raise RuntimeError('No hay OPENROUTER_API_KEY configurada en el servidor.')
    contenido = [{'type': 'text', 'text': PROMPT}]
    for png in pngs:
        b64 = base64.b64encode(png).decode()
        contenido.append({'type': 'image_url',
                          'image_url': {'url': 'data:image/png;base64,' + b64}})
    payload = {
        'model': MODELO,
        'messages': [{'role': 'user', 'content': contenido}],
        'temperature': 0,
    }
    req = urllib.request.Request(
        'https://openrouter.ai/api/v1/chat/completions',
        data=json.dumps(payload).encode(),
        headers={'Authorization': 'Bearer ' + OPENROUTER,
                 'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read().decode())
    return resp['choices'][0]['message']['content']


def _parsear_json(texto):
    """El modelo a veces envuelve el JSON en ```json ... ``` o agrega texto suelto."""
    texto = texto.strip()
    m = re.search(r'\{.*\}', texto, re.S)
    if m:
        texto = m.group(0)
    return json.loads(texto)


def a_decimal(v):
    """Convierte un número del modelo a Decimal, tolerando el formato argentino."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    s = str(v).strip().replace('$', '').replace('u', '').strip()
    if not s:
        return None
    # Formato argentino: "49.113,00" (punto=miles, coma=decimal).
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def leer_factura(ruta):
    """Lee el archivo y devuelve el dict con los datos normalizados del comprobante."""
    texto = _pedir_vision(_a_png(ruta))
    d = _parsear_json(texto)

    items = []
    for it in d.get('items') or []:
        neto = a_decimal(it.get('precio_neto'))
        lista = a_decimal(it.get('precio_lista'))
        # Compat: si el modelo devolvió el formato viejo de un solo precio
        if neto is None and lista is None:
            neto = a_decimal(it.get('precio_unitario'))
        # Los precios del remito son Decimal(9,2): redondear a centavos
        if neto is not None:
            neto = neto.quantize(Decimal('0.01'))
        if lista is not None:
            lista = lista.quantize(Decimal('0.01'))
        items.append({
            'codigo': str(it.get('codigo') or '').strip(),
            'cod_barras': str(it.get('cod_barras') or '').strip(),
            'descripcion': str(it.get('descripcion') or '').strip(),
            'cantidad': a_decimal(it.get('cantidad')) or Decimal('1'),
            # precio_unitario = el neto (sin IVA, post-bonif); es lo que va al remito
            'precio_unitario': neto if neto is not None else (lista or Decimal('0')),
            'precio_lista': lista,
            # True si el documento solo traía precio de lista y no neto
            'es_lista': neto is None and lista is not None,
            'bonif_pct': a_decimal(it.get('bonif_pct')),
        })

    return {
        'proveedor': (d.get('proveedor') or '').strip(),
        'cuit_proveedor': re.sub(r'\D', '', str(d.get('cuit_proveedor') or '')),
        'fecha': (d.get('fecha') or '').strip(),
        'numero': (d.get('numero') or '').strip(),
        'tipo': (d.get('tipo') or 'FACTURA_A').strip().upper(),
        'items': items,
        'descuento': a_decimal(d.get('descuento')) or Decimal('0'),
        'iva_porcentaje': a_decimal(d.get('iva_porcentaje')),
        'total': a_decimal(d.get('total')),
    }
