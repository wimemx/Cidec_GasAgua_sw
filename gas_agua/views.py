from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, HttpResponse, \
    HttpResponseRedirect, get_object_or_404
from rbac.rbac_functions import get_buildings_context
from rbac.models import *
from c_center.c_center_functions import set_default_session_vars

VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")

@login_required(login_url='/')
def gas_medition(request):
    datacontext, b_list = get_buildings_context(request.user)
    if not datacontext:
        request.session['consumer_unit'] = None
    set_default_session_vars(request, b_list)
    empresa = request.session['main_building']
    set_default_session_vars(request, datacontext)
    company = request.session['company']
    template_vars_tags = dict(
                             empresa=empresa,
                             datacontext=datacontext,
                             company=company,
                             operations=Operation.objects.all())
    template_vars_tags['tipo'] = 'gas'
    template_vars_tags['consumer_unit'] = request.session['consumer_unit']
    template_vars_tags['years'] = request.session['years']
    template_vars = template_vars_tags
    return render_to_response("gas_agua/gas.html", template_vars)

@login_required(login_url='/')
def water_medition(request):
    datacontext, b_list = get_buildings_context(request.user)
    if not datacontext:
        request.session['consumer_unit'] = None
    set_default_session_vars(request, b_list)
    empresa = request.session['main_building']
    company = request.session['company']
    template_vars_tags = dict(
                             empresa=empresa,
                             datacontext=datacontext,
                             company=company,
                             operations=Operation.objects.all())
    template_vars_tags['tipo'] = 'water'
    template_vars = template_vars_tags
    return render_to_response("gas_agua/agua.html", template_vars)
