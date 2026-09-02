"""
Vista para registro de actividades de usuarios
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, TemplateView
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta
from ..models import ActivityLog


class ActivityLogView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vista para ver registro de actividades (solo superusuarios)"""
    model = ActivityLog
    template_name = 'erp/activity_log.html'
    context_object_name = 'activities'
    paginate_by = 50
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', '')
        
        if action == 'delete_all':
            count = ActivityLog.objects.all().count()
            ActivityLog.objects.all().delete()
            return JsonResponse({'success': True, 'deleted': count})
        
        elif action == 'delete_filtered':
            qs = self.get_queryset()
            count = qs.count()
            qs.delete()
            return JsonResponse({'success': True, 'deleted': count})
        
        elif action == 'delete_one':
            log_id = request.POST.get('id')
            if log_id:
                ActivityLog.objects.filter(id=log_id).delete()
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': 'ID no proporcionado'}, status=400)
        
        return JsonResponse({'error': 'Acción no válida'}, status=400)
    
    def get_queryset(self):
        queryset = ActivityLog.objects.all().select_related('user', 'company')
        
        # Filtros
        user_filter = self.request.GET.get('user')
        action_filter = self.request.GET.get('action')
        date_filter = self.request.GET.get('date')
        company_filter = self.request.GET.get('company')
        
        if user_filter:
            queryset = queryset.filter(user_id=user_filter)
        
        if action_filter:
            queryset = queryset.filter(action=action_filter)
            
        if date_filter:
            if date_filter == 'today':
                queryset = queryset.filter(timestamp__date=timezone.now().date())
            elif date_filter == 'week':
                queryset = queryset.filter(timestamp__gte=timezone.now() - timedelta(days=7))
            elif date_filter == 'month':
                queryset = queryset.filter(timestamp__gte=timezone.now() - timedelta(days=30))
        
        if company_filter:
            queryset = queryset.filter(company_id=company_filter)
            
        return queryset.order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estadísticas
        context['total_activities'] = ActivityLog.objects.count()
        context['today_activities'] = ActivityLog.objects.filter(
            timestamp__date=timezone.now().date()
        ).count()
        
        # Actividades más comunes
        context['common_actions'] = ActivityLog.objects.values('action').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Usuarios más activos
        context['active_users'] = ActivityLog.objects.values(
            'user__username'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Opciones de filtro
        context['action_choices'] = ActivityLog.objects.exclude(action='VIEW').values_list('action', flat=True).distinct()
        context['users'] = (
            ActivityLog.objects
            .filter(user__isnull=False)
            .values_list('user__id', 'user__username')
            .distinct()
            .order_by('user__username')
        )
        
        return context


class ActivityLogDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Dashboard de estadísticas de actividades (solo superusuarios)"""
    template_name = 'erp/activity_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        now = timezone.now()
        
        # Estadísticas generales
        context['total_activities'] = ActivityLog.objects.count()
        context['today_activities'] = ActivityLog.objects.filter(
            timestamp__date=now.date()
        ).count()
        context['week_activities'] = ActivityLog.objects.filter(
            timestamp__gte=now - timedelta(days=7)
        ).count()
        context['month_activities'] = ActivityLog.objects.filter(
            timestamp__gte=now - timedelta(days=30)
        ).count()
        
        # Actividades por día (últimos 7 días)
        daily_stats = []
        for i in range(7):
            date = now - timedelta(days=i)
            count = ActivityLog.objects.filter(timestamp__date=date.date()).count()
            daily_stats.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': count
            })
        context['daily_stats'] = list(reversed(daily_stats))
        
        # Top acciones
        context['top_actions'] = ActivityLog.objects.values('action').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Top usuarios
        context['top_users'] = ActivityLog.objects.values(
            'user__username'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        return context
