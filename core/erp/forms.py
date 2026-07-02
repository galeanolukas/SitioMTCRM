from django.forms import *
from django.forms.widgets import CheckboxInput
from datetime import datetime
from django.core.exceptions import ValidationError
from core.erp.models import Category, Product, Client, Sale, Company, Supplier, Expense, MercadoPagoConfig, AutoSyncConfig, InternalTransfer, InternalTransferDetail, RemitoEntrada, Remito

from django.contrib.auth.forms import AuthenticationForm


class CategoryForm(ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            if form.name != 'company':
                form.field.widget.attrs["class"] = "form-control"
                form.field.widget.attrs["autocomplete"] = "off"
        self.fields["name"].widget.attrs["autofocus"] = True
        
        # Manejar campo company según usuario
        if 'company' in self.fields and self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
            if getattr(self.request.user, 'company_id', None):
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id, is_active=True)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False
        elif 'company' in self.fields:
            # Para superusuarios, mostrar solo empresas activas
            self.fields['company'].queryset = Company.objects.filter(is_active=True)

    class Meta:
        model = Category
        fields = "__all__"
        widgets = {
            "name": TextInput(
                attrs={
                    "placeholder": "Ingrese un nombre",
                }
            ),
            "desc": Textarea(
                attrs={"placeholder": "Ingrese una descripción", "rows": 3, "cols": 3}
            ),
        }
        exclude = ['user_updated', 'user_creation']

    def save(self, commit=True):
        data = {}
        form = super()
        try:
            if form.is_valid():
                obj = form.save(commit=False)
                # Asignar empresa automáticamente si no tiene
                if self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
                    if getattr(self.request.user, 'company_id', None) and not getattr(obj, 'company_id', None):
                        obj.company_id = self.request.user.company_id
                if commit:
                    obj.save()
                data = obj.toJSON() if hasattr(obj, 'toJSON') else {}
            else:
                data["error"] = form.errors
        except Exception as e:
            data["error"] = str(e)
        return data

