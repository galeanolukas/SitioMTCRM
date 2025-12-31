from django import template

register = template.Library()

@register.filter
def ars_format(value):
    """
    Formatea un número con separador de miles en formato argentino
    Ej: 1234567 -> 1.234.567
    """
    try:
        if value is None or value == '':
            return '0'
        
        # Convertir a string y eliminar decimales si es necesario
        value_str = str(value)
        
        # Si tiene decimales, separar la parte entera
        if '.' in value_str:
            integer_part, decimal_part = value_str.split('.')
        else:
            integer_part = value_str
            decimal_part = None
        
        # Eliminar signos negativos temporalmente
        is_negative = integer_part.startswith('-')
        if is_negative:
            integer_part = integer_part[1:]
        
        # Eliminar ceros a la izquierda
        integer_part = integer_part.lstrip('0') or '0'
        
        # Formatear con separador de miles
        if len(integer_part) > 3:
            formatted = ''
            for i, digit in enumerate(reversed(integer_part)):
                if i > 0 and i % 3 == 0:
                    formatted = '.' + formatted
                formatted = digit + formatted
            integer_part = formatted
        
        # Restaurar signo negativo
        if is_negative:
            integer_part = '-' + integer_part
        
        # Si hay decimales y no son ceros, incluirlos
        if decimal_part and decimal_part != '00':
            return f"{integer_part},{decimal_part}"
        else:
            return integer_part
            
    except (ValueError, TypeError):
        return '0'

@register.filter
def ars_currency(value):
    """
    Formatea un número como moneda argentina
    Ej: 1234567.89 -> $1.234.567,89
    """
    try:
        if value is None or value == '':
            return '$0'
        
        # Convertir a float para manejar decimales correctamente
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            return '$0'
        
        # Formatear con 2 decimales
        formatted = f"{float_value:,.2f}"
        
        # Reemplazar coma por punto y punto por coma (formato argentino)
        formatted = formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
        
        return f"${formatted}"
        
    except (ValueError, TypeError):
        return '$0'
