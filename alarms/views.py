# -*- coding: utf-8 -*-
import time
import datetime
import json
import re

from django.core.mail import send_mail, EmailMultiAlternatives
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.context import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.contrib.auth.decorators import login_required

from rbac.rbac_functions import get_buildings_context, has_permission
from c_center.c_center_functions import get_clusters_for_operation, \
    get_c_unitsforbuilding_for_operation

from alarms.models import *
from c_center.models import Building, Alarm
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
            el = ElectricParameters.objects.get(
                pk=int(request.POST['alarm_param']))
            timeunix = time.mktime(datetime.datetime.now().timetuple())
            timeunix = str(int(timeunix))
            user_pk = str(request.user.pk)
            building = Building.objects.get(pk=int(request.POST['building']))
            if request.POST['c_unit'] == "todas":
                cus = get_c_unitsforbuilding_for_operation(
                    permission, CREATE, request.user, building
                )[0]
                for cu in cus:
                    id_al = cu.profile_powermeter.powermeter.powermeter_serial
                    id_al += "_"
                    id_al += timeunix
                    id_al += "_"
                    id_al += user_pk
                    alarma = Alarms(
                        alarm_identifier=id_al,
                        electric_parameter=el,
                        max_value=request.POST['alarm_max_value'].strip(),
                        min_value=request.POST['alarm_min_value'].strip(),
                        consumer_unit=cu)
                    alarma.save()
            else:
                cu = ConsumerUnit.objects.get(pk=int(request.POST['c_unit']))
                id_al = cu.profile_powermeter.powermeter.powermeter_serial
                id_al += "_"
                id_al += timeunix
                id_al += "_"
                id_al += user_pk

                alarma = Alarms(
                    alarm_identifier=id_al,
                    electric_parameter=el,
                    max_value=request.POST['alarm_max_value'].strip(),
                    min_value=request.POST['alarm_min_value'].strip(),
                    consumer_unit=cu)
                alarma.save()

            message = "La alarma se ha creado exitosamente"
            _type = "n_success"
            # make json for new config
            b_alarms = Alarms.objects.filter(consumer_unit__building=building)
            alarm_arr = []
            for ba in b_alarms:
                status = "true" if ba.status else "false"
                min_value = 0 if not ba.min_value else float(str(ba.min_value))
                max_value = 0 if not ba.max_value else float(str(ba.max_value))
                alarm_arr.append(
                    dict(alarm_identifier=ba.alarm_identifier,
                         electric_parameter_id=ba.electric_parameter.pk,
                         min_value=min_value,
                         max_value=max_value,
                         status=status
                         ))
            i_eq = IndustrialEquipment.objects.get(building=building)
            i_eq.has_new_alarm_config = True
            i_eq.new_alarm_config = json.dumps(alarm_arr)
            i_eq.modified_by = request.user
            i_eq.save()

            if has_permission(request.user, VIEW,
                              "Ver alarmas") or \
                    request.user.is_superuser:
                return HttpResponseRedirect(
                    "/configuracion/alarmas?msj=" +
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
    alarm = get_object_or_404(Alarm, pk=int(id_ie))
    template_vars["id_ie"] = id_ie
    permission = "Modificar alarmas"
    if has_permission(request.user, UPDATE,
                      permission) or \
            request.user.is_superuser:
        
        clusters = get_clusters_for_operation(permission, UPDATE, request.user)
        buildings = get_all_buildings_for_operation(
            permission, CREATE, request.user)
        template_vars['buildings'] = buildings

        if request.method == 'POST':
            building = Building.objects.get(pk=int(request.POST['ie_building']))
            alarm.alias = request.POST['ie_alias'].strip()
            alarm.description = request.POST['ie_desc'].strip()
            alarm.server = request.POST['ie_server'].strip()
            alarm.building = building
            alarm.modified_by = request.user
            alarm.save()
            message = "El equipo industrial se ha actualizado exitosamente"
            _type = "n_success"
            if has_permission(request.user, VIEW,
                              "Ver equipos industriales") or \
                    request.user.is_superuser:
                return HttpResponseRedirect(
                    "/buildings/alarmuipments?msj=" +
                    message +
                    "&ntype=" + _type)
            template_vars["message"] = message
            template_vars["type"] = type
        template_vars["post"] = dict(ie_alias=alarm.alias,
                                     ie_desc=alarm.description,
                                     ie_server=alarm.server,
                                     ie_building = alarm.building.pk)

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/consumer_units/ind_eq.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def alarm_list(request):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']

    if has_permission(request.user, VIEW,
                      "Ver alarmas") or request.user.is_superuser:
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_consumer = 'asc'
        order_parameter = 'asc'
        order_min_value = 'asc'
        order_max_value = 'asc'
        order_changed = 'asc'
        order_status = 'asc'
        order_building = 'asc'
        #default order
        order = "consumer_unit__profile_powermeter__powermeter" \
                "__powermeter_anotation"
        if "order_consumer" in request.GET:
            if request.GET["order_consumer"] == "desc":
                order = "-consumer_unit__profile_powermeter__powermeter" \
                        "__powermeter_anotation"
                order_consumer = "asc"
            else:
                order_consumer = "desc"

        elif "order_building" in request.GET:
            if request.GET["order_building"] == "asc":
                order = "consumer_unit__building__building_name"
                order_building = "desc"
            else:
                order = "-consumer_unit__building__building_name"

        elif "order_parameter" in request.GET:
            if request.GET["order_parameter"] == "asc":
                order = "electric_parameter__name"
                order_parameter = "desc"
            else:
                order = "-electric_parameter__name"

        elif "order_min_value" in request.GET:
            if request.GET["order_min_value"] == "asc":
                order = "min_value"
                order_min_value = "desc"
            else:
                order = "-min_value"

        elif "order_max_value" in request.GET:
            if request.GET["order_max_value"] == "asc":
                order = "max_value"
                order_max_value = "desc"
            else:
                order = "-max_value"

        elif "order_changed" in request.GET:
            if request.GET["order_changed"] == "asc":
                order = "last_changed"
                order_changed = "desc"
            else:
                order = "-last_changed"

        elif "order_status" in request.GET:
            if request.GET["order_status"] == "asc":
                order = "status"
                order_status = "desc"
            else:
                order = "-status"
                order_status = "asc"

        if search:
            lista = Alarms.objects.filter(
                Q(
                    consumer_unit__building__building_name__icontains=
                    request.GET['search']) |
                Q(electric_parameter__name__icontains=request.GET['search']) |
                Q(
                    consumer_unit__profile_powermeter__powermeter__icontains=
                    request.GET['search'])).order_by(order)

        else:
            lista = Alarms.objects.all().order_by(order)

        # muestra 10 resultados por pagina
        paginator = Paginator(lista, 10)
        template_vars['order_consumer'] = order_consumer
        template_vars['order_building'] = order_building
        template_vars['order_parameter'] = order_parameter
        template_vars['order_min_value'] = order_min_value
        template_vars['order_max_value'] = order_max_value
        template_vars['order_changed'] = order_changed
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
            "alarms/alarm_list.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_alarm(request):
    if has_permission(request.user,
                      UPDATE,
                      "Modificar alarmas") or \
            request.user.is_superuser:
        if request.POST['actions'] != '0':
            for key in request.POST:
                if re.search('^alarma_\w+', key):
                    r_id = int(key.replace("alarma_", ""))
                    alarm = get_object_or_404(Alarms, pk=r_id)

                    if alarm.status:
                        alarm.status = False
                    else:
                        alarm.status = True

                    alarm.save()

            mensaje = "Las alarmas seleccionadas han " \
                      "cambiado su estatus correctamente"
            _type = "n_success"
        else:
            mensaje = str("No se ha seleccionado una acción").decode("utf-8")
            _type = "n_notif"
        return HttpResponseRedirect("/configuracion/alarmas/?msj=" +
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
                      "Modificar alarmas") or \
            request.user.is_superuser:
        alarm = get_object_or_404(Alarms, pk=id_alarm)
        if alarm.status:
            alarm.status = False
            str_status = "Inctivo"
        else:
            alarm.status = True
            str_status = "Activo"
        alarm.save()
        mensaje = "El estatus de la alarma " + \
                  alarm.consumer_unit.profile_powermeter.powermeter\
                      .powermeter_anotation + \
                  " - " + alarm.electric_parameter.name + \
                  ", ha cambiado a " + str_status
        _type = "n_success"

        return HttpResponseRedirect(
            "/configuracion/alarmas/?msj=" + mensaje +
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
        template_vars["alarm"] = get_object_or_404(Alarm,
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

            lista = PowermeterForAlarm.objects.filter(
                alarmuipment=template_vars["alarm"]
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