from django.db import models
from django.utils import timezone


class GlobalSyncStatus(models.Model):
    """Model to store global sync status that can be checked by background threads"""
    sync_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, blank=True)
    
    class Meta:
        verbose_name = "Estado de Sincronización Global"
        verbose_name_plural = "Estados de Sincronización Global"
    
    @classmethod
    def is_sync_enabled(cls):
        """Check if sync is globally enabled"""
        try:
            status = cls.objects.first()
            return status.sync_enabled if status else True  # Default to True if no record exists
        except Exception:
            return True  # Default to True on error
    
    @classmethod
    def set_sync_status(cls, enabled, updated_by=None):
        """Set global sync status"""
        status, created = cls.objects.get_or_create(
            pk=1,  # Use a single record
            defaults={'sync_enabled': enabled, 'updated_by': updated_by or 'system'}
        )
        if not created:
            status.sync_enabled = enabled
            status.updated_by = updated_by or 'system'
            status.save()
    
    def __str__(self):
        return f"Sync {'Enabled' if self.sync_enabled else 'Disabled'}"
