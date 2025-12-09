from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, ListView
from django.db.models import Sum, Count, Q, F, FloatField
from django.db.models.functions import Coalesce
from datetime import datetime, timedelta
from calendar import monthrange
import json

from core.erp.models import ProfitReport, Company, Sale, DetSale
from core.erp.mixins import ValidatePermissionRequiredMixin


class ProfitReportView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/profit_report.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Solo superusuarios pueden acceder
        if not request.user.is_superuser:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("No tiene permisos para acceder a reportes de ganancias")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Reporte de Ganancias'
        context['entity'] = 'Reportes'
        
        # Obtener empresas disponibles
        if self.request.user.is_superuser:
            context['companies'] = Company.objects.all()
        else:
            context['companies'] = Company.objects.filter(
                id=self.request.user.company_id
            )
        
        # Fechas por defecto (mes actual)
        today = datetime.now().date()
        first_day = today.replace(day=1)
        context['default_date_from'] = first_day.strftime('%Y-%m-%d')
        context['default_date_to'] = today.strftime('%Y-%m-%d')
        
        return context


@method_decorator(csrf_exempt, name='dispatch')
class GenerateProfitReportView(LoginRequiredMixin, TemplateView):
    
    def dispatch(self, request, *args, **kwargs):
        # Solo superusuarios pueden acceder
        if not request.user.is_superuser:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("No tiene permisos para generar reportes de ganancias")
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST.get('action', '')
            
            if action == 'generate_report':
                date_from = request.POST.get('date_from')
                date_to = request.POST.get('date_to')
                company_id = request.POST.get('company_id')
                report_type = request.POST.get('report_type', 'custom')
                
                # Validar fechas
                if not date_from or not date_to:
                    data['error'] = 'Debe especificar fechas desde y hasta'
                    return JsonResponse(data)
                
                # Convertir fechas
                try:
                    date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                    date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                except ValueError:
                    data['error'] = 'Formato de fechas inválido'
                    return JsonResponse(data)
                
                # Validar rango de fechas
                if date_from > date_to:
                    data['error'] = 'La fecha desde no puede ser mayor que la fecha hasta'
                    return JsonResponse(data)
                
                # Obtener empresa
                if not request.user.is_superuser:
                    company_id = request.user.company_id
                
                company = Company.objects.get(id=company_id)
                
                # Generar reporte
                report_data = self.calculate_profit_report(company, date_from, date_to)
                
                # Guardar reporte en base de datos
                profit_report = ProfitReport.objects.create(
                    company=company,
                    date_from=date_from,
                    date_to=date_to,
                    total_sales=report_data['total_sales'],
                    total_cost=report_data['total_cost'],
                    total_profit=report_data['total_profit'],
                    profit_margin=report_data['profit_margin'],
                    total_products_sold=report_data['total_products_sold']
                )
                
                data = {
                    'id': profit_report.id,
                    'company_name': company.name,
                    'date_from': date_from.strftime('%d/%m/%Y'),
                    'date_to': date_to.strftime('%d/%m/%Y'),
                    'period_type': profit_report.period_type,
                    'total_sales': f"{report_data['total_sales']:.2f}",
                    'total_cost': f"{report_data['total_cost']:.2f}",
                    'total_profit': f"{report_data['total_profit']:.2f}",
                    'profit_margin': f"{report_data['profit_margin']:.2f}",
                    'total_products_sold': report_data['total_products_sold'],
                    'top_products': report_data['top_products'],
                    'daily_breakdown': report_data['daily_breakdown']
                }
                
            elif action == 'get_monthly_data':
                year = request.POST.get('year', datetime.now().year)
                company_id = request.POST.get('company_id')
                
                if not request.user.is_superuser:
                    company_id = request.user.company_id
                
                company = Company.objects.get(id=company_id)
                monthly_data = self.get_monthly_profit_data(company, int(year))
                
                data = {
                    'monthly_data': monthly_data,
                    'year': year
                }
                
            else:
                data['error'] = 'Acción no válida'
                
        except Exception as e:
            data['error'] = str(e)
            
        return JsonResponse(data)
    
    def calculate_profit_report(self, company, date_from, date_to):
        """Calcular datos completos del reporte de ganancias"""
        
        # Obtener ventas del período
        sales = Sale.objects.filter(
            company=company,
            date_joined__date__range=[date_from, date_to]
        )
        
        # Calcular totales generales
        totals = sales.aggregate(
            total_sales=Coalesce(Sum('total'), 0),
            total_iva=Coalesce(Sum('iva'), 0),
            total_subtotal=Coalesce(Sum('subtotal'), 0)
        )
        
        total_sales = float(totals['total_sales'] or 0)
        
        # Calcular costo total y productos vendidos
        total_cost = 0
        total_products = 0
        product_sales = {}
        
        for sale in sales:
            for detail in sale.detsale_set.all():
                product_name = detail.prod.name
                quantity = detail.cant
                unit_price = float(detail.pvp)
                
                # Acumular estadísticas por producto
                if product_name not in product_sales:
                    product_sales[product_name] = {
                        'quantity': 0,
                        'revenue': 0,
                        'cost': 0,
                        'profit': 0,
                        'unit_cost': float(detail.prod.cost_price or 0)
                    }
                
                product_sales[product_name]['quantity'] += quantity
                product_sales[product_name]['revenue'] += unit_price * quantity
                
                if detail.prod.cost_price:
                    product_cost = float(detail.prod.cost_price) * quantity
                    product_sales[product_name]['cost'] += product_cost
                    total_cost += product_cost
                
                total_products += quantity
        
        # Calcular ganancias por producto
        for product in product_sales.values():
            product['profit'] = product['revenue'] - product['cost']
        
        # Calcular totales finales
        total_profit = total_sales - total_cost
        profit_margin = (total_profit / total_cost * 100) if total_cost > 0 else 0
        
        # Top productos por ganancia
        top_products = sorted(
            product_sales.items(),
            key=lambda x: x[1]['profit'],
            reverse=True
        )[:10]
        
        # Desglose diario
        daily_breakdown = {}
        current_date = date_from
        while current_date <= date_to:
            day_sales = sales.filter(date_joined__date=current_date)
            day_total = float(day_sales.aggregate(
                total=Coalesce(Sum('total'), 0)
            )['total'] or 0)
            
            # Calcular costo del día
            day_cost = 0
            for sale in day_sales:
                for detail in sale.detsale_set.all():
                    if detail.prod.cost_price:
                        day_cost += float(detail.prod.cost_price) * detail.cant
            
            daily_breakdown[current_date.strftime('%Y-%m-%d')] = {
                'sales': day_total,
                'cost': day_cost,
                'profit': day_total - day_cost
            }
            
            current_date += timedelta(days=1)
        
        return {
            'total_sales': total_sales,
            'total_cost': total_cost,
            'total_profit': total_profit,
            'profit_margin': profit_margin,
            'total_products_sold': total_products,
            'top_products': [
                {
                    'name': name,
                    'quantity': data['quantity'],
                    'revenue': data['revenue'],
                    'cost': data['cost'],
                    'profit': data['profit'],
                    'margin': (data['profit'] / data['cost'] * 100) if data['cost'] > 0 else 0
                }
                for name, data in top_products
            ],
            'daily_breakdown': daily_breakdown
        }
    
    def get_monthly_profit_data(self, company, year):
        """Obtener datos mensuales de ganancias para un año"""
        monthly_data = []
        
        for month in range(1, 13):
            # Primer y último día del mes
            first_day = datetime(year, month, 1).date()
            last_day = datetime(year, month, monthrange(year, month)[1]).date()
            
            # Obtener ventas del mes
            sales = Sale.objects.filter(
                company=company,
                date_joined__date__range=[first_day, last_day]
            )
            
            # Calcular totales
            totals = sales.aggregate(
                total_sales=Coalesce(Sum('total'), 0)
            )
            
            total_sales = float(totals['total_sales'] or 0)
            
            # Calcular costo del mes
            total_cost = 0
            for sale in sales:
                for detail in sale.detsale_set.all():
                    if detail.prod.cost_price:
                        total_cost += float(detail.prod.cost_price) * detail.cant
            
            total_profit = total_sales - total_cost
            profit_margin = (total_profit / total_cost * 100) if total_cost > 0 else 0
            
            monthly_data.append({
                'month': month,
                'month_name': datetime(year, month, 1).strftime('%B'),
                'total_sales': total_sales,
                'total_cost': total_cost,
                'total_profit': total_profit,
                'profit_margin': profit_margin
            })
        
        return monthly_data


class ProfitReportListView(LoginRequiredMixin, ListView):
    model = ProfitReport
    template_name = 'reports/profit_report_list.html'
    context_object_name = 'reports'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        # Solo superusuarios pueden acceder
        if not request.user.is_superuser:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("No tiene permisos para ver reportes de ganancias")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros opcionales (solo para superusuarios)
        company_id = self.request.GET.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(date_from__gte=date_from)
            except ValueError:
                pass
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(date_to__lte=date_to)
            except ValueError:
                pass
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Empresas para filtro (solo superusuarios)
        context['companies'] = Company.objects.all()
        
        # Mantener filtros en el contexto
        context['filters'] = {
            'company': self.request.GET.get('company', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', '')
        }
        
        return context
