"""
Vistas para generación y exportación de Libro IVA Digital
"""
from django.shortcuts import render
from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from core.erp.mixins import ValidatePermissionRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.urls import reverse_lazy
from core.erp.models import LibroIvaRegistro, Company
from django.db.models import Sum
from datetime import datetime
import csv
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required


class LibroIvaListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    """Lista de registros del Libro IVA"""
    model = LibroIvaRegistro
    template_name = 'afip/libro_iva_list.html'
    permission_required = 'erp.view_libroivaregistro'

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'company') and self.request.user.company:
                qs = qs.filter(company=self.request.user.company)
            else:
                qs = qs.none()

        # Filtros
        tipo_registro = self.request.GET.get('tipo_registro')
        fecha_desde = self.request.GET.get('fecha_desde')
        fecha_hasta = self.request.GET.get('fecha_hasta')

        if tipo_registro:
            qs = qs.filter(tipo_registro=tipo_registro)
        if fecha_desde:
            qs = qs.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha__lte=fecha_hasta)

        return qs.select_related('company', 'sale', 'supplier')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipo_registro'] = self.request.GET.get('tipo_registro', '')
        context['fecha_desde'] = self.request.GET.get('fecha_desde', '')
        context['fecha_hasta'] = self.request.GET.get('fecha_hasta', '')

        # Calcular totales
        qs = self.get_queryset()
        context['total_registros'] = qs.count()
        context['total_neto_gravado'] = qs.aggregate(Sum('neto_gravado'))['neto_gravado__sum'] or 0
        context['total_iva_21'] = qs.aggregate(Sum('iva_21'))['iva_21__sum'] or 0
        context['total_iva_10_5'] = qs.aggregate(Sum('iva_10_5'))['iva_10_5__sum'] or 0
        context['total_iva_27'] = qs.aggregate(Sum('iva_27'))['iva_27__sum'] or 0
        context['total_iva_2_5'] = qs.aggregate(Sum('iva_2_5'))['iva_2_5__sum'] or 0
        context['total_iva_0'] = qs.aggregate(Sum('iva_0'))['iva_0__sum'] or 0
        context['total_general'] = qs.aggregate(Sum('total'))['total__sum'] or 0

        return context


class LibroIvaExportView(LoginRequiredMixin, ValidatePermissionRequiredMixin, TemplateView):
    """Exportar Libro IVA a formato CSV compatible con AFIP"""
    permission_required = 'erp.view_libroivaregistro'

    def get(self, request, *args, **kwargs):
        tipo_registro = request.GET.get('tipo_registro')
        fecha_desde = request.GET.get('fecha_desde')
        fecha_hasta = request.GET.get('fecha_hasta')

        qs = LibroIvaRegistro.objects.all()
        if not request.user.is_superuser:
            if hasattr(request.user, 'company') and request.user.company:
                qs = qs.filter(company=request.user.company)
            else:
                qs = qs.none()

        if tipo_registro:
            qs = qs.filter(tipo_registro=tipo_registro)
        if fecha_desde:
            qs = qs.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha__lte=fecha_hasta)

        qs = qs.order_by('fecha', 'numero_comprobante')

        # Crear respuesta CSV
        response = HttpResponse(content_type='text/csv')
        filename = f"libro_iva_{tipo_registro or 'todos'}_{datetime.now().strftime('%Y%m%d')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        # Encabezados según formato AFIP
        writer.writerow([
            'Fecha', 'Tipo', 'PtoVenta', 'NroComprobante', 'CUIT Emisor',
            'CUIT Receptor', 'Razón Social', 'Condición IVA', 'Aplicación IVA',
            'Neto Gravado', 'Neto No Gravado', 'Neto Exento',
            'IVA 21%', 'IVA 10.5%', 'IVA 27%', 'IVA 2.5%', 'IVA 0%',
            'Impuesto Interno', 'Total', 'CAE', 'Vto CAE'
        ])

        for reg in qs:
            writer.writerow([
                reg.fecha.strftime('%d/%m/%Y'),
                reg.get_tipo_registro_display(),
                reg.punto_venta,
                reg.numero_comprobante,
                reg.cuit_emisor or '',
                reg.cuit_receptor or '',
                reg.razon_social or '',
                reg.get_condicion_iva_display(),
                reg.get_aplicacion_iva_display(),
                reg.neto_gravado,
                reg.neto_no_gravado,
                reg.neto_exento,
                reg.iva_21,
                reg.iva_10_5,
                reg.iva_27,
                reg.iva_2_5,
                reg.iva_0,
                reg.impuesto_interno,
                reg.total,
                reg.cae or '',
                reg.cae_vto.strftime('%d/%m/%Y') if reg.cae_vto else '',
            ])

        return response


@login_required
@csrf_exempt
def libro_iva_delete_all(request):
    """Eliminar todos los registros del Libro IVA (solo superuser)"""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'No tiene permisos para realizar esta acción'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    try:
        # Eliminar todos los registros
        count = LibroIvaRegistro.objects.all().delete()[0]
        return JsonResponse({'success': True, 'deleted_count': count})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