class AuthenticationFormWithFormControl(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs["class"] = "form-control"
            form.field.widget.attrs["autocomplete"] = "off"

class ProductForm(ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            if form.name not in ("cat", "supplier"):
                form.field.widget.attrs["class"] = "form-control"
                form.field.widget.attrs["autocomplete"] = "off"
        self.fields['name'].widget.attrs['autofocus'] = True
        # supplier opcional
        if 'supplier' in self.fields:
            self.fields['supplier'].required = False
            self.fields['supplier'].empty_label = '--- Sin proveedor ---'
        
        # Filtrar categorías por empresa
        if 'cat' in self.fields:
            if self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
                active_cid = self.request.session.get('company_id') or getattr(self.request.user, 'company_id', None)
                if active_cid:
                    self.fields['cat'].queryset = Category.objects.filter(company_id=active_cid)
                else:
                    self.fields['cat'].queryset = Category.objects.none()
            else:
                # Para superusuarios, mostrar todas las categorías
                self.fields['cat'].queryset = Category.objects.all()
        
        if 'company' in self.fields and self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
            if getattr(self.request.user, 'company_id', None):
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id, is_active=True)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False
        elif 'company' in self.fields:
            # Para superusuarios, mostrar solo empresas activas
            self.fields['company'].queryset = Company.objects.filter(is_active=True)

    class Meta:
        model = Product
        # Ocultamos synced_to_server del formulario; es un flag interno de sync.
        fields = [
            'company',
            'name',
            'code',
            'codigo_proveedor',
            'descripcion',
            'qr_token',
            'cat',
            'supplier',
            'image',
            'cost_price',
            'pvp',
            'iva_rate',
            'margin_percentage',
            'pvp_final',
            'unit',
            'stock',
        ]
        widgets = {
            'name': TextInput(
                attrs={
                    'placeholder': 'Ingrese un nombre',
                }
            ),
            'cat': Select(
                attrs={
                    'class': 'select2',
                    'style': 'width: 100%'
                }
            ),
            'supplier': Select(
                attrs={
                    'class': 'select2',
                    'style': 'width: 100%'
                }
            ),
        }

    def clean_cost_price(self):
        cost_price = self.cleaned_data.get('cost_price')
        if cost_price is not None and cost_price != '':
            # Si ya es Decimal, redondearlo directamente
            from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
            if isinstance(cost_price, Decimal):
                # Redondear a 2 decimales en lugar de rechazar
                rounded_price = cost_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                return rounded_price
            
            try:
                # Limpiar el valor de entrada
                cleaned_value = str(cost_price).strip()
                # Remover caracteres no numéricos excepto punto y coma
                import re
                cleaned_value = re.sub(r'[^0-9.,]', '', cleaned_value)
                # Reemplazar coma por punto para estandarizar
                cleaned_value = cleaned_value.replace(',', '.')
                
                if not cleaned_value or cleaned_value == '.':
                    return Decimal('0.00')
                
                price = Decimal(cleaned_value)
                
                # Redondear a 2 decimales en lugar de rechazar
                rounded_price = price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                
                return rounded_price
            except (ValueError, TypeError, InvalidOperation) as e:
                raise ValidationError('Ingrese un valor numérico válido para el precio de costo.')
        return cost_price

    def clean_pvp(self):
        pvp = self.cleaned_data.get('pvp')
        if pvp is not None and pvp != '':
            try:
                from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
                price = Decimal(str(pvp).replace(',', '.'))
                # Redondear a 2 decimales en lugar de rechazar
                rounded_price = price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                return rounded_price
            except (ValueError, TypeError, InvalidOperation) as e:
                raise ValidationError('Ingrese un valor numérico válido para el precio neto.')
        return pvp

    def clean_pvp_final(self):
        pvp_final = self.cleaned_data.get('pvp_final')
        if pvp_final is not None and pvp_final != '':
            try:
                from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
                price = Decimal(str(pvp_final).replace(',', '.'))
                # Redondear a 2 decimales
                rounded_price = price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                return rounded_price
            except (ValueError, TypeError, InvalidOperation) as e:
                raise ValidationError('Ingrese un valor numérico válido para el precio final.')
        return pvp_final

    def clean_stock(self):
        stock = self.cleaned_data.get('stock')
        if stock is not None and stock != '':
            try:
                from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
                qty = Decimal(str(stock).replace(',', '.'))
                # Redondear a 2 decimales en lugar de rechazar
                rounded_qty = qty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                return rounded_qty
            except (ValueError, TypeError, InvalidOperation) as e:
                raise ValidationError('Ingrese un valor numérico válido para el stock.')
        return stock

    
    def save(self, commit=True):
         data = {}
         form = super()
         try:
             if form.is_valid():
                 obj = form.save(commit=False)
                 if self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
                     if getattr(self.request.user, 'company_id', None) and not getattr(obj, 'company_id', None):
                         obj.company_id = self.request.user.company_id
                 if commit:
                     obj.save()
                 try:
                     data = obj.toJSON() if hasattr(obj, 'toJSON') else {}
                 except Exception as json_error:
                     print('ERROR EN toJSON:', str(json_error))
                     data = {'id': obj.id, 'name': obj.name}
             else:
                 print('ERRORES DEL FORMULARIO:', form.errors)
                 data['error'] = form.errors
         except Exception as e:
             print('EXCEPCIÓN EN SAVE:', str(e))
             data['error'] = str(e)
         return data

class ClientForm(ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            if form.name != 'is_active':  # No aplicar form-control al checkbox
                form.field.widget.attrs["class"] = "form-control"
            form.field.widget.attrs["autocomplete"] = "off"
        self.fields['names'].widget.attrs['autofocus'] = True
        if 'company' in self.fields and self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
            if getattr(self.request.user, 'company_id', None):
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id, is_active=True)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False
        elif 'company' in self.fields:
            # Para superusuarios, mostrar solo empresas activas
            self.fields['company'].queryset = Company.objects.filter(is_active=True)

    class Meta:
        model = Client
        fields = '__all__'
        exclude = ['synced_to_server', 'user_updated', 'user_creation']
        widgets = {
            'names': TextInput(
                attrs={
                    'placeholder': 'Ingrese sus nombres',
                }
            ),
            'surnames': TextInput(
                attrs={
                    'placeholder': 'Ingrese sus apellidos',
                }
            ),
            'dni': TextInput(
                attrs={
                    'placeholder': 'Ingrese su dni',
                    
                }
            ),
            'date_birthday': DateInput(format='%d/%m/%Y',
                attrs={
                    'value': datetime.now().strftime('%d-%m-%Y'),
                    'type': 'date',
                }
            ),
            'address': TextInput(
                attrs={
                    'placeholder': 'Ingrese su dirección',
                }
            ),
            'gender': Select(),
            'is_active': CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def save(self, commit=True):
        data = {}
        form = super()
        try:
            if form.is_valid():
                obj = form.save(commit=False)
                if self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
                    if getattr(self.request.user, 'company_id', None) and not getattr(obj, 'company_id', None):
                        obj.company_id = self.request.user.company_id
                if commit:
                    obj.save()
                data = obj.toJSON() if hasattr(obj, 'toJSON') else {}
            else:
                data['error'] = form.errors
        except Exception as e:
            data['error'] = str(e)
        return data


class SupplierForm(ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs["class"] = "form-control"
            form.field.widget.attrs["autocomplete"] = "off"
        self.fields['name'].widget.attrs['autofocus'] = True
        
        # Ocultar campos de sistema
        if 'is_active' in self.fields:
            self.fields['is_active'].widget = HiddenInput()
            self.fields['is_active'].required = False
        if 'synced_to_server' in self.fields:
            self.fields['synced_to_server'].widget = HiddenInput()
            self.fields['synced_to_server'].required = False
            
        if 'company' in self.fields and self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
            if getattr(self.request.user, 'company_id', None):
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id, is_active=True)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False
        elif 'company' in self.fields:
            # Para superusuarios, mostrar solo empresas activas
            self.fields['company'].queryset = Company.objects.filter(is_active=True)

    class Meta:
        model = Supplier
        fields = '__all__'
        widgets = {
            'name': TextInput(attrs={'placeholder': 'Nombre proveedor'}),
            'cuit': TextInput(attrs={'placeholder': 'CUIT'}),
            'address': TextInput(attrs={'placeholder': 'Dirección'}),
            'phone': TextInput(attrs={'placeholder': 'Teléfono'}),
            'email': EmailInput(attrs={'placeholder': 'Email'}),
        }

    def save(self, commit=True):
        data = {}
        form = super()
        try:
            if form.is_valid():
                obj = form.save(commit=False)
                if self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
                    if getattr(self.request.user, 'company_id', None) and not getattr(obj, 'company_id', None):
                        obj.company_id = self.request.user.company_id
                if commit:
                    obj.save()
                data = obj.toJSON() if hasattr(obj, 'toJSON') else {}
            else:
                data['error'] = form.errors
        except Exception as e:
            data['error'] = str(e)
        return data

class SaleForm(ModelForm):

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if 'cli' in self.fields:
            self.fields['cli'].empty_label = 'Anónimo'
            self.fields['cli'].required = False
        if 'company' in self.fields and self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
            if getattr(self.request.user, 'company_id', None):
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id, is_active=True)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False
        elif 'company' in self.fields:
            # Para superusuarios, mostrar solo empresas activas
            self.fields['company'].queryset = Company.objects.filter(is_active=True)

    class Meta:
        model = Sale
        fields = '__all__'
        widgets = {
            'cli': Select(
                attrs={
                    'class': 'select2',
                    'style': 'width: 100%'
                }
            ),
            'iva': TextInput(attrs={
                    'class': 'form-control',
            }),
            'date_joined': TextInput(attrs={
                    'autocomplete': 'off',
                    'class': 'form-control datetimepicker-input',
                    'id': 'date_joined',
                    'data-target': '#date_joined',
                    'data-toggle': 'datetimepicker'
            }),
            'subtotal': TextInput(attrs={
                    'readonly': True,
                    'class': 'form-control',
            }),
            'total': TextInput(attrs={
                    'readonly': True,
                    'class': 'form-control',
            }),
            'payment_method': Select(
                attrs={
                    'class': 'form-control',
                }
            ),
        }

class CompanyForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs["class"] = "form-control"
            form.field.widget.attrs["autocomplete"] = "off"
        self.fields['name'].widget.attrs['autofocus'] = True

    class Meta:
        model = Company
        # Solo mostrar campos relevantes para el usuario; los flags internos
        # como synced_to_server e is_active se manejan en la lógica de sync.
        fields = [
            'name',
            'address',
            'cuit',
            'iibb',
            'start',
            'pos',
            'phone',
            'email',
            'logo',
            'logo_round',
            'custom_title',
            'logo_remote_url',
        ]

class MercadoPagoConfigForm(ModelForm):
    class Meta:
        model = MercadoPagoConfig
        fields = ['company', 'name', 'access_token', 'public_key', 'mode']  # Eliminado 'enabled'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.visible_fields():
            f.field.widget.attrs['class'] = 'form-control'
            f.field.widget.attrs['autocomplete'] = 'off'
        # company solo lectura en este formulario
        if 'company' in self.fields:
            self.fields['company'].disabled = True



class MercadoPagoConfigForm(ModelForm):
    class Meta:
        model = MercadoPagoConfig
        fields = ['company', 'name', 'access_token', 'public_key', 'mode']  # Eliminado 'enabled'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.visible_fields():
            f.field.widget.attrs['class'] = 'form-control'
            f.field.widget.attrs['autocomplete'] = 'off'
        # company solo lectura en este formulario
        if 'company' in self.fields:
            self.fields['company'].disabled = True


class ExpenseForm(ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Establecer fecha por defecto a hoy si no hay valor inicial
        if not self.initial.get('date') and not self.instance.pk:
            from django.utils import timezone
            self.initial['date'] = timezone.now().date()
        
        # Configurar el widget de fecha para mostrar la fecha actual
        if 'date' in self.fields:
            from django.utils import timezone
            self.fields['date'].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })
        
        # Establecer hora por defecto a la actual si no hay valor inicial
        if not self.initial.get('time') and not self.instance.pk:
            from django.utils import timezone
            self.initial['time'] = timezone.now().time()
        
        # Configurar el widget de hora
        if 'time' in self.fields:
            self.fields['time'].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })
            self.fields['time'].required = False
        
        # Establecer usuario actual como valor por defecto en 'pagado por'
        if 'payer' in self.fields and self.request and hasattr(self.request, 'user'):
            if not self.initial.get('payer') and not self.instance.pk:
                user = self.request.user
                full_name = user.get_full_name().strip()
                if full_name:
                    self.initial['payer'] = full_name
                else:
                    self.initial['payer'] = user.username
        
        for f in self.visible_fields():
            if f.name not in ('supplier', 'date', 'time'):
                f.field.widget.attrs['class'] = 'form-control'
                f.field.widget.attrs['autocomplete'] = 'off'
        if 'supplier' in self.fields:
            self.fields['supplier'].required = False
            self.fields['supplier'].empty_label = '--- Sin proveedor ---'
        if 'company' in self.fields and self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
            if getattr(self.request.user, 'company_id', None):
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id, is_active=True)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False
        elif 'company' in self.fields:
            # Para superusuarios, mostrar solo empresas activas
            self.fields['company'].queryset = Company.objects.filter(is_active=True)

    class Meta:
        model = Expense
        fields = '__all__'
        widgets = {
            'date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'time': TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'supplier': Select(attrs={'class': 'select2', 'style': 'width: 100%'}),
            'description': TextInput(attrs={'placeholder': 'Descripción del gasto'}),
            'amount': NumberInput(attrs={'step': '0.01'}),
            'payer': TextInput(attrs={'placeholder': 'Pagado por'}),
        }

    def save(self, commit=True):
        data = {}
        try:
            if self.is_valid():
                obj = super().save(commit=False)
                
                # Validación para evitar duplicados
                if not self.instance.pk:  # Solo para nuevos gastos
                    from django.utils import timezone
                    from datetime import datetime, timedelta
                    
                    # Combinar fecha y hora para datetime completo
                    if obj.date and obj.time:
                        expense_datetime = datetime.combine(obj.date, obj.time)
                    else:
                        expense_datetime = timezone.now()
                    
                    # Buscar posibles duplicados (mismos campos clave en última hora)
                    from core.erp.models import Expense
                    potential_duplicates = Expense.objects.filter(
                        amount=obj.amount,
                        date__gte=expense_datetime - timedelta(hours=1),
                        date__lte=expense_datetime + timedelta(hours=1),
                        description=obj.description,
                        company_id=obj.company_id
                    ).exclude(is_active=False)
                    
                    if potential_duplicates.exists():
                        data['error'] = 'Ya existe un gasto similar con el mismo monto, descripción y fecha en la última hora. Por favor, verifique si es un duplicado.'
                        return data
                
                # Establecer hora actual si no se proporcionó
                if not obj.time and not self.instance.pk:
                    from django.utils import timezone
                    obj.time = timezone.now().time()
                
                if self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
                    if getattr(self.request.user, 'company_id', None) and not getattr(obj, 'company_id', None):
                        obj.company_id = self.request.user.company_id
                
                if commit:
                    obj.save()
                data = obj.toJSON() if hasattr(obj, 'toJSON') else {}
            else:
                print('ERRORES DEL FORMULARIO EXPENSE:', self.errors)
                data['error'] = self.errors
        except Exception as e:
            print('EXCEPCIÓN EN SAVE EXPENSE:', str(e))
            data['error'] = str(e)
        return data


