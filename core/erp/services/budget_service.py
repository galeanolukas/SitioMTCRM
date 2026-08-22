"""
Servicio para envío y recepción de presupuestos entre servidor y POS local.
"""
import logging
import requests
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


def send_budget_to_local_server(budget_id: int, local_server_url: str = None) -> Tuple[bool, Optional[str]]:
    """
    Envía un presupuesto al servidor local (POS) vía HTTP API.

    Args:
        budget_id: ID del presupuesto (Sale) a enviar
        local_server_url: URL del servidor local. Si es None, se obtiene de la empresa.

    Returns:
        Tuple (success, error_message)
    """
    from core.erp.models import Sale, Company

    try:
        budget = Sale.objects.get(pk=budget_id, is_budget=True, status='budget')
    except Sale.DoesNotExist:
        return False, 'Presupuesto no encontrado'

    # Obtener URL del servidor local si no se proporcionó
    if not local_server_url:
        company = budget.company
        if not company or not company.local_server_url:
            return False, 'No hay URL de servidor local configurada para la empresa'
        local_server_url = company.local_server_url

    # Preparar datos del presupuesto
    items = []
    for det in budget.detsale_set.select_related('prod').all():
        items.append({
            'product_id': det.prod_id,
            'product_code': det.prod.code if det.prod else '',
            'product_name': det.prod.name if det.prod else '',
            'quantity': float(det.cant),
            'price': float(det.price),
            'subtotal': float(det.subtotal),
        })

    client_data = {}
    if budget.cli:
        client_data = {
            'id': budget.cli_id,
            'names': budget.cli.names,
            'surnames': getattr(budget.cli, 'surnames', ''),
            'dni': budget.cli.dni or '',
            'cuit_cuil': budget.cli.cuit_cuil or '',
            'phone': budget.cli.phone or '',
            'address': budget.cli.address or '',
        }

    payload = {
        'local_uuid': budget.local_uuid or f'budget_{budget.id}',
        'company_id': budget.company_id,
        'client_data': client_data,
        'items': items,
        'subtotal': float(budget.subtotal),
        'iva': float(budget.iva),
        'total': float(budget.total),
        'payment_method': budget.payment_method,
        'budget_notes': budget.budget_notes or '',
        'pos_id': budget.pos_id or '',
        'date_joined': budget.date_joined.isoformat(),
    }

    try:
        url = f"{local_server_url.rstrip('/')}/erp/api/budgets/receive/"
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 201:
            logger.info(f"Presupuesto {budget_id} enviado al POS local exitosamente")
            return True, None
        elif response.status_code == 409:
            # Ya existe, no es error
            logger.info(f"Presupuesto {budget_id} ya existe en POS local")
            return True, 'Presupuesto ya existente en POS local'
        else:
            error = f"Error {response.status_code}: {response.text}"
            logger.error(f"Error enviando presupuesto {budget_id}: {error}")
            return False, error
    except requests.exceptions.ConnectionError:
        return False, 'No se pudo conectar al servidor local'
    except Exception as e:
        logger.error(f"Error enviando presupuesto {budget_id}: {e}")
        return False, str(e)


def send_pending_budgets_to_local_server(company_id: int = None) -> dict:
    """
    Envía todos los presupuestos pendientes al servidor local.

    Args:
        company_id: Si se especifica, solo envía presupuestos de esa empresa

    Returns:
        Dict con estadísticas: {sent, skipped, errors}
    """
    from core.erp.models import Sale

    qs = Sale.objects.filter(
        is_budget=True,
        status='budget',
        sent_to_local=False
    )
    if company_id:
        qs = qs.filter(company_id=company_id)

    stats = {'sent': 0, 'skipped': 0, 'errors': 0}

    for budget in qs:
        success, error = send_budget_to_local_server(budget.id)
        if success:
            budget.sent_to_local = True
            budget.save(update_fields=['sent_to_local'])
            stats['sent'] += 1
        else:
            stats['errors'] += 1
            logger.warning(f"No se pudo enviar presupuesto {budget.id}: {error}")

    return stats
