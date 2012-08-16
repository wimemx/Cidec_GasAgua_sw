#standard library imports
from datetime import *
#related third party imports

#local application/library specific imports
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from django.template.context import RequestContext

from c_center.calculations import *
from c_center.models import Building, ElectricData
from rbac.models import Operation, DataContextPermission
from rbac.rbac_functions import  has_permission


VIEW = Operation.objects.get(operation_name="view")
CREATE = Operation.objects.get(operation_name="create")
DELETE = Operation.objects.get(operation_name="delete")
UPDATE = Operation.objects.get(operation_name="update")

def main_page(request):
    """ in the mean time the main view is the graphics view """
    if has_permission(request.user, VIEW, "graphs") or request.user.is_superuser:
        #has perm to view graphs, now check what can the user see
        datacontext = DataContextPermission.objects.filter(user_role__user=request.user)

        if not request.session['main_building']:
            print "sets the default building"
            request.session['main_building'] = datacontext[0].building
        else:
            print "the building is set"
        template_vars = {"type":"graphs", "datacontext":datacontext,'empresa':request.session['main_building']}
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/main.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def cfe_bill(request):
    if has_permission(request.user, VIEW, "CFE bill") or request.user.is_superuser:
        datacontext = DataContextPermission.objects.filter(user_role__user=request.user)
        if not request.session['main_building']:
            #sets the default building
            request.session['main_building'] = datacontext[0].building
        powermeter = ConsumerUnit.objects.get(building=datacontext[0].building)

        start_date = '2012-01-01 00:00:00'
        end_date = '2012-07-31 23:59:59'
        if 'f1_init' in request.GET:
            start_date = request.GET['f1_init']
            end_date = request.GET['f1_end']

        print tarifaHM(powermeter.profile_powermeter, start_date, end_date, datacontext[0].building.region)
        template_vars={"type":"cfe", "datacontext":datacontext, 'empresa':request.session['main_building']}
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/cfe.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def potencia_activa(request):
    template_vars = {"type":"kvar"}
    if request.GET:
        for key in request.GET:
            print "compare", request.session['main_building'], "with building", key

    template_vars_template = RequestContext(request, template_vars)
    return render_to_response("consumption_centers/graphs/potencia_activa.html", template_vars_template)

def potencia_reactiva(request):
    template_vars = {"type":"kvar"}
    if request.GET:
        for key in request.GET:
            print "compare", request.session['main_building'], "with building", key
    template_vars_template = RequestContext(request, template_vars)
    return render_to_response("consumption_centers/graphs/potencia_reactiva.html", template_vars_template)

def factor_potencia(request):
    template_vars = {"type":"pf"}
    if request.GET:
        for key in request.GET:
            print "compare", request.session['main_building'], "with building", key
    template_vars_template = RequestContext(request, template_vars)
    return render_to_response("consumption_centers/graphs/factor_potencia.html", template_vars_template)

def perfil_carga(request):
    template_vars = {"type":"profile"}
    if request.GET:
        for key in request.GET:
            if re.search('^compare_to\d+', key):
                print "compare", request.session['main_building'], "with building", key
    template_vars_template = RequestContext(request,template_vars)
    return render_to_response("consumption_centers/graphs/perfil_carga.html", template_vars_template)

def set_default_building(request, id_building):
    request.session['main_building'] = Building.objects.get(pk=id_building)
    if 'referer' in request.GET:
        if request.GET['referer'] == "cfe":
            return HttpResponseRedirect("/reportes/cfe/")
    return HttpResponse(content='', content_type=None, status=200)

def recibocfe(request):

    #Obtiene los registros de un medidor en un determinado periodo de tiempo
    pr_powermeter = 2
    region = 2
    start_date = '2012-01-01 00:00:00'
    end_date = '2012-07-31 23:59:59'

    print tarifaHM(pr_powermeter, start_date, end_date, region)


    variables = RequestContext(request, vars)
    return render_to_response('consumption_centers/cfe.html', variables)

def changedate(key):
    """
    sets all the data in intervals of 3 hours
    """

    data = ElectricData.objects.filter(profile_powermeter__pk=key)
    initial_date = datetime.datetime(2012,01,01,00,00)
    for dato in data:
        initial_date += timedelta(hours=3)
        dato.medition_date = initial_date
        dato.save()
        print dato.medition_date