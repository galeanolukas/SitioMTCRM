from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum, Count, F, ExpressionWrapper, FloatField, Q
from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from django.utils import timezone
from django.http import HttpResponse
from datetime import timedelta, datetime
import json
import csv
import openpyxl
from openpyxl.styles import Font, Alignment
from io import BytesIO

from core.erp.models import Sale, DetSale, Product, Company, Expense
from core.user.models import User


class UnifiedReportsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'reports/unified_reports.html'
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener parámetros de filtro
        report_type = self.request.GET.get('report_type', 'sales')
        company_id = self.request.GET.get('company', '')
        start_date = self.request.GET.get('start_date', '')
        end_date = self.request.GET.get('end_date', '')
        payment_method = self.request.GET.get('payment_method', '')
        
        # Empresas para el dropdown
        companies = Company.objects.all()
        context['companies'] = companies
        
        # Fechas por defecto (últimos 30 días)
        if not start_date or not end_date:
            end_date_obj = timezone.now()
            start_date_obj = end_date_obj - timedelta(days=30)
            start_date = start_date_obj.strftime('%Y-%m-%d')
            end_date = end_date_obj.strftime('%Y-%m-%d')
        
        context.update({
            'report_type': report_type,
            'company_id': company_id,
            'start_date': start_date,
            'end_date': end_date,
            'payment_method': payment_method,
        })
        
        # Obtener datos según el tipo de reporte
        if report_type == 'sales':
            context['sales_data'] = self.get_sales_data(company_id, start_date, end_date, payment_method)
        elif report_type == 'inventory':
            context['inventory_data'] = self.get_inventory_data(company_id)
        elif report_type == 'expenses':
            context['expenses_data'] = self.get_expenses_data(company_id, start_date, end_date)
        elif report_type == 'profit':
            context['profit_data'] = self.get_profit_data(company_id, start_date, end_date)
        
        return context
    
    def get_sales_data(self, company_id, start_date, end_date, payment_method):
        from core.erp.choices import payment_method_choices
        
        # Filtros base
        filters = {
            'date_joined__date__range': [start_date, end_date],
        }
        
        if company_id:
            filters['company_id'] = company_id
        
        if payment_method:
            filters['payment_method'] = payment_method
        
        sales = Sale.objects.filter(**filters).select_related('cli', 'company')
        
        # Resumen
        summary = sales.aggregate(
            total_sales=Sum('total'),
            total_count=Count('id'),
            avg_ticket=Sum('total') / Count('id')
        )
        
        # Por forma de pago
        payment_breakdown = sales.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('total')
        ).order_by('-total')
        
        # Ventas diarias
        daily_sales = sales.annotate(
            date=TruncDay('date_joined')
        ).values('date').annotate(
            total=Sum('total'),
            count=Count('id')
        ).order_by('date')
        
        return {
            'sales': sales,
            'summary': summary,
            'payment_breakdown': payment_breakdown,
            'daily_sales': daily_sales,
            'payment_method_choices': dict(payment_method_choices),
        }
    
    def get_inventory_data(self, company_id):
        filters = {}
        if company_id:
            filters['company_id'] = company_id
        
        products = Product.objects.filter(**filters).select_related('cat', 'supplier')
        
        # Resumen
        summary = products.aggregate(
            total_products=Count('id'),
            total_stock=Sum('stock'),
            total_value=Sum(F('stock') * F('pvp_final'))
        )
        
        return {
            'products': products,
            'summary': summary,
        }
    
    def get_expenses_data(self, company_id, start_date, end_date):
        filters = {
            'date__range': [start_date, end_date],
        }
        
        if company_id:
            filters['company_id'] = company_id
        
        expenses = Expense.objects.filter(**filters).select_related('supplier', 'company')
        
        # Resumen
        summary = expenses.aggregate(
            total_expenses=Sum('amount'),
            total_count=Count('id'),
            avg_expense=Sum('amount') / Count('id')
        )
        
        # Por proveedor
        supplier_breakdown = expenses.values('supplier__name').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('-total')
        
        # Gastos diarios
        daily_expenses = expenses.annotate(
            expense_date=TruncDay('date')
        ).values('expense_date').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('expense_date')
        
        return {
            'expenses': expenses,
            'summary': summary,
            'supplier_breakdown': supplier_breakdown,
            'daily_expenses': daily_expenses,
        }
    
    def get_profit_data(self, company_id, start_date, end_date):
        # Calcular ganancias basadas en ventas vs costos
        filters = {
            'date_joined__date__range': [start_date, end_date],
        }
        
        if company_id:
            filters['company_id'] = company_id
        
        # Ventas
        sales = Sale.objects.filter(**filters)
        total_sales = sales.aggregate(total=Sum('total'))['total'] or 0
        
        # Costos de productos vendidos
        sales_details = DetSale.objects.filter(sale__in=sales)
        total_cost = sales_details.aggregate(
            total=Sum(F('cant') * F('prod__cost_price'))
        )['total'] or 0
        
        # Gastos
        expenses = Expense.objects.filter(
            date__range=[start_date, end_date],
            **({'company_id': company_id} if company_id else {})
        )
        total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
        
        # Ganancias
        gross_profit = total_sales - total_cost
        net_profit = gross_profit - total_expenses
        
        return {
            'total_sales': total_sales,
            'total_cost': total_cost,
            'total_expenses': total_expenses,
            'gross_profit': gross_profit,
            'net_profit': net_profit,
            'profit_margin': (net_profit / total_sales * 100) if total_sales > 0 else 0,
        }


