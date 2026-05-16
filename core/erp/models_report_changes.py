"""
Modelos para control de cambios en reportes - Sistema de Deshacer
"""
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import json

User = get_user_model()


class ReportChangeLog(models.Model):
    """Registro de cambios en configuraciones de reportes"""
    
    CHANGE_TYPES = [
        ('create', 'Creación'),
        ('update', 'Actualización'),
        ('delete', 'Eliminación'),
        ('restore', 'Restauración'),
    ]
    
    REPORT_TYPES = [
        ('inventory_enhanced', 'Inventario Detallado'),
        ('sales_by_period', 'Ventas por Período'),
        ('product_sales', 'Ventas por Producto'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Usuario')
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES, verbose_name='Tipo de Reporte')
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES, verbose_name='Tipo de Cambio')
    description = models.TextField(verbose_name='Descripción del Cambio')
    
    # Datos anteriores y nuevos en formato JSON
    old_data = models.JSONField(default=dict, blank=True, verbose_name='Datos Anteriores')
    new_data = models.JSONField(default=dict, blank=True, verbose_name='Datos Nuevos')
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha del Cambio')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='Dirección IP')
    user_agent = models.TextField(null=True, blank=True, verbose_name='User Agent')
    
    # Control de reversión
    is_reverted = models.BooleanField(default=False, verbose_name='Está Revertido')
    reverted_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Reversión')
    reverted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                  related_name='reverted_changes', verbose_name='Revertido por')
    
    class Meta:
        verbose_name = 'Log de Cambios de Reporte'
        verbose_name_plural = 'Logs de Cambios de Reportes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['is_reverted']),
        ]
    
    def __str__(self):
        return f"{self.get_change_type_display()} - {self.get_report_type_display()} - {self.created_at}"
    
    def can_revert(self):
        """Verificar si este cambio puede ser revertido"""
        return not self.is_reverted and self.change_type in ['update', 'delete']
    
    def revert(self, user):
        """Revertir este cambio"""
        if not self.can_revert():
            return False, "Este cambio no puede ser revertido"
        
        try:
            # Lógica de reversión según el tipo de reporte
            if self.report_type == 'inventory_enhanced':
                success = self._revert_inventory_enhanced()
            elif self.report_type == 'sales_by_period':
                success = self._revert_sales_by_period()
            elif self.report_type == 'product_sales':
                success = self._revert_product_sales()
            else:
                return False, "Tipo de reporte no soportado"
            
            if success:
                self.is_reverted = True
                self.reverted_at = timezone.now()
                self.reverted_by = user
                self.save()
                
                # Crear log de la reversión
                ReportChangeLog.objects.create(
                    user=user,
                    report_type=self.report_type,
                    change_type='restore',
                    description=f"Revertido: {self.description}",
                    old_data=self.new_data,
                    new_data=self.old_data,
                    ip_address=getattr(user, '_ip_address', None),
                )
                
                return True, "Cambio revertido exitosamente"
            else:
                return False, "Error al revertir el cambio"
                
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def _revert_inventory_enhanced(self):
        """Lógica específica para revertir cambios en inventario"""
        # Implementar lógica específica según los datos guardados
        return True
    
    def _revert_sales_by_period(self):
        """Lógica específica para revertir cambios en ventas por período"""
        # Implementar lógica específica según los datos guardados
        return True
    
    def _revert_product_sales(self):
        """Lógica específica para revertir cambios en ventas por producto"""
        # Implementar lógica específica según los datos guardados
        return True


class ReportConfiguration(models.Model):
    """Configuraciones personalizadas de reportes"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Usuario')
    report_type = models.CharField(max_length=50, choices=ReportChangeLog.REPORT_TYPES, verbose_name='Tipo de Reporte')
    name = models.CharField(max_length=100, verbose_name='Nombre de Configuración')
    configuration = models.JSONField(default=dict, verbose_name='Configuración Guardada')
    
    # Control de versiones
    version = models.PositiveIntegerField(default=1, verbose_name='Versión')
    is_active = models.BooleanField(default=True, verbose_name='Activa')
    is_default = models.BooleanField(default=False, verbose_name='Predeterminada')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de Actualización')
    
    class Meta:
        verbose_name = 'Configuración de Reporte'
        verbose_name_plural = 'Configuraciones de Reportes'
        ordering = ['report_type', 'name']
        unique_together = ['user', 'report_type', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.get_report_type_display()}"
    
    def save(self, *args, **kwargs):
        # Incrementar versión si es una actualización
        if self.pk:
            old_version = ReportConfiguration.objects.get(pk=self.pk).version
            self.version = old_version + 1
        
        super().save(*args, **kwargs)
    
    def create_change_log(self, user, change_type, description, old_data=None, new_data=None):
        """Crear un registro de cambio para esta configuración"""
        ReportChangeLog.objects.create(
            user=user,
            report_type=self.report_type,
            change_type=change_type,
            description=description,
            old_data=old_data or {},
            new_data=new_data or self.configuration,
        )
