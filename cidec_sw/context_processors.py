__author__ = 'wime'
from django.conf import settings


def extra_template_vars(request):
    return { 'SERVER_URL': settings.SERVER_URL }