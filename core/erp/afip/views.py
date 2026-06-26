"""
Vistas para integración con AFIP SDK
"""
from django.shortcuts import render
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from core.erp.mixins import ValidatePermissionRequiredMixin
from django.http import JsonResponse
from django.urls import reverse_lazy
from core.erp.models import AfipConfig, Company, Sale
from .client import AfipClient


class AfipConfigListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    """Lista de configuraciones AFIP"""
    model = AfipConfig
    template_name = 'afip/list.html'
    permission_required = 'erp.view_afipconfig'
    
    def get_queryset(self):
        return AfipConfig.objects.select_related('company').all()


class AfipConfigCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CreateView):
    """Crear configuración AFIP"""
    model = AfipConfig
    template_name = 'afip/form.html'
    permission_required = 'erp.add_afipconfig'
    fields = ['company', 'cuit', 'access_token', 'cert', 'key', 'environment', 'is_active']
    success_url = reverse_lazy('erp:afip:list')


class AfipConfigUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    """Actualizar configuración AFIP"""
    model = AfipConfig
    template_name = 'afip/form.html'
    permission_required = 'erp.change_afipconfig'
    fields = ['company', 'cuit', 'access_token', 'cert', 'key', 'environment', 'is_active']
    success_url = reverse_lazy('erp:afip:list')


class AfipConfigDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    """Eliminar configuración AFIP"""
    model = AfipConfig
    template_name = 'afip/delete.html'
    permission_required = 'erp.delete_afipconfig'
    success_url = reverse_lazy('erp:afip:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Eliminar Configuración AFIP'
        context['action'] = 'delete'
        context['list_url'] = reverse_lazy('erp:afip:list')
        return context


class AfipTestView(LoginRequiredMixin, ValidatePermissionRequiredMixin, TemplateView):
    """Vista para probar conexión con AFIP"""
    template_name = 'afip/test.html'
    permission_required = 'erp.view_afipconfig'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['companies'] = Company.objects.filter(is_active=True)
        return context
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        data = {}
        
        if action == 'test_connection':
            company_id = request.POST.get('company_id')
            
            try:
                client = AfipClient(company_id=company_id)
                status = client.get_server_status()
                
                if 'error' in status:
                    data = {'success': False, 'error': status['error']}
                else:
                    data = {'success': True, 'status': status}
            except Exception as e:
                data = {'success': False, 'error': str(e)}
        
        elif action == 'get_taxpayer':
            cuit = request.POST.get('cuit')
            company_id = request.POST.get('company_id')
            
            try:
                client = AfipClient(company_id=company_id)
                taxpayer = client.get_taxpayer_info(cuit)
                
                if 'error' in taxpayer:
                    data = {'success': False, 'error': taxpayer['error']}
                else:
                    data = {'success': True, 'taxpayer': taxpayer}
            except Exception as e:
                data = {'success': False, 'error': str(e)}
        
        elif action == 'get_invoice_types':
            company_id = request.POST.get('company_id')
            
            try:
                client = AfipClient(company_id=company_id)
                types = client.get_invoice_types()
                
                if 'error' in types:
                    data = {'success': False, 'error': types['error']}
                else:
                    data = {'success': True, 'types': types}
            except Exception as e:
                data = {'success': False, 'error': str(e)}
        
        return JsonResponse(data)


class AfipDashboardView(LoginRequiredMixin, ValidatePermissionRequiredMixin, TemplateView):
    """Dashboard de AFIP"""
    template_name = 'afip/dashboard.html'
    permission_required = 'erp.view_afipconfig'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['configs'] = AfipConfig.objects.filter(is_active=True).select_related('company')
        context['companies'] = Company.objects.filter(is_active=True)
        
        # Obtener empresa del usuario actual
        if hasattr(self.request.user, 'company_id') and self.request.user.company_id:
            context['user_company'] = Company.objects.filter(id=self.request.user.company_id).first()
        
        return context
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        data = {}
        
        if action == 'create_config':
            company_id = request.POST.get('company_id')
            
            try:
                company = Company.objects.get(id=company_id)
                
                # Verificar si ya existe config para esta empresa
                existing_config = AfipConfig.objects.filter(company=company).first()
                if existing_config:
                    data = {'success': False, 'error': 'Ya existe una configuración AFIP para esta empresa'}
                else:
                    # Crear config usando CUIT de la empresa
                    access_token = request.POST.get('access_token')
                    environment = request.POST.get('environment', 'dev')
                    punto_venta = request.POST.get('punto_venta', 1)
                    tipo_comprobante = request.POST.get('tipo_comprobante', 6)
                    
                    if not access_token:
                        # Usar access token global del .env
                        from django.conf import settings
                        access_token = getattr(settings, 'AFIP_ACCESS_TOKEN', None)
                    
                    if not company.cuit:
                        data = {'success': False, 'error': 'La empresa no tiene CUIT configurado'}
                    else:
                        config = AfipConfig.objects.create(
                            company=company,
                            cuit=company.cuit,
                            access_token=access_token,
                            environment=environment,
                            punto_venta=punto_venta,
                            tipo_comprobante=tipo_comprobante,
                            is_active=True
                        )
                        data = {'success': True, 'config_id': config.id, 'message': 'Configuración AFIP creada exitosamente'}
            except Company.DoesNotExist:
                data = {'success': False, 'error': 'Empresa no encontrada'}
            except Exception as e:
                data = {'success': False, 'error': str(e)}
        
        return JsonResponse(data)


class AfipVouchersListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    """Lista de comprobantes electrónicos emitidos (ventas con CAE)"""
    model = Sale
    template_name = 'afip/vouchers.html'
    permission_required = 'erp.view_afipconfig'
    paginate_by = 25

    def get_queryset(self):
        active_cid = self.request.session.get('company_id')
        if not active_cid:
            active_cid = getattr(self.request.user, 'company_id', None)

        qs = Sale.objects.select_related('cli', 'company').filter(
            afip_cae__isnull=False
        ).exclude(afip_cae='')

        if active_cid:
            qs = qs.filter(company_id=active_cid)

        return qs.order_by('-date_joined')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Comprobantes AFIP'
        context['entity'] = 'Comprobantes AFIP'
        context['list_url'] = reverse_lazy('erp:afip:vouchers')

        qs = context.get('object_list') or []
        for sale in qs:
            if sale.afip_error:
                sale.afip_status = 'error'
            elif sale.afip_cae:
                sale.afip_status = 'ok'
            else:
                sale.afip_status = 'pending'

        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        data = {}

        if action == 'retry_invoice':
            sale_id = request.POST.get('sale_id')
            try:
                sale = Sale.objects.get(pk=sale_id)
                if sale.afip_cae:
                    data = {'success': False, 'error': 'Esta venta ya tiene CAE asignado'}
                else:
                    result = sale.emitir_factura_afip()
                    if result:
                        data = {'success': True, 'message': 'Factura emitida correctamente', 'cae': sale.afip_cae}
                    else:
                        data = {'success': False, 'error': sale.afip_error or 'Error al emitir factura'}
            except Sale.DoesNotExist:
                data = {'success': False, 'error': 'Venta no encontrada'}
            except Exception as e:
                data = {'success': False, 'error': str(e)}

        return JsonResponse(data)
