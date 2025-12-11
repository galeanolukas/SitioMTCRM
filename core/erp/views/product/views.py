from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView

import json

try:
    import pandas as pd
except Exception:
    pd = None

from core.erp.forms import ProductForm
from core.erp.models import Product, Category, Company
from core.erp.mixins import ValidatePermissionRequiredMixin

try:
    import mercadopago
except Exception:
    mercadopago = None


@method_decorator(csrf_exempt, name='dispatch')
class ProductListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
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
                    data.append(i.toJSON())
                print(f"DEBUG Product: Returning {len(data)} products")
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
        ctx['products'] = qs.order_by('cat__name', 'name')
        ctx['categories'] = Category.objects.all().order_by('name')
        ctx['title'] = 'Etiquetas QR de Productos'
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
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if pd is None:
            messages.error(request, 'Pandas no está instalado. Ejecuta: pip install pandas openpyxl')
            return self.get(request, *args, **kwargs)
        action = request.POST.get('action')
        # Paso 1: analizar columnas y mostrar mapeo (archivo "limpio")
        if action == 'analyze':
            file = request.FILES.get('file')
            if not file:
                messages.error(request, 'Debe seleccionar un archivo CSV o Excel')
                return self.get(request, *args, **kwargs)
            try:
                if file.name.lower().endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file)
                else:
                    sep = request.POST.get('sep') or ','
                    df = pd.read_csv(file, sep=sep)
            except Exception as e:
                messages.error(request, f'No se pudo leer el archivo: {e}')
                return self.get(request, *args, **kwargs)

            columns = list(df.columns)
            request.session['import_df'] = df.to_json(orient='records')
            request.session['import_cols'] = columns
            ctx = {
                'columns': columns,
                'unit_choices': Product.UNIT_CHOICES,
                'fields': ['name', 'code', 'cat', 'pvp', 'iva_rate', 'pvp_final', 'unit', 'stock', 'company'],
            }
            return self.render_to_response(ctx)

        # Paso 1b: analizar lista de proveedor y devolver CSV limpio para completar
        if action == 'analyze_supplier':
            file = request.FILES.get('file')
            if not file:
                messages.error(request, 'Debe seleccionar un archivo CSV o Excel')
                return self.get(request, *args, **kwargs)
            if pd is None:
                messages.error(request, 'Pandas no está instalado. Ejecuta: pip install pandas openpyxl')
                return self.get(request, *args, **kwargs)
            try:
                if file.name.lower().endswith(('.xlsx', '.xls')):
                    raw_df = pd.read_excel(file, header=None)
                else:
                    sep = request.POST.get('sep') or ','
                    raw_df = pd.read_csv(file, sep=sep, header=None)
            except Exception as e:
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
            if file.name.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file, header=header_row)
            else:
                sep = request.POST.get('sep') or ','
                df = pd.read_csv(file, sep=sep, header=header_row)

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
            import_cols = request.session.get('import_cols')
            import_json = request.session.get('import_df')
            if not import_json or not import_cols:
                messages.error(request, 'Sesión de importación no encontrada. Analice el archivo nuevamente.')
                return self.get(request, *args, **kwargs)
            df = pd.read_json(import_json)
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

            # Validar que los campos mínimos estén mapeados
            if not map_code or not map_name or not map_pvp or not map_stock:
                messages.error(request, 'Debe mapear al menos las columnas de Código, Nombre, Precio y Stock.')
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

            # Pre-cargar categorías por nombre
            cat_names = set()
            if map_cat:
                for _, row in df.iterrows():
                    if pd.isna(row.get(map_cat)):
                        continue
                    cname = str(row[map_cat]).strip()
                    if cname:
                        cat_names.add(cname)
            existing_cats = Category.objects.filter(name__in=cat_names)
            cats_by_name = {c.name: c for c in existing_cats}

            for idx, row in df.iterrows():
                try:
                    # Código obligatorio
                    raw_code = row.get(map_code)
                    if pd.isna(raw_code):
                        errors.append(f'Fila {idx+1}: Código vacío.')
                        continue
                    code = str(raw_code).strip()
                    if not code:
                        errors.append(f'Fila {idx+1}: Código vacío.')
                        continue

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
                    try:
                        pvp = float(raw_pvp)
                    except Exception:
                        errors.append(f'Fila {idx+1}: Precio no numérico.')
                        continue

                    # Stock obligatorio
                    raw_stock = row.get(map_stock)
                    if pd.isna(raw_stock):
                        errors.append(f'Fila {idx+1}: Stock vacío.')
                        continue
                    try:
                        stock = float(raw_stock)
                    except Exception:
                        errors.append(f'Fila {idx+1}: Stock no numérico.')
                        continue

                    # Campos opcionales
                    iva_rate = None
                    if map_iva and not pd.isna(row.get(map_iva)):
                        try:
                            iva_rate = float(row.get(map_iva))
                        except Exception:
                            errors.append(f'Fila {idx+1}: IVA no numérico, se ignora.')

                    pvp_final = None
                    if map_pvp_final and not pd.isna(row.get(map_pvp_final)):
                        try:
                            pvp_final = float(row.get(map_pvp_final))
                        except Exception:
                            errors.append(f'Fila {idx+1}: Precio final no numérico, se ignora.')

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
                                cat, _ = Category.objects.get_or_create(name=cat_name)
                                cats_by_name[cat_name] = cat

                    comp_name = None
                    if map_company and not pd.isna(row.get(map_company)):
                        comp_name = str(row.get(map_company)).strip()

                    # Resolver empresa: por nombre o empresa activa
                    company_id = active_cid
                    if comp_name:
                        comp = Company.objects.filter(name__iexact=comp_name).first()
                        if comp:
                            company_id = comp.id

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
                        )
                        if iva_rate is not None:
                            prod.iva_rate = iva_rate
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
                        if pvp_final is not None:
                            prod.pvp_final = pvp_final
                        prod.unit = unit
                        prod.stock = stock
                        if company_id:
                            prod.company_id = company_id
                        prod.save()
                        updated += 1
                except Exception as e:
                    errors.append(f'Fila {idx+1}: {e}')
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

        return HttpResponse(status=400)



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
