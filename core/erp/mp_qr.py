"""Integracion con Mercado Pago - QR dinamico de caja (Instore Orders).

Flujo por empresa (usa el access_token de MercadoPagoConfig):
  1. GET  /users/me                                   -> collector_id
  2. GET/POST /users/{uid}/stores                     -> store_id (Sucursal)
  3. GET/POST /pos?external_id=..                     -> pos_external_id (Caja)
  4. PUT  /instore/orders/qr/seller/collectors/{uid}/pos/{pos_ext}/qrs
                                                      -> qr_data + in_store_order_id
  5. GET  /merchant_orders/{in_store_order_id}        -> estado del pago (polling)
  6. DELETE /instore/orders/qr/seller/collectors/{uid}/pos/{pos_ext}/qrs
                                                      -> cancelar la orden
"""
import base64
import io
import logging
from datetime import timedelta

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

MP_API = 'https://api.mercadopago.com'
TIMEOUT = 20
ORDER_EXPIRE_MINUTES = 15


class MpQrError(Exception):
    """Error de integracion con Mercado Pago (mensaje apto para mostrar al cajero)."""


def _headers(cfg):
    return {
        'Authorization': f'Bearer {cfg.access_token}',
        'Content-Type': 'application/json',
    }


def _err(resp, prefix):
    try:
        detail = resp.json()
    except Exception:
        detail = resp.text[:200]
    raise MpQrError(f'{prefix} (HTTP {resp.status_code}): {detail}')


def ensure_collector_id(cfg):
    if cfg.collector_id:
        return cfg.collector_id
    r = requests.get(f'{MP_API}/users/me', headers=_headers(cfg), timeout=TIMEOUT)
    if r.status_code != 200:
        _err(r, 'No se pudo obtener el usuario de Mercado Pago (token invalido?)')
    cfg.collector_id = str(r.json()['id'])
    cfg.save(update_fields=['collector_id'])
    return cfg.collector_id


def ensure_store(cfg):
    if cfg.store_id:
        return cfg.store_id
    uid = ensure_collector_id(cfg)
    r = requests.get(f'{MP_API}/users/{uid}/stores/search',
                     headers=_headers(cfg), timeout=TIMEOUT)
    if r.status_code == 200:
        data = r.json()
        items = data.get('results') if isinstance(data, dict) else data
        if items:
            cfg.store_id = str(items[0]['id'])
            cfg.save(update_fields=['store_id'])
            return cfg.store_id
    body = {
        'name': (cfg.company.name or 'Sucursal')[:60],
        'business_hours': {
            day: [{'open': '00:00', 'close': '23:59'}]
            for day in ('monday', 'tuesday', 'wednesday', 'thursday',
                        'friday', 'saturday', 'sunday')
        },
        'location': {
            'street_name': 'Calle',
            'street_number': 'S/N',
            'city_name': '-',
            'state_name': '-',
            'latitude': 0.0,
            'longitude': 0.0,
            'reference': '',
        },
    }
    r = requests.post(f'{MP_API}/users/{uid}/stores', json=body,
                      headers=_headers(cfg), timeout=TIMEOUT)
    if r.status_code not in (200, 201):
        if r.status_code == 403:
            raise MpQrError(
                'La cuenta de Mercado Pago no tiene habilitado el cobro por QR '
                '(o son credenciales de prueba: el QR solo funciona con '
                'credenciales de produccion).')
        _err(r, 'No se pudo crear la sucursal en Mercado Pago')
    cfg.store_id = str(r.json()['id'])
    cfg.save(update_fields=['store_id'])
    return cfg.store_id


def ensure_pos(cfg):
    if cfg.pos_external_id:
        return cfg.pos_external_id
    store_id = ensure_store(cfg)
    uid = ensure_collector_id(cfg)
    ext_id = f'mtcrm{cfg.company_id}-caja1'
    r = requests.get(f'{MP_API}/pos', params={'external_id': ext_id},
                     headers=_headers(cfg), timeout=TIMEOUT)
    if r.status_code == 200:
        data = r.json()
        items = data.get('results') if isinstance(data, dict) else data
        if items:
            cfg.pos_external_id = ext_id
            cfg.save(update_fields=['pos_external_id'])
            return ext_id
    body = {
        'name': f'Caja {cfg.company.name}'[:60],
        'fixed_amount': False,
        'store_id': int(store_id),
        'external_id': ext_id,
    }
    r = requests.post(f'{MP_API}/pos', json=body, headers=_headers(cfg), timeout=TIMEOUT)
    if r.status_code not in (200, 201):
        _err(r, 'No se pudo crear la caja (POS) en Mercado Pago')
    cfg.pos_external_id = ext_id
    cfg.save(update_fields=['pos_external_id'])
    return ext_id


def create_order(cfg, total, title, external_reference):
    """Crea la orden QR en la caja de MP. Devuelve dict con qr_data e in_store_order_id."""
    uid = ensure_collector_id(cfg)
    pos_ext = ensure_pos(cfg)
    body = {
        'external_reference': external_reference,
        'title': title[:60],
        'description': title[:120],
        'total_amount': round(float(total), 2),
        'items': [{
            'title': title[:60],
            'description': title[:120],
            'quantity': 1,
            'unit_price': round(float(total), 2),
            'unit_measure': 'unit',
            'total_amount': round(float(total), 2),
        }],
        'expiration_date': (timezone.now() + timedelta(minutes=ORDER_EXPIRE_MINUTES)).isoformat(),
    }
    url = f'{MP_API}/instore/orders/qr/seller/collectors/{uid}/pos/{pos_ext}/qrs'
    r = requests.put(url, json=body, headers=_headers(cfg), timeout=TIMEOUT)
    if r.status_code not in (200, 201):
        _err(r, 'No se pudo generar la orden QR')
    return r.json()


def get_payment_status(cfg, in_store_order_id):
    """Consulta el estado del pago. Devuelve 'paid', 'expired' o 'pending'."""
    r = requests.get(f'{MP_API}/merchant_orders/{in_store_order_id}',
                     headers=_headers(cfg), timeout=TIMEOUT)
    if r.status_code == 404:
        return 'pending'  # todavia no se materializo la orden
    if r.status_code != 200:
        logger.warning('mp_qr status error: %s %s', r.status_code, r.text[:200])
        return 'pending'
    data = r.json()
    if data.get('order_status') == 'paid':
        return 'paid'
    if data.get('status') in ('expired', 'cancelled'):
        return 'expired'
    return 'pending'


def create_preference(cfg, total, title, external_reference):
    """Fallback cuando la cuenta no tiene QR instore habilitado:
    crea una preferencia de Checkout Pro y se dibuja un QR del init_point.
    Devuelve dict con id e init_point."""
    body = {
        'external_reference': external_reference,
        'items': [{
            'title': title[:120],
            'quantity': 1,
            'currency_id': 'ARS',
            'unit_price': round(float(total), 2),
        }],
    }
    r = requests.post(f'{MP_API}/checkout/preferences', json=body,
                      headers=_headers(cfg), timeout=TIMEOUT)
    if r.status_code not in (200, 201):
        _err(r, 'No se pudo crear la preferencia de pago')
    return r.json()


def get_payment_status_by_ref(cfg, external_reference):
    """Busca pagos por external_reference (modo preferencia).
    Devuelve 'paid' o 'pending'."""
    r = requests.get(f'{MP_API}/v1/payments/search',
                     params={'external_reference': external_reference,
                             'sort': 'date_created', 'criteria': 'desc'},
                     headers=_headers(cfg), timeout=TIMEOUT)
    if r.status_code != 200:
        logger.warning('mp payments search error: %s %s', r.status_code, r.text[:200])
        return 'pending'
    for p in (r.json().get('results') or []):
        if p.get('status') == 'approved':
            return 'paid'
    return 'pending'


def cancel_order(cfg, pos_external_id=None):
    uid = ensure_collector_id(cfg)
    pos_ext = pos_external_id or cfg.pos_external_id
    url = f'{MP_API}/instore/orders/qr/seller/collectors/{uid}/pos/{pos_ext}/qrs'
    r = requests.delete(url, headers=_headers(cfg), timeout=TIMEOUT)
    return r.status_code in (200, 204)


def qr_png_base64(qr_data):
    """Renderiza el payload EMV del QR como PNG base64 para <img src>."""
    import qrcode
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
