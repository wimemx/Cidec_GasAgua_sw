import re

from django import template
from django.utils.html import mark_safe
register = template.Library()

class_re = re.compile(r'(?<=class=["\'])(.*)(?=["\'])')


@register.filter
def add_class(value, css_class):
    string = unicode(value)
    match = class_re.search(string)
    if match:
        m = re.search(r'^%s$|^%s\s|\s%s\s|\s%s$' % (css_class, css_class,
                                                    css_class, css_class),
                                                    match.group(1))
        print match.group(1)
        if not m:
            return mark_safe(class_re.sub(match.group(1) + " " + css_class,
                                          string))
    else:
        return mark_safe(string.replace(' ', ' class="%s" ' % css_class, 1))
    return value

tag_re = re.compile(r'^<+(.*)')

@register.filter
def add_attr(value, new_attr):
    #html control string
    string = unicode(value)
    match = class_re.search(string)
    #if encounters the beginning of tag
    if match:
        str1 = string.replace(" ", " " + new_attr+" ", 1)
        return mark_safe(str1)
    else:
        return value