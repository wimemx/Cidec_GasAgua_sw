from django.views.generic.simple import direct_to_template
from django.shortcuts import render_to_response
from django.template.context import RequestContext

from rbac.models import *
from rbac.rbac_functions import has_permission, get_buildings_context
VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")


def add_role(request):
    """Add role web form"""
    if has_permission(request.user, CREATE, "crear rol"):
        if request.method == "POST":
            pass
        else:
            datacontext = get_buildings_context(request.user)
            template_vars = dict(datacontext=datacontext, empresa=request.session[
                                                                  'main_building'])
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("rbac/add_role.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def add_data_context_permissions(request):
    """Permission Asigments
    show a form for data context permission asigment
    """
    if has_permission(request.user, CREATE, "data_context_permissions"):
        #has perm to view graphs, now check what can the user see
        datacontext = get_buildings_context(request.user)

        set_default_session_vars(request, datacontext)
        #valid years for reporting
        request.session['years'] = [__date.year
                                    for __date in
                                    ElectricData.objects.all().dates('medition_date', 'year')]

        template_vars = {"type":"graphs", "datacontext":datacontext,
                         'empresa': request.session['main_building'],
                         'consumer_unit': request.session['consumer_unit']
        }
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/main.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))