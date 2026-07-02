from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView

import json
import logging
import os
from datetime import datetime

# Importar librerías para manejo de Excel/CSV
import numpy
NUMPY_AVAILABLE = True

import pandas as pd
PANDAS_AVAILABLE = True

import openpyxl
OPENPYXL_AVAILABLE = True

from core.erp.forms import ProductForm
from core.erp.models import Product, Category, Company
from core.erp.mixins import ValidatePermissionRequiredMixin
from core.erp.services.server_sync_service import ServerSyncService

# Configurar logging para importación de productos
def setup_import_logger():
    """Configura y retorna un logger para registrar errores de importación"""
    logger = logging.getLogger('import_inventory')
    
    # Si ya tiene handlers, no agregar duplicados
    if logger.handlers:
        return logger
    
    # Crear directorio de logs si no existe
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configurar archivo de log con fecha
    log_file = os.path.join(log_dir, f'import_inventory_{datetime.now().strftime("%Y%m")}.log')
    
    # Crear handler para archivo
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Crear formato de log
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # Configurar logger
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    
    return logger

# Logger global para importación
import_logger = setup_import_logger()

try:
    import mercadopago
except Exception:
    mercadopago = None


class ProductListView(ValidatePermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = Product
    template_name = 'product/list.html'
    permission_required = 'erp.view_product'
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['import_url'] = reverse_lazy('erp:product_import')
        return ctx

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            print(f"DEBUG Product: Action received: {action}")
            if action == 'searchdata':
                data = []
                active_cid = request.session.get('company_id') if hasattr(request, 'session') else None
                if not request.user.is_superuser:
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
                qs = Product.objects.all()
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                print(f"DEBUG Product: Found {qs.count()} products")
                for i in qs:
                    product_data = i.toJSON()
                    # Formatear valores monetarios con separadores de miles
                    if 'pvp' in product_data:
                        product_data['pvp_formatted'] = "${:,.2f}".format(float(product_data['pvp']))
                    if 'pvp_final' in product_data:
                        product_data['pvp_final_formatted'] = "${:,.2f}".format(float(product_data['pvp_final']))
                    data.append(product_data)
                print(f"DEBUG Product: Returning {len(data)} products")
            elif action == 'delete_all':
                # Eliminar todos los productos de la empresa activa
                active_cid = request.session.get('company_id') if hasattr(request, 'session') else None
                if not request.user.is_superuser:
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
                
                qs = Product.objects.all()
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                count = qs.count()
                qs.delete()
                data = {'success': True, 'count': count}
            else:
                data = {'error': 'Ha ocurrido un error'}
        except Exception as e:
            print(f"DEBUG Product: Exception: {e}")
            data = {'error': str(e)}
        print(f"DEBUG Product: Final data length: {len(data) if isinstance(data, list) else 'error'}")
        return JsonResponse(data, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Listado de Productos'
        context['create_url'] = reverse_lazy('erp:product_create')
        context['list_url'] = reverse_lazy('erp:product_list')
        context['entity'] = 'Productos'
        return context


class ProductCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'product/create.html'
    success_url = reverse_lazy('erp:product_list')
    permission_required = 'erp.add_product'
    url_redirect = success_url

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_superuser:
            return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def post(self, request, *args, **kwargs):
         data = {}
         try:
             action = request.POST['action']
             if action == 'add':
                 form = self.get_form()
                 data = form.save()
             else:
                 data['error'] = 'No ha ingresado a ninguna opción'
         except Exception as e:
             data['error'] = str(e)
         return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Creación de un Producto'
        context['entity'] = 'Productos'
        context['list_url'] = reverse_lazy('erp:product_list')
        context['action'] = 'add'
        return context


class ProductUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'product/create.html'
    success_url = reverse_lazy('erp:product_list')
    permission_required = 'erp.change_product'
    url_redirect = success_url

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.user.is_superuser:
            return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST.get('action')
            if action == 'edit':
                form = self.get_form()
                data = form.save()
            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edición de un Producto'
        context['entity'] = 'Productos'
        context['list_url'] = self.success_url
        context['action'] = 'edit'
        return context


class ProductLabelsView(LoginRequiredMixin, ValidatePermissionRequiredMixin, TemplateView):
    permission_required = 'erp.view_product'
    template_name = 'product/labels.html'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        active_cid = self.request.session.get('company_id')
        if not self.request.user.is_superuser:
            active_cid = active_cid or getattr(self.request.user, 'company_id', None)
        qs = Product.objects.all().select_related('cat')
        if active_cid:
            qs = qs.filter(company_id=active_cid)
        cat_id = self.request.GET.get('cat')
        if cat_id:
            qs = qs.filter(cat_id=cat_id)
        for p in qs:
            if not p.qr_token:
                p.save()
        
        # Paginación
        from django.core.paginator import Paginator
        paginator = Paginator(qs.order_by('cat__name', 'name'), self.paginate_by)
        page_number = self.request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        ctx['products'] = page_obj
        ctx['page_obj'] = page_obj
        ctx['categories'] = Category.objects.all().order_by('name')
        ctx['title'] = 'Etiquetas de Productos'
        ctx['entity'] = 'Productos'
        return ctx


class ProductPublicDetailView(TemplateView):
    template_name = 'product/product_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        token = self.kwargs.get('token')
        prod = Product.objects.filter(qr_token=token).select_related('cat', 'company').first()
        ctx['product'] = prod
        return ctx


class QuickCartView(TemplateView):
    template_name = 'product/quick_cart.html'

    def _get_cart(self, request):
        cart = request.session.get('quick_cart') or {}
        if not isinstance(cart, dict):
            cart = {}
        return cart

    def _save_cart(self, request, cart):
        request.session['quick_cart'] = cart
        request.session.modified = True

    def get(self, request, *args, **kwargs):
        cart = self._get_cart(request)

        token = request.GET.get('add')
        if token:
            prod = Product.objects.filter(qr_token=token).first()
            if prod:
                key = str(prod.id)
                cart[key] = int(cart.get(key, 0) or 0) + 1
                self._save_cart(request, cart)

        if request.GET.get('clear') == '1':
            cart = {}
            self._save_cart(request, cart)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cart = self._get_cart(self.request)
        ids = [int(k) for k in cart.keys() if str(k).isdigit()]
        items = []
        total = 0
        company = None
        if ids:
            prods = Product.objects.filter(id__in=ids).select_related('company')
            for p in prods:
                qty = int(cart.get(str(p.id), 0) or 0)
                if qty <= 0:
                    continue
                if company is None:
                    company = p.company
                line_total = float(p.pvp_final or p.pvp or 0) * qty
                total += line_total
                items.append({
                    'product': p,
                    'qty': qty,
                    'line_total': line_total,
                })
        ctx['items'] = items
        ctx['total'] = total
        mp_config = None
        if company is not None:
            mp_config = getattr(company, 'mp_config', None)
        ctx['mp_enabled'] = bool(mp_config and mp_config.enabled and mp_config.access_token)
        return ctx


@csrf_exempt
def quick_cart_mp_checkout(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    cart = request.session.get('quick_cart') or {}
    if not isinstance(cart, dict) or not cart:
        return JsonResponse({'error': 'Carrito vacío'}, status=400)

    ids = [int(k) for k in cart.keys() if str(k).isdigit()]
    prods = list(Product.objects.filter(id__in=ids).select_related('company'))
    if not prods:
        return JsonResponse({'error': 'Carrito inválido'}, status=400)

    company = prods[0].company
    mp_config = getattr(company, 'mp_config', None) if company else None
    if not (mp_config and mp_config.enabled and mp_config.access_token):
        return JsonResponse({'error': 'Mercado Pago no está configurado para esta empresa'}, status=400)

    if mercadopago is None:
        return JsonResponse({'error': 'SDK de Mercado Pago no está instalado en el servidor'}, status=500)

    sdk = mercadopago.SDK(mp_config.access_token)

    items = []
    for p in prods:
        qty = int(cart.get(str(p.id), 0) or 0)
        if qty <= 0:
            continue
        price = float(p.pvp_final or p.pvp or 0)
        items.append({
            "title": p.name,
            "quantity": qty,
            "currency_id": "ARS",
            "unit_price": price,
        })

    if not items:
        return JsonResponse({'error': 'Carrito vacío'}, status=400)

    base_url = request.build_absolute_uri('/')[:-1]
    preference_data = {
        "items": items,
        "back_urls": {
            "success": f"{base_url}/erp/quick-cart/",
            "pending": f"{base_url}/erp/quick-cart/",
            "failure": f"{base_url}/erp/quick-cart/",
        },
        "auto_return": "approved",
    }

    pref = sdk.preference().create(preference_data)
    init_point = pref.get("response", {}).get("init_point")
    if not init_point:
        return JsonResponse({'error': 'No se pudo crear preferencia de pago'}, status=500)

    return JsonResponse({"init_point": init_point})


class ImportInventoryView(LoginRequiredMixin, ValidatePermissionRequiredMixin, TemplateView):
    permission_required = 'erp.add_product'
    template_name = 'product/import.html'
    url_redirect = reverse_lazy('erp:product_list')

    def get(self, request, *args, **kwargs):
        print(f"DEBUG IMPORT: Accediendo a la página de importación")
        print(f"DEBUG IMPORT: numpy disponible: {NUMPY_AVAILABLE}")
        print(f"DEBUG IMPORT: pandas disponible: {PANDAS_AVAILABLE}")
        print(f"DEBUG IMPORT: openpyxl disponible: {OPENPYXL_AVAILABLE}")
        if NUMPY_AVAILABLE:
            print(f"DEBUG IMPORT: Versión numpy: {numpy.__version__}")
        if PANDAS_AVAILABLE:
            print(f"DEBUG IMPORT: Versión pandas: {pd.__version__}")
        if OPENPYXL_AVAILABLE:
            print(f"DEBUG IMPORT: Versión openpyxl: {openpyxl.__version__}")
        
        # Registrar en log
        import_logger.info(f"Usuario {request.user.username} accedió a página de importación")
        import_logger.info(f"Librerías - numpy: {NUMPY_AVAILABLE}, pandas: {PANDAS_AVAILABLE}, openpyxl: {OPENPYXL_AVAILABLE}")
        if NUMPY_AVAILABLE:
            import_logger.info(f"Versión numpy: {numpy.__version__}")
        if PANDAS_AVAILABLE:
            import_logger.info(f"Versión pandas: {pd.__version__}")
        if OPENPYXL_AVAILABLE:
            import_logger.info(f"Versión openpyxl: {openpyxl.__version__}")
        
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not NUMPY_AVAILABLE or not PANDAS_AVAILABLE or not OPENPYXL_AVAILABLE:
            missing_libs = []
            if not NUMPY_AVAILABLE:
                missing_libs.append("numpy")
            if not PANDAS_AVAILABLE:
                missing_libs.append("pandas")
            if not OPENPYXL_AVAILABLE:
                missing_libs.append("openpyxl")
            
            error_msg = f"""
            ERROR: Las librerías para importación de Excel/CSV no están instaladas.
            Faltan: {', '.join(missing_libs)}
            
            Solución:
            1. Abre una terminal o símbolo del sistema
            2. Activa el entorno virtual: venv\\Scripts\\activate
            3. Instala las librerías: pip install numpy pandas openpyxl
            4. O ejecuta el script: fix_pandas_windows.bat
            
            Si el problema persiste, ejecuta el instalador completo: instalador_pos_bat.bat
            """
            messages.error(request, error_msg)
            return self.get(request, *args, **kwargs)
        action = request.POST.get('action')
        
        # Nueva acción: Importar desde servidor
        if action == 'import_from_server':
            return self.import_from_server(request)
        
        # Nueva acción: Clonar productos seleccionados
        if action == 'clone_server_products':
            return self.clone_server_products(request)
        
        # Paso 1: analizar columnas y mostrar mapeo (archivo "limpio")
        if action == 'analyze':
            file = request.FILES.get('file')
            if not file:
                messages.error(request, 'Debe seleccionar un archivo CSV o Excel')
                return self.get(request, *args, **kwargs)
            try:
                print(f"DEBUG: Intentando leer archivo: {file.name}")
                print(f"DEBUG: Tamaño del archivo: {file.size} bytes")
                print(f"DEBUG: Tipo de contenido: {file.content_type}")
                print(f"DEBUG: pandas disponible: {PANDAS_AVAILABLE}")
                print(f"DEBUG: openpyxl disponible: {OPENPYXL_AVAILABLE}")
                
                # Registrar en log
                import_logger.info(f"Usuario {request.user.username} iniciando análisis de archivo")
                import_logger.info(f"Archivo: {file.name}, Tamaño: {file.size} bytes, Content-Type: {file.content_type}")
                import_logger.info(f"Librerías disponibles - pandas: {PANDAS_AVAILABLE}, openpyxl: {OPENPYXL_AVAILABLE}")
                
                # Detectar sistema operativo para usar método adecuado
                import platform
                is_windows = platform.system() == 'Windows'
                
                if file.name.lower().endswith(('.xlsx', '.xls')):
                    print("DEBUG: Detectado archivo Excel, intentando leer con pandas...")
                    import_logger.info("Detectado archivo Excel, iniciando lectura con pandas...")
                    
                    if is_windows:
                        # MÉTODO WINDOWS: Usar archivo temporal para evitar bloqueos
                        print("DEBUG: Usando método para Windows...")
                        import_logger.info("Usando método de lectura para Windows")
                        
                        try:
                            import tempfile
                            import os
                            
                            # Crear archivo temporal
                            temp_dir = tempfile.gettempdir()
                            temp_file_path = os.path.join(temp_dir, f"temp_import_{request.user.id}_{os.getpid()}.xlsx")
                            
                            # Guardar archivo subido temporalmente
                            with open(temp_file_path, 'wb') as temp_file:
                                for chunk in file.chunks():
                                    temp_file.write(chunk)
                            
                            print(f"DEBUG: Archivo guardado temporalmente en: {temp_file_path}")
                            import_logger.info(f"Archivo guardado temporalmente: {temp_file_path}")
                            
                            # Leer desde archivo temporal
                            df = pd.read_excel(temp_file_path, header=0)
                            print(f"DEBUG: Excel leído desde temporal. Columnas: {list(df.columns)}")
                            
                            # Si hay columnas "Unnamed", intentar detectar encabezados
                            if any(col.startswith('Unnamed:') for col in df.columns):
                                print("DEBUG: Detectadas columnas Unnamed, intentando detectar encabezados...")
                                df_temp = pd.read_excel(temp_file_path, header=None)
                                
                                # Buscar fila de encabezados
                                header_row = None
                                for i in range(min(5, len(df_temp))):
                                    row = df_temp.iloc[i]
                                    if not row.isna().all():
                                        row_str = [str(val).lower() for val in row if pd.notna(val)]
                                        header_keywords = ['nombre', 'codigo', 'precio', 'costo', 'cantidad', 'iva', 'venta', 'proveedor']
                                        if any(keyword in ' '.join(row_str) for keyword in header_keywords):
                                            header_row = i
                                            break
                                
                                if header_row is not None:
                                    df = pd.read_excel(temp_file_path, header=header_row)
                                    print(f"DEBUG: Encabezados encontrados en fila {header_row}")
                                else:
                                    df.columns = [f"Column_{i}" for i in range(len(df.columns))]
                                    print("DEBUG: Usando nombres genéricos")
                            
                            # Limpiar archivo temporal
                            try:
                                os.unlink(temp_file_path)
                                print(f"DEBUG: Archivo temporal eliminado")
                            except Exception as cleanup_error:
                                print(f"WARNING: No se pudo eliminar archivo temporal: {cleanup_error}")
                            
                        except Exception as e:
                            print(f"DEBUG: Método Windows falló: {e}")
                            # Fallback al método Linux
                            print("DEBUG: Intentando fallback al método Linux...")
                            df = pd.read_excel(file, header=0)
                            print(f"DEBUG: Fallback exitoso. Columnas: {list(df.columns)}")
                    
                    else:
                        # MÉTODO LINUX: Lectura directa (método actual)
                        print("DEBUG: Usando método para Linux...")
                        import_logger.info("Usando método de lectura para Linux")
                        
                        # Intentar diferentes métodos para leer el archivo Excel
                        try:
                            # Método 1: Leer con encabezado en la primera fila
                            df = pd.read_excel(file, header=0)
                            print(f"DEBUG: Método 1 - Excel leído con header=0. Columnas: {list(df.columns)}")
                            
                            # Si hay columnas "Unnamed" o la primera fila tiene NaN, intentar detectar encabezados reales
                            if any(col.startswith('Unnamed:') for col in df.columns) or (len(df) > 0 and df.iloc[0].isna().all()):
                                print("DEBUG: Detectadas columnas Unnamed o primera fila vacía, intentando detectar encabezados...")
                                # Volver a leer el archivo desde el principio
                                file.seek(0)
                                df_temp = pd.read_excel(file, header=None)
                                print(f"DEBUG: Excel leído sin encabezado. Columnas: {list(df_temp.columns)}")
                                
                                # Buscar la fila que contiene los encabezados reales
                                header_row = None
                                for i in range(min(5, len(df_temp))):  # Revisar primeras 5 filas
                                    row = df_temp.iloc[i]
                                    # Si la fila tiene datos válidos y no todos son NaN
                                    if not row.isna().all() and any(str(val) not in ['NaN', 'nan', ''] for val in row if pd.notna(val)):
                                        # Si contiene palabras típicas de encabezados
                                        row_str = [str(val).lower() for val in row if pd.notna(val)]
                                        header_keywords = ['nombre', 'codigo', 'precio', 'costo', 'cantidad', 'iva', 'venta', 'proveedor']
                                        if any(keyword in ' '.join(row_str) for keyword in header_keywords):
                                            header_row = i
                                            print(f"DEBUG: Encabezados encontrados en fila {i}: {list(row)}")
                                            break
                                
                                if header_row is not None:
                                    # Usar la fila encontrada como encabezados
                                    df = pd.read_excel(file, header=header_row)
                                    print(f"DEBUG: Excel leído con header={header_row}. Columnas: {list(df.columns)}")
                                else:
                                    # Si no se encuentran encabezados, usar nombres genéricos
                                    file.seek(0)
                                    df = pd.read_excel(file, header=None)
                                    df.columns = [f"Column_{i}" for i in range(len(df.columns))]
                                    print(f"DEBUG: Columnas renombradas genéricamente: {list(df.columns)}")
                        
                        except Exception as e1:
                            print(f"DEBUG: Método 1 falló: {e1}")
                            try:
                                # Método 2: Leer sin encabezado
                                file.seek(0)
                                df = pd.read_excel(file, header=None)
                                print(f"DEBUG: Método 2 - Excel leído sin encabezado. Columnas: {list(df.columns)}")
                                
                                # Asignar nombres genéricos a las columnas
                                df.columns = [f"Column_{i}" for i in range(len(df.columns))]
                                print(f"DEBUG: Columnas renombradas: {list(df.columns)}")
                                
                            except Exception as e2:
                                print(f"DEBUG: Método 2 falló: {e2}")
                                # Método 3: Último intento con parámetros por defecto
                                file.seek(0)
                                df = pd.read_excel(file)
                                print(f"DEBUG: Método 3 - Excel leído con parámetros por defecto. Columnas: {list(df.columns)}")
                    
                    print(f"DEBUG: Excel leído exitosamente. Filas: {len(df)}, Columnas: {len(df.columns)}")
                    import_logger.info(f"Excel leído exitosamente - Filas: {len(df)}, Columnas: {len(df.columns)}")
                    
                else:
                    # Manejo de CSV
                    sep = request.POST.get('sep') or ','
                    print(f"DEBUG: Detectado archivo CSV, usando separador: '{sep}'")
                    import_logger.info(f"Detectado archivo CSV, separador: '{sep}'")
                    
                    if is_windows:
                        # MÉTODO WINDOWS: Usar archivo temporal y múltiples codificaciones
                        print("DEBUG: Usando método CSV para Windows...")
                        import_logger.info("Usando método CSV para Windows")
                        
                        try:
                            import tempfile
                            import os
                            
                            # Crear archivo temporal
                            temp_dir = tempfile.gettempdir()
                            temp_file_path = os.path.join(temp_dir, f"temp_import_{request.user.id}_{os.getpid()}.csv")
                            
                            # Guardar archivo subido temporalmente
                            with open(temp_file_path, 'wb') as temp_file:
                                for chunk in file.chunks():
                                    temp_file.write(chunk)
                            
                            print(f"DEBUG: CSV guardado temporalmente en: {temp_file_path}")
                            
                            # Intentar diferentes codificaciones para Windows
                            encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                            df = None
                            
                            for encoding in encodings_to_try:
                                try:
                                    print(f"DEBUG: Intentando encoding: {encoding}")
                                    df = pd.read_csv(temp_file_path, sep=sep, encoding=encoding)
                                    print(f"DEBUG: CSV leído con encoding {encoding}. Columnas: {list(df.columns)}")
                                    break
                                except Exception as encoding_error:
                                    print(f"DEBUG: Encoding {encoding} falló: {encoding_error}")
                                    continue
                            
                            if df is None:
                                # Último intento con configuración por defecto
                                print("DEBUG: Todos los encodings fallaron, intentando con configuración por defecto")
                                df = pd.read_csv(temp_file_path, sep=sep)
                            
                            # Limpiar archivo temporal
                            try:
                                os.unlink(temp_file_path)
                                print(f"DEBUG: Archivo temporal CSV eliminado")
                            except Exception as cleanup_error:
                                print(f"WARNING: No se pudo eliminar archivo temporal CSV: {cleanup_error}")
                            
                        except Exception as e:
                            print(f"DEBUG: Método CSV Windows falló: {e}")
                            # Fallback al método Linux
                            print("DEBUG: Intentando fallback CSV al método Linux...")
                            df = pd.read_csv(file, sep=sep)
                            print(f"DEBUG: Fallback CSV exitoso. Columnas: {list(df.columns)}")
                    
                    else:
                        # MÉTODO LINUX: Lectura directa con UTF-8
                        print("DEBUG: Usando método CSV para Linux...")
                        import_logger.info("Usando método CSV para Linux")
                        df = pd.read_csv(file, sep=sep, encoding='utf-8')
                        print(f"DEBUG: CSV leído con UTF-8. Columnas: {list(df.columns)}")
                    
                    print(f"DEBUG: CSV leído exitosamente. Filas: {len(df)}, Columnas: {len(df.columns)}")
                    import_logger.info(f"CSV leído exitosamente - Filas: {len(df)}, Columnas: {len(df.columns)}")
                
                print(f"DEBUG: Columnas encontradas: {list(df.columns)}")
                print(f"DEBUG: Primeras 5 filas:")
                print(df.head().to_string())
                
                # Registrar información del archivo en log
                import_logger.info(f"Columnas encontradas: {list(df.columns)}")
                import_logger.debug(f"Primeras 5 filas:\n{df.head().to_string()}")
                
            except Exception as e:
                print(f"DEBUG ERROR: Error al leer archivo: {type(e).__name__}: {e}")
                print(f"DEBUG ERROR: Args: {e.args}")
                import traceback
                print(f"DEBUG ERROR: Traceback completo:")
                traceback.print_exc()
                
                # Información adicional para Windows
                import sys
                print(f"DEBUG: Versión de Python: {sys.version}")
                print(f"DEBUG: Versión de pandas: {pd.__version__ if pd else 'No disponible'}")
                print(f"DEBUG: Versión de openpyxl: {openpyxl.__version__ if openpyxl else 'No disponible'}")
                
                # Análisis específico para Windows
                error_str = str(e).lower()
                windows_solution = ""
                
                if 'no module named' in error_str or 'modulenotfounderror' in error_str:
                    if 'pandas' in error_str:
                        windows_solution = """
                        ❌ ERROR: Pandas no está instalado
                        💡 SOLUCIÓN PARA WINDOWS:
                        1. Abrir Símbolo del sistema COMO ADMINISTRADOR
                        2. Ejecutar: pip install pandas
                        3. O ejecutar: pip install --user pandas
                        4. Reiniciar el servidor
                        
                        🚀 SOLUCIÓN AUTOMÁTICA:
                        Ejecutar: instalador_pos_bat.bat
                        """
                    elif 'openpyxl' in error_str:
                        windows_solution = """
                        ❌ ERROR: Openpyxl no está instalado
                        💡 SOLUCIÓN PARA WINDOWS:
                        1. Abrir Símbolo del sistema COMO ADMINISTRADOR
                        2. Ejecutar: pip install openpyxl
                        3. O ejecutar: pip install --user openpyxl
                        4. Reiniciar el servidor
                        
                        🚀 SOLUCIÓN AUTOMÁTICA:
                        Ejecutar: instalador_pos_bat.bat
                        """
                    else:
                        windows_solution = f"""
                        ❌ ERROR: Módulo faltante - {e}
                        💡 SOLUCIÓN PARA WINDOWS:
                        1. Abrir Símbolo del sistema COMO ADMINISTRADOR
                        2. Ejecutar: pip install <nombre_del_módulo>
                        3. O ejecutar: pip install --user <nombre_del_módulo>
                        4. Reiniciar el servidor
                        
                        🚀 SOLUCIÓN AUTOMÁTICA:
                        Ejecutar: instalador_pos_bat.bat
                        """
                
                elif 'permission denied' in error_str or 'access is denied' in error_str:
                    windows_solution = """
                    ❌ ERROR: Permisos denegados
                    💡 SOLUCIÓN PARA WINDOWS:
                    1. Cerrar Excel si está abierto
                    2. Ejecutar el servidor COMO ADMINISTRADOR
                    3. Mover el archivo a una carpeta sin permisos especiales
                    4. Verificar que el archivo no esté de solo lectura
                    
                    📁 CARPETA RECOMENDADA:
                    C:\\Users\\TuUsuario\\Desktop\\importar\\
                    """
                
                elif 'invalid file' in error_str or 'badzipfile' in error_str:
                    windows_solution = f"""
                    ❌ ERROR: Archivo Excel inválido o corrupto
                    💡 SOLUCIÓN PARA WINDOWS:
                    1. Abrir el archivo en Excel y guardarlo como ".xlsx"
                    2. Asegurarse que no esté protegido con contraseña
                    3. Verificar que no esté abierto en otro programa
                    4. Intentar guardar una copia nueva del archivo
                    
                    📋 DETALLES DEL ERROR: {e}
                    """
                
                elif 'memory' in error_str or 'out of memory' in error_str:
                    windows_solution = f"""
                    ❌ ERROR: Sin memoria suficiente
                    💡 SOLUCIÓN PARA WINDOWS:
                    1. Cerrar otros programas
                    2. Dividir el archivo en partes más pequeñas
                    3. Reiniciar el servidor
                    4. Aumentar memoria virtual del sistema
                    
                    📊 ARCHIVO DEMASIADO GRANDE: {file.size} bytes
                    """
                
                elif 'encoding' in error_str or 'utf' in error_str:
                    windows_solution = """
                    ❌ ERROR: Problemas de codificación
                    💡 SOLUCIÓN PARA WINDOWS:
                    1. Guardar el archivo como CSV UTF-8
                    2. O usar Excel y guardarlo como ".xlsx"
                    3. Evitar caracteres especiales en los nombres
                    
                    🔤 CODIFICACIÓN RECOMENDADA: UTF-8
                    """
                
                # Si no se identificó el error específico
                if not windows_solution:
                    windows_solution = f"""
                    ❌ ERROR DESCONOCIDO: {e}
                    💡 SOLUCIÓN GENERAL PARA WINDOWS:
                    1. Ejecutar diagnóstico completo: python diagnostic_excel.py
                    2. Verificar instalación de librerías
                    3. Reiniciar el servidor
                    4. Ejecutar: instalador_pos_bat.bat
                    
                    📋 PARA SOPORTE TÉCNICO:
                    Enviar captura de este error completo
                    """
                
                # Mostrar solución específica
                print("=" * 80)
                print("🔍 DIAGNÓSTICO PARA WINDOWS:")
                print(windows_solution)
                print("=" * 80)
                
                # Registrar error detallado en log
                import_logger.error(f"Error al leer archivo - Usuario: {request.user.username}")
                import_logger.error(f"Archivo: {file.name}, Tamaño: {file.size} bytes")
                import_logger.error(f"Error: {type(e).__name__}: {e}")
                import_logger.error(f"Args: {e.args}")
                import_logger.error(f"Python: {sys.version}")
                import_logger.error(f"Pandas: {pd.__version__ if pd else 'No disponible'}")
                import_logger.error(f"Openpyxl: {openpyxl.__version__ if openpyxl else 'No disponible'}")
                import_logger.error(f"Solución Windows: {windows_solution}")
                import_logger.error(f"Traceback:\n{traceback.format_exc()}")
                
                # En lugar de mostrar solo el error, mostrar la solución
                error_msg = f"""
                ❌ ERROR AL PROCESAR ARCHIVO: {e}
                
                💡 SOLUCIÓN PARA WINDOWS:
                {windows_solution}
                
                📋 PASOS ADICIONALES:
                1. Ejecutar: python diagnostic_excel.py
                2. Seguir las instrucciones específicas
                3. Reiniciar el servidor después de instalar
                4. Intentar nuevamente
                """
                messages.error(request, error_msg)
                return self.get(request, *args, **kwargs)

            columns = list(df.columns)
            
            # Verificar que las columnas sean únicas
            if len(columns) != len(set(columns)):
                print(f"DEBUG: Columnas duplicadas encontradas: {columns}")
                # Hacer únicas las columnas duplicadas
                column_counts = {}
                unique_columns = []
                for i, col in enumerate(columns):
                    if col in column_counts:
                        column_counts[col] += 1
                        unique_col = f"{col}_{column_counts[col]}"
                        unique_columns.append(unique_col)
                        print(f"DEBUG: Renombrando columna duplicada '{col}' a '{unique_col}'")
                    else:
                        column_counts[col] = 0
                        unique_columns.append(col)
                
                # Renombrar las columnas del DataFrame
                df.columns = unique_columns
                columns = unique_columns
                print(f"DEBUG: Columnas únicas finales: {columns}")
            
            request.session['import_df'] = df.to_json(orient='records')
            request.session['import_cols'] = columns
            ctx = {
                'columns': columns,
                'unit_choices': Product.UNIT_CHOICES,
                'fields': ['name', 'cat', 'pvp', 'iva_rate', 'pvp_final', 'unit', 'stock', 'company'],
                'entity_type': request.POST.get('entity_type', 'product'),
            }
            return self.render_to_response(ctx)

        # Paso 1b: analizar lista de proveedor y devolver CSV limpio para completar
        if action == 'analyze_supplier':
            file = request.FILES.get('file')
            if not file:
                messages.error(request, 'Debe seleccionar un archivo CSV o Excel')
                return self.get(request, *args, **kwargs)
            if not PANDAS_AVAILABLE or not OPENPYXL_AVAILABLE:
                missing_libs = []
                if not PANDAS_AVAILABLE:
                    missing_libs.append("pandas")
                if not OPENPYXL_AVAILABLE:
                    missing_libs.append("openpyxl")
                
                error_msg = f"""
                ERROR: Las librerías para importación de Excel/CSV no están instaladas.
                Faltan: {', '.join(missing_libs)}
                
                Solución:
                1. Abre una terminal o símbolo del sistema
                2. Activa el entorno virtual: venv\\Scripts\\activate
                3. Instala las librerías: pip install pandas openpyxl
                4. O ejecuta el script: fix_pandas_windows.bat
                
                Si el problema persiste, ejecuta el instalador completo: instalador_pos_bat.bat
                """
                messages.error(request, error_msg)
                return self.get(request, *args, **kwargs)
            try:
                print(f"DEBUG PROVEEDOR: Intentando leer archivo: {file.name}")
                print(f"DEBUG PROVEEDOR: Tamaño del archivo: {file.size} bytes")
                print(f"DEBUG PROVEEDOR: Tipo de contenido: {file.content_type}")
                
                # Registrar en log
                import_logger.info(f"Usuario {request.user.username} iniciando análisis de proveedor")
                import_logger.info(f"Archivo proveedor: {file.name}, Tamaño: {file.size} bytes")
                
                if file.name.lower().endswith(('.xlsx', '.xls')):
                    print("DEBUG PROVEEDOR: Detectado archivo Excel, leyendo sin encabezados...")
                    import_logger.info("Detectado archivo Excel de proveedor, leyendo sin encabezados...")
                    raw_df = pd.read_excel(file, header=None)
                    print(f"DEBUG PROVEEDOR: Excel leído. Filas: {len(raw_df)}, Columnas: {len(raw_df.columns)}")
                    import_logger.info(f"Excel leído - Filas: {len(raw_df)}, Columnas: {len(raw_df.columns)}")
                else:
                    sep = request.POST.get('sep') or ','
                    print(f"DEBUG PROVEEDOR: Detectado archivo CSV, usando separador: '{sep}'")
                    import_logger.info(f"Detectado archivo CSV de proveedor, separador: '{sep}'")
                    raw_df = pd.read_csv(file, sep=sep, header=None)
                    print(f"DEBUG PROVEEDOR: CSV leído. Filas: {len(raw_df)}, Columnas: {len(raw_df.columns)}")
                    import_logger.info(f"CSV leído - Filas: {len(raw_df)}, Columnas: {len(raw_df.columns)}")
                
                print(f"DEBUG PROVEEDOR: Primeras 10 filas del archivo original:")
                print(raw_df.head(10).to_string())
                
                # Registrar información del archivo original en log
                import_logger.debug(f"Primeras 10 filas del archivo original:\n{raw_df.head(10).to_string()}")
                
            except Exception as e:
                print(f"DEBUG PROVEEDOR ERROR: Error al leer archivo: {type(e).__name__}: {e}")
                print(f"DEBUG PROVEEDOR ERROR: Args: {e.args}")
                import traceback
                print(f"DEBUG PROVEEDOR ERROR: Traceback completo:")
                traceback.print_exc()
                
                # Registrar error en log
                import_logger.error(f"Error al leer archivo de proveedor - Usuario: {request.user.username}")
                import_logger.error(f"Archivo: {file.name}, Error: {type(e).__name__}: {e}")
                import_logger.error(f"Traceback:\n{traceback.format_exc()}")
                
                messages.error(request, f'No se pudo leer el archivo: {e}')
                return self.get(request, *args, **kwargs)

            # Localizar fila de encabezados (donde aparezca DESCRIPCION)
            header_row = None
            for i, row in raw_df.iterrows():
                values = row.astype(str).str.upper().tolist()
                if any('DESCRIPCION' in v for v in values):
                    header_row = i
                    break
            if header_row is None:
                messages.error(request, 'No se encontró una fila de encabezados con la columna DESCRIPCION.')
                return self.get(request, *args, **kwargs)

            # Releer con encabezados reales
            try:
                print(f"DEBUG PROVEEDOR: Releyendo archivo con encabezados en fila {header_row}")
                import_logger.info(f"Releyendo archivo con encabezados en fila {header_row}")
                
                if file.name.lower().endswith(('.xlsx', '.xls')):
                    print("DEBUG PROVEEDOR: Leyendo Excel con encabezados...")
                    import_logger.info("Leyendo Excel con encabezados...")
                    df = pd.read_excel(file, header=header_row)
                    print(f"DEBUG PROVEEDOR: Excel con encabezados leído. Filas: {len(df)}, Columnas: {len(df.columns)}")
                    import_logger.info(f"Excel con encabezados leído - Filas: {len(df)}, Columnas: {len(df.columns)}")
                else:
                    sep = request.POST.get('sep') or ','
                    print(f"DEBUG PROVEEDOR: Leyendo CSV con encabezados, separador: '{sep}'")
                    import_logger.info(f"Leyendo CSV con encabezados, separador: '{sep}'")
                    df = pd.read_csv(file, sep=sep, header=header_row)
                    print(f"DEBUG PROVEEDOR: CSV con encabezados leído. Filas: {len(df)}, Columnas: {len(df.columns)}")
                    import_logger.info(f"CSV con encabezados leído - Filas: {len(df)}, Columnas: {len(df.columns)}")
                
                print(f"DEBUG PROVEEDOR: Columnas con encabezados: {list(df.columns)}")
                print(f"DEBUG PROVEEDOR: Primeras 5 filas con encabezados:")
                print(df.head().to_string())
                
                # Registrar información con encabezados en log
                import_logger.info(f"Columnas con encabezados: {list(df.columns)}")
                import_logger.debug(f"Primeras 5 filas con encabezados:\n{df.head().to_string()}")
                
            except Exception as e:
                print(f"DEBUG PROVEEDOR ERROR: Error al releer archivo con encabezados: {type(e).__name__}: {e}")
                print(f"DEBUG PROVEEDOR ERROR: Args: {e.args}")
                import traceback
                print(f"DEBUG PROVEEDOR ERROR: Traceback completo:")
                traceback.print_exc()
                
                # Registrar error en log
                import_logger.error(f"Error al releer archivo con encabezados - Usuario: {request.user.username}")
                import_logger.error(f"Archivo: {file.name}, Fila encabezados: {header_row}")
                import_logger.error(f"Error: {type(e).__name__}: {e}")
                import_logger.error(f"Traceback:\n{traceback.format_exc()}")
                
                messages.error(request, f'No se pudo releer el archivo con encabezados: {e}')
                return self.get(request, *args, **kwargs)

            # Normalizar nombres de columnas para buscar equivalentes
            norm_cols = {str(c).strip().upper(): c for c in df.columns}
            col_desc = norm_cols.get('DESCRIPCION') or norm_cols.get('DESCRIPCIÓN')
            col_emp = norm_cols.get('EMPAQUE')
            col_iva = norm_cols.get('IVA')
            col_p_sin = None
            col_p_con = None
            for key, orig in norm_cols.items():
                if 'PRECIO' in key and 'SIN' in key and col_p_sin is None:
                    col_p_sin = orig
                if 'PRECIO' in key and 'SIN' not in key and col_p_con is None:
                    col_p_con = orig

            if col_desc is None or col_p_con is None:
                messages.error(request, 'No se pudieron identificar columnas de DESCRIPCION y PRECIO.')
                return self.get(request, *args, **kwargs)

            # Construir filas normalizadas desde la lista del proveedor
            salida = []
            categoria_actual = None
            for _, row in df.iterrows():
                desc_val = row.get(col_desc)
                emp_val = row.get(col_emp) if col_emp in df.columns else None
                iva_val = row.get(col_iva) if col_iva in df.columns else None
                p_sin_val = row.get(col_p_sin) if col_p_sin in df.columns else None
                p_con_val = row.get(col_p_con)

                # Fila de categoría: solo descripción con resto vacío
                if (pd.notna(desc_val) and str(desc_val).strip() and
                    (col_emp is None or pd.isna(emp_val)) and
                    (col_p_con is None or pd.isna(p_con_val))):
                    categoria_actual = str(desc_val).strip()
                    continue

                # Fila de producto: tiene descripción y precio
                if pd.notna(desc_val) and pd.notna(p_con_val):
                    salida.append({
                        'categoria': categoria_actual,
                        'empaque': str(emp_val).strip() if (col_emp and not pd.isna(emp_val)) else '',
                        'descripcion': str(desc_val).strip(),
                        'iva_raw': str(iva_val).strip() if (col_iva and not pd.isna(iva_val)) else '',
                        'precio_sin': p_sin_val,
                        'precio_con': p_con_val,
                    })

            if not salida:
                messages.error(request, 'No se detectaron filas de productos en la lista del proveedor.')
                return self.get(request, *args, **kwargs)

            norm_df = pd.DataFrame(salida)

            # Armar DataFrame en formato de importación, dejando columnas para completar
            def parse_iva(val):
                try:
                    if not val:
                        return ''
                    txt = str(val).replace('%', '').replace(',', '.').strip()
                    return float(txt)
                except Exception:
                    return ''

            import_df = pd.DataFrame()
            import_df['code'] = ''  # para que completes el código
            import_df['name'] = norm_df['descripcion']
            import_df['cat'] = norm_df['categoria']
            import_df['pvp'] = norm_df['precio_con']
            import_df['iva_rate'] = norm_df['iva_raw'].apply(parse_iva)
            import_df['pvp_final'] = ''
            import_df['unit'] = ''
            import_df['stock'] = ''
            import_df['company'] = ''

            # Generar CSV como respuesta descargable
            from django.http import HttpResponse
            import csv as _csv
            response = HttpResponse(content_type='text/csv')
            base_name = file.name.rsplit('.', 1)[0]
            response['Content-Disposition'] = f'attachment; filename="{base_name}_limpio.csv"'

            writer = _csv.writer(response)
            writer.writerow(list(import_df.columns))
            for _, r in import_df.iterrows():
                writer.writerow([r.get(col, '') for col in import_df.columns])

            return response

        # Paso 2: importar usando mapeo
        if action == 'import':
            import_logger.info(f"Usuario {request.user.username} iniciando proceso de importación")

            import_cols = request.session.get('import_cols')
            import_json = request.session.get('import_df')
            if not import_json or not import_cols:
                import_logger.error(f"Sesión de importación no encontrada para usuario {request.user.username}")
                messages.error(request, 'Sesión de importación no encontrada. Analice el archivo nuevamente.')
                return self.get(request, *args, **kwargs)

            df = pd.read_json(import_json)
            import_logger.info(f"DataFrame cargado desde sesión - Filas: {len(df)}, Columnas: {len(df.columns)}")

            # Dispatch por tipo de entidad
            entity_type = request.POST.get('entity_type', 'product')

            # --- Importar clientes ---
            if entity_type == 'client':
                from core.erp.models import Client
                map_names = request.POST.get('map_names')
                map_surnames = request.POST.get('map_surnames')
                map_dni = request.POST.get('map_dni')
                map_cuit_cuil = request.POST.get('map_cuit_cuil')
                map_email = request.POST.get('map_email')
                map_telefono = request.POST.get('map_telefono')
                map_address = request.POST.get('map_address')
                map_ciudad = request.POST.get('map_ciudad')
                map_provincia = request.POST.get('map_provincia')
                map_condicion_iva = request.POST.get('map_condicion_iva')

                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    active_cid = active_cid or getattr(request.user, 'company_id', None)

                created, updated = 0, 0
                errors = []
                iva_map = {'ri': 'RI', 'responsable inscripto': 'RI', 'm': 'M', 'monotributista': 'M',
                           'cf': 'CF', 'consumidor final': 'CF', 'ex': 'EX', 'exento': 'EX',
                           'nc': 'NC', 'no categorizado': 'NC'}

                for idx, row in df.iterrows():
                    try:
                        raw_names = row.get(map_names) if map_names else None
                        names = str(raw_names).strip() if raw_names is not None and not pd.isna(raw_names) else ''
                        if not names:
                            errors.append(f'Fila {idx+1}: Nombre vacío.')
                            continue

                        raw_dni = row.get(map_dni) if map_dni else None
                        dni = str(raw_dni).strip() if raw_dni is not None and not pd.isna(raw_dni) else ''
                        if not dni:
                            errors.append(f'Fila {idx+1}: DNI vacío.')
                            continue
                        if dni.endswith('.0'):
                            dni = dni[:-2]

                        surnames = ''
                        if map_surnames and not pd.isna(row.get(map_surnames)):
                            surnames = str(row.get(map_surnames)).strip()

                        cuit_cuil = ''
                        if map_cuit_cuil and not pd.isna(row.get(map_cuit_cuil)):
                            cuit_cuil = str(row.get(map_cuit_cuil)).strip()

                        email = ''
                        if map_email and not pd.isna(row.get(map_email)):
                            email = str(row.get(map_email)).strip()

                        telefono = ''
                        if map_telefono and not pd.isna(row.get(map_telefono)):
                            telefono = str(row.get(map_telefono)).strip()

                        address = ''
                        if map_address and not pd.isna(row.get(map_address)):
                            address = str(row.get(map_address)).strip()

                        ciudad = ''
                        if map_ciudad and not pd.isna(row.get(map_ciudad)):
                            ciudad = str(row.get(map_ciudad)).strip()

                        provincia = ''
                        if map_provincia and not pd.isna(row.get(map_provincia)):
                            provincia = str(row.get(map_provincia)).strip()

                        condicion_iva = 'CF'
                        if map_condicion_iva and not pd.isna(row.get(map_condicion_iva)):
                            iva_text = str(row.get(map_condicion_iva)).strip().lower()
                            condicion_iva = iva_map.get(iva_text, 'CF')

                        client = Client.objects.filter(dni=dni).first()
                        if client is None:
                            client = Client(
                                names=names, surnames=surnames, dni=dni,
                                cuit_cuil=cuit_cuil or None, email=email or None,
                                telefono=telefono or None, address=address or None,
                                ciudad=ciudad or None, provincia=provincia or None,
                                condicion_iva=condicion_iva, company_id=active_cid,
                            )
                            client.save()
                            created += 1
                        else:
                            client.names = names
                            if surnames: client.surnames = surnames
                            if cuit_cuil: client.cuit_cuil = cuit_cuil
                            if email: client.email = email
                            if telefono: client.telefono = telefono
                            if address: client.address = address
                            if ciudad: client.ciudad = ciudad
                            if provincia: client.provincia = provincia
                            client.condicion_iva = condicion_iva
                            if active_cid: client.company_id = active_cid
                            client.save()
                            updated += 1
                    except Exception as e:
                        errors.append(f'Fila {idx+1}: {e}')
                        import_logger.error(f"Error procesando cliente fila {idx+1}: {e}")

                ctx = {'result': True, 'created': created, 'updated': updated, 'errors': errors}
                for k in ('import_cols', 'import_df'):
                    request.session.pop(k, None)
                return self.render_to_response(ctx)

            # --- Importar proveedores ---
            if entity_type == 'supplier':
                from core.erp.models import Supplier
                map_name = request.POST.get('map_supplier_name')
                map_cuit = request.POST.get('map_supplier_cuit')
                map_address = request.POST.get('map_supplier_address')
                map_phone = request.POST.get('map_supplier_phone')
                map_email = request.POST.get('map_supplier_email')

                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    active_cid = active_cid or getattr(request.user, 'company_id', None)

                created, updated = 0, 0
                errors = []

                for idx, row in df.iterrows():
                    try:
                        raw_name = row.get(map_name) if map_name else None
                        name = str(raw_name).strip() if raw_name is not None and not pd.isna(raw_name) else ''
                        if not name:
                            errors.append(f'Fila {idx+1}: Nombre vacío.')
                            continue

                        cuit = ''
                        if map_cuit and not pd.isna(row.get(map_cuit)):
                            cuit = str(row.get(map_cuit)).strip()

                        address = ''
                        if map_address and not pd.isna(row.get(map_address)):
                            address = str(row.get(map_address)).strip()

                        phone = ''
                        if map_phone and not pd.isna(row.get(map_phone)):
                            phone = str(row.get(map_phone)).strip()

                        email = ''
                        if map_email and not pd.isna(row.get(map_email)):
                            email = str(row.get(map_email)).strip()

                        supplier = None
                        if cuit:
                            supplier = Supplier.objects.filter(cuit=cuit).first()
                        if supplier is None:
                            supplier = Supplier.objects.filter(name__iexact=name).first()

                        if supplier is None:
                            supplier = Supplier(
                                name=name, cuit=cuit or None, address=address or None,
                                phone=phone or None, email=email or None, company_id=active_cid,
                            )
                            supplier.save()
                            created += 1
                        else:
                            supplier.name = name
                            if cuit: supplier.cuit = cuit
                            if address: supplier.address = address
                            if phone: supplier.phone = phone
                            if email: supplier.email = email
                            if active_cid: supplier.company_id = active_cid
                            supplier.save()
                            updated += 1
                    except Exception as e:
                        errors.append(f'Fila {idx+1}: {e}')
                        import_logger.error(f"Error procesando proveedor fila {idx+1}: {e}")

                ctx = {'result': True, 'created': created, 'updated': updated, 'errors': errors}
                for k in ('import_cols', 'import_df'):
                    request.session.pop(k, None)
                return self.render_to_response(ctx)

            # --- Importar productos (default) ---
            # Mapeo desde POST
            map_name = request.POST.get('map_name')
            map_code = request.POST.get('map_code')
            map_cat = request.POST.get('map_cat')
            map_pvp = request.POST.get('map_pvp')
            map_iva = request.POST.get('map_iva_rate')
            map_pvp_final = request.POST.get('map_pvp_final')
            map_unit = request.POST.get('map_unit')
            map_stock = request.POST.get('map_stock')
            map_company = request.POST.get('map_company')

            def parse_number(val):
                """Parsea valores numéricos en formato argentino o internacional.
                Ej: '$ 5300,00' -> 5300.0, '4240,00' -> 4240.0, '21%' -> 21.0
                """
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    return None
                if isinstance(val, (int, float)) and not pd.isna(val):
                    return float(val)
                s = str(val).strip()
                if not s:
                    return None
                # Remover símbolos de moneda, espacios, y %
                s = s.replace('$', '').replace('€', '').replace('%', '').strip()
                # Si tiene punto como separador de miles y coma como decimal (formato AR)
                # Ej: '5.300,00' -> '5300.00'
                if ',' in s and '.' in s:
                    s = s.replace('.', '').replace(',', '.')
                elif ',' in s:
                    # Solo coma como separador decimal: '5300,00' -> '5300.00'
                    s = s.replace(',', '.')
                try:
                    return float(s)
                except ValueError:
                    return None

            import_logger.info(f"Mapeo de columnas - name: {map_name}, code: {map_code}, cat: {map_cat}, pvp: {map_pvp}, stock: {map_stock}")

            # Validar que los campos mínimos estén mapeados
            missing_fields = []
            # El código ya no es obligatorio ya que se puede generar automáticamente
            if not map_name:
                missing_fields.append("Nombre")
            if not map_pvp:
                missing_fields.append("Precio")
            if not map_stock:
                missing_fields.append("Stock")
                
            if missing_fields:
                import_logger.error(f"Campos obligatorios no mapeados: {', '.join(missing_fields)}")
                messages.error(request, f'Debe mapear los campos obligatorios: {", ".join(missing_fields)}')
                return self.get(request, *args, **kwargs)
            active_cid = request.session.get('company_id')
            if not request.user.is_superuser:
                active_cid = active_cid or getattr(request.user, 'company_id', None)
            created, updated = 0, 0
            errors = []
            unit_choices = dict(Product.UNIT_CHOICES)

            # Pre-cargar productos existentes por código para evitar duplicados y reducir queries
            codes_in_file = set()
            for _, row in df.iterrows():
                val = row.get(map_code)
                if pd.isna(val):
                    continue
                code_val = str(val).strip()
                if code_val:
                    codes_in_file.add(code_val)

            existing_products = Product.objects.filter(code__in=codes_in_file)
            products_by_code = {p.code: p for p in existing_products}
            
            # Función para generar código automático si está vacío
            def generate_auto_code(name, company_id=None):
                """Genera código automático basado en el nombre y empresa"""
                import re
                # Limpiar el nombre: remover caracteres especiales y espacios
                clean_name = re.sub(r'[^a-zA-Z0-9]', '', str(name).upper())
                # Tomar primeras 6 letras del nombre limpio
                prefix = clean_name[:6] if clean_name else 'PROD'
                
                # Buscar el próximo número correlativo para este prefijo
                base_query = Product.objects.filter(code__startswith=prefix)
                if company_id:
                    base_query = base_query.filter(company_id=company_id)
                
                # Encontrar el mayor número existente para este prefijo
                existing_codes = base_query.values_list('code', flat=True)
                max_num = 0
                for code in existing_codes:
                    try:
                        # Extraer número del código (formato: PREFIX001)
                        suffix = code[len(prefix):]
                        if suffix.isdigit():
                            num = int(suffix)
                            if num > max_num:
                                max_num = num
                    except:
                        continue
                
                # Generar nuevo código con 3 dígitos
                new_num = max_num + 1
                return f"{prefix}{new_num:03d}"

            # Pre-cargar categorías por nombre y empresa
            cat_names = set()
            if map_cat:
                for _, row in df.iterrows():
                    if pd.isna(row.get(map_cat)):
                        continue
                    cname = str(row[map_cat]).strip()
                    if cname:
                        cat_names.add(cname)
            
            # Buscar categorías existentes por nombre y empresa activa
            existing_cats = Category.objects.filter(name__in=cat_names)
            if active_cid:
                existing_cats = existing_cats.filter(company_id=active_cid)
            cats_by_name = {c.name: c for c in existing_cats}

            for idx, row in df.iterrows():
                try:
                    # Código: si está vacío, generar automático; si tiene valor, limpiar .0
                    raw_code = row.get(map_code)
                    code = None
                    
                    if pd.isna(raw_code) or str(raw_code).strip() == '':
                        # Generar código automático usando el nombre
                        raw_name_for_code = row.get(map_name)
                        name_for_code = str(raw_name_for_code).strip() if not pd.isna(raw_name_for_code) else ''
                        if not name_for_code:
                            errors.append(f'Fila {idx+1}: Nombre vacío (necesario para generar código automático).')
                            continue
                        code = generate_auto_code(name_for_code, active_cid)
                        import_logger.info(f"Fila {idx+1}: Código generado automáticamente: {code}")
                    else:
                        # Limpiar el código: convertir a string y remover .0 si es numérico
                        code = str(raw_code).strip()
                        # Si termina en .0, removerlo (ej: "123.0" -> "123")
                        if code.endswith('.0'):
                            code = code[:-2]
                        # Asegurar que no tenga decimales
                        if '.' in code:
                            parts = code.split('.')
                            if len(parts) == 2 and parts[1] == '0':
                                code = parts[0]

                    # Nombre obligatorio
                    raw_name = row.get(map_name)
                    name = str(raw_name).strip() if not pd.isna(raw_name) else ''
                    if not name:
                        errors.append(f'Fila {idx+1}: Nombre vacío.')
                        continue

                    # Precio obligatorio
                    raw_pvp = row.get(map_pvp)
                    if pd.isna(raw_pvp):
                        errors.append(f'Fila {idx+1}: Precio vacío.')
                        continue
                    pvp = parse_number(raw_pvp)
                    if pvp is None:
                        errors.append(f'Fila {idx+1}: Precio no numérico ({raw_pvp}).')
                        continue

                    # Stock obligatorio
                    raw_stock = row.get(map_stock)
                    if pd.isna(raw_stock):
                        errors.append(f'Fila {idx+1}: Stock vacío.')
                        continue
                    stock = parse_number(raw_stock)
                    if stock is None:
                        errors.append(f'Fila {idx+1}: Stock no numérico ({raw_stock}).')
                        continue

                    # Campos opcionales
                    iva_rate = 0  # Default: 0 (exento / no gravado)
                    if map_iva and not pd.isna(row.get(map_iva)):
                        parsed = parse_number(row.get(map_iva))
                        if parsed is not None:
                            iva_rate = parsed
                        else:
                            # Mapear valores de texto comunes de IVA
                            iva_text = str(row.get(map_iva)).strip().lower()
                            iva_map = {'exento': 0, 'exenta': 0, 'no gravado': 0,
                                       'no gravada': 0, '0': 0, '21': 0.21, '21%': 0.21,
                                       '10.5': 0.105, '10.5%': 0.105, '27': 0.27, '27%': 0.27,
                                       'iva 21': 0.21, 'iva 10.5': 0.105, 'iva 27': 0.27,
                                       'responsable inscripto': 0.21}
                            iva_rate = iva_map.get(iva_text, 0)  # Default 0 si no se reconoce

                    pvp_final = None
                    if map_pvp_final and not pd.isna(row.get(map_pvp_final)):
                        pvp_final = parse_number(row.get(map_pvp_final))
                        if pvp_final is None:
                            errors.append(f'Fila {idx+1}: Precio final no numérico ({row.get(map_pvp_final)}), se ignora.')

                    unit = 'unit'
                    if map_unit and not pd.isna(row.get(map_unit)):
                        unit_val = str(row.get(map_unit)).strip().lower()
                        unit = unit_val if unit_val in unit_choices else 'unit'

                    cat = None
                    if map_cat and not pd.isna(row.get(map_cat)):
                        cat_name = str(row.get(map_cat)).strip()
                        if cat_name:
                            cat = cats_by_name.get(cat_name)
                            if not cat:
                                # Crear categoría con empresa activa
                                cat, _ = Category.objects.get_or_create(
                                    name=cat_name,
                                    company_id=active_cid
                                )
                                cats_by_name[cat_name] = cat

                    comp_name = None
                    if map_company and not pd.isna(row.get(map_company)):
                        comp_name = str(row.get(map_company)).strip()

                    # Resolver empresa: por nombre, empresa activa o empresa del usuario
                    company_id = active_cid
                    if comp_name:
                        comp = Company.objects.filter(name__iexact=comp_name).first()
                        if comp:
                            company_id = comp.id
                    else:
                        # Si no hay empresa en el archivo, usar la empresa del usuario
                        if not company_id and hasattr(request.user, 'company') and request.user.company:
                            company_id = request.user.company.id
                            import_logger.info(f"Fila {idx+1}: Asignando empresa del usuario {request.user.username} (ID: {company_id})")
                        elif not company_id:
                            import_logger.warning(f"Fila {idx+1}: No se pudo determinar empresa para el producto '{code}'")

                    # Upsert por código
                    prod = products_by_code.get(code)
                    if prod is None:
                        prod = Product(
                            code=code,
                            name=name,
                            cat=cat or Category.objects.first(),
                            pvp=pvp,
                            unit=unit,
                            stock=stock,
                            company_id=company_id,
                            synced_to_server=False,  # Marcar para sincronizar
                        )
                        if iva_rate is not None:
                            prod.iva_rate = iva_rate
                        # Solo asignar pvp_final si se proporcionó un valor
                        if pvp_final is not None:
                            prod.pvp_final = pvp_final
                        prod.save()
                        products_by_code[code] = prod
                        created += 1
                    else:
                        if name:
                            prod.name = name
                        if cat:
                            prod.cat = cat
                        prod.pvp = pvp
                        if iva_rate is not None:
                            prod.iva_rate = iva_rate
                        # Solo actualizar pvp_final si se proporcionó un valor
                        if pvp_final is not None:
                            prod.pvp_final = pvp_final
                        prod.unit = unit
                        prod.stock = stock
                        prod.stock_modified_locally = timezone.now()  # Marcar modificación de stock
                        if company_id:
                            prod.company_id = company_id
                        elif not prod.company_id and hasattr(request.user, 'company') and request.user.company:
                            # Si el producto no tiene empresa y el usuario sí, asignar la del usuario
                            prod.company_id = request.user.company.id
                            import_logger.info(f"Fila {idx+1}: Actualizando producto '{code}' con empresa del usuario {request.user.username} (ID: {request.user.company.id})")
                        prod.synced_to_server = False  # Marcar para sincronizar stock actualizado
                        prod.save()
                        updated += 1
                except Exception as e:
                    errors.append(f'Fila {idx+1}: {e}')
                    import_logger.error(f"Error procesando fila {idx+1}: {e}")
            
            # Registrar resultados finales en log
            import_logger.info(f"Importación finalizada - Usuario: {request.user.username}")
            import_logger.info(f"Resultados - Creados: {created}, Actualizados: {updated}, Errores: {len(errors)}")
            
            # Mensaje informativo sobre asignación de empresas
            if hasattr(request.user, 'company') and request.user.company:
                messages.info(request, f'Los productos sin empresa especificada se asignaron automáticamente a: {request.user.company.name}')
            
            # Sincronización automática en modo servidor
            if ServerSyncService.is_server_mode():
                try:
                    # Obtener empresas que tienen productos en esta importación
                    companies_with_products = set()
                    for _, row in df.iterrows():
                        comp_name = None
                        if map_company and not pd.isna(row.get(map_company)):
                            comp_name = str(row.get(map_company)).strip()
                        
                        if comp_name:
                            comp = Company.objects.filter(name__iexact=comp_name).first()
                            if comp:
                                companies_with_products.add(comp.id)
                        else:
                            # Usar empresa del usuario o activa
                            company_id = active_cid
                            if not company_id and hasattr(request.user, 'company') and request.user.company:
                                company_id = request.user.company.id
                            if company_id:
                                companies_with_products.add(company_id)
                    
                    # Sincronizar productos para cada empresa
                    sync_results = []
                    for company_id in companies_with_products:
                        success, message = ServerSyncService.sync_products_for_company(company_id)
                        sync_results.append(f"Empresa {company_id}: {message}")
                    
                    if sync_results:
                        sync_message = "Sincronización con servidor: " + "; ".join(sync_results)
                        messages.info(request, sync_message)
                        import_logger.info(f"Sincronización completada: {sync_message}")
                
                except Exception as e:
                    error_msg = f"Error en sincronización automática: {e}"
                    messages.warning(request, error_msg)
                    import_logger.error(error_msg)
            
            ctx = {
                'result': True,
                'created': created,
                'updated': updated,
                'errors': errors,
            }
            # Limpiar sesión
            for k in ('import_cols', 'import_df'):
                request.session.pop(k, None)
            return self.render_to_response(ctx)

    def import_from_server(self, request):
        """Importar productos desde el servidor remoto usando sync_products_safe"""
        from django.core.management import call_command
        from core.erp.models import Product, Company
        import io
        import sys
        from contextlib import redirect_stdout
        
        try:
            # Obtener empresa del usuario
            user = request.user
            if not hasattr(user, 'company') or not user.company:
                return JsonResponse({
                    'success': False,
                    'message': 'El usuario no tiene una empresa asignada'
                })
            
            company = user.company
            
            # Obtener conteo antes de sincronizar
            local_count_before = Product.objects.filter(company=company).count()
            
            # Ejecutar sync_products_safe con parámetro de empresa
            captured_output = io.StringIO()
            with redirect_stdout(captured_output):
                call_command("sync_products_safe", "--company-id", str(company.id))
            
            output = captured_output.getvalue()
            
            # Obtener conteo después de sincronizar
            local_count_after = Product.objects.filter(company=company).count()
            new_products = local_count_after - local_count_before
            
            # Obtener productos recién importados (con server_product_id)
            imported_products = Product.objects.filter(
                company=company,
                server_product_id__isnull=False
            ).values('id', 'name', 'code', 'pvp', 'stock', 'unit')
            
            products_list = []
            for product in imported_products:
                products_list.append({
                    'server_id': product['id'],
                    'name': product['name'],
                    'code': product['code'] or '',
                    'pvp': float(product['pvp']),
                    'stock': float(product['stock']),
                    'unit': product['unit']
                })
            
            return JsonResponse({
                'success': True,
                'products': products_list,
                'message': f'Sincronización completada para {company.name}. {new_products} productos nuevos importados.',
                'output': output,
                'stats': {
                    'before': local_count_before,
                    'after': local_count_after,
                    'new': new_products,
                    'company': company.name
                }
            })
            
        except Exception as e:
            # Log detallado del error
            import traceback
            error_details = f"Error: {str(e)}\nTipo: {type(e).__name__}\nTraceback: {traceback.format_exc()}"
            print(f"ERROR IMPORT FROM SERVER: {error_details}")
            
            return JsonResponse({
                'success': False,
                'message': f'Error al sincronizar productos: {str(e)}',
                'error_type': type(e).__name__,
                'debug_info': error_details if settings.DEBUG else None
            })

    def clone_server_products(self, request):
        """Clonar productos seleccionados del servidor"""
        from django.db import connections, transaction
        from core.erp.models import Product, Category, Company
        import json
        
        try:
            data = json.loads(request.body)
            selected_products = data.get('products', [])
            
            if not selected_products:
                return JsonResponse({
                    'success': False,
                    'message': 'No se seleccionaron productos'
                })
            
            user = request.user
            company = user.company
            
            created_count = 0
            errors = []
            
            with transaction.atomic():
                for product_id in selected_products:
                    try:
                        # Obtener producto del servidor
                        with connections['remote'].cursor() as cursor:
                            cursor.execute("""
                                SELECT id, name, code, pvp, pvp_final, cost_price, unit, stock, 
                                       min_stock, iva_rate, cat_id
                                FROM erp_product 
                                WHERE id = %s AND company_id = %s
                            """, [product_id, company.id])
                            server_product = cursor.fetchone()
                        
                        if not server_product:
                            errors.append(f'Producto ID {product_id} no encontrado en servidor')
                            continue
                        
                        # Obtener o crear categoría
                        cat = None
                        if server_product[10]:  # cat_id
                            cat, created = Category.objects.get_or_create(
                                id=server_product[10],
                                company=company,
                                defaults={'name': f'Categoría {server_product[10]}'}
                            )
                        
                        # Crear producto local
                        Product.objects.create(
                            company=company,
                            cat=cat,
                            name=server_product[1],
                            code=server_product[2] or '',
                            pvp=server_product[3],
                            pvp_final=server_product[4],
                            cost_price=server_product[5] or 0,
                            unit=server_product[6],
                            stock=server_product[7],
                            min_stock=server_product[8] or 5,
                            iva_rate=server_product[9],
                            server_product_id=server_product[0],
                            synced_from_server=True,
                            synced_to_server=True,  # Marcar como sincronizado para no volver a subirlo
                            track_stock=True
                        )
                        
                        created_count += 1
                        
                    except Exception as e:
                        errors.append(f'Error al crear producto ID {product_id}: {str(e)}')
            
            return JsonResponse({
                'success': True,
                'created': created_count,
                'errors': errors,
                'message': f'Se importaron {created_count} productos correctamente'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al importar productos: {str(e)}'
            })


class ProductDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    model = Product
    template_name = 'product/delete.html'
    success_url = reverse_lazy('erp:product_list')
    permission_required = 'erp.delete_product'
    url_redirect = success_url


    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.user.is_superuser:
            return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            self.object.delete()
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Eliminación de un Producto'
        context['entity'] = 'Productos'
        context['list_url'] = reverse_lazy('erp:product_list')
        return context
