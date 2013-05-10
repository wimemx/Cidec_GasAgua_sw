# -*- coding: utf-8 -*-
import time
import datetime
import json
from django.utils import simplejson
import re
import locale

import variety

from django.core.mail import send_mail, EmailMultiAlternatives
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.context import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.db.models import Q
from django.db.models.aggregates import Count
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.contrib.auth.decorators import login_required
from django.utils import timezone


from rbac.rbac_functions import get_buildings_context, has_permission
from c_center.c_center_functions import get_clusters_for_operation, \
    get_c_unitsforbuilding_for_operation, get_cu_siblings, \
    get_building_siblings, get_company_siblings, get_all_buildings_for_operation

from alarms.alarm_functions import *
from alarms.models import *
from c_center.models import Building, IndustrialEquipment, CompanyBuilding
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
        parameters = ElectricParamaeters.objects.all()
        template_vars['parameters'] = parameters
        if request.method == 'POST':
            el = ElectricParameters.objects.get(
                pk=int(request.POST['alarm_param']))
            timeunix = time.mktime(datetime.datetime.now().timetuple())
            timeunix = str(int(timeunix))
            user_pk = str(request.user.pk)
            building = Building.objects.get(pk=int(request.POST['building']))

            max_value = request.POST['alarm_max_value'].strip()
            min_value = request.POST['alarm_min_value'].strip()
            if not max_value:
                max_value = 0
            if not min_value:
                min_value = 0
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
                        max_value=max_value,
                        min_value=min_value,
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
                    max_value=max_value,
                    min_value=min_value,
                    consumer_unit=cu)
                alarma.save()

            message = "La alarma se ha creado exitosamente"
            _type = "n_success"

            set_alarm_json(building, request.user)

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
    alarm = get_object_or_404(Alarms, pk=int(id_alarm))
    permission = "Modificar alarmas"
    if has_permission(request.user, UPDATE,
                      permission) or \
            request.user.is_superuser:

        clusters = get_clusters_for_operation(permission, UPDATE, request.user)
        template_vars['clusters'] = clusters
        parameters = ElectricParameters.objects.all()
        template_vars['parameters'] = parameters
        template_vars['consumer_units'] = get_cu_siblings(alarm.consumer_unit)
        template_vars['comp_buildings'] = get_building_siblings(
            alarm.consumer_unit.building)
        template_vars['curr_company'] = \
            template_vars['comp_buildings'][0].company
        template_vars['companies'] = get_company_siblings(
            template_vars['curr_company'])
        template_vars['curr_cluster'] = template_vars['companies'][0].cluster

        if request.method == 'POST':
            el = ElectricParameters.objects.get(
                pk=int(request.POST['alarm_param']))
            timeunix = time.mktime(datetime.datetime.now().timetuple())
            timeunix = str(int(timeunix))
            user_pk = str(request.user.pk)
            building = Building.objects.get(pk=int(request.POST['building']))

            max_value = request.POST['alarm_max_value'].strip()
            min_value = request.POST['alarm_min_value'].strip()
            if not max_value:
                max_value = 0
            if not min_value:
                min_value = 0

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
                    alarm.alarm_identifier = id_al
                    alarm.electric_parameter = el
                    alarm.max_value = max_value
                    alarm.min_value = min_value
                    alarm.consumer_unit = cu
                    alarm.save()
            else:
                cu = ConsumerUnit.objects.get(pk=int(request.POST['c_unit']))
                id_al = cu.profile_powermeter.powermeter.powermeter_serial
                id_al += "_"
                id_al += timeunix
                id_al += "_"
                id_al += user_pk

                alarm.alarm_identifier = id_al
                alarm.electric_parameter = el
                alarm.max_value = max_value
                alarm.min_value = min_value
                alarm.consumer_unit = cu
                alarm.save()

            message = "La alarma se ha actualizado exitosamente"
            _type = "n_success"

            set_alarm_json(building, request.user)

            if has_permission(request.user, VIEW,
                              "Ver alarmas") or \
                    request.user.is_superuser:
                return HttpResponseRedirect(
                    "/configuracion/alarmas?msj=" +
                    message +
                    "&ntype=" + _type)
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars["alarm"] = alarm

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "alarms/alarm.html",
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

                    building = alarm.consumer_unit.building

                    if alarm.status:
                        alarm.status = False
                    else:
                        alarm.status = True

                    alarm.save()

                    set_alarm_json(building, request.user)

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
        building = alarm.consumer_unit.building
        set_alarm_json(building, request.user)
        mensaje = "El estatus de la alarma " + \
                  alarm.consumer_unit.profile_powermeter.powermeter \
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


