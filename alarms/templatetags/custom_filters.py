__author__ = 'wime'

from django import template
from django.utils.datastructures import SortedDict

register = template.Library()

@register.filter(name='sortKeys')
def listsort(value, reverse=False):
    if reverse:
        reverse = True
    else:
        reverse = False
    if isinstance(value, dict):
        new_dict = SortedDict()
        key_list = value.keys()
        key_list.sort(reverse=reverse)
        for key in key_list:
            new_dict[key] = value[key]
        return new_dict
    elif isinstance(value, list):
        new_list = list(value)
        new_list.sort(reverse=reverse)
        return new_list
    else:
        return value