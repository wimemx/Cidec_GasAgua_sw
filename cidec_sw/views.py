# -*- coding: utf-8 -*-
#standard library imports
import os
import csv
from itertools import cycle
from random import uniform, randrange
from datetime import timedelta
from decimal import Decimal
import pytz #for timezone support
import datetime

#related third party imports
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from collections import defaultdict

#local application/library specific imports
from c_center.models import ProfilePowermeter, ElectricData, ElectricDataTemp, \
    ConsumerUnit, Powermeter
from c_center.views import main_page, week_report_kwh
from c_center.c_center_functions import set_default_session_vars
from rbac.models import DataContextPermission, Object, PermissionAsigment, \
    UserRole, GroupObject, MenuCategs, MenuHierarchy
from rbac.rbac_functions import get_buildings_context
from variety import unique_from_array, timed

from django.shortcuts import redirect, render

GRAPHS = ['Potencia Activa (kW)', 'Potencia Reactiva (KVar)',
          'Factor de Potencia (PF)',
          'kW Hora', 'kWh/h Consumido', 'kVAR Hora', 'kVAR Hora Consumido']
GRAPHS_ENERGY = [ob.object.object_name for ob in GroupObject.objects.filter(
    group__group_name="Energía")] #['Potencia Activa (KW)', 'Kw Fase1', 'Kw Fase2', 'Kw Fase3', 'Kw/H acumulado', 'Kw/h/h']
GRAPHS_I = [ob.object.object_name for ob in GroupObject.objects.filter(
    group__group_name="Corriente")] #['I1', 'I2', 'I3']
GRAPHS_V = [ob.object.object_name for ob in GroupObject.objects.filter(
    group__group_name="Voltaje")] #['V1', 'V2', 'V3']
GRAPHS_PF = [ob.object.object_name for ob in GroupObject.objects.filter(
    group__group_name="Factor de Potencia")] #['PF',]
GRAPHS.extend(GRAPHS_ENERGY)
GRAPHS.extend(GRAPHS_I)
GRAPHS.extend(GRAPHS_V)
GRAPHS.extend(GRAPHS_PF)


def set_timezone(request):
    if request.method == 'POST':
        request.session['django_timezone'] = pytz.timezone(
            request.POST['timezone'])
        return redirect('/')
    else:
        return render(request, 'set_timezone.html',
                      {'timezones': pytz.common_timezones})


def parse_csv(request):
    dir_path = '/Users/wime/Downloads/BaseDeDatosSATEC/'
    files = os.listdir(dir_path)
    dir_fd = os.open(dir_path, os.O_RDONLY)
    os.fchdir(dir_fd)
    html = ''
    for file in files:
        if file == '.DS_Store':
            continue
        data = csv.reader(open(file))
        # Read the column names from the first line of the file
        fields = data.next()
        for row in data:
        # Zip together the field names and values
            items = zip(fields, row)
            item = {}
            # Add the value to our dictionary
            for (name, value) in items:
                item[name] = value.strip()

            powerp = ProfilePowermeter.objects.order_by('?')

            elec_data = ElectricData(
                profile_powermeter=powerp[0],
                powermeter_serial=item['powermeter_serial'],
                medition_date=datetime.datetime.now(),
                V1=item['V1'],
                V2=item['V2'],
                V3=item['V3'],
                I1=item['I1'],
                I2=item['I2'],
                I3=item['I3'],
                kWL1=item['kWL1'],
                kWL2=item['kWL2'],
                kWL3=item['kWL3'],
                kvarL1=item['kvarL1'],
                kvarL2=item['kvarL2'],
                kvarL3=item['kvarL3'],
                kVAL1=item['kVAL1'],
                kVAL2=item['kVAL2'],
                kVAL3=item['kVAL3'],
                PFL1=item['PFL1'],
                PFL2=item['PFL2'],
                PFL3=item['PFL3'],
                kW=item['kW'],
                kvar=item['kvar'],
                kVA=item['kVA'],
                PF=item['PF'],
                In=item['In'],
                FREQ=item['FREQ'],
                kWIMPSDMAX=item['kWIMPSDMAX'],
                kWIMPACCDMD=item['kWIMPACCDMD'],
                kVASDMAX=item['kVASDMAX'],
                kVAACCDMD=item['kVAACCDMD'],
                I1DMDMAX=item['I1DMDMAX'],
                I2DMDMAX=item['I2DMDMAX'],
                I3DMDMAX=item['I3DMDMAX'],
                kWhIMPORT=item['kWhIMPORT'],
                kWhEXPORT=item['kWhEXPORT'],
                kvarhNET=item['kvarhNET'],
                kvarhIMPORT=item['kvarhIMPORT'],
                V1THD=item['V1THD'],
                V2THD=item['V2THD'],
                V3THD=item['V3THD'],
                I1THD=item['I1THD'],
                I2THD=item['I2THD'],
                I3THD=item['I3THD']
            )

            elec_data.save()

            html += str(elec_data) + "<br/>"
        html += "<hr/><br/>"
    os.close(dir_fd)

    return HttpResponse(html)


