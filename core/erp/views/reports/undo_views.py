"""
Vistas para sistema de deshacer cambios en reportes
"""
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from core.erp.models_report_changes import ReportChangeLog, ReportConfiguration
from core.user.models import User


class UndoChangeView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vista para deshacer cambios en reportes"""
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def post(self, request):
        change_id = request.POST.get('change_id')
        
        if not change_id:
            return JsonResponse({
                'success': False,
                'message': 'ID de cambio no proporcionado'
            })
        
        try:
            change = ReportChangeLog.objects.get(pk=change_id)
            
            if not change.can_revert():
                return JsonResponse({
                    'success': False,
                    'message': 'Este cambio no puede ser revertido'
                })
            
            # Guardar IP del usuario para auditoría
            request.user._ip_address = self.get_client_ip(request)
            
            # Ejecutar reversión
            success, message = change.revert(request.user)
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'reverted_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': message
                })
                
        except ReportChangeLog.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Cambio no encontrado'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    def get_client_ip(self, request):
        """Obtener IP real del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ChangeHistoryView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vista para ver historial de cambios"""
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def get(self, request):
        report_type = request.GET.get('report_type', '')
        limit = int(request.GET.get('limit', 50))
        
        changes = ReportChangeLog.objects.all()
        
        if report_type:
            changes = changes.filter(report_type=report_type)
        
        changes = changes.select_related('user', 'reverted_by').order_by('-created_at')[:limit]
        
        changes_data = []
        for change in changes:
            changes_data.append({
                'id': change.id,
                'report_type': change.report_type,
                'report_type_display': change.get_report_type_display(),
                'change_type': change.change_type,
                'change_type_display': change.get_change_type_display(),
                'description': change.description,
                'user': change.user.get_full_name() or change.user.username,
                'created_at': change.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'is_reverted': change.is_reverted,
                'reverted_at': change.reverted_at.strftime('%Y-%m-%d %H:%M:%S') if change.reverted_at else None,
                'reverted_by': change.reverted_by.get_full_name() if change.reverted_by else None,
                'can_revert': change.can_revert(),
            })
        
        return JsonResponse({
            'success': True,
            'changes': changes_data
        })


class SaveConfigurationView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vista para guardar configuraciones de reportes"""
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def post(self, request):
        report_type = request.POST.get('report_type')
        name = request.POST.get('name', '')
        configuration = request.POST.get('configuration', '{}')
        
        if not report_type or not name:
            return JsonResponse({
                'success': False,
                'message': 'Tipo de reporte y nombre son requeridos'
            })
        
        try:
            import json
            config_data = json.loads(configuration)
            
            # Crear o actualizar configuración
            config, created = ReportConfiguration.objects.update_or_create(
                user=request.user,
                report_type=report_type,
                name=name,
                defaults={'configuration': config_data}
            )
            
            # Crear log del cambio
            action = 'Creación' if created else 'Actualización'
            config.create_change_log(
                user=request.user,
                change_type='update' if not created else 'create',
                description=f"{action} de configuración: {name}",
                new_data=config_data
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Configuración {"guardada" if created else "actualizada"} exitosamente',
                'config_id': config.id,
                'version': config.version
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Formato de configuración inválido'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })


class LoadConfigurationView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vista para cargar configuraciones guardadas"""
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def get(self, request):
        report_type = request.GET.get('report_type', '')
        
        configs = ReportConfiguration.objects.filter(
            user=request.user,
            report_type=report_type,
            is_active=True
        ).order_by('-updated_at')
        
        configs_data = []
        for config in configs:
            configs_data.append({
                'id': config.id,
                'name': config.name,
                'configuration': config.configuration,
                'version': config.version,
                'is_default': config.is_default,
                'updated_at': config.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            })
        
        return JsonResponse({
            'success': True,
            'configurations': configs_data
        })
