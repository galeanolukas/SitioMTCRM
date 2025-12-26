from django import template

register = template.Library()

@register.filter
def currency(value):
    """
    Formatea un valor numérico como moneda con separador de miles
    Ejemplo: 1500.50 -> $1,500.50
    """
    try:
        if value is None or value == '':
            return '$0.00'
        
        # Convertir a float
        value = float(value)
        
        # Formatear con separador de miles y 2 decimales
        formatted = "${:,.2f}".format(abs(value))
        
        # Agregar signo negativo si es necesario
        if value < 0:
            formatted = "-$" + formatted[1:]
        
        return formatted
    except (ValueError, TypeError):
        return '$0.00'

@register.filter
def currency_simple(value):
    """
    Formatea un valor numérico como moneda simple sin símbolo $
    Ejemplo: 1500.50 -> 1,500.50
    """
    try:
        if value is None or value == '':
            return '0.00'
        
        # Convertir a float
        value = float(value)
        
        # Formatear con separador de miles y 2 decimales
        formatted = "{:,.2f}".format(abs(value))
        
        # Agregar signo negativo si es necesario
        if value < 0:
            formatted = "-" + formatted
        
        return formatted
    except (ValueError, TypeError):
        return '0.00'

@register.filter
def currency_int(value):
    """
    Formatea un valor numérico como moneda sin decimales
    Ejemplo: 1500 -> $1,500
    """
    try:
        if value is None or value == '':
            return '$0'
        
        # Convertir a int
        value = int(float(value))
        
        # Formatear con separador de miles
        formatted = "${:,}".format(abs(value))
        
        # Agregar signo negativo si es necesario
        if value < 0:
            formatted = "-$" + formatted[1:]
        
        return formatted
    except (ValueError, TypeError):
        return '$0'
