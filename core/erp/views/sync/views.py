from django.shortcuts import render
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
import json


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
