from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum, Count, F, ExpressionWrapper, FloatField, Q
from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from django.utils import timezone
from datetime import timedelta
import json

from core.erp.models import Sale, DetSale, Product, Company
from core.user.models import User


class ReportDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'reports/dashboard.html'
    
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.request.user.company
        
        # Filtros por defecto (últimos 30 días)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        # Obtener datos de ventas
        sales_data = self.get_sales_data(start_date, end_date, company)
        
        context.update({
            'sales_data': json.dumps(sales_data),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
        })
        return context
    
    def get_sales_data(self, start_date, end_date, company=None):
        # Filtrar ventas por rango de fechas y compañía si es necesario
        sales = Sale.objects.filter(
            date_joined__date__range=[start_date, end_date],
            **({'company': company} if company and not self.request.user.is_superuser else {})
        )
        
        # Agrupar ventas por día
        daily_sales = sales.annotate(
            date_trunc=TruncDay('date_joined')
        ).values('date_trunc').annotate(
            total=Sum('total')
        ).order_by('date_trunc')
        
        # Preparar datos para el gráfico
        labels = [sale['date_trunc'].strftime('%Y-%m-%d') for sale in daily_sales]
        data = [float(sale['total'] or 0) for sale in daily_sales]
        
        return {
            'labels': labels,
            'datasets': [{
                'label': 'Ventas Diarias',
                'data': data,
                'borderColor': 'rgb(75, 192, 192)',
                'tension': 0.1
            }]
        }


class SalesReportView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'reports/sales_report.html'
    
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff


class ProductsReportView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'reports/products_report.html'
    
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.request.user.company
        
        # Obtener productos más vendidos
        top_products = SaleDetail.objects.filter(
            **({'sale__company': company} if company and not self.request.user.is_superuser else {})
        ).values(
            'product__name'
        ).annotate(
            total_sold=Sum('cant'),
            total_revenue=Sum('subtotal')
        ).order_by('-total_sold')[:10]
        
        context['top_products'] = top_products
        return context


class CashFlowReportView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'reports/cash_flow.html'
    
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff
