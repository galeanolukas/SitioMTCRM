from django.forms import *
from django.forms.widgets import CheckboxInput
from datetime import datetime
from django.core.exceptions import ValidationError
from core.erp.models import Category, Product, Client, Sale, Company, Supplier, Expense, MercadoPagoConfig, AutoSyncConfig, InternalTransfer, InternalTransferDetail

from django.contrib.auth.forms import AuthenticationForm


class CategoryForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs["class"] = "form-control"
            form.field.widget.attrs["autocomplete"] = "off"
        self.fields["name"].widget.attrs["autofocus"] = True

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
                form.save()
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
        if 'company' in self.fields and self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
            if getattr(self.request.user, 'company_id', None):
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False

    class Meta:
        model = Product
        # Ocultamos synced_to_server del formulario; es un flag interno de sync.
        fields = [
            'company',
            'name',
            'code',
            'qr_token',
            'cat',
            'supplier',
            'image',
            'cost_price',
            'pvp',
            'iva_rate',
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
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False

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
        if 'company' in self.fields and self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
            if getattr(self.request.user, 'company_id', None):
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False

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
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False

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
            if f.name not in ('supplier', 'date'):
                f.field.widget.attrs['class'] = 'form-control'
                f.field.widget.attrs['autocomplete'] = 'off'
        if 'supplier' in self.fields:
            self.fields['supplier'].required = False
            self.fields['supplier'].empty_label = '--- Sin proveedor ---'
        if 'company' in self.fields and self.request and hasattr(self.request, 'user') and not getattr(self.request.user, 'is_superuser', False):
            if getattr(self.request.user, 'company_id', None):
                self.fields['company'].queryset = Company.objects.filter(pk=self.request.user.company_id)
                self.fields['company'].initial = self.request.user.company
                self.fields['company'].widget = HiddenInput()
                self.fields['company'].required = False

    class Meta:
        model = Expense
        fields = '__all__'
        widgets = {
            'date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'supplier': Select(attrs={'class': 'select2', 'style': 'width: 100%'}),
            'description': TextInput(attrs={'placeholder': 'Descripción del gasto'}),
            'amount': NumberInput(attrs={'step': '0.01'}),
            'payer': TextInput(attrs={'placeholder': 'Pagado por'}),
        }


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
