#standard library imports

#related third party imports

#local application/library specific imports
from django.shortcuts import render_to_response
from django.template.context import RequestContext
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
        template_vars={"type":"graphs", "datacontext":datacontext}
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

    template_vars_template = RequestContext(request,template_vars)
    return render_to_response("consumption_centers/graphs/potencia_activa.html", template_vars_template)

def potencia_reactiva(request):
    template_vars={"type":"kvar"}
    template_vars_template = RequestContext(request,template_vars)
    return render_to_response("consumption_centers/graphs/potencia_reactiva.html", template_vars_template)

def factor_potencia(request):
    template_vars={"type":"pf"}
    template_vars_template = RequestContext(request,template_vars)
    return render_to_response("consumption_centers/graphs/factor_potencia.html", template_vars_template)

def perfil_carga(request):
    template_vars={"type":"profile"}
    template_vars_template = RequestContext(request,template_vars)
    return render_to_response("consumption_centers/graphs/perfil_carga.html", template_vars_template)