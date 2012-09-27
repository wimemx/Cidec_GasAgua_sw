# -*- coding: utf-8 -*-
import re

from django.views.generic.simple import direct_to_template
from django.shortcuts import render_to_response, HttpResponse, HttpResponseRedirect, get_object_or_404
from django.template.context import RequestContext
from django.http import Http404
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models.aggregates import Count

from rbac.models import *
from rbac.rbac_functions import has_permission, get_buildings_context
VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")

def save_perm(role, objs_ids, operation):
    """Add a PermissionAsigment for a given role
    role = a Role instance
    objs_ids = array with ids of objects
    operation = string ["ver", "Crear", "Eliminar"], if neither, defaults UPDATE
    """
    if operation == "Ver":
        operation = VIEW
    elif operation == "Crear":
        operation = CREATE
    elif operation == "Eliminar":
        operation = DELETE
    else:
        operation = UPDATE


    for obj_id in objs_ids:
        if obj_id != "all":
            try:
                object = Object.objects.get(pk=int(obj_id))
            except ObjectDoesNotExist:

                mensaje = "El privilegio no existe, por favor seleccione nuevamente la " \
                          "operaci&oacute;n y el privilegio"
                return False, mensaje
            else:
                perm=PermissionAsigment(role=role, operation=operation,
                    object=object)
                perm.save()
    return True, "El registro se completó exitosamente"
def add_role(request):
    """Add role web form"""
    if has_permission(request.user, CREATE, "crear rol"):
        if request.method == "POST":
            role = request.POST['role_name'].strip()
            role_desc = request.POST['role_desc'].strip()
            rol = Role.objects.filter(role_name__iexact=role)
            mensaje = ''
            ntype = ''
            if rol:
                asignation = False
                mensaje = "El rol ya existe, por favor edita el existente o crea uno nuevo"
            else:
                rol = Role(role_name=role, role_description=role_desc, role_importance="average" )
                rol.save()
                if has_permission(request.user, CREATE, "Asignacion de privilegios"):
                    asignation = False
                    for key in request.POST:
                        objs_ids = request.POST[str(key)].split(",")

                        #checks the type of the allowed operation for the role
                        if re.search('^Ver_\w+', key):
                            asignation, mensaje = save_perm(rol, objs_ids, "Ver")

                        elif re.search('^Crear_\w+', key):
                            asignation, mensaje = save_perm(rol, objs_ids, "Crear")

                        elif re.search('^Eliminar_\w+', key):
                            asignation, mensaje = save_perm(rol, objs_ids, "Eliminar")

                        elif re.search('^Modificar_\w+', key):
                            asignation, mensaje = save_perm(rol, objs_ids, "Modificar")
                else:
                    asignation = True
                    mensaje = "Debido a tus privilegios, solo se ha dado de alta el rol"
                    ntype = "notif"

            if asignation:
                #if save_perm register the PermissionAsigment correctly
                if not ntype:
                    ntype = "success"
                if has_permission(request.user, VIEW, "Ver roles"):
                    return HttpResponseRedirect("/panel_de_control/roles?msj=" + mensaje +
                                                "&ntype="+ntype)
                else:
                    #regresa al formulario de alta
                    datacontext = get_buildings_context(request.user)
                    template_vars = dict(datacontext=datacontext,
                        empresa=request.session['main_building'],
                        operations=Operation.objects.all(),
                        message=mensaje,
                        msg_type=ntype
                    )
                    template_vars_template = RequestContext(request, template_vars)
                    return render_to_response("rbac/add_role.html", template_vars_template)
            else:
                #regresa al formulario de alta con el mensaje de error,
                # borro el rol y los privilegios asociados
                PermissionAsigment.objects.filter(role=rol).delete()
                rol.delete()
                datacontext = get_buildings_context(request.user)
                template_vars = dict(datacontext=datacontext,
                    empresa=request.session['main_building'],
                    operations=Operation.objects.all(),
                    message=mensaje,
                    msg_type="fail",
                    post=request.POST
                )
                template_vars_template = RequestContext(request, template_vars)
                return render_to_response("rbac/add_role.html", template_vars_template)

        else:
            datacontext = get_buildings_context(request.user)
            template_vars = dict(datacontext=datacontext,
                                 empresa=request.session['main_building'],
                                 operations=Operation.objects.all())
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("rbac/add_role.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))
def edit_role(request, id_role):
    if has_permission(request.user, UPDATE, "Modificar asignaciones de permisos a roles"):
        rol = get_object_or_404(Role, pk=id_role)
        datacontext = get_buildings_context(request.user)
        template_vars = dict(rol=rol,datacontext=datacontext,
            empresa=request.session['main_building'],
            operations=Operation.objects.all())
        permissions = PermissionAsigment.objects.filter(role=rol)
        objects = [ob.object.pk for ob in permissions]
        objs_group_perms = OperationForGroupObjects.objects.filter(group_object__object__pk__in=objects)
        template_vars['objs_group_perms'] = objs_group_perms
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("rbac/add_role.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def view_roles(request):
    if has_permission(request.user, VIEW, "Ver roles"):

        lista = Role.objects.all()
        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(roles=paginator)
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_role = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_role = paginator.page(paginator.num_pages)

        template_vars['paginacion']=pag_role

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']
        if has_permission(request.user, CREATE, "crear rol"):
            template_vars['create_rol']="create"
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("rbac/role_list.html", template_vars_template)
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
                                <input type="checkbox" name="object_%s" id="%s"/>
                                <label for="%s" >
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