class AutoSyncConfigForm(ModelForm):
    class Meta:
        model = AutoSyncConfig
        fields = ['interval_seconds']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.visible_fields():
            f.field.widget.attrs['class'] = 'form-control'
            f.field.widget.attrs['autocomplete'] = 'off'
        if 'interval_seconds' in self.fields:
            # Mostrar y editar en minutos para el usuario
            inst = self.instance or None
            secs = getattr(inst, 'interval_seconds', 300) or 300
            mins = max(2, min(60, int(round(secs / 60))))
            self.fields['interval_seconds'].initial = mins
            self.fields['interval_seconds'].label = 'Intervalo de sync automática (minutos)'
            self.fields['interval_seconds'].widget = NumberInput(attrs={
                'class': 'form-control',
                'min': 2,
                'max': 60,
            })

    def clean_interval_seconds(self):
        mins = self.cleaned_data.get('interval_seconds') or 5
        if mins < 2 or mins > 60:
            raise ValidationError('El intervalo debe estar entre 2 y 60 minutos.')
        return int(mins) * 60

class TestForm(Form):
    categories = ModelChoiceField(queryset=Category.objects.all(), widget=Select(attrs={
        'class': 'form-control select2',
        'style': 'width: 100%'
    }))

    products = ModelChoiceField(queryset=Product.objects.none(), widget=Select(attrs={
        'class': 'form-control select2',
        'style': 'width: 100%'
    }))
    search = ModelChoiceField(queryset=Product.objects.none(), widget=Select(attrs={
        'class': 'form-control select2',
        'style': 'width: 100%'
    }))


# Formularios para Transferencias Internas
class InternalTransferForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs["class"] = "form-control"
            form.field.widget.attrs["autocomplete"] = "off"
    
    class Meta:
        model = InternalTransfer
        fields = ['origin_pos', 'destination_pos', 'observations']


class InternalTransferDetailForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs["class"] = "form-control"
            form.field.widget.attrs["autocomplete"] = "off"
    
    class Meta:
        model = InternalTransferDetail
        fields = ['product', 'quantity', 'unit_price']


class RemitoEntradaForm(ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs["class"] = "form-control"
            form.field.widget.attrs["autocomplete"] = "off"
        
        # Manejar campo company según usuario
        if 'company' in self.fields and self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
            if getattr(self.request.user, 'company_id', None):
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id, is_active=True)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False
        elif 'company' in self.fields:
            self.fields['company'].queryset = Company.objects.filter(is_active=True)

        # Auto-generar número de remito si está vacío
        if not self.initial.get('numero') and not self.data.get('numero'):
            last_remito = RemitoEntrada.objects.order_by('-id').first()
            if last_remito and last_remito.numero:
                try:
                    num = int(last_remito.numero.split('-')[-1]) + 1
                    self.initial['numero'] = f"R-{num:06d}"
                except (ValueError, IndexError):
                    self.initial['numero'] = f"R-000001"
            else:
                self.initial['numero'] = "R-000001"

        # Fecha por defecto: hoy
        if not self.initial.get('fecha') and not self.data.get('fecha'):
            from datetime import date
            self.initial['fecha'] = date.today()
    
    class Meta:
        model = RemitoEntrada
        fields = ['supplier', 'numero', 'fecha', 'estado', 'observaciones']
        widgets = {
            'fecha': DateInput(attrs={'type': 'date'}),
            'observaciones': Textarea(attrs={'rows': 3}),
        }


