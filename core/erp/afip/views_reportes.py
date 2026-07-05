from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse
import csv
from datetime import datetime
from ..models import AsientoContable, FacturaProveedor, CuentaCorrienteCliente


@login_required
def asientos_contables_list(request):
    """Vista para listar asientos contables con filtros"""
    company = request.user.company if hasattr(request.user, 'company') else None
    
    # Filtros
    tipo_asiento = request.GET.get('tipo_asiento', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    # Queryset base
    queryset = AsientoContable.objects.all()
    
    # Filtrar por empresa si no es superusuario
    if not request.user.is_superuser and company:
        queryset = queryset.filter(company=company)
    
    # Aplicar filtros
    if tipo_asiento:
        queryset = queryset.filter(tipo_asiento=tipo_asiento)
    if fecha_desde:
        queryset = queryset.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        queryset = queryset.filter(fecha__lte=fecha_hasta)
    
    # Calcular totales
    total_debe = queryset.aggregate(Sum('debe_total'))['debe_total__sum'] or 0
    total_haber = queryset.aggregate(Sum('haber_total'))['haber_total__sum'] or 0
    
    context = {
        'object_list': queryset,
        'tipo_asiento': tipo_asiento,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'total_debe': total_debe,
        'total_haber': total_haber,
        'TIPO_ASIENTO_CHOICES': AsientoContable.TIPO_ASIENTO_CHOICES,
    }
    
    return render(request, 'afip/asientos_contables_list.html', context)


@login_required
def asientos_contables_export(request):
    """Exportar asientos contables a CSV"""
    company = request.user.company if hasattr(request.user, 'company') else None
    
    queryset = AsientoContable.objects.all()
    
    if not request.user.is_superuser and company:
        queryset = queryset.filter(company=company)
    
    # Aplicar filtros
    tipo_asiento = request.GET.get('tipo_asiento', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    if tipo_asiento:
        queryset = queryset.filter(tipo_asiento=tipo_asiento)
    if fecha_desde:
        queryset = queryset.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        queryset = queryset.filter(fecha__lte=fecha_hasta)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="asientos_contables_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Fecha', 'Tipo', 'Descripción', 'Debe', 'Haber', 'Venta Relacionada'])
    
    for asiento in queryset:
        writer.writerow([
            asiento.fecha.strftime('%d/%m/%Y') if asiento.fecha else '',
            asiento.get_tipo_asiento_display(),
            asiento.descripcion,
            asiento.debe_total,
            asiento.haber_total,
            asiento.sale.id if asiento.sale else ''
        ])
    
    return response


@login_required
def facturas_proveedores_list(request):
    """Vista para listar facturas de proveedores con filtros"""
    company = request.user.company if hasattr(request.user, 'company') else None
    
    # Filtros
    supplier_id = request.GET.get('supplier', '')
    tipo_comprobante = request.GET.get('tipo_comprobante', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    # Queryset base
    queryset = FacturaProveedor.objects.select_related('supplier', 'company').all()
    
    # Filtrar por empresa si no es superusuario
    if not request.user.is_superuser and company:
        queryset = queryset.filter(company=company)
    
    # Aplicar filtros
    if supplier_id:
        queryset = queryset.filter(supplier_id=supplier_id)
    if tipo_comprobante:
        queryset = queryset.filter(tipo_comprobante=tipo_comprobante)
    if fecha_desde:
        queryset = queryset.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        queryset = queryset.filter(fecha__lte=fecha_hasta)
    
    # Calcular totales
    total_general = queryset.aggregate(Sum('total'))['total__sum'] or 0
    total_iva_21 = queryset.aggregate(Sum('iva_21'))['iva_21__sum'] or 0
    total_iva_10_5 = queryset.aggregate(Sum('iva_10_5'))['iva_10_5__sum'] or 0
    
    # Obtener proveedores para el filtro
    from ..models import Supplier
    suppliers = Supplier.objects.all()
    if not request.user.is_superuser and company:
        suppliers = suppliers.filter(company=company)
    
    context = {
        'object_list': queryset,
        'supplier': supplier_id,
        'tipo_comprobante': tipo_comprobante,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'total_general': total_general,
        'total_iva_21': total_iva_21,
        'total_iva_10_5': total_iva_10_5,
        'suppliers': suppliers,
        'TIPO_COMPROBANTE_CHOICES': FacturaProveedor.TIPO_COMPROBANTE_CHOICES,
    }
    
    return render(request, 'afip/facturas_proveedores_list.html', context)


@login_required
def facturas_proveedores_export(request):
    """Exportar facturas de proveedores a CSV"""
    company = request.user.company if hasattr(request.user, 'company') else None
    
    queryset = FacturaProveedor.objects.select_related('supplier', 'company').all()
    
    if not request.user.is_superuser and company:
        queryset = queryset.filter(company=company)
    
    # Aplicar filtros
    supplier_id = request.GET.get('supplier', '')
    tipo_comprobante = request.GET.get('tipo_comprobante', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    if supplier_id:
        queryset = queryset.filter(supplier_id=supplier_id)
    if tipo_comprobante:
        queryset = queryset.filter(tipo_comprobante=tipo_comprobante)
    if fecha_desde:
        queryset = queryset.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        queryset = queryset.filter(fecha__lte=fecha_hasta)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="facturas_proveedores_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Fecha', 'Proveedor', 'Tipo Comprobante', 'Punto Venta', 'Número', 'CUIT', 'Condición IVA', 
                     'Neto Gravado', 'IVA 21%', 'IVA 10.5%', 'Total', 'CAE'])
    
    for factura in queryset:
        writer.writerow([
            factura.fecha.strftime('%d/%m/%Y') if factura.fecha else '',
            factura.supplier.name if factura.supplier else '',
            factura.get_tipo_comprobante_display(),
            factura.punto_venta,
            factura.numero_comprobante,
            factura.cuit_proveedor,
            factura.get_condicion_iva_display(),
            factura.neto_gravado,
            factura.iva_21,
            factura.iva_10_5,
            factura.total,
            factura.cae or ''
        ])
    
    return response


@login_required
def cuenta_corriente_clientes_list(request):
    """Vista para listar cuenta corriente de clientes con filtros"""
    company = request.user.company if hasattr(request.user, 'company') else None
    
    # Filtros
    client_id = request.GET.get('client', '')
    tipo_movimiento = request.GET.get('tipo_movimiento', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    # Queryset base
    queryset = CuentaCorrienteCliente.objects.select_related('client', 'company').all()
    
    # Filtrar por empresa si no es superusuario
    if not request.user.is_superuser and company:
        queryset = queryset.filter(company=company)
    
    # Aplicar filtros
    if client_id:
        queryset = queryset.filter(client_id=client_id)
    if tipo_movimiento:
        queryset = queryset.filter(tipo_movimiento=tipo_movimiento)
    if fecha_desde:
        queryset = queryset.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        queryset = queryset.filter(fecha__lte=fecha_hasta)
    
    # Calcular totales
    total_debe = queryset.filter(tipo_movimiento='debe').aggregate(Sum('monto'))['monto__sum'] or 0
    total_haber = queryset.filter(tipo_movimiento='haber').aggregate(Sum('monto'))['monto__sum'] or 0
    saldo = total_debe - total_haber
    
    # Obtener clientes para el filtro
    from ..models import Client
    clients = Client.objects.all()
    if not request.user.is_superuser and company:
        clients = clients.filter(company=company)
    
    context = {
        'object_list': queryset,
        'client': client_id,
        'tipo_movimiento': tipo_movimiento,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'total_debe': total_debe,
        'total_haber': total_haber,
        'saldo': saldo,
        'clients': clients,
        'TIPO_MOVIMIENTO_CHOICES': CuentaCorrienteCliente.TIPO_MOVIMIENTO_CHOICES,
    }
    
    return render(request, 'afip/cuenta_corriente_clientes_list.html', context)


@login_required
def cuenta_corriente_clientes_export(request):
    """Exportar cuenta corriente de clientes a CSV"""
    company = request.user.company if hasattr(request.user, 'company') else None
    
    queryset = CuentaCorrienteCliente.objects.select_related('client', 'company').all()
    
    if not request.user.is_superuser and company:
        queryset = queryset.filter(company=company)
    
    # Aplicar filtros
    client_id = request.GET.get('client', '')
    tipo_movimiento = request.GET.get('tipo_movimiento', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    if client_id:
        queryset = queryset.filter(client_id=client_id)
    if tipo_movimiento:
        queryset = queryset.filter(tipo_movimiento=tipo_movimiento)
    if fecha_desde:
        queryset = queryset.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        queryset = queryset.filter(fecha__lte=fecha_hasta)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="cuenta_corriente_clientes_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Fecha', 'Cliente', 'Tipo Movimiento', 'Monto', 'Descripción', 'Venta Relacionada'])
    
    for movimiento in queryset:
        writer.writerow([
            movimiento.fecha.strftime('%d/%m/%Y') if movimiento.fecha else '',
            movimiento.client.name if movimiento.client else '',
            movimiento.get_tipo_movimiento_display(),
            movimiento.monto,
            movimiento.descripcion,
            movimiento.sale.id if movimiento.sale else ''
        ])
    
    return response
