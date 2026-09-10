import json
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.contrib import messages

from core.erp.mixins import get_active_company_id

User = get_user_model()


# Definición centralizada de modelos a limpiar.
# Cada entrada: (label, model, company_path)
#   company_path = 'company' para modelos con FK directo a Company
#   company_path = 'sale__company', 'cash_register__company', ... para modelos
#   de detalle que no tienen FK directo pero se filtran vía su padre.
#   company_path = None para modelos GLOBALES (sin FK a Company, ej. SyncLog):
#     - si hay empresa seleccionada se OMITE el borrado (no se puede aislar por empresa)
#     - si está en "Todas" se borra todo el contenido del modelo
# Orden: primero detalles, luego padres (para respetar restricciones de FK).
_MODELS_TO_CLEAR = None


def _get_models_to_clear():
    global _MODELS_TO_CLEAR
    if _MODELS_TO_CLEAR is not None:
        return _MODELS_TO_CLEAR
    from core.erp.models import (
        Product, Category, Client, Supplier, Sale, DetSale,
        CashRegister, CashMovement, Expense, PriceList, PriceListProduct,
        CardInstallmentPlan, InternalTransfer, InternalTransferDetail,
        RemitoEntrada, Remito, DetalleRemito, LibroIvaRegistro,
        CuentaCorrienteCliente, AsientoContable, FacturaProveedor,
        SaleVatBreakdown, QuickOrder, SyncLog, ProfitReport,
        AfipConfig, AfipPuntoVenta, CatalogoConfig, PosTerminal,
        DetalleRemitoEntrada, MercadoPagoConfig,
    )
    _MODELS_TO_CLEAR = [
        # Detalles primero
        ('Detalles de Venta', DetSale, 'sale__company'),
        ('Detalles de Remito', DetalleRemito, 'remito__company'),
        ('Detalles de Remito de Entrada', DetalleRemitoEntrada, 'remito__company'),
        ('Detalles de Transferencia', InternalTransferDetail, 'transfer__company'),
        ('Productos en Listas', PriceListProduct, 'price_list__company'),
        ('Apertura IVA por Venta', SaleVatBreakdown, 'sale__company'),
        ('Movimientos de Caja', CashMovement, 'cash_register__company'),
        ('Logs de Sync', SyncLog, None),  # global: sin company, se omite si hay empresa seleccionada
        ('Reportes de Ganancia', ProfitReport, 'company'),
        ('Cuenta Corriente Clientes', CuentaCorrienteCliente, 'company'),
        ('Asientos Contables', AsientoContable, 'company'),
        ('Registros Libro IVA', LibroIvaRegistro, 'company'),
        ('Facturas Proveedores', FacturaProveedor, 'company'),
        # Padres
        ('Ventas', Sale, 'company'),
        ('Cajas', CashRegister, 'company'),
        ('Gastos', Expense, 'company'),
        ('Pedidos Rápidos', QuickOrder, 'company'),
        ('Transferencias', InternalTransfer, 'company'),
        ('Remitos de Entrada', RemitoEntrada, 'company'),
        ('Remitos', Remito, 'company'),
        ('Listas de Precios', PriceList, 'company'),
        ('Planes de Cuotas', CardInstallmentPlan, 'company'),
        ('Productos', Product, 'company'),
        ('Categorías', Category, 'company'),
        ('Clientes', Client, 'company'),
        ('Proveedores', Supplier, 'company'),
        # Configs que se pueden limpiar (se resincronizan)
        ('Configs AFIP', AfipConfig, 'company'),
        ('Puntos de Venta AFIP', AfipPuntoVenta, 'company'),
        ('Configs Catálogo', CatalogoConfig, 'company'),
        ('Terminales POS', PosTerminal, 'company'),
        ('Configs Mercado Pago', MercadoPagoConfig, 'company'),
    ]
    return _MODELS_TO_CLEAR


def _filtered_queryset(model, company_path, company_id):
    """Devuelve el queryset del modelo a borrar según el alcance.

    - Si company_id es None (Todas): devuelve todos los registros.
    - Si company_id está seteado y company_path no es None: filtra por empresa.
    - Si company_id está seteado y company_path es None (modelo global): devuelve
      queryset vacío (se omite el borrado para no afectar a otras empresas).
    """
    if company_id:
        if company_path is None:
            return model.objects.none()
        return model.objects.filter(**{company_path: company_id})
    return model.objects.all()


