#standard library imports

#related third party imports

#local application/library specific imports
from django.shortcuts import render_to_response
from django.http import HttpResponse
from django.template.context import RequestContext
from c_center.models import Building
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
        datacontext=DataContextPermission.objects.filter(user_role__user=request.user)

        if not request.session['main_building']:
            print "sets the default building"
            request.session['main_building'] = datacontext[0].building
        else:
            print "the building is set"
        template_vars={"type":"graphs", "datacontext":datacontext,'empresa':request.session['main_building']}
        template_vars_template = RequestContext(request,template_vars)
        return render_to_response("consumption_centers/main.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def cfe_bill(request):
    if has_permission(request.user, VIEW, "CFE bill") or request.user.is_superuser:
        template_vars={"type":"cfe"}
        template_vars_template = RequestContext(request,template_vars)
        return render_to_response("consumption_centers/cfe.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def potencia_activa(request):
    template_vars={"type":"kvar"}
    if request.GET:
        for key in request.GET:
            print "compare",request.session['main_building'],"with building",key

    template_vars_template = RequestContext(request,template_vars)
    return render_to_response("consumption_centers/graphs/potencia_activa.html", template_vars_template)

def potencia_reactiva(request):
    template_vars={"type":"kvar"}
    if request.GET:
        for key in request.GET:
            print "compare",request.session['main_building'],"with building",key
    template_vars_template = RequestContext(request,template_vars)
    return render_to_response("consumption_centers/graphs/potencia_reactiva.html", template_vars_template)

def factor_potencia(request):
    template_vars={"type":"pf"}
    if request.GET:
        for key in request.GET:
            print "compare",request.session['main_building'],"with building",key
    template_vars_template = RequestContext(request,template_vars)
    return render_to_response("consumption_centers/graphs/factor_potencia.html", template_vars_template)

def perfil_carga(request):
    template_vars={"type":"profile"}
    if request.GET:
        for key in request.GET:
            print "compare",request.session['main_building'],"with building",key
    template_vars_template = RequestContext(request,template_vars)
    return render_to_response("consumption_centers/graphs/perfil_carga.html", template_vars_template)

def set_default_building(request, id_building):
    request.session['main_building']=Building.objects.get(pk=id_building)
    print "sucess"
    return HttpResponse(content='', content_type=None, status=200)
