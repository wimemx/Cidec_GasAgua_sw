from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, HttpResponse, \
    HttpResponseRedirect, get_object_or_404
from rbac.rbac_functions import get_buildings_context_for_gaswater
from rbac.models import *
from c_center.models import IndustrialEquipment
from gas_agua.models import WaterGasData
from c_center.c_center_functions import set_default_session_vars

VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")

@login_required(login_url='/')
def gas_medition(request):
    builds = WaterGasData.objects.values(
        'industrial_equipment__building').distinct()
    datacontext, b_list = get_buildings_context_for_gaswater(
        request.user,builds)
    if 'main_building' in request.session:
        if not WaterGasData.objects.filter(
                industrial_equipment__building=request.session['main_building']
        ):
            del request.session['main_building']
    if not datacontext:
        request.session['consumer_unit'] = None
    set_default_session_vars(request, b_list)
    empresa = request.session['main_building']
    company = request.session['company']
    request.session['tipo'] = 'gas'
    tipo = request.session['tipo']
    template_vars_tags = dict(
        empresa=empresa,
        datacontext=datacontext,
        company=company,
        tipo=tipo,
        operations=Operation.objects.all())
    template_vars_tags['years'] = request.session['years']
    template_vars = template_vars_tags
    return render_to_response("gas_agua/gas.html", template_vars)

@login_required(login_url='/')
def water_medition(request):
    builds = WaterGasData.objects.values(
        'industrial_equipment__building').distinct()
    datacontext, b_list = get_buildings_context_for_gaswater(
        request.user, builds)
    if 'main_building' in request.session:
        if not WaterGasData.objects.filter(
                industrial_equipment__building=request.session['main_building']
        ):
            del request.session['main_building']
    if not datacontext:
        request.session['consumer_unit'] = None
    set_default_session_vars(request, b_list)
    empresa = request.session['main_building']
    company = request.session['company']
    request.session['tipo'] = 'water'
    tipo = request.session['tipo']
    template_vars_tags = dict(
        empresa=empresa,
        datacontext=datacontext,
        company=company,
        tipo=tipo,
        operations=Operation.objects.all())
    template_vars = template_vars_tags
    return render_to_response("gas_agua/agua.html", template_vars)