def _login(request):
    error = username = password = ''
    if request.user.is_authenticated():
        return HttpResponseRedirect("/main/")
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                request.session.set_expiry(900)
                ur_get = request.META['HTTP_REFERER']
                ur_get = ur_get.split("next=")
                url = "/main/"
                if len(ur_get) > 1:
                    url += "?next=" + ur_get[1]
                return HttpResponseRedirect(url)
            else:
                error = "Tu cuenta ha sido desactivada, por favor ponte en contacto con tu administrador"
        else:
            error = "Tu nombre de usuario o contrase&ntilde;a son incorrectos."
    variables = dict(username=username, password=password, error=error)
    variables_template = RequestContext(request, variables)
    return render_to_response("login.html", variables_template)


def index(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        pa = PermissionAsigment.objects.all().exclude(
            object__object_access_point="/")
    else:
        data_context = DataContextPermission.objects.filter(
            user_role__user=request.user)
        roles = [dc.user_role.role.pk for dc in data_context]
        pa = PermissionAsigment.objects.filter(role__pk__in=roles).exclude(
            object__object_access_point="/")

    d = defaultdict(list)
    for permission in pa:
        if permission.object.object_name not in GRAPHS and permission.object.object_name != "Consultar recibo CFE" and permission.object.object_name != "Perfil de carga":
            gObject = GroupObject.objects.get(
                object__object_name=permission.object.object_name)
            d[gObject.group.group_name].append(gObject.object)

    groups = d.keys()
    menu_option_str = "<ul id='main_menu'>"
    categories = MenuCategs.objects.filter(main=True).order_by("order")

    for category in categories:
        menu_option_str += "<li class='" + category.added_class + "'>"
        if category.categ_access_point:
            menu_option_str += "<a href='" + category.categ_access_point + "'>"
            menu_option_str += category.categ_name
            menu_option_str += "</a>"
        else:
            menu_option_str += category.categ_name
            menu_option_str += get_sub_categs_items(category)
        menu_option_str += "</li>"
    menu_option_str += "</ul>"


    #for gp in groups:
    #    sd_opts = d[gp]
    #    sd_opts = unique_from_array(sd_opts)
    #    if gp == 'Unidades de consumo':
    #        gp = 'U. de consumo'
    #    menu_option_str += "<span class='sidebar_option desp'>" \
    #                       "<span>" + gp + "</span></span>" \
    #                                       "<ul class='sidebarsub_op'>"
    #    for option in sd_opts:
    #        menu_option_str += "<li><a href='" + option.object_access_point + "'>" + option.object_name + "</a></li>"
    #    if gp == 'Empresas':
    #        menu_option_str += "<li><a href='/buildings/estructura/'>Organizaci&oacute;n Empresas</a></li>"
    #    menu_option_str += "</ul>"

    #if request.user.is_superuser:
    #    menu_option_str += "<span class='sidebar_option desp'>" \
    #                       "<span>Regiones</span></span>" \
    #                       "<ul class='sidebarsub_op'>" \
    #                       "<li><a href='/location/ver_regiones/'>Ver Regiones</a></li>" \
    #                       "<li><a href='/location/ver_estados/'>Ver Estados</a></li>" \
    #                       "<li><a href='/location/ver_municipios/'>Ver Municipios</a></li>" \
    #                       "<li><a href='/location/ver_colonias/'>Ver Colonias</a></li>" \
    #                       "<li><a href='/location/ver_calles/'>Ver Calles</a></li>" \
    #                       "</ul>"
    request.session['sidebar'] = menu_option_str

    if 'next' in request.GET:
        datacontext = get_buildings_context(request.user)
        if not datacontext:
            request.session['consumer_unit'] = None
        set_default_session_vars(request, datacontext)
        return HttpResponseRedirect(request.GET['next'])
    elif 'g_type' in request.GET:
        return main_page(request)
    else:
        return week_report_kwh(request)


def get_sub_categs_items(parent):
    sub_cat = MenuHierarchy.objects.filter(
        parent_cat=parent).order_by("child_cat__order")
    sub_menu = ''
    if sub_cat:
        sub_menu = "<ul>"
        for sub_c in sub_cat:
            sub_menu += "<li class='" + sub_c.child_cat.added_class + "'>"
            if sub_c.child_cat.categ_access_point:
                sub_menu += "<a href='" + sub_c.child_cat.categ_access_point + "'>"
                sub_menu += sub_c.child_cat.categ_name
                sub_menu += "</a>"
            elif sub_c.child_cat:
                sub_menu += sub_c.child_cat.categ_name
                sub_menu += get_sub_categs_items(sub_c.child_cat)
            sub_menu += "</li>"
        sub_menu += "</ul>"

    return sub_menu


def logout_page(request):
    logout(request)
    return HttpResponseRedirect('/main/?logout')


def changedate(profile_pk, initial_date, delta):
    """
    sets all the data in intervals of 3 hours
    profile_pk = profile_powermeter__pk
    initial_date = starting datetime
    delta = number of minutes for the interval
    """
    data = ElectricData.objects.filter(
        profile_powermeter__pk=profile_pk).order_by("medition_date")
    delta = timedelta(minutes=delta)
    for dato in data:
        print "antes", dato.medition_date
        initial_date += delta
        dato.medition_date = initial_date
        dato.save()
        print "despues", dato.medition_date


def data_exchange():
    electric_d = ElectricData.objects.all()
    for el in electric_d:
        elec = ElectricDataTemp(
            profile_powermeter=el.profile_powermeter,
            powermeter_serial=el.powermeter_serial,
            medition_date=el.medition_date,
            V1=el.V1,
            V2=el.V2,
            V3=el.V3,
            I1=el.I1,
            I2=el.I2,
            I3=el.I3,
            kWL1=el.kWL1,
            kWL2=el.kWL2,
            kWL3=el.kWL3,
            kvarL1=el.kvarL1,
            kvarL2=el.kvarL2,
            kvarL3=el.kvarL3,
            kVAL1=el.kVAL1,
            kVAL2=el.kVAL2,
            kVAL3=el.kVAL3,
            PFL1=el.PFL1,
            PFL2=el.PFL2,
            PFL3=el.PFL3,
            kW=el.kW,
            kvar=el.kvar,
            TotalkVA=el.kVA,
            PF=el.PF,
            FREQ=el.FREQ,
            TotalkWhIMPORT=el.kWhIMPORT,
            kvahTOTAL=el.kvahTOTAL,
            TotalkvarhIMPORT=el.kvarhIMPORT,
            kWhL1=el.kWhL1,
            kWhL2=el.kWhL2,
            kwhL3=el.kwhL3,
            kvarhL1=el.kvarhL1,
            kvarhL2=el.kvarhL2,
            kvarhL3=el.kvarhL3,
            kVAhL1=el.kVAhL1,
            kVAhL2=el.kVAhL2,
            kVAhL3=el.kVAhL3,
            kW_import_sliding_window_demand=el.kW_import_sliding_window_demand,
            kvar_import_sliding_window_demand=el.kvar_import_sliding_window_demand,
            kVA_sliding_window_demand=el.kVA_sliding_window_demand
        )
        elec.save()
    print "success :D"


def data_replication(
        consumer_unit_original,
        consumer_unit_copy
):
    pass


def data_multiplier_3000():
    todos_los_datos = ElectricDataTemp.objects.filter(
        TotalkWhIMPORT__gt=1000000)
    #datos = ElectricDataTemp.objects.filter(TotalkWhIMPORT__gt=30000, profile_powermeter__powermeter__powermeter_anotation__icontains="cidec").filter(Q(medition_date__lt=datetime.datetime(2012, 12, 14)), Q(medition_date__gt=datetime.datetime(2012, 12, 12)))
    #datos = ElectricDataTemp.objects.filter(TotalkWhIMPORT__gt=51000, profile_powermeter__powermeter__powermeter_anotation__icontains="cidec").filter(Q(medition_date__lte=datetime.datetime(2012, 12, 13)), Q(medition_date__gt=datetime.datetime(2012, 12, 11)))
    datos = ElectricDataTemp.objects.filter(TotalkWhIMPORT__gte=32000,
                                            profile_powermeter__powermeter__powermeter_anotation__icontains="cidec").filter(

        Q(medition_date__lte=datetime.datetime(2012, 12, 14)),
        Q(medition_date__gt=datetime.datetime(2012, 12, 12)))
    for dato in datos:
        print dato.pk, dato.TotalkWhIMPORT, dato.TotalkvarhIMPORT, dato.kWhL1
        print dato.kWhL2, dato.kwhL3, dato.kvarhL1, dato.kvarhL2, dato.kvarhL3
        print dato.kVAhL1, dato.kVAhL2, dato.kVAhL3

        if dato.TotalkWhIMPORT and dato.TotalkWhIMPORT > 0:
            dato.TotalkWhIMPORT /= 1000
        if dato.TotalkvarhIMPORT and dato.TotalkvarhIMPORT > 0 and dato.TotalkvarhIMPORT < 10000000000:
            dato.TotalkvarhIMPORT /= 1000
        if dato.kvahTOTAL and dato.kvahTOTAL > 40000 and dato.kvahTOTAL < 10000000000:
            dato.kvahTOTAL /= 1000
        if dato.kWhL1 and dato.kWhL1 > 0:
            dato.kWhL1 /= 1000
        if dato.kWhL2 and dato.kWhL2 > 0:
            dato.kWhL2 /= 1000
        if dato.kwhL3 and dato.kwhL3 > 0:
            dato.kwhL3 /= 1000
        if dato.kvarhL1 and dato.kvarhL1 > 0:
            dato.kvarhL1 /= 1000
        if dato.kvarhL2 and dato.kvarhL2 > 0:
            dato.kvarhL2 /= 1000
        if dato.kvarhL3 and dato.kvarhL3 > 0:
            dato.kvarhL3 /= 1000
        if dato.kVAhL1 and dato.kVAhL1 > 0:
            dato.kVAhL1 /= 1000
        if dato.kVAhL2 and dato.kVAhL2 > 0:
            dato.kVAhL2 /= 1000
        if dato.kVAhL3 and dato.kVAhL3 > 0:
            dato.kVAhL3 /= 1000
        dato.save()
        print dato
    print "EXITO!!!!!!"
    return True


@timed
def asign_electric_data_to_pw(serials):
    """ change the profile_powermeter of all the meditions with an specific
    power_meter_serial
    serials: an array containing strings: powermeter_serials
    """
    for serial in serials:
        profile = ProfilePowermeter.objects.get(
            powermeter__powermeter_serial=serial)
        ed = ElectricDataTemp.objects.filter(powermeter_serial=serial)
        for e in ed:
            e.profile_powermeter = profile
            e.save()

    return "done"


@timed
def migrate_electric_data(serials):
    """ searches for electric data with a given serial,
    then searches for that serial in a remote database and gets or creates a
    profile powermeter, then save each electic data in the remote database
    serials = Array of strings: powermeter_serials
    """
    for serial in serials:
        loc_profile = ProfilePowermeter.objects.get(
            powermeter__powermeter_serial=serial)
        try:
            profile = ProfilePowermeter.objects.using('production').get(
                powermeter__powermeter_serial=serial)
        except ObjectDoesNotExist:
            pw, created = Powermeter.objects.using(
                "production"
            ).get_or_create(
                powermeter_model=loc_profile.powermeter.powermeter_model,
                powermeter_anotation=loc_profile.powermeter.powermeter_anotation,
                powermeter_serial=loc_profile.powermeter.powermeter_serial
            )
            profile, created = ProfilePowermeter.objects.using(
                "production"
            ).get_or_create(powermeter=pw)

        ed = ElectricDataTemp.objects.filter(powermeter_serial=serial)
        for e in ed:
            f = e
            f.save(using="production")
            f.profile_powermeter = profile
            f.save(using="production")
    return "done"