@login_required(login_url='/')
def mostrar_alarma(request, id_alarm):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}
    permission = "Ver suscripciones a alarmas"
    if has_permission(request.user, VIEW,
                      permission) or \
            request.user.is_superuser:
        if datacontext:
            template_vars["datacontext"] = datacontext
        template_vars["sidebar"] = request.session['sidebar']
        template_vars["empresa"] = request.session['main_building']
        template_vars["company"] = request.session['company']
        alarm = get_object_or_404(Alarms, id=id_alarm)
        template_vars["alarm"] = alarm
        template_vars['building'] = get_building_siblings(
            alarm.consumer_unit.building)
        template_vars['compania'] = template_vars['building'][0].company
        template_vars['company'] = get_company_siblings(template_vars['compania'])
        template_vars['curr_cluster'] = template_vars['company'][0].cluster
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("alarms/alarm_detail.html",
                                  template_vars_template)


@login_required(login_url='/')
def mostrar_suscripcion_alarma(request, id_alarm):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}
    permission = "Ver suscripciones a alarmas"
    if has_permission(request.user, VIEW,
                      permission) or \
            request.user.is_superuser:
        if datacontext:
            template_vars["datacontext"] = datacontext

        template_vars["sidebar"] = request.session['sidebar']
        template_vars["empresa"] = request.session['main_building']
        template_vars["company"] = request.session['company']
        alarm = get_object_or_404(UserNotificationSettings, id=id_alarm)

        template_vars["usuario"] = alarm.user
        template_vars['building'] = alarm.alarm.consumer_unit.building.building_name
        template_vars['parameter'] = alarm.alarm.electric_parameter.name

        if alarm.notification_type == 1:
            notificacion = 'Push'
        elif alarm.notification_type == 3:
            notificacion = 'E-mail'
        else:
            notificacion = 'Ninguno'




    template_vars['notification'] = notificacion

    template_vars_template = RequestContext(request, template_vars)
    return render_to_response("alarms/alarm_suscription_detail.html",
                              template_vars_template)