class ExportReportView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        # Allow superusers and users with view permissions
        return self.request.user.is_superuser or (
            hasattr(self.request.user, 'has_perm') and 
            (self.request.user.has_perm('erp.view_sale') or 
             self.request.user.has_perm('erp.view_product') or
             self.request.user.has_perm('erp.view_expense'))
        )
    
    def get(self, request):
        report_type = request.GET.get('report_type', 'sales')
        company_id = request.GET.get('company', '')
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        payment_method = request.GET.get('payment_method', '')
        export_format = request.GET.get('format', 'csv')
        
        try:
            # Obtener datos según el tipo de reporte
            if report_type == 'sales':
                data = self.get_sales_export_data(company_id, start_date, end_date, payment_method)
                filename = f'ventas_{start_date}_al_{end_date}'
            elif report_type == 'inventory':
                data = self.get_inventory_export_data(company_id)
                filename = f'inventario_{datetime.now().strftime("%Y-%m-%d")}'
            elif report_type == 'expenses':
                data = self.get_expenses_export_data(company_id, start_date, end_date)
                filename = f'gastos_{start_date}_al_{end_date}'
            elif report_type == 'profit':
                data = self.get_profit_export_data(company_id, start_date, end_date)
                filename = f'ganancias_{start_date}_al_{end_date}'
            
            # Exportar según formato
            if export_format == 'excel':
                return self.export_to_excel(data, filename, report_type)
            else:
                return self.export_to_csv(data, filename, report_type)
        except Exception as e:
            # Return error as plain text for debugging
            return HttpResponse(f"Error en exportación: {str(e)}", content_type='text/plain')
    
    def get_sales_export_data(self, company_id, start_date, end_date, payment_method):
        filters = {
            'date_joined__date__range': [start_date, end_date],
        }
        
        if company_id:
            filters['company_id'] = company_id
        
        if payment_method:
            filters['payment_method'] = payment_method
        
        return Sale.objects.filter(**filters).select_related('cli', 'company')
    
    def get_inventory_export_data(self, company_id):
        filters = {}
        if company_id:
            filters['company_id'] = company_id
        
        return Product.objects.filter(**filters).select_related('cat', 'supplier')
    
    def get_expenses_export_data(self, company_id, start_date, end_date):
        filters = {
            'date__range': [start_date, end_date],
        }
        
        if company_id:
            filters['company_id'] = company_id
        
        return Expense.objects.filter(**filters).select_related('supplier', 'company')
    
    def get_profit_export_data(self, company_id, start_date, end_date):
        # Similar a get_profit_data pero para exportación
        unified_view = UnifiedReportsView()
        return unified_view.get_profit_data(company_id, start_date, end_date)
    
    def export_to_csv(self, data, filename, report_type):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        
        writer = csv.writer(response)
        
        if report_type == 'sales':
            # Título del reporte
            writer.writerow(['REPORTE DE VENTAS'])
            writer.writerow([])  # Fila vacía
            writer.writerow(['Fecha', 'Ticket/Factura', 'Cliente', 'Subtotal', 'IVA', 'Total', 'Forma de Pago', 'Empresa'])
            total_amount = 0
            total_iva = 0
            for sale in data:
                ticket_factura = ''
                if sale.invoice_number:
                    ticket_factura = f"{sale.invoice_pos}-{sale.invoice_number}"
                else:
                    ticket_factura = f"Ticket #{sale.id}"
                    
                writer.writerow([
                    sale.date_joined.strftime('%Y-%m-%d %H:%M'),
                    ticket_factura,
                    sale.cli.names if sale.cli else 'N/A',
                    float(sale.subtotal),
                    float(sale.iva),
                    float(sale.total),
                    sale.get_payment_method_display(),
                    sale.company.name if sale.company else 'N/A'
                ])
                total_amount += float(sale.total)
                total_iva += float(sale.iva)
            
            # Resumen final
            writer.writerow([])  # Fila vacía
            writer.writerow(['RESUMEN'])
            writer.writerow(['Total Ventas', total_amount])
            writer.writerow(['Total IVA', total_iva])
            writer.writerow(['Cantidad de Ventas', len(data)])
            writer.writerow(['Promedio por Venta', total_amount / len(data) if data else 0])
            
            # Totales por forma de pago
            writer.writerow([])  # Fila vacía
            writer.writerow(['VENTAS POR FORMA DE PAGO'])
            
            # Calcular totales por forma de pago
            from django.db.models import Sum
            payment_totals = data.values('payment_method').annotate(
                total=Sum('total'),
                count=Count('id')
            ).order_by('-total')
            
            for payment in payment_totals:
                payment_name = dict(payment_method_choices).get(payment['payment_method'], payment['payment_method'])
                writer.writerow([payment_name, f"{payment['total']:.2f}", f"({payment['count']} ventas)"])  
        
        elif report_type == 'inventory':
            # Título del reporte
            writer.writerow(['REPORTE DE INVENTARIO'])
            writer.writerow([])  # Fila vacía
            writer.writerow(['Producto', 'Código', 'Categoría', 'Stock', 'Costo', 'Precio Final', 'Valor Total'])
            total_stock = 0
            total_value = 0
            for product in data:
                product_value = float(product.stock * product.pvp_final)
                writer.writerow([
                    product.name,
                    product.code or '',
                    product.cat.name if product.cat else '',
                    product.stock,
                    product.cost_price,
                    product.pvp_final,
                    product_value
                ])
                total_stock += float(product.stock)
                total_value += product_value
            
            # Resumen final
            writer.writerow([])  # Fila vacía
            writer.writerow(['RESUMEN'])
            writer.writerow(['Total Productos', len(data)])
            writer.writerow(['Stock Total', total_stock])
            writer.writerow(['Valor Total del Inventario', total_value])
        
        elif report_type == 'expenses':
            # Título del reporte
            writer.writerow(['REPORTE DE GASTOS'])
            writer.writerow([])  # Fila vacía
            writer.writerow(['Fecha', 'Descripción', 'Monto', 'Proveedor', 'Empresa'])
            total_amount = 0
            for expense in data:
                writer.writerow([
                    expense.date,
                    expense.description or '',
                    expense.amount,
                    expense.supplier.name if expense.supplier else 'N/A',
                    expense.company.name if expense.company else 'N/A'
                ])
                total_amount += float(expense.amount)
            
            # Resumen final
            writer.writerow([])  # Fila vacía
            writer.writerow(['RESUMEN'])
            writer.writerow(['Total Gastos', total_amount])
            writer.writerow(['Cantidad de Gastos', len(data)])
            writer.writerow(['Promedio por Gasto', total_amount / len(data) if data else 0])
        
        elif report_type == 'profit':
            # Título del reporte
            writer.writerow(['REPORTE DE GANANCIAS'])
            writer.writerow([])  # Fila vacía
            writer.writerow(['Concepto', 'Monto'])
            writer.writerow(['Ventas Totales', data['total_sales']])
            writer.writerow(['Costo de Ventas', data['total_cost']])
            writer.writerow(['Gastos', data['total_expenses']])
            writer.writerow(['Ganancia Bruta', data['gross_profit']])
            writer.writerow(['Ganancia Neta', data['net_profit']])
            writer.writerow(['Margen de Ganancia %', f"{data['profit_margin']:.2f}%"])
        
        return response
    
    def export_to_excel(self, data, filename, report_type):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Reporte'
        
        # Estilos
        title_font = Font(bold=True, size=14)
        title_alignment = Alignment(horizontal='center')
        header_font = Font(bold=True)
        header_alignment = Alignment(horizontal='center')
        summary_font = Font(bold=True)
        
        row = 1
        
        if report_type == 'sales':
            # Título del reporte
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
            ws.cell(row=row, column=1, value='REPORTE DE VENTAS')
            ws.cell(row=row, column=1).font = title_font
            ws.cell(row=row, column=1).alignment = title_alignment
            row += 2
            
            headers = ['Fecha', 'Ticket/Factura', 'Cliente', 'Subtotal', 'IVA', 'Total', 'Forma de Pago', 'Empresa']
            ws.append(headers)
            
            for cell in ws[row]:
                cell.font = header_font
                cell.alignment = header_alignment
            
            total_amount = 0
            total_iva = 0
            for sale in data:
                row += 1
                ticket_factura = ''
                if sale.invoice_number:
                    ticket_factura = f"{sale.invoice_pos}-{sale.invoice_number}"
                else:
                    ticket_factura = f"Ticket #{sale.id}"
                    
                ws.append([
                    sale.date_joined.strftime('%Y-%m-%d %H:%M'),
                    ticket_factura,
                    sale.cli.names if sale.cli else 'N/A',
                    float(sale.subtotal),
                    float(sale.iva),
                    float(sale.total),
                    sale.get_payment_method_display(),
                    sale.company.name if sale.company else 'N/A'
                ])
                total_amount += float(sale.total)
                total_iva += float(sale.iva)
            
            # Resumen final
            row += 2
            ws.append(['RESUMEN'])
            ws.cell(row=row, column=1).font = summary_font
            row += 1
            ws.append(['Total Ventas', total_amount])
            row += 1
            ws.append(['Total IVA', total_iva])
            row += 1
            ws.append(['Cantidad de Ventas', len(data)])
            row += 1
            ws.append(['Promedio por Venta', total_amount / len(data) if data else 0])
            
            # Totales por forma de pago
            row += 2
            ws.append(['VENTAS POR FORMA DE PAGO'])
            ws.cell(row=row, column=1).font = summary_font
            row += 1
            
            # Calcular totales por forma de pago
            from django.db.models import Sum
            payment_totals = data.values('payment_method').annotate(
                total=Sum('total'),
                count=Count('id')
            ).order_by('-total')
            
            for payment in payment_totals:
                from core.erp.choices import payment_method_choices
                payment_name = dict(payment_method_choices).get(payment['payment_method'], payment['payment_method'])
                ws.append([payment_name, float(payment['total']), f"({payment['count']} ventas)"])
                row += 1
        
        elif report_type == 'inventory':
            # Título del reporte
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
            ws.cell(row=row, column=1, value='REPORTE DE INVENTARIO')
            ws.cell(row=row, column=1).font = title_font
            ws.cell(row=row, column=1).alignment = title_alignment
            row += 2
            
            headers = ['Producto', 'Código', 'Categoría', 'Stock', 'Costo', 'Precio Final', 'Valor Total']
            ws.append(headers)
            
            for cell in ws[row]:
                cell.font = header_font
                cell.alignment = header_alignment
            
            total_stock = 0
            total_value = 0
            for product in data:
                row += 1
                product_value = float(product.stock * product.pvp_final)
                ws.append([
                    product.name,
                    product.code or '',
                    product.cat.name if product.cat else '',
                    float(product.stock),
                    float(product.cost_price),
                    float(product.pvp_final),
                    product_value
                ])
                total_stock += float(product.stock)
                total_value += product_value
            
            # Resumen final
            row += 2
            ws.append(['RESUMEN'])
            ws.cell(row=row, column=1).font = summary_font
            row += 1
            ws.append(['Total Productos', len(data)])
            row += 1
            ws.append(['Stock Total', total_stock])
            row += 1
            ws.append(['Valor Total del Inventario', total_value])
        
        elif report_type == 'expenses':
            # Título del reporte
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
            ws.cell(row=row, column=1, value='REPORTE DE GASTOS')
            ws.cell(row=row, column=1).font = title_font
            ws.cell(row=row, column=1).alignment = title_alignment
            row += 2
            
            headers = ['Fecha', 'Descripción', 'Monto', 'Proveedor', 'Empresa']
            ws.append(headers)
            
            for cell in ws[row]:
                cell.font = header_font
                cell.alignment = header_alignment
            
            total_amount = 0
            for expense in data:
                row += 1
                ws.append([
                    expense.date.strftime('%Y-%m-%d'),
                    expense.description or '',
                    float(expense.amount),
                    expense.supplier.name if expense.supplier else 'N/A',
                    expense.company.name if expense.company else 'N/A'
                ])
                total_amount += float(expense.amount)
            
            # Resumen final
            row += 2
            ws.append(['RESUMEN'])
            ws.cell(row=row, column=1).font = summary_font
            row += 1
            ws.append(['Total Gastos', total_amount])
            row += 1
            ws.append(['Cantidad de Gastos', len(data)])
            row += 1
            ws.append(['Promedio por Gasto', total_amount / len(data) if data else 0])
        
        elif report_type == 'profit':
            # Título del reporte
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
            ws.cell(row=row, column=1, value='REPORTE DE GANANCIAS')
            ws.cell(row=row, column=1).font = title_font
            ws.cell(row=row, column=1).alignment = title_alignment
            row += 2
            
            headers = ['Concepto', 'Monto']
            ws.append(headers)
            
            for cell in ws[row]:
                cell.font = header_font
                cell.alignment = header_alignment
            
            profit_data = [
                ['Ventas Totales', float(data['total_sales'])],
                ['Costo de Ventas', float(data['total_cost'])],
                ['Gastos', float(data['total_expenses'])],
                ['Ganancia Bruta', float(data['gross_profit'])],
                ['Ganancia Neta', float(data['net_profit'])],
                ['Margen de Ganancia %', f"{data['profit_margin']:.2f}%"]
            ]
            
            for item in profit_data:
                row += 1
                ws.append(item)
        
        # Ajustar ancho de columnas
        for column in ws.columns:
            max_length = 0
            # Obtener la primera celda no fusionada para obtener el column_letter
            column_letter = None
            for cell in column:
                if not isinstance(cell, openpyxl.cell.cell.MergedCell):
                    column_letter = cell.column_letter
                    break
            
            if column_letter:
                for cell in column:
                    try:
                        if not isinstance(cell, openpyxl.cell.cell.MergedCell) and len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
        
        # Guardar en BytesIO
        excel_file = BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)
        
        response.write(excel_file.read())
        return response