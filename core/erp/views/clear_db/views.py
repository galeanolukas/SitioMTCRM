import json
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.contrib import messages

User = get_user_model()


@method_decorator([csrf_exempt, login_required], name='dispatch')
class ClearLocalDBView(TemplateView):
    """Vista para limpiar la DB local (todo menos usuarios, grupos, empresas y configs de sync)."""
    template_name = 'clear_db/clear_local_db.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return JsonResponse({'error': 'Solo superusuarios pueden acceder'}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Limpiar Base de Datos Local'
        ctx['entity'] = 'Administración'
        # Contar registros actuales para mostrar al usuario
        from core.erp.models import (
            Product, Category, Client, Supplier, Sale, DetSale,
            CashRegister, CashMovement, Expense, PriceList, PriceListProduct,
            CardInstallmentPlan, InternalTransfer, InternalTransferDetail,
            RemitoEntrada, Remito, DetalleRemito, LibroIvaRegistro,
            CuentaCorrienteCliente, AsientoContable, FacturaProveedor,
            SaleVatBreakdown, QuickOrder, SyncLog, ProfitReport,
            AfipConfig, AfipPuntoVenta, CatalogoConfig, PosTerminal,
            DetalleRemitoEntrada,
        )
        models_to_count = [
            ('Productos', Product),
            ('Categorías', Category),
            ('Clientes', Client),
            ('Proveedores', Supplier),
            ('Ventas', Sale),
            ('Detalles de Venta', DetSale),
            ('Cajas', CashRegister),
            ('Movimientos de Caja', CashMovement),
            ('Gastos', Expense),
            ('Listas de Precios', PriceList),
            ('Productos en Listas', PriceListProduct),
            ('Planes de Cuotas', CardInstallmentPlan),
            ('Transferencias', InternalTransfer),
            ('Detalles de Transferencia', InternalTransferDetail),
            ('Remitos de Entrada', RemitoEntrada),
            ('Remitos', Remito),
            ('Detalles de Remito', DetalleRemito),
            ('Registros Libro IVA', LibroIvaRegistro),
            ('Cuenta Corriente Clientes', CuentaCorrienteCliente),
            ('Asientos Contables', AsientoContable),
            ('Facturas Proveedores', FacturaProveedor),
            ('Apertura IVA por Venta', SaleVatBreakdown),
            ('Pedidos Rápidos', QuickOrder),
            ('Logs de Sync', SyncLog),
            ('Reportes de Ganancia', ProfitReport),
            ('Configs AFIP', AfipConfig),
            ('Puntos de Venta AFIP', AfipPuntoVenta),
            ('Configs Catálogo', CatalogoConfig),
            ('Terminales POS', PosTerminal),
        ]
        ctx['counts'] = []
        total = 0
        for label, model in models_to_count:
            count = model.objects.count()
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

        try:
            with transaction.atomic():
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

                # Orden de borrado: primero dependencias, luego padres
                # Usar _raw_delete para bypass de signals y mejorar performance
                deleted_counts = {}

                def delete_model(model, label):
                    count, _ = model.objects.all().delete()
                    deleted_counts[label] = count
                    return count

                # Detalles primero
                delete_model(DetSale, 'Detalles de Venta')
                delete_model(DetalleRemito, 'Detalles de Remito')
                delete_model(InternalTransferDetail, 'Detalles de Transferencia')
                delete_model(PriceListProduct, 'Productos en Listas')
                delete_model(SaleVatBreakdown, 'Apertura IVA por Venta')
                delete_model(CashMovement, 'Movimientos de Caja')
                delete_model(SyncLog, 'Logs de Sync')
                delete_model(ProfitReport, 'Reportes de Ganancia')
                delete_model(CuentaCorrienteCliente, 'Cuenta Corriente Clientes')
                delete_model(AsientoContable, 'Asientos Contables')
                delete_model(LibroIvaRegistro, 'Registros Libro IVA')
                delete_model(FacturaProveedor, 'Facturas Proveedores')

                # Padres
                delete_model(Sale, 'Ventas')
                delete_model(CashRegister, 'Cajas')
                delete_model(Expense, 'Gastos')
                delete_model(QuickOrder, 'Pedidos Rápidos')
                delete_model(InternalTransfer, 'Transferencias')
                delete_model(RemitoEntrada, 'Remitos de Entrada')
                delete_model(Remito, 'Remitos')
                delete_model(PriceList, 'Listas de Precios')
                delete_model(CardInstallmentPlan, 'Planes de Cuotas')
                delete_model(Product, 'Productos')
                delete_model(Category, 'Categorías')
                delete_model(Client, 'Clientes')
                delete_model(Supplier, 'Proveedores')

                # Configs que se pueden limpiar (se resincronizan)
                delete_model(AfipConfig, 'Configs AFIP')
                delete_model(AfipPuntoVenta, 'Puntos de Venta AFIP')
                delete_model(CatalogoConfig, 'Configs Catálogo')
                delete_model(PosTerminal, 'Terminales POS')
                delete_model(MercadoPagoConfig, 'Configs Mercado Pago')

                # Resetear auto_increment en SQLite/PostgreSQL
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
                        ]))

            return JsonResponse({
                'success': True,
                'message': 'Base de datos local limpiada correctamente.',
                'deleted': deleted_counts,
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error al limpiar: {str(e)}'
            }, status=500)