class RemitoForm(ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs["class"] = "form-control"
            form.field.widget.attrs["autocomplete"] = "off"
        
        # Manejar campo company según usuario
        if 'company' in self.fields and self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
            if getattr(self.request.user, 'company_id', None):
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id, is_active=True)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False
        elif 'company' in self.fields:
            self.fields['company'].queryset = Company.objects.filter(is_active=True)

        # Auto-generar número de remito si está vacío
        if not self.initial.get('numero') and not self.data.get('numero'):
            last_remito = Remito.objects.order_by('-id').first()
            if last_remito and last_remito.numero:
                try:
                    num = int(last_remito.numero.split('-')[-1]) + 1
                    self.initial['numero'] = f"R-{num:06d}"
                except (ValueError, IndexError):
                    self.initial['numero'] = f"R-000001"
            else:
                self.initial['numero'] = "R-000001"

        # Fecha por defecto: hoy
        if not self.initial.get('fecha') and not self.data.get('fecha'):
            from datetime import date
            self.initial['fecha'] = date.today()
    
    class Meta:
        model = Remito
        fields = ['tipo', 'supplier', 'numero', 'fecha', 'estado', 'observaciones']
        widgets = {
            'fecha': DateInput(attrs={'type': 'date'}),
            'observaciones': Textarea(attrs={'rows': 3}),
        }
        exclude = ['company', 'synced_to_server', 'created_at', 'updated_at', 'created_by']
