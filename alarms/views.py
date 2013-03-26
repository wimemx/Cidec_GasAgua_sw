# -*- coding: utf-8 -*-
from django.core.mail import send_mail, EmailMultiAlternatives
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.context import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.contrib.auth.decorators import login_required

from rbac.rbac_functions import get_buildings_context, has_permission
from c_center.c_center_functions import get_clusters_for_operation

from alarms.models import *
from rbac.models import Operation


VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")


def send_notif_mail(request):
    subject, from_email, to = 'hello', 'from@example.com', 'hector@wime.com.mx'
    text_content = 'This is an important message.'
    html_content = '<p>This is an <strong>important</strong> message.</p>'
    msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    return HttpResponse(content=":)", status=200)


@login_required(login_url='/')
def add_alarm(request):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']
    permission = "Alta de alarma eléctrica"
    if has_permission(request.user, CREATE,
                      permission) or \
            request.user.is_superuser:
        template_vars["operation"] = "alta"
        clusters = get_clusters_for_operation(permission, CREATE, request.user)
        template_vars['clusters'] = clusters
        parameters = ElectricParameters.objects.all()
        template_vars['parameters'] = parameters
        if request.method == 'POST':
            # TODO
            template_vars["post"] = request.POST.copy()
            template_vars["post"]['ie_building'] = int(
                template_vars["post"]['ie_building'])
            building = Building.objects.get(pk=int(request.POST['ie_building']))
            ie = IndustrialEquipment(
                alias=request.POST['ie_alias'].strip(),
                description=request.POST['ie_desc'].strip(),
                server=request.POST['ie_server'].strip(),
                building=building,
                modified_by=request.user
            )
            ie.save()
            message = "El equipo industrial se ha creado exitosamente"
            _type = "n_success"
            if has_permission(request.user, VIEW,
                              "Ver equipos industriales") or \
                    request.user.is_superuser:
                return HttpResponseRedirect(
                    "/buildings/industrial_equipments?msj=" +
                    message +
                    "&ntype=" + _type)
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "alarms/alarm.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def edit_alarm(request, id_alarm):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']
    template_vars["operation"] = "edit"
    industrial_eq = get_object_or_404(IndustrialEquipment, pk=int(id_ie))
    template_vars["id_ie"] = id_ie
    permission = "Modificar equipos industriales"
    if has_permission(request.user, UPDATE,
                      permission) or \
            request.user.is_superuser:
        buildings = get_all_buildings_for_operation(
            permission, CREATE, request.user)
        template_vars['buildings'] = buildings

        if request.method == 'POST':
            building = Building.objects.get(pk=int(request.POST['ie_building']))
            industrial_eq.alias = request.POST['ie_alias'].strip()
            industrial_eq.description = request.POST['ie_desc'].strip()
            industrial_eq.server = request.POST['ie_server'].strip()
            industrial_eq.building = building
            industrial_eq.modified_by = request.user
            industrial_eq.save()
            message = "El equipo industrial se ha actualizado exitosamente"
            _type = "n_success"
            if has_permission(request.user, VIEW,
                              "Ver equipos industriales") or \
                    request.user.is_superuser:
                return HttpResponseRedirect(
                    "/buildings/industrial_equipments?msj=" +
                    message +
                    "&ntype=" + _type)
            template_vars["message"] = message
            template_vars["type"] = type
        template_vars["post"] = dict(ie_alias=industrial_eq.alias,
                                     ie_desc=industrial_eq.description,
                                     ie_server=industrial_eq.server,
                                     ie_building = industrial_eq.building.pk)

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/consumer_units/ind_eq.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def alarm_list(request):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']

    if has_permission(request.user, VIEW,
                      "Ver equipos industriales") or request.user.is_superuser:
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_server = 'asc'
        order_status = 'asc'
        order = "alias" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-alias"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_server" in request.GET:
                if request.GET["order_state"] == "asc":
                    order = "server"
                    order_server = "desc"
                else:
                    order = "-server"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "building__building_status"
                    order_status = "desc"
                else:
                    order = "-building__building_status"
                    order_status = "asc"

        if search:
            lista = IndustrialEquipment.objects.filter(
                Q(alias__icontains=request.GET['search']) | Q(
                    server__icontains=request.GET['search']) | Q(
                    description=request.GET['search'])).order_by(order)

        else:
            lista = IndustrialEquipment.objects.all().order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars['order_name'] = order_name
        template_vars['order_server'] = order_server
        template_vars['order_status'] = order_status
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

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/consumer_units/ie_list.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_alarm(request):
    if has_permission(request.user,
                      UPDATE,
                      "Modificar equipos industriales") or \
            request.user.is_superuser:
        if request.POST['actions'] != '0':
            for key in request.POST:
                if re.search('^equipo_\w+', key):
                    r_id = int(key.replace("equipo_", ""))
                    equipo_ind = get_object_or_404(IndustrialEquipment, pk=r_id)

                    if equipo_ind.status:
                        equipo_ind.status = False
                    else:
                        equipo_ind.status = True

                    equipo_ind.save()

            mensaje = "Los equipos industriales seleccionados han " \
                      "cambiado su estatus correctamente"
            _type = "n_success"
        else:
            mensaje = str("No se ha seleccionado una acción").decode("utf-8")
            _type = "n_notif"
        return HttpResponseRedirect("/buildings/industrial_equipments/?msj=" +
                                    mensaje + "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def status_alarm(request, id_alarm):
    if has_permission(request.user,
                      UPDATE,
                      "Modificar equipos industriales") or \
            request.user.is_superuser:
        ind_eq = get_object_or_404(IndustrialEquipment, pk=id_ie)
        if ind_eq.status:
            ind_eq.status = False
            str_status = "Activo"
        else:
            ind_eq.status = True
            str_status = "Activo"
        ind_eq.save()
        mensaje = "El estatus del equipo industrial " + ind_eq.alias + \
                  ", ha cambiado a " + str_status
        _type = "n_success"

        return HttpResponseRedirect(
            "/buildings/industrial_equipments/?msj=" + mensaje +
            "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def see_alarm(request, id_alarm):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']

    if has_permission(request.user, VIEW,
                      "Ver equipos industriales") or request.user.is_superuser:
        template_vars["industrial_eq"] = get_object_or_404(IndustrialEquipment,
                                                           pk=int(id_ie))

        #Asociated powermeters
        if has_permission(request.user, VIEW,
                          "Ver medidores eléctricos") or \
                request.user.is_superuser:
            order_alias = 'asc'
            order_serial = 'asc'
            order_model = 'asc'
            order_status = 'asc'
            order = "powermeter__powermeter_anotation" #default order
            if "order_alias" in request.GET:
                if request.GET["order_alias"] == "desc":
                    order = "-powermeter__powermeter_anotation"
                    order_alias = "asc"
                else:
                    order_alias = "desc"
            else:
                if "order_model" in request.GET:
                    if request.GET["order_model"] == "asc":
                        order = "powermeter__powermeter_model__powermeter_brand"
                        order_model = "desc"
                    else:
                        order = \
                            "-powermeter__powermeter_model__powermeter_brand"
                        order_model = "asc"

                if "order_serial" in request.GET:
                    if request.GET["order_serial"] == "asc":
                        order = "powermeter__powermeter_serial"
                        order_serial = "desc"
                    else:
                        order = "-powermeter__powermeter_serial"
                        order_serial = "asc"

                if "order_status" in request.GET:
                    if request.GET["order_status"] == "asc":
                        order = "powermeter__status"
                        order_status = "desc"
                    else:
                        order = "-powermeter__status"
                        order_status = "asc"

            lista = PowermeterForIndustrialEquipment.objects.filter(
                industrial_equipment=template_vars["industrial_eq"]
            ).order_by(order)
            template_vars['order_alias'] = order_alias
            template_vars['order_model'] = order_model
            template_vars['order_serial'] = order_serial
            template_vars['order_status'] = order_status
            template_vars['powermeters'] = lista

            if 'msj' in request.GET:
                template_vars['message'] = request.GET['msj']
                template_vars['msg_type'] = request.GET['ntype']

            template_vars['ver_medidores'] = True
            if has_permission(
                    request.user,
                    CREATE,
                    "Asignación de medidores eléctricos a equipos industriales"
            ) or request.user.is_superuser:
                template_vars['show_asign'] = True
            else:
                template_vars['show_asign'] = False
        else:
            template_vars['ver_medidores'] = False
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/consumer_units/see_ie.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def suscribe_alarm(request, id_alarm):
    pass

@login_required(login_url='/')
def unsuscribe_alarm(request, id_alarm):
    pass

def search_alarm(request):
    pass