@method_decorator([csrf_exempt, login_required], name='dispatch')
class ClearLocalDBView(TemplateView):
    """Vista para limpiar la DB local (todo menos usuarios, grupos, empresas y configs de sync).

    Si hay una empresa activa seleccionada en el topheader (session['company_id']),
    sólo se eliminan los registros de esa empresa. Si no hay empresa seleccionada
    (opción "Todas"), se eliminan todos los registros de todas las empresas.
    """
    template_name = 'clear_db/clear_local_db.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return JsonResponse({'error': 'Solo superusuarios pueden acceder'}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Limpiar Base de Datos Local'
        ctx['entity'] = 'Administración'

        company_id = get_active_company_id(self.request)
        ctx['scope_company_id'] = company_id
        if company_id:
            from core.erp.models import Company
            ctx['scope_company'] = Company.objects.filter(pk=company_id).first()
            ctx['scope_label'] = ctx['scope_company'].name if ctx['scope_company'] else 'Empresa #%s' % company_id
        else:
            ctx['scope_company'] = None
            ctx['scope_label'] = 'Todas las empresas'

        models = _get_models_to_clear()
        ctx['counts'] = []
        total = 0
        for label, model, company_path in models:
            count = _filtered_queryset(model, company_path, company_id).count()
            ctx['counts'].append({'label': label, 'count': count})
            total += count
        ctx['total_records'] = total
        return ctx

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body) if request.body else {}
        except (json.JSONDecodeError, ValueError):
            data = request.POST

        confirm_key = data.get('confirm_key', '').strip()
        expected_key = data.get('expected_key', '').strip()

        # Validar clave de confirmación (debe escribir "LIMPIAR" en mayúsculas)
        if confirm_key != 'LIMPIAR':
            return JsonResponse({
                'success': False,
                'error': 'Clave de confirmación incorrecta. Debe escribir "LIMPIAR" para confirmar.'
            }, status=400)

        company_id = get_active_company_id(request)
        scope_label = 'Todas las empresas'
        if company_id:
            from core.erp.models import Company
            c = Company.objects.filter(pk=company_id).first()
            scope_label = c.name if c else 'Empresa #%s' % company_id

        try:
            with transaction.atomic():
                models = _get_models_to_clear()
                deleted_counts = {}

                for label, model, company_path in models:
                    qs = _filtered_queryset(model, company_path, company_id)
                    count, _ = qs.delete()
                    deleted_counts[label] = count

                # Resetear auto_increment sólo cuando se limpia TODO (sin filtro de empresa).
                # Si se filtra por empresa, no se tocan las secuencias.
                if not company_id:
                    with connection.cursor() as cursor:
                        if connection.vendor == 'sqlite':
                            # SQLite: resetear sqlite_sequence
                            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN (%s)" % ','.join([
                                "'erp_product'", "'erp_category'", "'erp_client'", "'erp_supplier'",
                                "'erp_sale'", "'erp_detsale'", "'erp_cashregister'", "'erp_cashmovement'",
                                "'erp_expense'", "'erp_pricelist'", "'erp_pricelistproduct'",
                                "'erp_cardinstallmentplan'", "'erp_internaltransfer'",
                                "'erp_internaltransferdetail'", "'erp_remitoentrada'",
                                "'erp_remito'", "'erp_detalleremito'", "'erp_libroivaregistro'",
                                "'erp_cuentacorrientecliente'", "'erp_asientocontable'",
                                "'erp_facturaproveedor'", "'erp_salevatbreakdown'",
                                "'erp_quickorder'", "'erp_synclog'", "'erp_profitreport'",
                                "'erp_afipconfig'", "'erp_afippuntoventa'", "'erp_catalogoconfig'",
                                "'erp_posterminal'", "'erp_mercadopagoconfig'",
                                "'erp_detalleremitoentrada'",
                            ]))

            return JsonResponse({
                'success': True,
                'message': 'Base de datos local limpiada correctamente (Alcance: %s).' % scope_label,
                'scope': scope_label,
                'company_id': company_id,
                'deleted': deleted_counts,
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error al limpiar: {str(e)}'
            }, status=500)
