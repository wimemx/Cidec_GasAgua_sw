# -*- coding: utf-8 -*-
import re
import urllib

from django.views.generic.simple import direct_to_template
from django.shortcuts import render_to_response, HttpResponse, HttpResponseRedirect, get_object_or_404
from django.template.context import RequestContext
from django.http import Http404
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.db.models.aggregates import Count
from django.db.models import Q

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
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
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

                    template_vars = dict(datacontext=datacontext,
                        empresa=empresa,
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

                template_vars = dict(datacontext=datacontext,
                    empresa=empresa,
                    operations=Operation.objects.all(),
                    message=mensaje,
                    msg_type="fail",
                    post=request.POST
                )
                template_vars_template = RequestContext(request, template_vars)
                return render_to_response("rbac/add_role.html", template_vars_template)

        else:
            template_vars = dict(datacontext=datacontext,
                                 empresa=empresa,
                                 operations=Operation.objects.all())
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("rbac/add_role.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def update_role_privs(role, objs_ids, operation):
    """Update a  list of PermissionAsigments for a given role
    role = a Role instance
    objs_ids = array with ids of objects
    operation = string ["Cer", "Crear", "Eliminar"], if neither, defaults UPDATE
    """
    if operation == "Ver":
        operation = VIEW
    elif operation == "Crear":
        operation = CREATE
    elif operation == "Eliminar":
        operation = DELETE
    else:
        operation = UPDATE

    objs_arr = []
    for obj_id in objs_ids:
        if obj_id != "all":
            try:
                objs_arr.append(Object.objects.get(pk=int(obj_id)))
            except ObjectDoesNotExist:
                mensaje = "El privilegio no existe, por favor seleccione nuevamente la "\
                          "operaci&oacute;n y el privilegio"
                return False, mensaje

    PermissionAsigment.objects.filter(role=role, operation=operation).delete()
    for object in objs_arr:
        perm=PermissionAsigment(role=role, operation=operation, object=object)
        perm.save()
    return True, "El rol se modificó exitosamente"

def edit_role(request, id_role):
    if has_permission(request.user, UPDATE, "Modificar asignaciones de permisos a roles"):
        rol = get_object_or_404(Role, pk=id_role)
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        ntype = ""
        mensaje = ""
        if request.method == "POST":
            asignation = False
            ids_ver = []
            ids_crear = []
            ids_modificar = []
            ids_eliminar = []
            for key in request.POST:
                objs_ids = request.POST[str(key)].split(",")

                #checks the type of the allowed operation for the role
                if re.search('^Ver_\w+', key):
                    ids_ver.extend(objs_ids)
                    #asignation, mensaje = save_perm(rol, objs_ids, "Ver")

                elif re.search('^Crear_\w+', key):
                    ids_crear.extend(objs_ids)
                    #asignation, mensaje = save_perm(rol, objs_ids, "Crear")

                elif re.search('^Eliminar_\w+', key):
                    ids_eliminar.extend(objs_ids)
                    #asignation, mensaje = save_perm(rol, objs_ids, "Eliminar")

                elif re.search('^Modificar_\w+', key):
                    ids_modificar.extend(objs_ids)
                    #asignation, mensaje = save_perm(rol, objs_ids, "Modificar")
            #guardo la totalidad de objetos, por operación, independientemente de su grupo
            if ids_ver:
                asignation, mensaje = update_role_privs(rol, ids_ver, "Ver")
            if ids_crear:
                asignation, mensaje = update_role_privs(rol, ids_crear, "Crear")
            if ids_eliminar:
                asignation, mensaje = update_role_privs(rol, ids_eliminar, "Eliminar")
            if ids_modificar:
                asignation, mensaje = update_role_privs(rol, ids_modificar, "Modificar")
            if asignation:
                #if save_perm register the PermissionAsigment correctly
                if not ntype:
                    ntype = "success"

                return HttpResponseRedirect("/panel_de_control/roles?msj=" + mensaje +
                                            "&ntype="+ntype)
            else:
                #regresa al formulario de alta con el mensaje de error,
                # borro el rol y los privilegios asociados
                PermissionAsigment.objects.filter(role=rol).delete()
                rol.delete()

                template_vars = dict(datacontext=datacontext,
                    empresa=empresa,
                    operations=Operation.objects.all(),
                    message=mensaje,
                    msg_type="fail",
                    post=request.POST
                )
                template_vars_template = RequestContext(request, template_vars)
                return render_to_response("rbac/add_role.html", template_vars_template)
        else:
            template_vars = dict(rol=rol,
                                 datacontext=datacontext,
                                 empresa=empresa,
                                 operations=Operation.objects.all())
            permissions = PermissionAsigment.objects.filter(role=rol)
            objects = [ob.object.pk for ob in permissions]

            objs_group_perms = OperationForGroupObjects.objects.filter(group_object__object__pk__in=objects)
            objs = {}
            for gp in objs_group_perms:
                key = gp.operation.operation_name+"-"+gp.group_object.group.group_name
                if key in objs:
                    objs[key].append(gp.group_object.object)
                else:
                    objs[key] = [gp.group_object.object,]
            arr_ops=[]
            for key in objs:
                key_split = key.split("-")
                operacion = key_split[0]
                grupo = key_split[1]
                arr_ops.append(dict(operacion=operacion, grupo=grupo, privs=objs[key]))

            template_vars['objs_group_perms'] = arr_ops
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("rbac/edit_role.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def see_role(request, id_role):
    if has_permission(request.user, VIEW, "Ver roles"):
        rol = get_object_or_404(Role, pk=id_role)
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        template_vars = dict(rol=rol,
            datacontext=datacontext,
            empresa=empresa,
            operations=Operation.objects.all())
        permissions = PermissionAsigment.objects.filter(role=rol)
        objects = [ob.object.pk for ob in permissions]

        objs_group_perms = OperationForGroupObjects.objects.filter(group_object__object__pk__in=objects)
        objs = {}
        for gp in objs_group_perms:
            key = gp.operation.operation_name+"-"+gp.group_object.group.group_name
            if key in objs:
                objs[key].append(gp.group_object.object)
            else:
                objs[key] = [gp.group_object.object,]
        arr_ops=[]
        for key in objs:
            key_split = key.split("-")
            operacion = key_split[0]
            grupo = key_split[1]
            arr_ops.append(dict(operacion=operacion, grupo=grupo, privs=objs[key]))

        template_vars['objs_group_perms'] = arr_ops
        template_vars['just_watch'] = "solo ver"
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("rbac/edit_role.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def view_roles(request):
    if has_permission(request.user, VIEW, "Ver roles"):
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''
        order_desc = 'asc'
        order_name = 'asc'
        order = "role_name" #default order
        if "order_name" in request.GET:
            #request.GET["order_name"]=asc or desc
            if request.GET["order_name"] == "desc":
                order = "-role_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:

            if "order_desc" in request.GET:
            #request.GET["order_name"]=asc or desc
                if request.GET["order_desc"] == "asc":
                    order = "role_description"
                    order_desc = "desc"
                else:
                    order = "-role_description"
                    order_desc = "asc"
        if search:
            lista = Role.objects.filter(Q(role_name__icontains=request.GET['search'])|Q(
                role_description__icontains=request.GET['search'])).order_by(order)
        else:
            lista = Role.objects.all().order_by(order)
        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(roles=paginator, order_name=order_name, order_desc=order_desc)
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


        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("rbac/role_list.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_role(request, id_role):
    if has_permission(request.user, DELETE, "Eliminar rol"):
        rol = get_object_or_404(Role, pk=id_role)
        user_r = UserRole.objects.filter(role=rol)
        if user_r:
            mensaje = "Para eliminar un rol, no debe haber ningún usuario asocioado, " \
                      "por favor elimine o cambie las asociaciones de usuarios a este rol e " \
                      "intente de nuevo"
            return HttpResponseRedirect("/panel_de_control/roles/?msj=" + mensaje +
                                       "&ntype=warning")
        else:
            PermissionAsigment.objects.filter(role=rol).delete()
            rol.delete()
            mensaje = "El rol, y todos los privilegios asociados al mismo se han eliminado"
            return HttpResponseRedirect("/panel_de_control/roles/?msj=" + mensaje +
                                        "&ntype=success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def delete_batch(request):
    if has_permission(request.user, DELETE, "Eliminar rol"):
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^rol_\w+', key):
                    r_id = int(key.replace("rol_",""))
                    rol = get_object_or_404(Role, pk=r_id)
                    user_r = UserRole.objects.filter(role=rol)
                    if user_r:
                        mensaje = "Para eliminar un rol, no debe haber ningún usuario asocioado, "\
                                  "por favor elimine o cambie las asociaciones de usuarios al " \
                                  "rol "+ str(rol.role_name) +", e intente de nuevo"
                        
                        return HttpResponseRedirect("/panel_de_control/roles/?msj=" + mensaje +
                                                    "&ntype=warning")
                    else:
                        PermissionAsigment.objects.filter(role=rol).delete()
                        rol.delete()
            mensaje = "Los roles seleccionados, y todos los privilegios asociados al mismo se " \
                      "han eliminado"
            return HttpResponseRedirect("/panel_de_control/roles/?msj=" + mensaje +
                                        "&ntype=success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/panel_de_control/roles/?msj=" + mensaje +
                                        "&ntype=success")
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

def add_user(request):
    if has_permission(request.user, CREATE, "Alta de usuarios"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa)
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("rbac/add_user.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

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