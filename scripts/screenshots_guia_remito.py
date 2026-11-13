#!/usr/bin/env python3
"""Saca capturas del formulario de remito de entrada para la guia PDF.

Usa la DB local (empresa de ejemplo) y los valores de la factura real
A00114-00004081 (Avicola Santa Ana -> Acro Activo). No guarda nada.

Uso:
    DJENV/bin/python scripts/screenshots_guia_remito.py

Requiere el server corriendo en 127.0.0.1:8000 (el script lo levanta solo).
"""
import os
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, get_user_model  # noqa: E402
from importlib import import_module  # noqa: E402

BASE_URL = os.environ.get('VIDEO_BASE_URL', 'http://127.0.0.1:8000')
OUT_DIR = os.path.join(BASE_DIR, 'videos_tutoriales', 'guia_remito')
USER = 'multilideres'
COMPANY_ID = 4

ITEMS = [
    # (producto, cant, lista, bonif, iva) -> neto esperado = lista*(1-bonif)/(1+iva)
    ('MILANESAS DE POLLO NOELMA X 6KG.',            '20', '44830',  '4',   '21',   '35567.60'),
    ('PATITAS REBOZADAS CRUNCH X 6KG CALISA',        '5',  '47370',  '1.5', '21',   '38561.53'),
    ('CAJA SOY  ALAS X15KG',                        '35', '37500',  '4',   '10.5', '32579.19'),
    ('CAJA DE POLLO ENERCOP  Nº 8',                  '80', '38640',  '5',   '10.5', '33219.91'),
]


def make_session_key(username, company_id):
    user = get_user_model().objects.get(username=username)
    engine = import_module(settings.SESSION_ENGINE)
    s = engine.SessionStore()
    s[SESSION_KEY] = str(user.pk)
    s[BACKEND_SESSION_KEY] = 'django.contrib.auth.backends.ModelBackend'
    s[HASH_SESSION_KEY] = user.get_session_auth_hash()
    s['company_id'] = company_id
    s.create()
    return s.session_key


def start_server():
    proc = subprocess.Popen(
        [sys.executable, 'manage.py', 'runserver', '127.0.0.1:8000', '--noreload'],
        cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            import urllib.request
            urllib.request.urlopen(BASE_URL + '/login/', timeout=2)
            return proc
        except Exception:
            time.sleep(1)
    proc.kill()
    raise RuntimeError('no levanto el server')


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    server = start_server()
    try:
        from playwright.sync_api import sync_playwright
        import secrets

        session_key = make_session_key(USER, COMPANY_ID)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            context = browser.new_context(
                viewport={'width': 1500, 'height': 950}, locale='es-AR')
            context.add_cookies([
                {'name': 'sessionid', 'value': session_key, 'url': BASE_URL},
                {'name': 'csrftoken', 'value': secrets.token_urlsafe(32), 'url': BASE_URL},
            ])
            page = context.new_page()
            page.on('dialog', lambda d: d.accept())
            page.set_default_timeout(20000)

            page.goto(BASE_URL + '/erp/remito/add/')
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(1200)

            # ---- Cabecera: tipo entrada, proveedor, numero, fecha, IVA modo
            page.select_option('#id_tipo', 'entrada')
            # proveedor: elegir el primero disponible (la empresa local es de ejemplo)
            page.select_option('#id_supplier', index=1)
            page.fill('#id_numero', 'A00114-00004081')
            page.fill('#id_fecha', '2026-11-12')
            page.select_option('#id_iva_modo', 'agregado')
            page.fill('#id_iva_porcentaje', '10.5')
            page.locator('#id_iva_porcentaje').dispatch_event('input')
            page.wait_for_timeout(600)
            # estado pendiente si el campo existe
            try:
                page.select_option('#id_estado', 'pending')
            except Exception:
                pass
            page.evaluate("document.getElementById('productSearchHint').scrollIntoView()")
            page.screenshot(path=os.path.join(OUT_DIR, 'paso1_cabecera.png'))

            # ---- Paso 2: fila de carga con radio "lista" + campos
            page.check('#precioEsLista')
            page.wait_for_timeout(300)

            # producto via select2 (de ejemplo; el nombre no importa para la captura)
            page.click('.select2-selection')
            page.wait_for_selector('.select2-search__field', state='visible')
            page.type('.select2-search__field', 'CENCERRO', delay=40)
            page.wait_for_timeout(1500)
            opt = page.locator('.select2-results__option').first
            try:
                opt.wait_for(state='visible', timeout=3000)
                opt.click()
            except Exception:
                page.keyboard.press('Escape')

            page.fill('#cantidad', '20')
            page.fill('#precioUnitario', '44830')
            page.fill('#bonifPct', '4')
            page.fill('#ivaPctLinea', '21')
            page.locator('#ivaPctLinea').dispatch_event('input')
            page.wait_for_timeout(500)
            page.evaluate("document.getElementById('precioEsLista').scrollIntoView({block:'center'})")
            page.screenshot(path=os.path.join(OUT_DIR, 'paso2_fila_lista.png'))

            # ---- Paso 3: cargar las lineas reales de la factura via JS
            # (así la tabla muestra los productos reales de la factura)
            items_js = ','.join(
                "{temp_id: %d, prod_id: '0', prod_name: '%s', cantidad: %s, "
                "precio_unitario: %s, bonif: %s, subtotal: %s * %s, iva_rate: %s}"
                % (i + 1, name, cant, neto, bonif, cant, neto, float(iva) / 100)
                for i, (name, cant, lista, bonif, iva, neto) in enumerate(ITEMS))
            page.evaluate("detalles.push(%s); renderDetalles();" % items_js)
            page.wait_for_timeout(600)
            page.evaluate("document.querySelector('table').scrollIntoView()")
            page.screenshot(path=os.path.join(OUT_DIR, 'paso3_tabla.png'))

            # ---- Paso 4: pie con totales
            page.evaluate("document.querySelector('tfoot').scrollIntoView({block:'end'})")
            page.wait_for_timeout(400)
            el = page.locator('tfoot')
            el.screenshot(path=os.path.join(OUT_DIR, 'paso4_totales.png'))

            browser.close()
            print('capturas en', OUT_DIR)
    finally:
        server.terminate()


if __name__ == '__main__':
    main()
