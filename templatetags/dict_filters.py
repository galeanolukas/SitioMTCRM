from django import template

register = template.Library()

@register.filter
def dict_item(dictionary, key):
    """Return the value for a key from a dictionary."""
    return dictionary.get(key, key)
