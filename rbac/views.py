# -*- coding: utf-8 -*-
import re
import urllib
from datetime import date

import variety

from django.views.generic.simple import direct_to_template
from django.shortcuts import render_to_response, HttpResponse, HttpResponseRedirect, get_object_or_404
from django.template.context import RequestContext
from django.http import Http404
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.db.models.aggregates import Count
from django.db.models import Q
from django.db import IntegrityError
from django.utils import simplejson

from django.contrib.auth.models import User
from rbac.models import *
from c_center.models import Cluster, ClusterCompany, CompanyBuilding
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
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")

    if has_permission(request.user, CREATE, "crear rol") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
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
                if has_permission(request.user, CREATE, "Asignacion de privilegios") or request.user.is_superuser:
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
                if has_permission(request.user, VIEW, "Ver roles") or request.user.is_superuser:
                    return HttpResponseRedirect("/panel_de_control/roles?msj=" + mensaje +
                                                "&ntype="+ntype)
                else:
                    #regresa al formulario de alta

                    template_vars = dict(datacontext=datacontext, company=company,
                        empresa=empresa, operations=Operation.objects.all(), message=mensaje,
                        msg_type=ntype
                    )
                    template_vars_template = RequestContext(request, template_vars)
                    return render_to_response("rbac/add_role.html", template_vars_template)
            else:
                #regresa al formulario de alta con el mensaje de error,
                # borro el rol y los privilegios asociados
                PermissionAsigment.objects.filter(role=rol).delete()
                rol.delete()

                template_vars = dict(datacontext=datacontext, empresa=empresa,
                    operations=Operation.objects.all(), company=company,
                    message=mensaje,
                    msg_type="fail",
                    post=request.POST
                )
                template_vars_template = RequestContext(request, template_vars)
                return render_to_response("rbac/add_role.html", template_vars_template)

        else:
            template_vars = dict(datacontext=datacontext, empresa=empresa,company=company,
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
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar asignaciones de permisos a roles") or request.user.is_superuser:
        rol = get_object_or_404(Role, pk=id_role)
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        ntype = ""
        mensaje = ""
        if request.method == "POST":
            valid = True
            if not variety.validate_string(request.POST['role_name']):
                valid = False
            if not variety.validate_string(request.POST['role_desc']):
                valid = False

            if valid:
                rol.role_name = request.POST['role_name']
                rol.role_description = request.POST['role_desc']
                rol.save()
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
                    company=company,
                    operations=Operation.objects.all(),
                    message=mensaje,
                    msg_type="fail",
                    post=request.POST
                )
                template_vars_template = RequestContext(request, template_vars)
                return render_to_response("rbac/add_role.html", template_vars_template)
        else:
            template_vars = dict(rol=rol,
                                 datacontext=datacontext, empresa=empresa, company=company,
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
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver roles") or request.user.is_superuser:
        rol = get_object_or_404(Role, pk=id_role)
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        template_vars = dict(rol=rol, datacontext=datacontext, empresa=empresa,
                             company=company, operations=Operation.objects.all())
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
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver roles") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
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
        template_vars = dict(roles=paginator, order_name=order_name, order_desc=order_desc,
                            empresa=empresa, company=company, datacontext=datacontext)
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
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Eliminar rol") or request.user.is_superuser:
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
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Eliminar rol") or request.user.is_superuser:
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
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    operation_group = OperationForGroup.objects.filter(operation__pk=id_operation)
    string_to_return=''
    for operation in operation_group:
        string_to_return += """<li rel="%s">
                                %s
                            </li>""" % (operation.group.pk, operation.group.group_name)
    return HttpResponse(content=string_to_return, content_type="text/html")

def get_select_object(request, id_group):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
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

def validate_user(post):

    data={}
    if variety.validate_string(post['username']):
        data['username'] = post['username'].strip()
    else:
        return False

    if variety.validate_string(post['name']):
        if not re.search("\d", post['name']):
            data['name'] = post['name'].strip()
        else:
            return False
    else:
        return False

    if variety.validate_string(post['last_name']):
            if not re.search("\d", post['last_name']):
                data['last_name'] = post['last_name'].strip()
            else:
                return False
    else:
        return False

    if post['surname']:
        if variety.validate_string(post['surname']):
            if not re.search("\d", post['surname']):
                data['surname'] = post['surname'].strip()
            else:
                return False
        else:
            return False
    else:
        data['surname'] = ''

    if variety.is_valid_email(post['mail']):
        data['mail'] = post['mail']
    else:
        return False

    if post['dob']:
        try:
            fnac = post['dob'].split("-")
            data['fnac'] = date(int(fnac[2]), int(fnac[1]), int(fnac[0]))
        except IndexError, ValueError:
            return False
    else:
        return False

    if post['pass1']:
        if post['pass1'] == post['pass2']:
            data['pass'] = post['pass1']
        else:
            return False
    else:
        data['pass'] = False

    return data





def add_user(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta de usuarios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        template_vars = dict(datacontext=datacontext,
            empresa=empresa, company=company
        )
        if request.method == "POST":

            post=variety.get_post_data(request.POST)
            template_vars["post"] = post
            valid = validate_user(post)

            if valid:

                age = int((date.today() - valid['fnac']).days/365.25)

                if age < 18:
                    template_vars["message"] = "El usuario debe de ser mayor de 18 "\
                                               "a&ntilde;os"
                    template_vars["type"] = "n_notif"
                elif age > 90:
                    template_vars["message"] = "Edad incorrecta, por favor revise la fecha " \
                                               "de nacimiento"
                    template_vars["type"] = "n_notif"
                else:
                    try:
                        newUser = User.objects.create_user(valid['username'],valid['mail'],valid['pass'])
                    except IntegrityError:
                        template_vars["message"] = "El nombre de usuario ya existe, "\
                                                   "por favor elija otro e intente de nuevo"
                        template_vars["type"] = "n_notif"
                    else:
                        newUser.first_name = valid['name']
                        newUser.last_name = valid['last_name']
                        newUser.is_staff = False
                        newUser.is_active = True
                        newUser.is_superuser = False
                        newUser.save()

                        ExtendedUser(
                            user = newUser,
                            user_activation_key = variety.random_string_generator(size=10)
                        ).save()
                        UserProfile(
                            user = newUser,
                            user_profile_surname_mother = valid['surname'],
                            user_profile_birth_dates = valid['fnac'],
                            user_profile_sex = request.POST['sex'],
                            user_profile_office_phone1 = request.POST['tel_o'],
                            user_profile_mobile_phone = request.POST['tel_m'],
                            user_profile_contact_email = valid['mail']
                        ).save()

                        template_vars["message"] = "Usuario creado exitosamente"
                        template_vars["type"] = "n_success"
                        if has_permission(request.user, VIEW, "Ver usuarios") or request.user.is_superuser:
                            return HttpResponseRedirect("/panel_de_control/usuarios?msj=" +
                                                        template_vars["message"] +
                                                        "&ntype=n_success")
            else:
                template_vars["message"] = "Ha ocurrido un error al validar los datos por " \
                                           "favor revise que no haya caracteres inv&aacute;lidos"
                template_vars["type"] = "n_notif"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("rbac/add_user.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def view_users(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver usuarios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''
        order_username = 'asc'
        order_name = 'asc'
        order_email = 'asc'
        order = "first_name" #default order
        if "order_name" in request.GET:
            #request.GET["order_name"]=asc or desc
            if request.GET["order_name"] == "desc":
                order = "-first_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:

            if "order_username" in request.GET:
                    #request.GET["order_name"]=asc or desc
                    if request.GET["order_username"] == "asc":
                        order = "username"
                        order_username = "desc"
                    else:
                        order = "-username"
                        order_username = "asc"
            else:
                if "order_mail" in request.GET:
                #request.GET["order_name"]=asc or desc
                    if request.GET["order_mail"] == "asc":
                        order = "email"
                        order_email = "desc"
                    else:
                        order = "-email"
                        order_email = "asc"
        if search:
            lista = User.objects.filter(Q(username__icontains=request.GET['search'])|Q(
                first_name__icontains=request.GET['search'])|Q(last_name__icontains=request
                .GET['search'])|Q(email__icontains=request.GET['search'])).exclude(
                is_active=False).order_by(
                order)
        else:
            lista = User.objects.all().exclude(is_active=False).order_by(order)
        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_username=order_username,
            order_email=order_email, datacontext=datacontext, empresa=empresa, company=company)
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion']=pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']


        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("rbac/user_list.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_user(request, id_user):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de usuarios") or request.user.is_superuser:
        user = get_object_or_404(User, pk=id_user)
        if user.is_superuser:
            mensaje = "No puedes eliminar a un super usuario"
            type = "n_notif"
        else:
            user.is_active = False
            user.save()
            mensaje = "El usuario se ha dado de baja correctamente"
            type="n_success"
        return HttpResponseRedirect("/panel_de_control/usuarios/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def edit_user(request, id_user):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Actualizar informacion de usuarios") or request.user.is_superuser:
        user = get_object_or_404(User, pk=id_user)
        profile = UserProfile.objects.get(user=user)
        post = {'username': user.username, 'name': user.first_name,
                'last_name': user.last_name, 'surname': profile.user_profile_surname_mother,
                'mail': user.email, 'sex': profile.user_profile_sex,
                'dob': profile.user_profile_birth_dates,
                'tel_o': profile.user_profile_office_phone1,
                'tel_m': profile.user_profile_mobile_phone}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        type = ''

        if request.method == "POST":
            post=variety.get_post_data(request.POST)

            valid = validate_user(post)


            if valid:
                print "valida"

                age = int((date.today() - valid['fnac']).days/365.25)

                if age < 18:
                    message = "El usuario debe de ser mayor de 18 "\
                                               "a&ntilde;os"
                    type = "n_notif"
                elif age > 90:
                    message = "Edad incorrecta, por favor revise la fecha "\
                                               "de nacimiento"
                    type = "n_notif"
                else:
                    #update user
                    if valid['pass']:
                        user.set_password(password)
                        user.save()
                    user.first_name = valid['name']
                    user.last_name = valid['last_name']
                    user.email = valid['mail']
                    user.save()
                    profile.user_profile_surname_mother = valid['surname']
                    profile.user_profile_birth_dates = valid['fnac']
                    profile.user_profile_sex = request.POST['sex']
                    profile.user_profile_office_phone1 = request.POST['tel_o']
                    profile.user_profile_mobile_phone = request.POST['tel_m']
                    profile.user_profile_contact_email = valid['mail']
                    profile.save()

                    message = "Usuario editado exitosamente"
                    type = "n_success"
                    if has_permission(request.user, VIEW, "Ver usuarios") or request.user.is_superuser:
                        return HttpResponseRedirect("/panel_de_control/usuarios?msj=" +
                                                    message +
                                                    "&ntype=n_success")
            else:
                message = "Ha ocurrido un error al validar los datos por "\
                          "favor revise que no haya caracteres inv&aacute;lidos"
                type = "n_notif"

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            operation="edit",
            message=message,
            type=type
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("rbac/add_user.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_batch_user(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de usuarios") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^user_\w+', key):
                    r_id = int(key.replace("user_",""))
                    user = get_object_or_404(User, pk=r_id)
                    if not user.is_superuser:
                        user.is_active = False
                        user.save()
            mensaje = "Los usuarios seleccionados (excepto super usuarios) se han dado de baja"
            return HttpResponseRedirect("/panel_de_control/usuarios/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/panel_de_control/roles/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def see_user(request, id_user):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver usuarios") or request.user.is_superuser:
        user1 = get_object_or_404(User, pk=id_user)
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        profile = UserProfile.objects.get(user=user1)
        age = int((date.today() - profile.user_profile_birth_dates).days/365.25)
        template_vars = dict(user1=user1, company=company, profile=profile,
            datacontext=datacontext, age = age, empresa=empresa)

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("rbac/see_user.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def add_data_context_permissions(request):
    """Permission Asigments
    show a form for data context permission asigment
    """
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Asignar roles a usuarios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        roles = Role.objects.all()
        #obtengo los clusters que tengan empresas asociadas
        #en caso de que haya clusters sin empresas (altas a medio hacer, por ejemplo)
        c_comp = ClusterCompany.objects.all()
        c_comp = [cl.cluster.pk for cl in c_comp]
        clusters = Cluster.objects.filter(pk__in=c_comp)
        message = ""
        type = ""
        if request.method == 'POST':
            try:
                usuario = User.objects.get(pk=int(request.POST['usuario']))
                rol = Role.objects.get(pk=int(request.POST['role']))
                cluster = Cluster.objects.get(pk=int(request.POST['cluster']))
                company = Company.objects.get(pk=int(request.POST['company']))
            except ObjectDoesNotExist:
                message = "Ha ocurrido un error al validar sus campos, por favor verifiquelos " \
                          "e intente de nuevo"
                type = "n_error"
            else:
                if request.POST['company'] != "todas":
                    if request.POST['building'] != "todos":
                        try:
                            building = Building.objects.get(pk=int(request.POST['building']))
                        except ObjectDoesNotExist:
                            message = "Ha ocurrido un error al seleccionar el edificio, por favor " \
                                      "verifique e intente de nuevo"
                            type = "n_error"
                        else:
                            if "part" in request.POST:

                                if request.POST['part'] != "todas":
                                    user_role, created = UserRole.objects.get_or_create(user=usuario,
                                        role=rol)
                                    part = PartOfBuilding.objects.get(pk=request.POST['part'])
                                    data_context, created = DataContextPermission.objects.get_or_create(
                                                            user_role=user_role,
                                                            cluster=cluster,
                                                            company=company,
                                                            building=building,
                                                            part_of_building=part
                                                            )
                                    message = "El rol, sus permisos y asignaciones al edificio y " \
                                              "sus partes, se ha guardado correctamente"
                                    type = "n_success"
                                else:
                                    #alta de asignaciónd de roles/permisos para todas las partes de
                                    # un edificio
                                    partes = PartOfBuilding.objects.filter(building=building)
                                    user_role, created = UserRole.objects.get_or_create(user=usuario,
                                                         role=rol)
                                    if partes:
                                        for parte in partes:
                                            data_context, created = DataContextPermission.objects.get_or_create(
                                                user_role=user_role,
                                                cluster=cluster,
                                                company=company,
                                                building=building,
                                                part_of_building=parte
                                            )
                                    else:
                                        data_context, created = DataContextPermission.objects.get_or_create(
                                            user_role=user_role,
                                            cluster=cluster,
                                            company=company,
                                            building=building
                                        )
                                    message = "El rol, sus permisos y asignaciones al edificio y "\
                                              "sus partes, se ha guardado correctamente"
                                    type = "n_success"
                            else:
                                user_role, created = UserRole.objects.get_or_create(user=usuario,
                                                     role=rol)
                                data_context, created = DataContextPermission.objects.get_or_create(
                                    user_role=user_role,
                                    cluster=cluster,
                                    company=company,
                                    building=building
                                )
                                message = "El rol, sus permisos y su asignación al edificio, se" \
                                          " ha guardado correctamente"
                                type = "n_success"
                    else:
                        #alta de asignación de roles/permisos para todas las partes de
                        # todos los edificios de una empresa
                        user_role, created = UserRole.objects.get_or_create(user=usuario,
                                             role=rol)
                        buildings = CompanyBuilding.objects.filter(company=company)
                        for building_com in buildings:
                            partes = PartOfBuilding.objects.filter(building=building_com.building)
                            user_role, created = UserRole.objects.get_or_create(user=usuario,
                                role=rol)
                            if partes:
                                for parte in partes:
                                    data_context, created = DataContextPermission.objects.get_or_create(
                                        user_role=user_role,
                                        cluster=cluster,
                                        company=company,
                                        building=building_com.building,
                                        part_of_building=parte
                                    )
                            else:
                                data_context, created = DataContextPermission.objects.get_or_create(
                                    user_role=user_role,
                                    cluster=cluster,
                                    company=company,
                                    building=building_com.building
                                )

                        message = "El rol, sus permisos y su asignación al edificio, se"\
                                  " ha guardado correctamente"
                        type = "n_success"
                else:
                    #alta de asignación de roles/permisos para todas las partes de
                    # todos los edificios de todas las empresas de un cluster
                    pass


        template_vars = dict(
            datacontext=datacontext,
            roles=roles,
            clusters=clusters,
            empresa=empresa,
            company=company,
            message=message,
            type=type
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("rbac/asign_data_context.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def added_data_context_permissions(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver asignaciones de roles a usuarios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']

        if "select_user" in request.GET:
            select_user = request.GET["select_user"]
        else:
            select_user = "0"
        if "select_emp" in request.GET:
            select_emp = request.GET['select_emp']
        else:
            select_emp = '0'

        order_username = 'asc'
        order_role = 'asc'
        order_entity = 'asc'
        order = "user_role__role__role_name" #default order
        if "order_role" in request.GET:
            #request.GET["order_name"]=asc or desc
            if request.GET["order_role"] == "desc":
                order = "-user_role__role__role_name"
                order_role = "asc"
            else:
                order_role = "desc"
        else:

            if "order_username" in request.GET:
                #request.GET["order_name"]=asc or desc
                if request.GET["order_username"] == "asc":
                    order = "user_role__user__username"
                    order_username = "desc"
                else:
                    order = "-user_role__user__username"
                    order_username = "asc"
            else:
                if "order_entity" in request.GET:
                #request.GET["order_name"]=asc or desc
                    if request.GET["order_entity"] == "asc":
                        order = "cluster__cluster_name"
                        order_entity = "desc"
                    else:
                        order = "-cluster__cluster_name"
                        order_entity = "asc"
        if select_user != '0' or select_emp != '0':
            lista = DataContextPermission.objects.filter(Q(user_role__user__pk=int(select_user))|Q(
                cluster__pk=int(select_emp))).order_by(order)
        else:
            lista = DataContextPermission.objects.all().order_by(order)
        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_role=order_role, order_username=order_username,
            order_entity=order_entity, datacontext=datacontext, empresa=empresa,
            company=company)
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion']=pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        users_in_dc = DataContextPermission.objects.all()
        users_pks = [dc.user_role.user.pk for dc in users_in_dc]
        template_vars["usuarios"] = User.objects.filter(pk__in=users_pks)
        company_pks = [dc.company.pk for dc in users_in_dc]
        template_vars["empresas"] = Company.objects.filter(pk__in=company_pks)

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("rbac/added_data_context.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def delete_data_context(request, id_data_context):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Eliminar asignaciones de roles a usuarios") or request.user.is_superuser:
        data_c = get_object_or_404(DataContextPermission, pk=id_data_context)
        data_c.delete()
        mensaje = "La asignación se ha eliminado correctamente"
        return HttpResponseRedirect("/panel_de_control/roles_asignados/?msj=" + mensaje +
                                    "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_batch_data_context(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Eliminar asignaciones de roles a usuarios") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^context_\w+', key):
                    r_id = int(key.replace("context_",""))
                    context = get_object_or_404(DataContextPermission, pk=r_id)
                    context.delete()
            mensaje = "Las asignaciones roles-usuarios se han dado de baja correctamente"
            return HttpResponseRedirect("/panel_de_control/roles_asignados/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/panel_de_control/roles/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def search_users(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if "term" in request.GET:
        term = request.GET['term']
        usuarios = User.objects.filter(Q(username__icontains=term)|Q(
            first_name__icontains=term) | Q(last_name__icontains=term))
        users = []
        for usuario in usuarios:
            nombre = usuario.username + " - " + usuario.first_name + " " + usuario.last_name
            users.append(dict(value=nombre, pk=usuario.pk, label=nombre))
        data=simplejson.dumps(users)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404