@login_required(login_url='/')
def alarm_suscription_list(request):
    permission = "Ver suscripciones a alarmas"
    if has_permission(request.user, VIEW,
                      permission) or \
            request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars["datacontext"] = datacontext

        template_vars["sidebar"] = request.session['sidebar']
        template_vars["empresa"] = request.session['main_building']
        template_vars["company"] = request.session['company']

        order_user = 'asc'
        order_name = 'asc'
        order_lastname = 'asc'
        order_alarm = 'asc'
        order_date = 'asc'
        order_status = 'asc'

        order = "alarm__consumer_unit__building__building_name"
        if "order_user" in request.GET:
            if request.GET["order_user"] == "desc":
                order = "-user__username"
                order_user = "asc"
            else:
                order = "user__username"
                order_user = "desc"

        elif "order_name" in request.GET:
            if request.GET["order_name"] == "asc":
                order = "user__first_name"
                order_name = "desc"
            else:
                order = "-user__first_name"

        elif "order_lastname" in request.GET:
            if request.GET["order_lastname"] == "asc":
                order = "user__last_name"
                order_lastname = "desc"
            else:
                order = "-user__last_name"

        elif "order_alarm" in request.GET:
            if request.GET["order_alarm"] == "asc":
                order = "alarm__consumer_unit__building__building_name"
                order_alarm = "desc"
            else:
                order = "-alarm__consumer_unit__building__building_name"

        elif "order_date" in request.GET:
            if request.GET["order_date"] == "asc":
                order = "alarm__last_changed"
                order_date = "desc"
            else:
                order = "-alarm__last_changed"

        elif "order_status" in request.GET:
            if request.GET["order_status"] == "asc":
                order = "status"
                order_status = "desc"
            else:
                order = "-status"
                order_status = "asc"



        if "search" in request.GET:
            search = request.GET["search"]
            if request.user.is_superuser:
                lista = UserNotificationSettings.objects.filter(
                    Q(user__username__icontains=request.GET['search']) |
                    Q(user__first_name__icontains=request.GET['search']) |
                    Q(user__last_name__icontains=request.GET['search']) |
                    Q(alarm__consumer_unit__building__building_name__icontains=
                        request.GET['search']) |
                    Q(alarm__electric_parameter__name__icontains=
                        request.GET['search'])).order_by(order)
            else:
                lista = UserNotificationSettings.objects.filter(
                    Q(user__username__icontains=request.GET['search']) |
                    Q(user__first_name__icontains=request.GET['search']) |
                    Q(user__last_name__icontains=request.GET['search']) |
                    Q(alarm__consumer_unit__building__building_name__icontains=
                        request.GET['search']) |
                    Q(alarm__electric_parameter__name__icontains=
                        request.GET['search']) and
                    Q(user=request.user)).order_by(order)

        else:
            if request.user.is_superuser:
                lista = UserNotificationSettings.objects.all().order_by(order)
            else:
                lista = UserNotificationSettings.objects.filter(user=request.user)

        # If page request (9999) is out of range, deliver last page of results.
        order_consumer = 'asc'
        #La lista es el queryset de la busqueda

        paginator = Paginator(lista, 10)
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)
        # Formato
        template_vars['paginacion'] = pag_user
        template_vars['order_user'] = order_user
        template_vars['order_name'] = order_name
        template_vars['order_lastname'] = order_lastname
        template_vars['order_alarm'] = order_alarm
        template_vars['order_date'] = order_date
        template_vars['order_status'] = order_status
        template_vars["lista"] = lista
        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']
        template_vars_template = RequestContext(request, template_vars)

        return render_to_response(
            "alarms/alarm_suscription_list.html",
            template_vars_template)



@login_required(login_url='/')
def add_alarm_suscription(request):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}
    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']

    permission = "Ver alta suscripción alarma"
    #Operación es CREATE
    if has_permission(request.user, CREATE,
                      permission) or \
            request.user.is_superuser:
        permission = "Ver edificios"
        edificios = get_all_buildings_for_operation(permission,
                                                    VIEW,
                                                    request.user)
        template_vars["edificios"] = edificios

        if request.GET.get('id'):

            b_id = request.GET.get('id')
            data = get_alarm_from_building(b_id)
            data= simplejson.dumps(data)

            return HttpResponse(content=data, content_type="application/json")

        if request.POST:
            alarma = Alarms.objects.get(pk=request.POST['alarmselector'])
            notificacion= request.POST['notiselect']
            usuario=  request.user

            usernoti = UserNotificationSettings(
                        alarm=alarma,
                        user=usuario,
                        notification_type=notificacion,
                        status=True)
            usernoti.save()
            mensaje = "Suscripción a alarma exitosa."
            _type = "n_success"
            return HttpResponseRedirect(
                "/configuracion/suscripcion_alarma/?msj=" +
                mensaje + "&ntype=" + _type)
    template_vars_template = RequestContext(request, template_vars)
    return render_to_response(
        "alarms/add_alarm_suscription.html",
        template_vars_template)


