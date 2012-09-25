from django.views.generic.simple import direct_to_template
from django.shortcuts import render_to_response, HttpResponse
from django.template.context import RequestContext
from django.http import Http404

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
            template_vars = dict(datacontext=datacontext,
                                 empresa=request.session['main_building'],
                                 operations=Operation.objects.all())
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("rbac/add_role.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def get_select_group(request, id_operation):
    operation_group = OperationForGroup.objects.filter(operation__pk=id_operation)
    string_to_return=''
    for operation in operation_group:
        string_to_return += """<li rel="%s">
                                %s
                            </li>""" % (operation.group.pk, operation.group.group_name)
    return HttpResponse(content=string_to_return, content_type="text/html")

def get_select_object(request, id_group):
    if request.GET['operation']:
        objects = OperationForGroupObjects.objects.filter(operation__pk=request.GET[
                                                                        'operation'],
                                                          group_object__group__pk=id_group)
        string_to_return = ''
        for object in objects:
            string_to_return+="""
                            <li>
                                <input type="checkbox" name="object_%s" id="object_%s"/>
                                <label for="object_%s" >
                                    %s
                                </label>
                            </li>
                            """ % (object.group_object.object.pk,
                                   object.group_object.object.pk,
                                   object.group_object.object.pk,
                                   object.group_object.object.object_name)
        return HttpResponse(content=string_to_return, content_type="text/html")
    else:
        raise Http404

def add_data_context_permissions(request):
    """Permission Asigments
    show a form for data context permission asigment
    """
    if has_permission(request.user, CREATE, "Asignar roles a usuarios"):
        #has perm to view graphs, now check what can the user see


        template_vars_template = RequestContext(request, {})
        return render_to_response("rbac/add_data_context_permissions.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))