from django import forms
from django.utils import timezone
from core.erp.models.discounts import DiscountRule
from core.erp.models import Product, Category


class DiscountRuleForm(forms.ModelForm):
    class Meta:
        model = DiscountRule
        fields = [
            'name', 'description', 'product', 'category', 'min_quantity', 'max_quantity',
            'discount_type', 'discount_value', 'buy_quantity', 'pay_quantity',
            'priority', 'is_active', 'is_cumulative', 'start_date', 'end_date',
            'max_uses'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la oferta'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción opcional'}),
            'product': forms.Select(attrs={'class': 'form-control', 'data-placeholder': 'Seleccione un producto'}),
            'category': forms.Select(attrs={'class': 'form-control', 'data-placeholder': 'Seleccione una categoría'}),
            'min_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'max_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'discount_type': forms.Select(attrs={'class': 'form-control'}),
            'discount_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'buy_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'pay_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_cumulative': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'start_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'max_uses': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrar productos y categorías por empresa si es necesario
        user = kwargs.get('user') if 'user' in kwargs else None
        if user and hasattr(user, 'company') and user.company:
            self.fields['product'].queryset = Product.objects.filter(company=user.company)
            self.fields['category'].queryset = Category.objects.all()
        
        # Configurar placeholder para datetime-local
        if not self.instance.pk:
            self.fields['start_date'].initial = timezone.now()
    
    def clean(self):
        cleaned_data = super().clean()
        discount_type = cleaned_data.get('discount_type')
        buy_quantity = cleaned_data.get('buy_quantity')
        pay_quantity = cleaned_data.get('pay_quantity')
        product = cleaned_data.get('product')
        category = cleaned_data.get('category')
        min_quantity = cleaned_data.get('min_quantity')
        max_quantity = cleaned_data.get('max_quantity')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        # Validaciones generales
        if not product and not category:
            raise forms.ValidationError('Debe seleccionar un producto o una categoría.')
        
        if product and category:
            raise forms.ValidationError('No puede seleccionar producto y categoría a la vez.')
        
        if max_quantity and min_quantity and max_quantity < min_quantity:
            raise forms.ValidationError('La cantidad máxima no puede ser menor que la mínima.')
        
        if end_date and start_date and end_date <= start_date:
            raise forms.ValidationError('La fecha de fin debe ser posterior a la fecha de inicio.')
        
        # Validaciones por tipo de descuento
        if discount_type == 'percentage':
            discount_value = cleaned_data.get('discount_value')
            if discount_value and (discount_value < 0 or discount_value > 100):
                raise forms.ValidationError('El porcentaje de descuento debe estar entre 0 y 100.')
        
        elif discount_type == 'fixed':
            discount_value = cleaned_data.get('discount_value')
            if discount_value and discount_value <= 0:
                raise forms.ValidationError('El monto fijo debe ser mayor que 0.')
        
        elif discount_type == 'special_price':
            discount_value = cleaned_data.get('discount_value')
            if discount_value and discount_value <= 0:
                raise forms.ValidationError('El precio especial debe ser mayor que 0.')
        
        elif discount_type == 'bxgy':
            if not buy_quantity or not pay_quantity:
                raise forms.ValidationError('Para "Lleva X Paga Y" debe especificar ambas cantidades.')
            if buy_quantity <= pay_quantity:
                raise forms.ValidationError('En "Lleva X Paga Y", la cantidad a llevar debe ser mayor que la cantidad a pagar.')
        
        return cleaned_data