@login_required(login_url='/')
def edit_alarm_suscription(request, id_alarm):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}
    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']
    suscripcion=get_object_or_404(UserNotificationSettings, pk=id_alarm)
    template_vars['edit_suscription'] = suscripcion
    template_vars['operation'] = 'edit'
    permission = "Modificar suscripción a alarmas"
    if has_permission(request.user, UPDATE,
                      permission) or \
            request.user.is_superuser:
        permission = "Ver edificios"
        edificios = get_all_buildings_for_operation(permission,
                                                    VIEW,
                                                    request.user)
        template_vars["edificios"] = edificios
        lista = UserNotificationSettings.objects.all()
        template_vars["lista"] = lista

    if request.POST:
            alarma = Alarms.objects.get(pk=request.POST['alarmselector'])
            notificacion = request.POST['notiselect']
            usuario = request.user

            usernoti = UserNotificationSettings.objects.get(pk=id_alarm)
            usernoti.alarm = alarma
            usernoti.user = usuario
            usernoti.notification_type = notificacion
            usernoti.save()
            mensaje = "Edición de suscripción a alarma exitosa."
            _type = "n_success"
            return HttpResponseRedirect(
                "/configuracion/suscripcion_alarma/?msj=" +
                mensaje + "&ntype=" + _type)

    template_vars_template = RequestContext(request, template_vars)
    return render_to_response(
        "alarms/add_alarm_suscription.html",
        template_vars_template)


