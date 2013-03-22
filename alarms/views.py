# -*- coding: utf-8 -*-
from django.core.mail import send_mail, EmailMultiAlternatives
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.context import RequestContext
from django.shortcuts import render_to_response, get_object_or_404

from rbac.rbac_functions import get_buildings_context, has_permission
from c_center.c_center_functions import get_clusters_for_operation

from alarms.models import *
from rbac.models import Operation


VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")


def change_ie_time_config(request):
    pass


def see_times(request):
    pass


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
        if request.method == 'POST':
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
def edit_alarm(request):
    pass


@login_required(login_url='/')
def alarm_list(request):
    pass


@login_required(login_url='/')
def suscribe_alarm(request):
    pass


