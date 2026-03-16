from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get value from dictionary by key"""
    if dictionary:
        return dictionary.get(key)
    return key
