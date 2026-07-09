"""
Vistas para integración con AFIP SDK
"""
from django.shortcuts import render
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from core.erp.mixins import ValidatePermissionRequiredMixin, CompanyInitialMixin
from django.http import JsonResponse
from django.urls import reverse_lazy
from core.erp.models import AfipConfig, Company, Sale, DetSale, AfipPuntoVenta
from .client import AfipClient
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, permission_required


def crear_punto_venta_por_defecto(company):
    """Crea un punto de venta 1 para la empresa si no tiene ninguno activo."""
    if company and not company.afippuntoventa_set.filter(is_active=True).exists():
        AfipPuntoVenta.objects.create(
            company=company,
            numero=1,
            descripcion='Punto de venta principal',
            is_active=True
        )


class AfipConfigListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    """Lista de configuraciones AFIP"""
    model = AfipConfig
    template_name = 'afip/list.html'
    permission_required = 'erp.view_afipconfig'
    
    def get_queryset(self):
        return AfipConfig.objects.select_related('company').all()


class AfipConfigCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CompanyInitialMixin, CreateView):
    """Crear configuración AFIP"""
    model = AfipConfig
    template_name = 'afip/form.html'
    permission_required = 'erp.add_afipconfig'
    fields = ['company', 'cuit', 'access_token', 'clave_fiscal_username', 'clave_fiscal_password', 'cert', 'key', 'environment', 'tipo_comprobante', 'concepto', 'moneda', 'cotizacion', 'usar_contingencia', 'is_active']
    success_url = reverse_lazy('erp:afip:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasar datos de empresas para autocompletar CUIT
        context['companies_data'] = list(Company.objects.filter(is_active=True).values('id', 'cuit'))
        return context
    
    def form_valid(self, form):
        # Si es una petición AJAX, devolver JSON
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            self.object = form.save()
            crear_punto_venta_por_defecto(self.object.company)
            data = {'success': True, 'message': 'Configuración AFIP creada exitosamente'}
            return JsonResponse(data)
        self.object = form.save()
        crear_punto_venta_por_defecto(self.object.company)
        return super().form_valid(form)
    
    def form_invalid(self, form):
        # Si es una petición AJAX, devolver JSON con errores
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            data = {'success': False, 'error': 'Error al crear configuración', 'errors': dict(form.errors)}
            return JsonResponse(data, status=400)
        return super().form_invalid(form)


class AfipConfigUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    """Actualizar configuración AFIP"""
    model = AfipConfig
    template_name = 'afip/form.html'
    permission_required = 'erp.change_afipconfig'
    fields = ['company', 'cuit', 'access_token', 'clave_fiscal_username', 'clave_fiscal_password', 'cert', 'key', 'environment', 'tipo_comprobante', 'concepto', 'moneda', 'cotizacion', 'usar_contingencia', 'is_active']
    success_url = reverse_lazy('erp:afip:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasar datos de empresas para autocompletar CUIT
        context['companies_data'] = list(Company.objects.filter(is_active=True).values('id', 'cuit'))
        return context
    
    def form_valid(self, form):
        # Si es una petición AJAX, devolver JSON
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            self.object = form.save()
            data = {'success': True, 'message': 'Configuración AFIP actualizada exitosamente'}
            return JsonResponse(data)
        return super().form_valid(form)
    
    def form_invalid(self, form):
        # Si es una petición AJAX, devolver JSON con errores
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            data = {'success': False, 'error': 'Error al actualizar configuración', 'errors': dict(form.errors)}
            return JsonResponse(data, status=400)
        return super().form_invalid(form)


class AfipConfigDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    """Eliminar configuración AFIP"""
    model = AfipConfig
    template_name = 'afip/delete.html'
    permission_required = 'erp.delete_afipconfig'
    success_url = reverse_lazy('erp:afip:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Eliminar Configuración AFIP'
        context['action'] = 'delete'
        context['list_url'] = reverse_lazy('erp:afip:list')
        return context


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
                taxpayer = client.get_taxpayer_info(cuit, user=request.user)

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
                    tipo_comprobante = request.POST.get('tipo_comprobante', 6)
                    
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
                            tipo_comprobante=tipo_comprobante,
                            is_active=True
                        )
                        crear_punto_venta_por_defecto(company)
                        data = {'success': True, 'config_id': config.id, 'message': 'Configuración AFIP creada exitosamente'}
            except Company.DoesNotExist:
                data = {'success': False, 'error': 'Empresa no encontrada'}
            except Exception as e:
                data = {'success': False, 'error': str(e)}
        
        elif action == 'generate_certificate':
            config_id = request.POST.get('config_id')
            cert_type = request.POST.get('cert_type', 'dev')  # 'dev' o 'prod'
            username = request.POST.get('username')
            password = request.POST.get('password')
            alias = request.POST.get('alias', 'afipsdk')

            try:
                config = AfipConfig.objects.get(id=config_id)

                if not config.cuit:
                    data = {'success': False, 'error': 'La configuración no tiene CUIT'}
                else:
                    # Usar credenciales guardadas si están disponibles, si no usar las del POST
                    if config.clave_fiscal_username and config.clave_fiscal_password:
                        username = config.clave_fiscal_username
                        password = config.clave_fiscal_password
                    elif not username or not password:
                        data = {'success': False, 'error': 'Faltan credenciales de Clave Fiscal (configurar en el formulario o ingresar manualmente)'}
                        return JsonResponse(data)

                    # Crear cliente AFIP
                    client = AfipClient(company_id=config.company_id if config.company else None)

                    # Generar certificado según tipo
                    if cert_type == 'prod':
                        result = client.create_prod_certificate(
                            cuit=config.cuit,
                            username=username,
                            password=password,
                            alias=alias,
                            user=request.user
                        )
                    else:
                        result = client.create_dev_certificate(
                            cuit=config.cuit,
                            username=username,
                            password=password,
                            alias=alias,
                            user=request.user
                        )

                    if 'error' in result:
                        data = {'success': False, 'error': result['error']}
                    else:
                        # Guardar cert y key en la configuración
                        config.cert = result['cert']
                        config.key = result['key']
                        config.save(update_fields=['cert', 'key'])

                        data = {
                            'success': True,
                            'message': f'Certificado de {cert_type.upper()} generado exitosamente',
                            'automation_id': result.get('automation_id')
                        }
            except AfipConfig.DoesNotExist:
                data = {'success': False, 'error': 'Configuración no encontrada'}
            except Exception as e:
                data = {'success': False, 'error': str(e)}

        elif action == 'auth_web_service':
            config_id = request.POST.get('config_id')
            service = request.POST.get('service', 'wsfe')
            username = request.POST.get('username')
            password = request.POST.get('password')
            alias = request.POST.get('alias', 'afipsdk')

            try:
                config = AfipConfig.objects.get(id=config_id)

                if not config.cuit:
                    data = {'success': False, 'error': 'La configuración no tiene CUIT'}
                else:
                    # Usar credenciales guardadas si están disponibles, si no usar las del POST
                    if config.clave_fiscal_username and config.clave_fiscal_password:
                        username = config.clave_fiscal_username
                        password = config.clave_fiscal_password
                    elif not username or not password:
                        data = {'success': False, 'error': 'Faltan credenciales de Clave Fiscal (configurar en el formulario o ingresar manualmente)'}
                        return JsonResponse(data)

                    # Crear cliente AFIP
                    client = AfipClient(company_id=config.company_id if config.company else None)

                    # Autorizar Web Service
                    result = client.auth_web_service(
                        cuit=config.cuit,
                        username=username,
                        password=password,
                        alias=alias,
                        service=service,
                        user=request.user
                    )

                    if 'error' in result:
                        data = {'success': False, 'error': result['error']}
                    else:
                        # Guardar estado de autorización en la configuración
                        from django.utils import timezone
                        config.wsfe_authorized = True
                        config.wsfe_authorized_at = timezone.now()
                        config.wsfe_automation_id = result.get('automation_id')
                        config.save(update_fields=['wsfe_authorized', 'wsfe_authorized_at', 'wsfe_automation_id'])

                        data = {
                            'success': True,
                            'message': f'Web Service {service.upper()} autorizado exitosamente',
                            'automation_id': result.get('automation_id'),
                            'status': result.get('status')
                        }
            except AfipConfig.DoesNotExist:
                data = {'success': False, 'error': 'Configuración no encontrada'}
            except Exception as e:
                data = {'success': False, 'error': str(e)}

        return JsonResponse(data)


class AfipVouchersListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    """Lista de comprobantes electrónicos emitidos (ventas con CAE)"""
    model = Sale
    template_name = 'afip/vouchers.html'
    permission_required = 'erp.view_afipconfig'
    paginate_by = 25

    def get_queryset(self):
        active_cid = self.request.session.get('company_id')
        if not active_cid:
            active_cid = getattr(self.request.user, 'company_id', None)

        qs = Sale.objects.select_related('cli', 'company').filter(
            afip_cae__isnull=False
        ).exclude(afip_cae='')

        if active_cid:
            qs = qs.filter(company_id=active_cid)

        return qs.order_by('-date_joined')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Comprobantes AFIP'
        context['entity'] = 'Comprobantes AFIP'
        context['list_url'] = reverse_lazy('erp:afip:vouchers')

        qs = context.get('object_list') or []
        for sale in qs:
            if sale.afip_error:
                sale.afip_status = 'error'
            elif sale.afip_cae:
                sale.afip_status = 'ok'
            else:
                sale.afip_status = 'pending'

        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        data = {}

        if action == 'retry_invoice':
            sale_id = request.POST.get('sale_id')
            try:
                sale = Sale.objects.get(pk=sale_id)
                if sale.afip_cae:
                    data = {'success': False, 'error': 'Esta venta ya tiene CAE asignado'}
                else:
                    result = sale.emitir_factura_afip(user=request.user)
                    if result:
                        data = {'success': True, 'message': 'Factura emitida correctamente', 'cae': sale.afip_cae}
                    else:
                        data = {'success': False, 'error': sale.afip_error or 'Error al emitir factura'}
            except Sale.DoesNotExist:
                data = {'success': False, 'error': 'Venta no encontrada'}
            except Exception as e:
                data = {'success': False, 'error': str(e)}

        return JsonResponse(data)


@login_required
@permission_required('erp.view_afipconfig', raise_exception=True)
@require_POST
def generate_afip_pdf(request):
    """
    Genera el PDF fiscal de un comprobante AFIP usando la API de AFIP SDK.
    Toma los datos de la venta y la configuración AFIP de la empresa.
    """
    sale_id = request.POST.get('sale_id')
    if not sale_id:
        return JsonResponse({'success': False, 'error': 'Falta el ID de la venta'}, status=400)

    try:
        sale = Sale.objects.select_related('cli', 'company').get(pk=sale_id)
    except Sale.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Venta no encontrada'}, status=404)

    # Verificar que la venta tenga CAE
    if not sale.afip_cae:
        return JsonResponse({'success': False, 'error': 'La venta no tiene CAE asignado'}, status=400)

    # Obtener configuración AFIP de la empresa
    config_obj = AfipConfig.objects.filter(company=sale.company, is_active=True).first()
    if not config_obj:
        return JsonResponse({'success': False, 'error': 'No hay configuración AFIP activa para la empresa'}, status=400)

    # Inicializar cliente AFIP
    client = AfipClient(company_id=sale.company_id)

    # Mapear tipo de comprobante a template de AFIP SDK
    template_map = {
        'A': 'invoice-a',
        'B': 'invoice-b',
        'C': 'invoice-c',
    }
    template_name = template_map.get(sale.invoice_type, 'invoice-b')

    # Datos del emisor (empresa)
    company = sale.company
    issuer_cuit = int(str(company.cuit or config_obj.cuit or '').replace('-', '').strip() or 0)
    issuer_business_name = company.name or 'Empresa'
    issuer_address = company.address or '-'
    issuer_iva_condition = company.get_condicion_iva_display() if hasattr(company, 'get_condicion_iva_display') else 'Responsable Inscripto'
    issuer_gross_income = getattr(company, 'iibb', 'CM 901-123456-7') or 'CM 901-123456-7'
    issuer_activity_start_date = getattr(company, 'start', '01/01/2020') or '01/01/2020'

    # Datos del receptor (cliente)
    if sale.cli:
        receiver_name = f"{sale.cli.names} {sale.cli.surnames or ''}".strip()
        receiver_address = sale.cli.address or '-'
        receiver_document_type = 80 if sale.cli.cuit else 99
        receiver_document_number = int(str(sale.cli.cuit or sale.cli.dni or '0').replace('-', '')) if (sale.cli.cuit or sale.cli.dni) else 0
        receiver_iva_condition = sale.cli.get_condicion_iva_display() if hasattr(sale.cli, 'get_condicion_iva_display') else 'Consumidor Final'
    else:
        receiver_name = 'CONSUMIDOR FINAL'
        receiver_address = '-'
        receiver_document_type = 99
        receiver_document_number = 0
        receiver_iva_condition = 'Consumidor Final'

    # Items de la venta
    items = []
    for det in DetSale.objects.filter(sale=sale).select_related('prod'):
        items.append({
            'code': det.prod.code or str(det.prod.id) if det.prod else '000',
            'description': det.prod.name if det.prod else 'Producto',
            'quantity': float(det.cant),
            'unit_price': float(det.price),
            'subtotal': float(det.subtotal),
        })

    if not items:
        items.append({
            'code': '000',
            'description': 'Venta',
            'quantity': 1,
            'unit_price': float(sale.total),
            'subtotal': float(sale.total),
        })

    # Fechas
    issue_date = sale.date_joined.strftime('%d/%m/%Y') if sale.date_joined else '-'
    cae_due_date = sale.afip_cae_vto.strftime('%d/%m/%Y') if sale.afip_cae_vto else '-'

    # Número de comprobante y punto de venta
    voucher_number = sale.afip_voucher_number or 1
    punto_venta_obj = AfipPuntoVenta.objects.filter(company=sale.company, is_active=True).first()
    sales_point = punto_venta_obj.numero if punto_venta_obj else 1

    # Construir datos para AFIP SDK PDF
    file_name = f"factura_{sale.invoice_type or 'B'}_{sales_point:04d}-{voucher_number:08d}.pdf"

    pdf_data = {
        'file_name': file_name,
        'template': {
            'name': template_name,
            'params': {
                'voucher_number': voucher_number,
                'sales_point': sales_point,
                'issue_date': issue_date,
                'cae_due_date': cae_due_date,
                'issuer_cuit': issuer_cuit,
                'cae': int(sale.afip_cae),
                'issuer_business_name': issuer_business_name,
                'issuer_address': issuer_address,
                'issuer_iva_condition': issuer_iva_condition,
                'issuer_gross_income': issuer_gross_income,
                'issuer_activity_start_date': issuer_activity_start_date,
                'receiver_name': receiver_name,
                'receiver_address': receiver_address,
                'receiver_document_type': receiver_document_type,
                'receiver_document_number': receiver_document_number,
                'receiver_iva_condition': receiver_iva_condition,
                'sale_condition': 'Contado',
                'currency_id': 'ARS',
                'currency_rate': 1,
                'concept': 1,
                'items': items,
                'vat_amount': float(sale.iva or 0),
                'tributes_amount': 0,
                'total_amount': float(sale.total),
                'billing_from': issue_date,
                'billing_to': issue_date,
                'payment_due_date': issue_date,
            }
        }
    }

    # Enviar email opcional si el cliente tiene email
    if sale.cli and sale.cli.email:
        pdf_data['send_to'] = sale.cli.email

    result = client.create_pdf(pdf_data, user=request.user)

    if 'error' in result:
        return JsonResponse({'success': False, 'error': result['error']}, status=500)

    # Guardar URL del PDF en la venta
    sale.afip_pdf_url = result.get('file', '')
    sale.save(update_fields=['afip_pdf_url'])

    return JsonResponse({'success': True, 'pdf_url': result.get('file'), 'file_name': file_name})


class AfipPuntoVentaListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    """Lista de puntos de venta AFIP"""
    model = AfipPuntoVenta
    template_name = 'afip/punto_venta/list.html'
    permission_required = 'erp.view_afippuntoventa'

    def get_queryset(self):
        return AfipPuntoVenta.objects.select_related('company').all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Puntos de Venta AFIP'
        context['create_url'] = reverse_lazy('erp:afip:punto_venta_create')
        context['list_url'] = reverse_lazy('erp:afip:punto_venta_list')
        context['entity'] = 'Puntos de Venta AFIP'
        return context


class AfipPuntoVentaCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CompanyInitialMixin, CreateView):
    """Crear punto de venta AFIP"""
    model = AfipPuntoVenta
    template_name = 'afip/punto_venta/form.html'
    permission_required = 'erp.add_afippuntoventa'
    fields = ['company', 'numero', 'descripcion', 'is_active']
    success_url = reverse_lazy('erp:afip:punto_venta_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Creación de Punto de Venta AFIP'
        context['entity'] = 'Puntos de Venta AFIP'
        context['list_url'] = reverse_lazy('erp:afip:punto_venta_list')
        context['action'] = 'add'
        return context


class AfipPuntoVentaUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    """Actualizar punto de venta AFIP"""
    model = AfipPuntoVenta
    template_name = 'afip/punto_venta/form.html'
    permission_required = 'erp.change_afippuntoventa'
    fields = ['company', 'numero', 'descripcion', 'is_active']
    success_url = reverse_lazy('erp:afip:punto_venta_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edición de Punto de Venta AFIP'
        context['entity'] = 'Puntos de Venta AFIP'
        context['list_url'] = reverse_lazy('erp:afip:punto_venta_list')
        context['action'] = 'edit'
        return context


class AfipPuntoVentaDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    """Eliminar punto de venta AFIP"""
    model = AfipPuntoVenta
    template_name = 'afip/punto_venta/delete.html'
    permission_required = 'erp.delete_afippuntoventa'
    success_url = reverse_lazy('erp:afip:punto_venta_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Eliminar Punto de Venta AFIP'
        context['entity'] = 'Puntos de Venta AFIP'
        context['list_url'] = reverse_lazy('erp:afip:punto_venta_list')
        context['action'] = 'delete'
        return context
