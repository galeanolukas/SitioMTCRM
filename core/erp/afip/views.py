"""
Vistas para integración con AFIP SDK
"""
from django.shortcuts import render
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from core.erp.mixins import ValidatePermissionRequiredMixin
from django.http import JsonResponse
from django.urls import reverse_lazy
from core.erp.models import AfipConfig, Company
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
    success_url = reverse_lazy('erp:afip_list')


class AfipConfigUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    """Actualizar configuración AFIP"""
    model = AfipConfig
    template_name = 'afip/form.html'
    permission_required = 'erp.change_afipconfig'
    fields = ['company', 'cuit', 'access_token', 'cert', 'key', 'environment', 'is_active']
    success_url = reverse_lazy('erp:afip_list')


class AfipConfigDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    """Eliminar configuración AFIP"""
    model = AfipConfig
    template_name = 'afip/delete.html'
    permission_required = 'erp.delete_afipconfig'
    success_url = reverse_lazy('erp:afip_list')


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
                            is_active=True
                        )
                        data = {'success': True, 'config_id': config.id, 'message': 'Configuración AFIP creada exitosamente'}
            except Company.DoesNotExist:
                data = {'success': False, 'error': 'Empresa no encontrada'}
            except Exception as e:
                data = {'success': False, 'error': str(e)}
        
        return JsonResponse(data)
