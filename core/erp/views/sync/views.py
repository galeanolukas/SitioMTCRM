from django.shortcuts import render, redirect
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.contrib import messages
import json

from core.erp.services.server_sync_service import ServerSyncService


class SyncToggleView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View to handle sync toggle functionality - superusers only"""
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def handle_no_permission(self):
        return JsonResponse({
            'success': False,
            'error': 'Permission denied'
        }, status=403)
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            sync_enabled = data.get('sync_enabled', True)
            
            # Store in session
            request.session['sync_enabled'] = 'true' if sync_enabled else 'false'
            request.session.save()
            
            # Also update global status for background threads
            try:
                from core.erp.models.sync_status import GlobalSyncStatus
                GlobalSyncStatus.set_sync_status(sync_enabled, request.user.get_full_name() or request.user.username)
            except Exception:
                # If global status fails, continue with session only
                pass
            
            return JsonResponse({
                'success': True,
                'sync_enabled': sync_enabled
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def get(self, request):
        """Get current sync status"""
        sync_enabled = request.session.get('sync_enabled', 'true') != 'false'
        
        return JsonResponse({
            'success': True,
            'sync_enabled': sync_enabled
        })


class SyncStatusView(LoginRequiredMixin, View):
    """Public view to check sync status - available for all authenticated users"""
    
    def get(self, request):
        """Get current sync status without requiring superuser permissions"""
        try:
            from core.erp.models import GlobalSyncStatus
            sync_enabled = GlobalSyncStatus.is_sync_enabled()
            
            return JsonResponse({
                'success': True,
                'sync_enabled': sync_enabled
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'sync_enabled': True  # Default to True on error
            })


class ProductSyncView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View para sincronización manual de productos - solo superusuarios"""
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def handle_no_permission(self):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Permisos insuficientes'
            }, status=403)
        messages.error(self.request, 'No tienes permisos para realizar esta acción')
        return redirect('/')
    
    def post(self, request):
        """Sincronizar productos manualmente"""
        try:
            data = json.loads(request.body)
            company_id = data.get('company_id')
            
            if not company_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Debe especificar una empresa'
                })
            
            # Verificar que estamos en modo servidor
            if not ServerSyncService.is_server_mode():
                return JsonResponse({
                    'success': False,
                    'error': 'Esta función solo está disponible en modo servidor'
                })
            
            # Sincronizar productos
            success, message = ServerSyncService.sync_products_for_company(company_id)
            
            return JsonResponse({
                'success': success,
                'message': message
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def get(self, request):
        """Obtener estado de sincronización o renderizar página HTML"""
        # Si es una solicitud AJAX, devolver JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                if not ServerSyncService.is_server_mode():
                    return JsonResponse({
                        'success': False,
                        'error': 'No estamos en modo servidor',
                        'is_server_mode': False
                    })
                
                # Obtener lista de empresas con productos
                from core.erp.models import Company, Product
                companies = Company.objects.filter(product__isnull=False).distinct()
                
                companies_data = []
                for company in companies:
                    product_count = Product.objects.filter(company=company).count()
                    synced_count = Product.objects.filter(company=company, synced_to_server=True).count()
                    
                    companies_data.append({
                        'id': company.id,
                        'name': company.name,
                        'total_products': product_count,
                        'synced_products': synced_count,
                        'pending_sync': product_count - synced_count
                    })
                
                return JsonResponse({
                    'success': True,
                    'is_server_mode': True,
                    'companies': companies_data
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
        
        # Si no es AJAX, renderizar la página HTML
        return render(request, 'sync/product_sync.html')