@login_required(login_url='/')
def status_suscription_alarm(request, id_alarm):
    if has_permission(request.user,
                      UPDATE,
                      "Modificar suscripción a alarmas") or \
            request.user.is_superuser:
        alarm = get_object_or_404(UserNotificationSettings, pk=id_alarm)

        if alarm.status:
            alarm.status = False
            str_status = "Inctivo"
        else:
            alarm.status = True
            str_status = "Activo"
        alarm.save()

        mensaje = \
            str("El estatus de la suscripción a la alarma ").decode("utf-8") + \
                  alarm.alarm.consumer_unit.profile_powermeter.powermeter \
                      .powermeter_anotation + \
                  " - " + alarm.alarm.electric_parameter.name + \
                  ", ha cambiado a " + str_status
        _type = "n_success"

        return HttpResponseRedirect(
            "/configuracion/suscripcion_alarma/?msj=" + mensaje +
            "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_suscription_batch_alarm(request):
    if has_permission(request.user,
                      UPDATE,
                      "Modificar suscripción a alarmas") or \
            request.user.is_superuser:
        if request.POST['actions'] != '0':
            for key in request.POST:
                if re.search('^alarma_\w+', key):
                    r_id = int(key.replace("alarma_", ""))
                    alarm = get_object_or_404(UserNotificationSettings, pk=r_id)
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
        return HttpResponseRedirect("/configuracion/suscripcion_alarma/?msj=" +
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
def user_notifications(request):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}
    if datacontext:
        template_vars = {"datacontext": datacontext}
    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']
    template_vars['building'] = request.session['main_building']
    if has_permission(request.user,
                      VIEW,
                      "Ver suscripciones a alarmas") or \
            request.user.is_superuser:
        date_notif = datetime.date.today() - datetime.timedelta(days=7)
        #get the last week notifications

        if "todas" in request.GET:
            notifs = UserNotifications.objects.all().exclude(
                alarm_event__alarm__status=False
            ).order_by("-alarm_event__triggered_time")
            template_vars['all'] = True
        else:
            notifs = UserNotifications.objects.filter(
                user=request.user,
                alarm_event__triggered_time__gte=date_notif
            ).exclude(
                alarm_event__alarm__status=False
            ).order_by("-alarm_event__triggered_time")
            template_vars['all'] = False
        arr_day_notif = {}

        today_str = str(datetime.date.today())
        #separate notifs by day
        tz = timezone.get_current_timezone()
        for notif in notifs:
            notif.read = True
            notif.save()
            #get localized time
            local_triggered_time = variety.convert_from_utc(
                notif.alarm_event.triggered_time.time(), tz)
            #get localized datetime
            notif.alarm_event.triggered_time = \
                notif.alarm_event.triggered_time.astimezone(tz)
            date_n = notif.alarm_event.triggered_time.date()

            #type of alarm (off limits, or under limits)
            if notif.alarm_event.value > notif.alarm_event.alarm.max_value:
                _type = "max"
            elif notif.alarm_event.value < notif.alarm_event.alarm.min_value:
                _type = "min"
            else:
                _type = "other"

            n_dic = {"notif": notif,
                     "triggered": local_triggered_time,
                     "type": _type
                     }
            if str(date_n) in arr_day_notif:
                #arr_day_notif['2013-04-25']={}
                arr_day_notif[str(date_n)].append(n_dic)
            else:
                arr_day_notif[str(date_n)] = [n_dic]

        template_vars['notifications'] = arr_day_notif
        template_vars['today_str'] = today_str

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("alarms/notification_list.html",
                                  template_vars_template)
    template_vars_template = RequestContext(request, template_vars)
    return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def get_unread_notifs_count(request):
    if has_permission(request.user,
                      VIEW,
                      "Ver suscripciones a alarmas") or \
            request.user.is_superuser:
        n_count = UserNotifications.objects.filter(
            user=request.user, read=False
        ).values("alarm_event").annotate(
            Count("alarm_event"))
        data = str(len(n_count))
    else:
        data = "false"

    return HttpResponse(content=data, status=200)


@login_required(login_url='/')
def get_latest_notifs(request):
    if has_permission(request.user,
                      VIEW,
                      "Ver suscripciones a alarmas") or \
            request.user.is_superuser:
        #a que alarmas está suscrito el usuario (alarmas distintas)
        usersettings = UserNotificationSettings.objects.filter(
            user=request.user, alarm__status=True
        ).values(
            "alarm__pk").annotate(Count("alarm"))
        arr_alarms = [al['alarm__pk'] for al in usersettings]

        #Las notificaciones sin leer
        notifs = UserNotifications.objects.filter(
            user=request.user, alarm_event__alarm__pk__in=arr_alarms,
            read=False
        ).exclude(
            alarm_event__alarm__status=False).order_by(
                "-alarm_event__triggered_time")

        arr_notif = []
        tz = timezone.get_current_timezone()
        ahora = datetime.datetime.now(tz)

        for notif in notifs:
            t_time = notif.alarm_event.triggered_time.astimezone(tz)
            diff = ahora - t_time
            difference = str(diff)
            #1 day, 18:01:54.334553
            differen = difference.split(",")
            time_ = ''
            if len(differen) > 1:
                differen[0] = differen[0].replace("day", "día")

                #['1 day', '18:01:54.334553']
                time_ = "Hace " + differen[0]
            else:
                #['18:01:54.334553']
                hours = differen[0].split(":")
                if int(hours[0]):
                    time_ = "hace " + hours[0] + " horas"
                elif int(hours[1]):
                    time_ = "hace " + hours[1] + " minutos"
                else:
                    time_ = "hace " + hours[2] + " segundos"
            comp = CompanyBuilding.objects.get(
                building=notif.alarm_event.alarm.consumer_unit.building)
            image = comp.company.company_logo.name
            cons_unit = \
                notif.alarm_event.alarm.consumer_unit.building.building_name
            cons_unit += " en "
            cons_unit += notif.alarm_event.alarm.consumer_unit\
                .electric_device_type.electric_device_type_name
            val_min = notif.alarm_event.alarm.min_value
            min_r = float(val_min) if val_min else ""
            val_max = notif.alarm_event.alarm.max_value
            max_r = float(val_max) if val_max else ""
            arr_notif.append(dict(
                ttime=str(t_time),
                readed=notif.read,
                param=notif.alarm_event.alarm.electric_parameter.name,
                units=notif.alarm_event.alarm.electric_parameter.param_units,
                n_value=float(notif.alarm_event.value),
                min_r=min_r,
                max_r=max_r,
                time=time_,
                image=image,
                consumer_unit=cons_unit
            ))
        return HttpResponse(content=json.dumps(arr_notif),
                            mimetype="application/json")