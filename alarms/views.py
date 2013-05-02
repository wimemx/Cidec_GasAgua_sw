# -*- coding: utf-8 -*-
import time
import datetime
import json
from django.utils import simplejson
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
                    alarm.max_value = request.POST['alarm_max_value'].strip()
                    alarm.min_value = request.POST['alarm_min_value'].strip()
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
                alarm.max_value = request.POST['alarm_max_value'].strip()
                alarm.min_value = request.POST['alarm_min_value'].strip()
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
    if datacontext:
        template_vars["datacontext"] = datacontext
    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']
    alarm = get_object_or_404(Alarms, id=id_alarm)
    template_vars["alarm"] = alarm
    template_vars['building'] = get_building_siblings(alarm.consumer_unit.building)
    template_vars['compania'] = template_vars['building'][0].company
    template_vars['company'] = get_company_siblings(template_vars['compania'])
    template_vars['curr_cluster'] = template_vars['company'][0].cluster
    template_vars_template = RequestContext(request, template_vars)
    return render_to_response("alarms/alarm_detail.html", template_vars_template)


@login_required(login_url='/')
def mostrar_suscripcion_alarma(request, id_alarm):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}
    if datacontext:
        template_vars["datacontext"] = datacontext
    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']
    alarm = get_object_or_404(UserNotificationSettings, id=id_alarm)

    template_vars["usuario"] = alarm.user
    template_vars['building'] = alarm.alarm.consumer_unit.building.building_name
    template_vars['parameter'] = alarm.alarm.electric_parameter.name
    if alarm.notification_type == 1 :
        notificacion= 'Push'
    if alarm.notification_type == 3 :
        notificacion= 'E-mail'
    if alarm.notification_type == 4 :
        notificacion= 'Ninguno'




    template_vars['notification'] = notificacion

    template_vars_template = RequestContext(request, template_vars)
    return render_to_response("alarms/alarm_suscription_detail.html", template_vars_template)




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
        lista = UserNotificationSettings.objects.all()
        template_vars["lista"] = lista

        paginator = Paginator(lista, 10)
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1


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

            lista = UserNotificationSettings.objects.filter(
                Q(
                    user__username__icontains=
                    request.GET['search']) |
                Q(user__first_name__icontains=request.GET['search'])|

                Q(user__last_name__icontains=request.GET['search'])|

                Q(alarm__consumer_unit__building__building_name__icontains=request.GET['search'])|

                Q(alarm__electric_parameter__name__icontains=request.GET['search'])).order_by(order)


            template_vars["lista"] = lista
        else:

            lista=UserNotificationSettings.objects.all().order_by(order)

        # If page request (9999) is out of range, deliver last page of results.
        order_consumer = 'asc'



        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user
        template_vars['order_user']=order_user
        template_vars['order_name']=order_name
        template_vars['order_lastname']=order_lastname
        template_vars['order_alarm']=order_alarm
        template_vars['order_date']=order_date
        template_vars['order_status']=order_status
        template_vars["lista"] = lista
        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']
        paginator = Paginator(lista, 10)
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
    if has_permission(request.user, VIEW,
                      permission) or \
            request.user.is_superuser:
        permission = "Ver edificios"
        edificios = get_all_buildings_for_operation(permission, VIEW, request.user)
        template_vars["edificios"] = edificios
        lista = UserNotificationSettings.objects.all()
        template_vars["lista"] = lista




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
            return HttpResponseRedirect("/configuracion/suscripcion_alarma/?msj=" +
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

    suscripcion= UserNotificationSettings.objects.get(pk=id_alarm)
    print suscripcion.alarm.consumer_unit.building.building_name
    template_vars['edit_suscription']= suscripcion
    template_vars['operation']='edit'
    permission = "Ver alta suscripción alarma"
    if has_permission(request.user, VIEW,
                      permission) or \
            request.user.is_superuser:
        permission = "Ver edificios"
        edificios = get_all_buildings_for_operation(permission, VIEW, request.user)
        template_vars["edificios"] = edificios
        lista = UserNotificationSettings.objects.all()
        template_vars["lista"] = lista


    if request.POST:
            alarma = Alarms.objects.get(pk=request.POST['alarmselector'])
            notificacion= request.POST['notiselect']
            usuario=  request.user

            usernoti = UserNotificationSettings.objects.get(pk=id_alarm)
            usernoti.alarm= alarma
            usernoti.user= usuario
            usernoti.notification_type=notificacion
            usernoti.save()
            mensaje = "Edición de suscripción a alarma exitosa."
            _type = "n_success"
            return HttpResponseRedirect("/configuracion/suscripcion_alarma/?msj=" +
                                    mensaje + "&ntype=" + _type)

    template_vars_template = RequestContext(request, template_vars)
    return render_to_response(
        "alarms/add_alarm_suscription.html",
        template_vars_template)



def search_alarm(request):
    pass


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

        mensaje = str("El estatus de la suscripción a la alarma ").decode("utf-8") + \
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


"""
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
      template_vars["alarm"] = get_object_or_404(Alarm,pk=int(id_ie))

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
            "alarms/alarm_detail.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

"""


