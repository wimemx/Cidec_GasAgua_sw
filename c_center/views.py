# -*- coding: utf-8 -*-
#standard library imports
from datetime import  timedelta, datetime
from dateutil.relativedelta import relativedelta
import Image
import cStringIO
import os
from django.core.files import File
import hashlib

import re
import time
import calendar
#related third party imports
import variety

#local application/library specific imports
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.context import RequestContext
from django.utils import timezone
from django.db.models.aggregates import *
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, InvalidPage

from cidec_sw import settings
from c_center.calculations import tarifaHM_mensual, tarifaHM_total, obtenerHistorico, obtenerHistoricoHM, \
    fechas_corte, tarifaHM, tarifaDAC
from c_center.models import *
from electric_rates.models import ElectricRatesDetail
from rbac.models import Operation, DataContextPermission
from rbac.rbac_functions import  has_permission, get_buildings_context, graphs_permission

import json as simplejson

#from tareas.tasks import add

VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")

GRAPHS =['Potencia Activa (KW)', 'Potencia Reactiva (KVar)', 'Factor de Potencia (PF)',
         'kW Hora', 'kW Hora Consumido', 'kVAR Hora', 'kVAR Hora Consumido']

#def call_celery_delay():
#    add.delay()
#    return "Task set to execute."

def week_of_month(datetime_variable):
    """Get the week number of the month for a datetime
    datetime_variable = the date
    returns the week number (int)
    """
    first_day_of_month = datetime.datetime(year=datetime_variable.year,
        month=datetime_variable.month, day=1)
    first_day_first_week = first_day_of_month - timedelta(days=first_day_of_month.weekday())
    week_delta = timedelta(weeks = 1)
    datetime_next = first_day_first_week + week_delta
    week_number = 1
    while datetime_next <= datetime_variable:
        week_number += 1
        datetime_next += week_delta

    return week_number

def get_intervals_1(get):
    """get the interval for the graphs
    by default we get the data from the last month
    returns f1_init, f1_end as datetime objects
    """
    f1_init = datetime.datetime.today() - relativedelta( months = 1 )
    f1_end = datetime.datetime.today()

    if "f1_init" in get:
        if get["f1_init"] != '':
            f1_init = time.strptime(get['f1_init'], "%d/%m/%Y")
            f1_init = datetime.datetime(f1_init.tm_year, f1_init.tm_mon, f1_init.tm_mday)
        if get["f1_end"] != '':
            f1_end = time.strptime(get['f1_end'], "%d/%m/%Y")
            f1_end = datetime.datetime(f1_end.tm_year, f1_end.tm_mon, f1_end.tm_mday)

    return f1_init, f1_end

def get_intervals_fecha(get):
    """get the interval for the graphs
    by default we get the data from the last month
    returns f1_init, f1_end as formated strings
    """
    f1_init = datetime.datetime.today() - relativedelta( months = 1 )
    f1_init = str(f1_init.year)+"-"+str(f1_init.month)+"-"+str(f1_init.day)+" 00:00:00"
    f1_end = datetime.datetime.today()
    f1_end = str(f1_end.year)+"-"+str(f1_end.month)+"-"+str(f1_end.day)+" 23:59:59"


    if "f1_init" in get:
        f1_init = get['f1_init']
        f1_init=str.split(str(f1_init),"/")
        f1_init = str(f1_init[2])+"-"+str(f1_init[1])+"-"+str(f1_init[0])+" 00:00:00"
        f1_end = get['f1_end']
        f1_end = str.split(str(f1_end),"/")
        f1_end = str(f1_end[2])+"-"+str(f1_end[1])+"-"+str(f1_end[0])+" 23:59:59"
    return f1_init, f1_end


def get_intervals_2(get):
    """gets the second date interval """
    get2=dict(f1_init=get['f2_init'], f1_end=get['f2_end'])
    return get_intervals_1(get2)

def set_default_session_vars(request, datacontext):
    """Sets the default building and consumer unit """
    if 'main_building' not in request.session:
        #sets the default building (the first in DataContextPermission)
        try:
            building=Building.objects.get(pk=datacontext[0]['building_pk'])
            request.session['main_building'] = building
        except ObjectDoesNotExist, KeyError:
            request.session['main_building'] = None
    if "company" not in request.session:
        c_b = CompanyBuilding.objects.get(building=request.session['main_building'])
        request.session['company'] = c_b.company
    if 'consumer_unit' not in request.session:
        #sets the default ConsumerUnit (the first in ConsumerUnit for the main building)
        try:
            c_unit = ConsumerUnit.objects.filter(building=request.session['main_building'])
            request.session['consumer_unit'] = c_unit[0]
        except ObjectDoesNotExist, KeyError:
            request.session['main_building'] = None

def set_default_building(request, id_building):
    """Sets the default building for reports"""
    request.session['main_building'] = Building.objects.get(pk=id_building)
    c_b = CompanyBuilding.objects.get(building=request.session['main_building'])
    request.session['company'] = c_b.company
    c_unit = ConsumerUnit.objects.filter(building=request.session['main_building'])
    request.session['consumer_unit'] = c_unit[0]
    dicc = dict(edificio=request.session['main_building'].building_name,
        electric_device_type=c_unit[0].electric_device_type.electric_device_type_name)
    data = simplejson.dumps( dicc )
    if 'referer' in request.GET:
        if request.GET['referer'] == "cfe":
            return HttpResponseRedirect("/reportes/cfe/")
    return HttpResponse(content=data,content_type="application/json")


def get_sons(parent, part):
    """ Gets a list of the direct sons of a given part, or consumer unit
    parent = instance of PartOfBuilding, or ConsumerUnit
    part = string, is the type of the parent
    """
    if part == "part":
        sons_of_parent = HierarchyOfPart.objects.filter(part_of_building_composite=parent)
    else:
        sons_of_parent = HierarchyOfPart.objects.filter(consumer_unit_composite=parent)

    if sons_of_parent:
        list = '<ul>'
        for son in sons_of_parent:
            if son.part_of_building_leaf:
                tag = son.part_of_building_leaf.part_of_building_name
                sons = get_sons(son.part_of_building_leaf, "part")
                cu = ConsumerUnit.objects.get(part_of_building=son.part_of_building_leaf)
                _class = "part_of_building"
            else:
                tag = son.consumer_unit_leaf.electric_device_type.electric_device_type_name
                sons = get_sons(son.consumer_unit_leaf, "consumer")
                cu = son.consumer_unit_leaf
                _class = "consumer_unit"
            list += '<li><a href="#" rel="' + str(cu.pk) + '" class="' + _class + '">'
            list +=  tag + '</a>' + sons
            list += '</li>'
        list += '</ul>'
        return list
    else:
        return ""

def set_consumer_unit(request):

    building = request.session['main_building']
    hierarchy = HierarchyOfPart.objects.filter(part_of_building_composite__building=building)
    ids_hierarchy = []
    for hy in hierarchy:
        if hy.part_of_building_leaf:
            ids_hierarchy.append(hy.part_of_building_leaf.pk)

    #sacar el padre(partes de edificios que no son hijos de nadie)
    parents = PartOfBuilding.objects.filter(building=building).exclude(pk__in=ids_hierarchy)

    main_cu = ConsumerUnit.objects.get(building=building,
        electric_device_type__electric_device_type_name="Total")
    hierarchy_list = "<ul id='org'>"\
                     "<li>"\
                     "<a href='#' rel='" + str(main_cu.pk) + "'>"+\
                     building.building_name +\
                     "</a>"

    try:
        parents[0]
    except IndexError:

        #revisar si tiene consumer_units anidadas
        hierarchy = HierarchyOfPart.objects.filter(consumer_unit_composite__building=building)
        ids_hierarchy = []
        for hy in hierarchy:
            if hy.consumer_unit_leaf:
                ids_hierarchy.append(hy.consumer_unit_leaf.pk)

        #sacar el padre(ConsumerUnits que no son hijos de nadie)
        parents = ConsumerUnit.objects.filter(building=building).exclude(
                  Q(pk__in=ids_hierarchy)|
                  Q(electric_device_type__electric_device_type_name="Total") )
        try:
            parents[0]
        except IndexError:
            #si no hay ninguno, es un edificio sin partes, o sin partes anidadas
            pass
        else:
            hierarchy_list += "<ul>"
            for parent in parents:
                hierarchy_list += "<li> <a href='#' rel='" + str(parent.pk) + "'>" +\
                                  parent.electric_device_type.electric_device_type_name + \
                                  "</a>"
                #obtengo la jerarquia de cada rama del arbol
                hierarchy_list += get_sons(parent, "consumer")
                hierarchy_list +="</li>"
            hierarchy_list +="</ul>"
    else:
        hierarchy_list += "<ul>"
        for parent in parents:

            c_unit_parent = ConsumerUnit.objects.filter(building=building,
                            part_of_building=parent).exclude(
                            electric_device_type__electric_device_type_name="Total")

            hierarchy_list += "<li> <a href='#' rel='" + str(c_unit_parent[0].pk) + "'>" + \
                              parent.part_of_building_name + "</a>"
            #obtengo la jerarquia de cada rama del arbol
            hierarchy_list += get_sons(parent, "part")
            hierarchy_list +="</li>"
        hierarchy_list +="</ul>"
    hierarchy_list +="</li></ul>"
    template_vars = dict(hierarchy=hierarchy_list)
    template_vars_template = RequestContext(request, template_vars)

    return render_to_response("consumption_centers/choose_hierarchy.html", template_vars_template)

def get_position_consumer_unit(id_c_u):
    consumerUnit = get_object_or_404(ConsumerUnit, pk=id_c_u)
    if consumerUnit.part_of_building:
        #es el consumer_unit de una parte de un edificio
        try:
            tree_element = HierarchyOfPart.objects.get(part_of_building_leaf=consumerUnit.part_of_building)
        except ObjectDoesNotExist:
            #es el primer hijo de la jerarquia
            pass
        else:
            if tree_element.ExistsPowermeter:
                #se usa este consumer unit
                pass
            else:
                #se hace el recorrido de sus hijos
                pass

    else:
        #es un consumer unit de algún electric device
        try:
            tree_element = HierarchyOfPart.objects.get(consumer_unit_leaf=consumerUnit)
        except ObjectDoesNotExist:
            #es el primer hijo de la jerarquia
            pass

def set_default_consumer_unit(request, id_c_u):
    """Sets the consumer_unit for all the reports"""
    c_unit = ConsumerUnit.objects.get(pk=id_c_u)
    request.session['consumer_unit'] = c_unit
    return HttpResponse(status=200)

def main_page(request):
    """Main Page
    in the mean time the main view is the graphics view
    sets the session variables needed to show graphs
    """
    datacontext = get_buildings_context(request.user)
    set_default_session_vars(request, datacontext)

    graphs = graphs_permission(request.user)

    if graphs:

        #valid years for reporting
        request.session['years'] = [__date.year for __date in
                                    ElectricDataTemp.objects.all().dates('medition_date', 'year')]

        template_vars = {"graphs":graphs, "datacontext":datacontext,
                         'empresa': request.session['main_building'],
                         'company': request.session['company'],
                         'consumer_unit': request.session['consumer_unit'],
                         }
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/main.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def cfe_bill(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Consultar recibo CFE"):
        datacontext = get_buildings_context(request.user)
        set_default_session_vars(request, datacontext)

        today = datetime.datetime.today().replace(hour=0,minute=0,second=0,tzinfo=timezone.get_current_timezone())
        month = int(today.month)
        year = int(today.year)
        dict(one=1, two=2)
        month_list = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto',
                       9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre' }
        year_list = {2010:2010, 2011:2011, 2012:2012, 2013:2013}

        template_vars={"type":"cfe", "datacontext":datacontext,
                       'empresa':request.session['main_building'],
                       'month':month, 'year':year, 'month_list':month_list, 'year_list':year_list
        }

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/cfe.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def cfe_calculations(request):
    """Renders the cfe bill and the historic data chart"""
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Consultar recibo CFE"):
        datacontext = get_buildings_context(request.user)
        set_default_session_vars(request, datacontext)

        template_vars={"type":"cfe", "datacontext":datacontext,
                       'empresa':request.session['main_building']
        }

        if request.GET:
            if request.method == "GET":
                month = int(request.GET['month'])
                year = int(request.GET['year'])

        else:
        #Obtener la fecha actual
            today = datetime.datetime.today().replace(hour=0,minute=0,second=0,tzinfo=timezone.get_current_timezone())
            month = int(today.month)
            year = int(today.year)

        powermeter = request.session['consumer_unit'].profile_powermeter.powermeter

        #Se obtiene el tipo de tarifa del edificio (HM o DAC)
        tipo_tarifa = request.session['main_building'].electric_rate


        if tipo_tarifa.pk == 1: #Tarifa HM
            resultado_mensual = tarifaHM(request.session['main_building'],powermeter,month,year)

        elif tipo_tarifa.pk == 2: #Tarifa DAC
            resultado_mensual = tarifaDAC(request.session['main_building'],powermeter,month,year)

        if resultado_mensual['status'] == 'OK':
            template_vars['resultados'] = resultado_mensual
            template_vars['tipo_tarifa'] = tipo_tarifa


            template_vars['historico'] = obtenerHistoricoHM
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/graphs/cfe_bill.html",
                template_vars_template)
        if resultado_mensual['status'] == 'ERROR':
            template_vars['mensaje'] = resultado_mensual['mensaje']
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/graphs/cfe_bill_error.html",
                template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))



def graficas(request):
    template_vars = {'fi': get_intervals_1(request.GET)[0],
                     'ff': get_intervals_1(request.GET)[1]}

    #second interval, None by default

    if request.GET:
        if "graph" not in request.GET:
            raise Http404
        else:
            template_vars['tipo']=request.GET["graph"]
            buildings = [request.session['main_building'].pk]
            template_vars['building_names'] = []
            if "f2_init" in request.GET:
                #comparacion con un intervalo
                template_vars['fi2'], template_vars['ff2'] = get_intervals_2(request.GET)
                buildings.append(1)
                template_vars['building_names'].append(get_object_or_404(Building,
                            pk = int(request.session['main_building'].pk)))
                template_vars['building_names'].append(get_object_or_404(Building,
                            pk = int(request.session['main_building'].pk)))
            else:
                #graficas de un edificio


                template_vars['building_names'].append(get_object_or_404(Building,
                            pk = request.session['main_building'].pk))

                if request.method == "GET":
                    for key in request.GET:
                        if re.search('^compare_to\d+', key):
                            #graficas comparativas de 2 o mas edificios
                            buildings.append(int(request.GET[key]))
                            template_vars['building_names'].append(get_object_or_404(Building,
                                                                  pk = int(request.GET[key])))

            template_vars['buildings'] = simplejson.dumps(buildings)
            if request.GET["graph"] == "pp":
                template_vars_template = RequestContext(request, template_vars)
                return render_to_response("consumption_centers/graphs/perfil_carga.html",
                    template_vars_template)
            else:
                template_vars['years'] = request.session['years']
                ahora = datetime.datetime.now()
                template_vars['year'] = ahora.year
                template_vars['month'] = ahora.month
                template_vars['week'] = week_of_month(ahora)
                template_vars_template = RequestContext(request, template_vars)
                return render_to_response("consumption_centers/graphs/test_graph.html",
                                          template_vars_template)
    else:
        return HttpResponse(content="", content_type="text/html")

def grafica_datos(request):
    f1_init, f1_end = get_intervals_1(request.GET)
    buildings = []
    profile=request.session['consumer_unit'].profile_powermeter
    for key in request.GET:
        if re.search('^building\d+', key):
            building = get_object_or_404(Building, pk=int(request.GET[key]))
            buildings.append(building)
    if "f2_init" in request.GET:
        f2_init, f2_end = get_intervals_2(request.GET)

        data=get_json_data_from_intervals(profile, f1_init, f1_end, f2_init, f2_end,
                                          request.GET['graph'])
        return HttpResponse(content=data,content_type="application/json")
    elif buildings:
        data=get_json_data(buildings, f1_init, f1_end, request.GET['graph'],profile)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404



def get_pp_data(request):
    if 'building' in request.GET:
        f1_init, f1_end = get_intervals_1(request.GET)
        data=get_power_profile_json(request.session['main_building'], f1_init, f1_end)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404


def perfil_carga(request):
    template_vars = {'fi': get_intervals_1(request.GET)[0],
                     'ff': get_intervals_1(request.GET)[1]}

    #second interval, None by default

    f1_init, f1_end = get_intervals_1(request.GET)

    if request.GET:
        template_vars['building_names'] = []
        if "f2_init" in request.GET:
            f2_init, f2_end = get_intervals_2(request.GET)

        for key in request.GET:
            if re.search('^compare_to\d+', key):
                # "compare", request.session['main_building'], "with building", key
                building_compare = Building.objects.get(pk=int(key))
                template_vars['compare_interval_pf'] = get_PF(building_compare, f1_init,
                                                              f1_end)
                template_vars['compare_interval_kvar'] = get_KVar(building_compare, f1_init,
                                                                  f1_end)
                template_vars['compare_interval_kw'] = get_KW(building_compare, f1_init,
                                                              f1_end)
                if f2_init:
                    template_vars['compare_interval2_pf'] = get_PF(building_compare, f2_init,
                                                                   f2_end)
                    template_vars['compare_interval2_kvar'] = get_KVar(building_compare,
                                                                       f2_init, f2_end)
                    template_vars['compare_interval2_kw'] = get_KW(building_compare, f2_init,
                                                                   f2_end)
    template_vars['building']=request.session['main_building'].pk
    template_vars['fi'], template_vars['ff'] = f1_init, f1_end

    if f2_init:
        template_vars['main_interval2_pf'] = get_PF(request.session['main_building'], f2_init,
                                                    f2_end)
        template_vars['main_interval_kvar_kw2'] = \
                        get_power_profile(request.session['main_building'], f2_init, f2_end)

    template_vars_template = RequestContext(request, template_vars)
    return render_to_response("consumption_centers/graphs/perfil_carga.html",
                              template_vars_template)

def get_medition_in_time(profile, datetime_from, datetime_to):
    """Gets the meditions registered in a time window

    profile = powermeter_profile model instance
    datetime_from = lower date limit
    datetime_to = upper date limit

    """

    profile_powermeter = profile

    date_gte = datetime_from.replace(hour=0, minute=0, second=0,
                                     tzinfo=timezone.get_current_timezone())
    date_lte = datetime_to.replace(hour=23 ,minute=59, second=59,
                                   tzinfo=timezone.get_current_timezone())

    meditions = ElectricDataTemp.objects.filter(profile_powermeter=profile_powermeter,
        medition_date__range=(date_gte, date_lte)).order_by("medition_date")
    return meditions

def get_KW(building, datetime_from, datetime_to):
    """Gets the KW data in a given interval needed for Power Profile"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    kw=[]
    fi = None
    for medition in meditions:
        if not fi:
            fi=medition.medition_date
        kw.append(dict(kw=medition.kW, date=medition.medition_date))
    ff = meditions[len(meditions)-1].medition_date
    return kw, fi, ff


def get_json_data_from_intervals(profile, f1_init, f1_end, f2_init, f2_end,  parameter):
    """Returns a JSON containing the date and the parameter for a profile en 2 ranges of time
    buildings = An array of buildings to compare
    datetime_from = initial date interval
    datetime_to = final date interval
    parameter = electric parameter to plot
    """

    if parameter == "kwh_consumido" or parameter == "kvarh_consumido":

        dayly_summary=[]

        day_delta = timedelta(hours=1)
        delta_days = f1_end - f1_init
        number_days = delta_days.days *24
        delta_days2 = f2_end - f2_init
        number_days2 = delta_days2.days *24

        if number_days2 > number_days:
            number_days = number_days2
            datetime_from = f2_init
            datetime_from2 = f1_init
        else:
            datetime_from = f1_init
            datetime_from2 = f2_init
        #de la fecha de inicio, al dia siguiente

        datetime_to = datetime_from + day_delta
        datetime_to2 = datetime_from2 + day_delta

        for day_index in range(0, number_days):
            f1_init = f1_init.replace(tzinfo=timezone.get_current_timezone())

            #intervalo1
            datetime_from = datetime_from.replace(tzinfo=timezone.get_current_timezone())
            datetime_to = datetime_to.replace(tzinfo=timezone.get_current_timezone())
            #intervalo2
            datetime_from2 = datetime_from2.replace(tzinfo=timezone.get_current_timezone())
            datetime_to2 = datetime_to2.replace(tzinfo=timezone.get_current_timezone())

            #all the meditions in a day for the first interval
            meditions = ElectricDataTemp.objects.filter(profile_powermeter=profile,
                medition_date__gte=datetime_from,
                medition_date__lt=datetime_to)
            #all the meditions in a day for the second interval
            meditions2 = ElectricDataTemp.objects.filter(profile_powermeter=profile,
                medition_date__gte=datetime_from2,
                medition_date__lt=datetime_to2)

            meditions_last_index = len(meditions) - 1
            meditions_last_index2 = len(meditions2) - 1

            if meditions_last_index < 1:
                e_parameter=0

            else:
                if parameter == "kwh_consumido":
                    e_parameter = meditions[meditions_last_index].TotalkWhIMPORT - \
                                  meditions[0].TotalkWhIMPORT
                else:
                    e_parameter = meditions[meditions_last_index].TotalkvarhIMPORT - \
                                  meditions[0].TotalkvarhIMPORT

            if meditions_last_index2 < 1:
                e_parameter2=0

            else:
                if parameter == "kwh_consumido":
                    e_parameter2 = meditions2[meditions_last_index2].TotalkWhIMPORT - \
                                   meditions2[0].TotalkWhIMPORT
                else:
                    e_parameter2 = meditions2[meditions_last_index2].TotalkvarhIMPORT - \
                                   meditions2[0].TotalkvarhIMPORT
            meditions_parameters = [float(e_parameter), float(e_parameter2)]
            labels = [str(datetime_from), str(datetime_from2)]
            dayly_summary.append({"date":int(time.mktime(f1_init.timetuple())),
                                  "meditions":meditions_parameters, 'labels':labels})
            datetime_from = datetime_to
            f1_init += day_delta
            datetime_to = datetime_from + day_delta

        return simplejson.dumps(dayly_summary)


    meditions_json = []
    buildings_meditions = [get_medition_in_time(profile, f1_init, f1_end),
                           get_medition_in_time(profile, f2_init, f2_end)]
    len0=len(buildings_meditions[0])
    len1=len(buildings_meditions[1])
    if len0>len1:
        meditions_number=len1
    else:
        meditions_number=len0

    for medition_index in range(0, meditions_number):
        meditions = []
        labels = []
        _time = 0
        for building_index in range(0, 2):
            try:
                current_medition = buildings_meditions[building_index][medition_index]
            except KeyError:
                meditions.append('0')
            else:
                medition_date=current_medition.medition_date
                if not _time:
                    _time = int(time.mktime(medition_date.timetuple()))

                if parameter == "kw":
                    meditions.append(str(current_medition.kW))
                elif parameter == "kwh":
                    meditions.append(str(current_medition.TotalkWhIMPORT))
                elif parameter == "kvarh":
                    meditions.append(str(current_medition.TotalkvarhIMPORT))
                elif parameter == "pf":
                    meditions.append(str(current_medition.PF))
                elif parameter == "kvar":
                    meditions.append(str(current_medition.kvar))

                labels.append(str(timezone.localtime(current_medition.medition_date)))

        meditions_json.append(dict(meditions = meditions, date = _time, labels = labels))
    return simplejson.dumps(meditions_json)

def get_json_data(buildings, datetime_from, datetime_to, parameter, profile):
    """Returns a JSON containing the date and the parameter
    buildings = An array of buildings to compare
    datetime_from = initial date interval
    datetime_to = final date interval
    parameter = electric parameter to plot
    """
    if parameter == "kwh_consumido" or parameter == "kvarh_consumido":
        dayly_summary=[]
        day_delta = timedelta(hours=1)
        delta_days = datetime_to - datetime_from

        number_days = delta_days.days * 24
        #de la fecha de inicio, al dia siguiente
        datetime_to = datetime_from + day_delta
        for day_index in range(0, number_days):

            datetime_from = datetime_from.replace(tzinfo=timezone.get_current_timezone())

            datetime_to = datetime_to.replace(tzinfo=timezone.get_current_timezone())
            #all the meditions in a day
            meditions = ElectricDataTemp.objects.filter(profile_powermeter=profile,
                                                    medition_date__gte=datetime_from,
                                                    medition_date__lt=datetime_to)

            meditions_last_index = len(meditions) - 1

            if meditions_last_index < 1:
                dayly_summary.append({"date":int(time.mktime(datetime_from.timetuple())),
                                      "meditions":[0], 'labels':[str(datetime_to)]})
            else:
                if parameter == "kwh_consumido":
                    e_parameter = meditions[meditions_last_index].TotalkWhIMPORT - \
                                  meditions[0].TotalkWhIMPORT
                else:
                    e_parameter = meditions[meditions_last_index].TotalkvarhIMPORT - \
                                  meditions[0].TotalkvarhIMPORT

                dayly_summary.append({"date":int(time.mktime(datetime_from.timetuple())),
                                      "meditions":[float(e_parameter)],
                                      'labels':[str(datetime_to)]})
            datetime_from = datetime_to
            datetime_to = datetime_from + day_delta

        return simplejson.dumps(dayly_summary)



    meditions_json = []
    buildings_number = len(buildings)
    if buildings_number < 1:
        return simplejson.dumps(meditions_json)

    buildings_meditions = []
    for building in buildings:
        buildings_meditions.append(get_medition_in_time(profile, datetime_from, datetime_to))

    meditions_number = len(buildings_meditions[0])

    for medition_index in range(0, meditions_number):
        current_medition = None
        meditions = []
        labels = []
        for building_index in range(0, buildings_number):
            #print buildings_meditions[building_index][medition_index]
            current_medition = buildings_meditions[building_index][medition_index]
            if parameter == "kw":
                meditions.append(str(current_medition.kW))
            elif parameter == "kwh":
                meditions.append(str(current_medition.TotalkWhIMPORT))
            elif parameter == "kvarh":
                meditions.append(str(current_medition.TotalkvarhIMPORT))
            elif parameter == "pf":
                meditions.append(str(current_medition.PF))
            elif parameter == "kvar":
                meditions.append(str(current_medition.kvar))

            labels.append(str(timezone.localtime(current_medition.medition_date)))
        medition_time = timezone.localtime(current_medition.medition_date)

        meditions_json.append(dict(meditions = meditions, date =
            int(time.mktime(medition_time.timetuple())),
            labels = labels))

    return simplejson.dumps(meditions_json)


def get_KVar(building, datetime_from, datetime_to):
    """Gets the KW data in a given interval needed for Power Profile"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    kvar=[]
    for medition in meditions:
        kvar.append(dict(kvar=medition.kvar, date=medition.medition_date))

    return kvar


def get_PF(building, datetime_from, datetime_to):
    """Gets the KW data in a given interval needed for Power Profile"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    pf=[]
    for medition in meditions:
        pf.append(dict(pf=medition.PF, date=medition.medition_date))
    return pf


def get_power_profile(building, datetime_from, datetime_to):
    """gets the data from the active and reactive energy for a building in a time window"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    kvar=[]
    kw=[]
    for medition in meditions:
        kw.append(dict(kw=medition.kW, date=medition.medition_date))
        kvar.append(dict(kvar=medition.kvar, date=medition.medition_date))
    return zip(kvar,kw)


def get_power_profile_json(building, datetime_from, datetime_to):
    """gets the data from the active and reactive energy for a building in a time window"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    #kvar=[]
    kw=[]
    for medition in meditions:
        kw.append(dict(kw=str(medition.kW), kvar=str(medition.kvar),
                  date=int(time.mktime(medition.medition_date.timetuple()))))
    return simplejson.dumps(kw)


def get_weekly_summary_for_parameter(year, month, week, type, profile):
    """
    year = year for the sumary
    month = month for the sumary
    week = week for the sumary
    year = year for the sumary
    """

    weekly_summary = []
    first_day_of_month = datetime(year=year, month=month, day=1)
    first_day_first_week = first_day_of_month - timedelta(days=first_day_of_month.weekday())
    week_delta = timedelta(weeks=1)
    week_number = 1
    first_day_of_week = first_day_first_week
    while (first_day_of_week + week_delta).year <= year and\
          (first_day_of_week + week_delta).month <= month and\
          week_number < week:

        week_number += 1
        first_day_of_week += week_delta

    week_start = first_day_of_week.replace(hour=0,
        minute=0,
        second=0,
        tzinfo=timezone.get_current_timezone())

    week_end = week_start + week_delta
    week_measures = ElectricDataTemp.objects.filter(profile_powermeter=profile,
        medition_date__gte=week_start,
        medition_date__lt=week_end).order_by("medition_date")

    week_measures_last_index = len(week_measures) - 1
    if week_measures_last_index < 1:
        week_measure = 0
    else:
        if type == "kwh" or type == "kwh_consumido":
            week_measure = week_measures[week_measures_last_index].TotalkWhIMPORT -\
                           week_measures[0].TotalkWhIMPORT

        else:
            week_measure = week_measures[week_measures_last_index].TotalkvarhIMPORT -\
                           week_measures[0].TotalkvarhIMPORT

    day_delta = timedelta(days=1)
    datetime_from = week_start
    datetime_to = datetime_from + day_delta
    for day_index in range(0,7):
        measures = ElectricDataTemp.objects.filter(profile_powermeter=profile,
            medition_date__gte=datetime_from,
            medition_date__lt=datetime_to)

        measures_last_index = len(measures) - 1
        if measures_last_index < 1:
            measure = 0
        else:
            if type == "kwh" or type == "kwh_consumido":

                measure = measures[measures_last_index].TotalkWhIMPORT - measures[0].TotalkWhIMPORT

            else:
                measure = measures[measures_last_index].TotalkvarhIMPORT - measures[0].TotalkvarhIMPORT

        if week_measure:
            measure_percentage = (measure / week_measure) * 100
        else:
            measure_percentage = 0

        weekly_summary.append({"date":datetime_from, "kwh":measure,
                               "percentage": measure_percentage})
        datetime_from = datetime_to
        datetime_to = datetime_from + day_delta

    return weekly_summary, week_measure

def get_weekly_summary_comparison_kwh(request):
    template_variables = {}
    week_days = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    if request.GET:
        week_01, tot1 = get_weekly_summary_for_parameter(int(request.GET['year01']),
                                               int(request.GET['month01']),
                                               int(request.GET['week01']),
                                               request.GET['type'],
                                               request.session['consumer_unit']
                                                .profile_powermeter)
        template_variables['total1'] = tot1
        if "year02" in request.GET:
            week_02, total2 = get_weekly_summary_for_parameter(int(request.GET['year02']),
                                                   int(request.GET['month02']),
                                                   int(request.GET['week02']),
                                                   request.GET['type'],
                                                   request.session['consumer_unit']
                                                   .profile_powermeter)
            template_variables['total2'] = total2
            template_variables['comparison'] = zip(week_days, week_01, week_02)
            template_variables['compared'] = True
        else:
            template_variables['comparison'] = zip(week_days, week_01)


        template_variables['type'] = request.GET['type']
        request_variables = RequestContext(request, template_variables)
        return render_to_response('consumption_centers/graphs/kwh.html', request_variables)
    else:
        raise Http404

def get_cluster_companies(request, id_cluster):
    cluster = get_object_or_404(Cluster, pk=id_cluster)
    c_buildings= ClusterCompany.objects.filter(cluster=cluster)
    companies = []
    for company in c_buildings:
        companies.append(dict(pk=company.company.pk, company=company.company.company_name))
    data=simplejson.dumps(companies)
    return HttpResponse(content=data,content_type="application/json")

def get_company_buildings(request, id_company):
    company = get_object_or_404(Company, pk=id_company)
    c_buildings= CompanyBuilding.objects.filter(company=company)
    buildings = []
    for building in c_buildings:
        buildings.append(dict(pk=building.building.pk, building=building.building.building_name))
    data=simplejson.dumps(buildings)
    return HttpResponse(content=data,content_type="application/json")

def get_parts_of_building(request, id_building):
    building = get_object_or_404(Building, pk=id_building)
    p_buildings= PartOfBuilding.objects.filter(building=building)
    parts = []
    for part in p_buildings:
        parts.append(dict(pk=part.pk, part=part.part_of_building_name))
    data=simplejson.dumps(parts)
    return HttpResponse(content=data,content_type="application/json")

def add_building_attr(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta de atributos de edificios"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        type = ""
        message = ""
        attributes = BuildingAttributesType.objects.all().order_by(
                     "building_attributes_type_sequence")
        template_vars = dict(datacontext=datacontext, empresa=empresa, company=company,
                             type=type, message=message, attributes=attributes)
        if request.method == "POST":
            template_vars['post'] = variety.get_post_data(request.POST)

            valid = True
            attr_name = template_vars['post']['attr_name']
            attr = get_object_or_404(BuildingAttributesType, pk=template_vars['post']['attr_type'])
            desc = template_vars['post']['description']
            if not variety.validate_string(desc) or not variety.validate_string(attr_name):
                valid = False
                template_vars['message'] = "Por favor solo ingrese caracteres v&aacute;lidos"


            if template_vars['post']['value_boolean'] == 1:
                bool = True
                unidades = template_vars['post']['unidades']
                if not unidades:
                    valid = False
                else:
                    if not variety.validate_string(unidades):
                        valid = False
                        template_vars['message'] = "Por favor solo ingrese caracteres v&aacute;lidos"
            else:
                bool = False
                unidades = ""
            if attr_name and valid:
                b_attr = BuildingAttributes(
                            building_attributes_type = attr,
                            building_attributes_name = attr_name,
                            building_attributes_description = desc,
                            building_attributes_value_boolean = bool,
                            building_attributes_units_of_measurement = unidades
                         )
                b_attr.save()
                template_vars['message'] = "El atributo fue dado de alta correctamente"
                template_vars['type'] = "n_success"
                if has_permission(request.user, VIEW, "Ver atributos de edificios"):
                    return HttpResponseRedirect("/buildings/atributos?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            else:

                template_vars['type'] = "n_error"


        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_building_attr.html",
               template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def b_attr_list(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver atributos de edificios"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''
        order_attrname = 'asc'
        order_type = 'asc'
        order_units = 'asc'
        order_sequence = 'asc'
        order = "building_attributes_name" #default order
        if "order_attrname" in request.GET:
            if request.GET["order_attrname"] == "desc":
                order = "-building_attributes_name"
                order_attrname = "asc"
            else:
                order_attrname = "desc"
        elif "order_type" in request.GET:

                if request.GET["order_type"] == "asc":
                    order = "building_attributes_type__building_attributes_type_name"
                    order_type = "desc"
                else:
                    order = "-building_attributes_type__building_attributes_type_name"
                    order_type = "asc"
        elif "order_units" in request.GET:
            if request.GET["order_units"] == "asc":
                order = "building_attributes_units_of_measurement"
                order_units = "desc"
            else:
                order = "-building_attributes_units_of_measurement"
                order_units = "asc"
        elif "order_sequence" in request.GET:
            if request.GET["order_sequence"] == "asc":
                order = "building_attributes_sequence"
                order_sequence = "desc"
            else:
                order = "-building_attributes_sequence"
                order_sequence = "asc"

        if search:
            lista = BuildingAttributes.objects.filter(
                        Q(building_attributes_name__icontains=request.GET['search'])|
                        Q(building_attributes_description__icontains=request.GET['search']))\
                    .order_by(order)
        else:
            lista = BuildingAttributes.objects.all().order_by(order)
        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(roles=paginator, order_attrname=order_attrname,
                             order_type=order_type, order_units=order_units,
                             order_sequence=order_sequence, empresa=empresa, company=company,
                             datacontext=datacontext)
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
        return render_to_response("consumption_centers/buildings/building_attr_list.html",
               template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_b_attr(request, id_b_attr):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Eliminar atributos de edificios"):
        b_attr = get_object_or_404(BuildingAttributes, pk=id_b_attr)
        b_attr_for_b = BuildingAttributesForBuilding.objects.filter(building_attributes=b_attr)
        if b_attr_for_b:
            mensaje = "Para eliminar un atributo, primero se tienen que eliminar las " \
                      "asignaciones de atributos a edificios"
            type = "n_notif"
        else:
            b_attr.delete()
            mensaje = "El atributo se ha dado de baja correctamente"
            type="n_success"
        return HttpResponseRedirect("/buildings/atributos/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def editar_b_attr(request, id_b_attr):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver atributos de edificios"):
        b_attr = get_object_or_404(BuildingAttributes, pk=id_b_attr)
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        if b_attr.building_attributes_value_boolean:
            bool = "1"
        else:
            bool = "0"
        post = {'attr_name': b_attr.building_attributes_name,
                'description': b_attr.building_attributes_description,
                'attr_type': b_attr.building_attributes_type.pk,
                'value_boolean': bool,
                'unidades': b_attr.building_attributes_units_of_measurement}
        message = ''
        type = ''
        attributes = BuildingAttributesType.objects.all().order_by(
                     "building_attributes_type_sequence")
        template_vars = dict(datacontext=datacontext, empresa=empresa, message=message,
                             post=post,type=type, operation="edit", company=company,
                             attributes=attributes)
        if request.method == "POST":
            template_vars['post'] = variety.get_post_data(request.POST)

            valid = True
            attr_name = template_vars['post']['attr_name']
            attr = get_object_or_404(BuildingAttributesType, pk=template_vars['post']['attr_type'])
            desc = template_vars['post']['description']
            if not variety.validate_string(desc) or not variety.validate_string(attr_name):
                valid = False
                template_vars['message'] = "Por favor solo ingrese caracteres v&aacute;lidos"


            if template_vars['post']['value_boolean'] == 1:
                bool = True
                unidades = template_vars['post']['unidades']
                if not unidades:
                    valid = False
                else:
                    if not variety.validate_string(unidades):
                        valid = False
                        template_vars['message'] = "Por favor solo ingrese caracteres v&aacute;lidos"
            else:
                bool = False
                unidades = ""
            if attr_name and valid:
                b_attr.building_attributes_type = attr
                b_attr.building_attributes_name = attr_name
                b_attr.building_attributes_description = desc
                b_attr.building_attributes_value_boolean = bool
                b_attr.building_attributes_units_of_measurement = unidades
                b_attr.save()
                template_vars['message'] = "El atributo fue editado correctamente"
                template_vars['type'] = "n_success"
                if has_permission(request.user, VIEW, "Ver atributos de edificios"):
                    return HttpResponseRedirect("/buildings/atributos?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            else:

                template_vars['type'] = "n_error"


        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_building_attr.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def ver_b_attr(request, id_b_attr):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver atributos de edificios"):
        b_attr = get_object_or_404(BuildingAttributes, pk=id_b_attr)
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        if b_attr.building_attributes_value_boolean:
            bool = "1"
        else:
            bool = "0"
        post = {'attr_name': b_attr.building_attributes_name,
                'description': b_attr.building_attributes_description,
                'attr_type': b_attr.building_attributes_type.building_attributes_type_name,
                'value_boolean': bool,
                'unidades': b_attr.building_attributes_units_of_measurement}
        message = ''
        type = ''
        attributes = BuildingAttributesType.objects.all().order_by(
            "building_attributes_type_sequence")
        template_vars = dict(datacontext=datacontext, empresa=empresa, message=message,
                             company=company, post=post,type=type, operation="edit",
                             attributes=attributes)


        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/see_building_attr.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

#====

def add_cluster(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta de clusters"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        #Se obtienen los sectores
        sectores = SectoralType.objects.all()
        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            sectores=sectores,
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            clustername = request.POST.get('clustername')
            clusterdescription = request.POST.get('clusterdescription')
            clustersector = request.POST.get('clustersector')

            sector_type = SectoralType.objects.get(pk = clustersector)

            newCluster = Cluster(
                sectoral_type = sector_type,
                cluster_description = clusterdescription,
                cluster_name = clustername,
            )
            newCluster.save()

            template_vars["message"] = "Cluster de Empresas creado exitosamente"
            template_vars["type"] = "n_success"

            if has_permission(request.user, VIEW, "Ver clusters"):
                return HttpResponseRedirect("/buildings/clusters?msj=" +
                                            template_vars["message"] +
                                            "&ntype=n_success")

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_cluster.html", template_vars_template)

    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_cluster(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver cluster de empresas"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_sector = 'asc'
        order = "cluster_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-cluster_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:

            if "order_sector" in request.GET:
                if request.GET["order_sector"] == "asc":
                    order = "sectoral_type__sectorial_type_name"
                    order_sector = "desc"
                else:
                    order = "-sectoral_type__sectorial_type_name"
                    order_sector = "asc"

        if search:
            lista = Cluster.objects.filter(Q(cluster_name__icontains=request.GET['search'])|Q(
                sectoral_type__sectorial_type_name__icontains=request.GET['search'])).exclude(cluster_status=2).order_by(order)

        else:
            lista = Cluster.objects.all().exclude(cluster_status=2).order_by(order)
        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_sector=order_sector,
            datacontext=datacontext, empresa=empresa)
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
        return render_to_response("consumption_centers/buildings/clusters.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_cluster(request, id_cluster):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de clusters"):
        cluster = get_object_or_404(Cluster, pk=id_cluster)
        cluster.cluster_status = 2
        cluster.save()
        mensaje = "El cluster ha sido dado de baja correctamente"
        type="n_success"

        return HttpResponseRedirect("/buildings/clusters/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_batch_cluster(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de clusters"):
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^cluster_\w+', key):
                    r_id = int(key.replace("cluster_",""))
                    cluster = get_object_or_404(Cluster, pk=r_id)
                    cluster.cluster_status = 2
                    cluster.save()

            mensaje = "Los clusters seleccionados se han dado de baja"
            return HttpResponseRedirect("/buildings/clusters/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/clusters/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))



def edit_cluster(request, id_cluster):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar cluster de empresas"):
        cluster = get_object_or_404(Cluster, pk = id_cluster)

        #Se obtienen los sectores
        sectores = SectoralType.objects.all()

        post = {'clustername': cluster.cluster_name, 'clusterdescription': cluster.cluster_description, 'clustersector': cluster.sectoral_type.pk}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        message = ''
        type = ''

        if request.method == "POST":
            post = request.POST
            clustername = request.POST.get('clustername')
            clusterdescription = request.POST.get('clusterdescription')
            clustersector = request.POST.get('clustersector')
            continuar = True
            if clustername == '':
                message = "El nombre del cluster no puede quedar vacío"
                type = "n_notif"
                continuar = False
            if clustersector == '':
                message = "El sector del cluster no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'clustername': clustername, 'clusterdescription': clusterdescription ,'clustersector': clustersector}


            if continuar:
                sector_type = SectoralType.objects.get(pk = clustersector)

                cluster.cluster_name = clustername
                cluster.cluster_description = clusterdescription
                cluster.sectoral_type = sector_type
                cluster.save()

                message = "Cluster editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW, "Ver cluster de empresas"):
                    return HttpResponseRedirect("/buildings/clusters?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            sectores=sectores,
            post=post,
            operation="edit",
            message=message,
            type=type
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_cluster.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def see_cluster(request, id_cluster):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver cluster de empresas"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        cluster = Cluster.objects.get(pk = id_cluster)
        cluster_companies = ClusterCompany.objects.filter(cluster=cluster)

        template_vars = dict(
            datacontext=datacontext,
            cluster = cluster,
            cluster_companies = cluster_companies,
            empresa=empresa)

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/see_cluster.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

"""
POWERMETER MODELS
"""

def add_powermetermodel(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta de modelos de medidores eléctricos"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        template_vars = dict(datacontext=datacontext,
            empresa=empresa
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            pw_brand = request.POST.get('pw_brand')
            pw_model = request.POST.get('pw_model')

            newPowerMeterModel = PowermeterModel(
                powermeter_brand = pw_brand,
                powermeter_model = pw_model
            )
            newPowerMeterModel.save()

            template_vars["message"] = "Modelo de Medidor creado exitosamente"
            template_vars["type"] = "n_success"

            if has_permission(request.user, VIEW, "Ver modelos de medidores eléctricos"):
                return HttpResponseRedirect("/buildings/modelos_medidor?msj=" +
                                            template_vars["message"] +
                                            "&ntype=n_success")

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_powermetermodel.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def edit_powermetermodel(request, id_powermetermodel):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar modelos de medidores eléctricos"):
        powermetermodel = get_object_or_404(PowermeterModel, pk = id_powermetermodel)

        post = {'pw_brand': powermetermodel.powermeter_brand, 'pw_model': powermetermodel.powermeter_model}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        message = ''
        type = ''

        if request.method == "POST":
            post = request.POST
            powermeter_brand = request.POST.get('pw_brand')
            powermeter_model = request.POST.get('pw_model')

            continuar = True
            if powermeter_brand == '':
                message = "La marca del medidor no puede quedar vacía"
                type = "n_notif"
                continuar = False
            if powermeter_model == '':
                message = "El modelo del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'pw_brand': powermetermodel.powermeter_brand, 'pw_model': powermetermodel.powermeter_model}

            if continuar:
                powermetermodel.powermeter_brand = powermeter_brand
                powermetermodel.powermeter_model = powermeter_model
                powermetermodel.save()

                message = "Modelo de Medidor editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW, "Ver modelos de medidores eléctricos"):
                    return HttpResponseRedirect("/buildings/modelos_medidor?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            post=post,
            operation="edit",
            message=message,
            type=type
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_powermetermodel.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_powermetermodels(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver modelos de medidores eléctricos"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_brand = 'asc'
        order_model = 'asc'
        order = "powermeter_brand" #default order
        if "order_brand" in request.GET:
            if request.GET["order_brand"] == "desc":
                order = "-powermeter_brand"
                order_brand = "asc"
            else:
                order_brand = "desc"
        else:

            if "order_model" in request.GET:
                if request.GET["order_model"] == "asc":
                    order = "powermeter_model"
                    order_model = "desc"
                else:
                    order = "-powermeter_model"
                    order_model = "asc"

        if search:
            lista = PowermeterModel.objects.filter(Q(powermeter_brand__icontains=request.GET['search'])|Q(
                powermeter_model__icontains=request.GET['search'])).order_by(order)

        else:
            lista = PowermeterModel.objects.all().order_by(order)
        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_brand=order_brand, order_model=order_model,
            datacontext=datacontext, empresa=empresa)
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
        return render_to_response("consumption_centers/buildings/powermetermodels.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_powermetermodel(request, id_powermetermodel):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de clusters"):
        powermetermodel = get_object_or_404(PowermeterModel, pk = id_powermetermodel)
        #Change the status in here
        powermetermodel.save()
        mensaje = "El modelo ha sido dado de baja correctamente"
        type="n_success"

        return HttpResponseRedirect("/buildings/modelos_medidor/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_batch_powermetermodel(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de clusters"):
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^model_\w+', key):
                    r_id = int(key.replace("model_",""))
                    powermetermodel = get_object_or_404(PowermeterModel, pk = r_id)
                    #Change the status in here
                    powermetermodel.save()

            mensaje = "Los modelos seleccionados se han dado de baja"
            return HttpResponseRedirect("/buildings/modelos_medidor/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/modelos_medidor/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


"""
POWERMETERS
"""

def add_powermeter(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta de medidor electrico"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        post = ''
        pw_models_list = PowermeterModel.objects.all().order_by("powermeter_brand")
        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            modelos=pw_models_list,
            post=post
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            pw_alias = request.POST.get('pw_alias')
            pw_model = request.POST.get('pw_model')
            pw_serial = request.POST.get('pw_serial')

            continuar = True
            if pw_alias == '':
                message = "El Alias del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False
            if pw_model == '':
                message = "El modelo del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False
            if pw_serial == '':
                message = "El número serial del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'pw_alias': pw_alias, 'pw_model': pw_model ,'pw_serial': pw_serial}


            if continuar:

                pw_model = PowermeterModel.objects.get(pk = pw_model)

                newPowerMeter = Powermeter(
                    powermeter_model = pw_model,
                    powermeter_anotation = pw_alias,
                    powermeter_serial = pw_serial

                )
                newPowerMeter.save()

                template_vars["message"] = "Medidor creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW, "Ver medidores eléctricos"):
                    return HttpResponseRedirect("/buildings/medidores?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_powermeter.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def edit_powermeter(request, id_powermeter):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar medidores eléctricos"):
        powermeter = get_object_or_404(Powermeter, pk = id_powermeter)

        pw_models_list = PowermeterModel.objects.all().order_by("powermeter_brand")

        post = {'pw_alias': powermeter.powermeter_anotation, 'pw_model': powermeter.powermeter_model.pk,'pw_serial': powermeter.powermeter_serial}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        message = ''
        type = ''

        if request.method == "POST":
            post = request.POST
            pw_alias = request.POST.get('pw_alias')
            pw_model = request.POST.get('pw_model')
            pw_serial = request.POST.get('pw_serial')

            continuar = True
            if pw_alias == '':
                message = "El Alias del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False
            if pw_model == '':
                message = "El modelo del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False
            if pw_serial == '':
                message = "El número serial del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'pw_alias': pw_alias, 'pw_model': pw_model ,'pw_serial': pw_serial}


            if continuar:

                pw_model = PowermeterModel.objects.get(pk = pw_model)

                powermeter.powermeter_anotation = pw_alias
                powermeter.powermeter_serial = pw_serial
                powermeter.powermeter_model = pw_model
                powermeter.save()

                message = "Medidor editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW, "Ver medidores eléctricos"):
                    return HttpResponseRedirect("/buildings/medidores?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            post=post,
            modelos = pw_models_list,
            operation="edit",
            message=message,
            type=type
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_powermeter.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_powermeter(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver medidores eléctricos"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_alias = 'asc'
        order_serial = 'asc'
        order_model = 'asc'
        order_status = 'asc'
        order_installed = 'asc'
        order = "powermeter_anotation" #default order
        if "order_alias" in request.GET:
            if request.GET["order_alias"] == "desc":
                order = "-powermeter_anotation"
                order_alias = "asc"
            else:
                order_alias = "desc"
        else:
            if "order_model" in request.GET:
                if request.GET["order_model"] == "asc":
                    order = "powermeter_model__powermeter_brand"
                    order_model = "desc"
                else:
                    order = "-powermeter_model__powermeter_brand"
                    order_model = "asc"

            if "order_serial" in request.GET:
                if request.GET["order_serial"] == "asc":
                    order = "powermeter_serial"
                    order_serial = "desc"
                else:
                    order = "-powermeter_serial"
                    order_serial = "asc"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "status"
                    order_status = "desc"
                else:
                    order = "-status"
                    order_status = "asc"

        if search:


            lista = Powermeter.objects.filter(Q(powermeter_anotation__icontains=request.GET['search'])|Q(
                powermeter_model__powermeter_brand__icontains=request.GET['search'])|Q(
                powermeter_model__powermeter_model__icontains=request.GET['search'])).exclude(status = 2).order_by(order)



        else:
            powermeter_objs = Powermeter.objects.all().exclude(status=2)
            powermeter_ids = [pw.pk for pw in powermeter_objs]
            profiles_pw_objs = ProfilePowermeter.objects.filter(powermeter__pk__in = powermeter_ids).filter(profile_powermeter_status = 1)

            lista = Powermeter.objects.all().exclude(status = 2).order_by(order)


        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_alias=order_alias, order_model=order_model, order_serial=order_serial, order_status=order_status,
            datacontext=datacontext, empresa=empresa)
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
        return render_to_response("consumption_centers/buildings/powermeters.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_powermeter(request, id_powermeter):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de medidores eléctricos"):
        powermeter = get_object_or_404(Powermeter, pk = id_powermeter )
        powermeter.status = 2
        powermeter.save()
        mensaje = "El medidor ha sido dado de baja correctamente"
        type="n_success"

        return HttpResponseRedirect("/buildings/medidores/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_batch_powermeter(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de medidores eléctricos"):
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^powermeter_\w+', key):
                    r_id = int(key.replace("powermeter_",""))
                    powermeter = get_object_or_404(Powermeter, pk = r_id )
                    powermeter.status = 2
                    powermeter.save()

            mensaje = "Los medidores seleccionados se han dado de baja"
            return HttpResponseRedirect("/buildings/medidores/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/medidores/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def status_powermeter(request, id_powermeter):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar medidores eléctricos"):
        powermeter = get_object_or_404(Powermeter, pk = id_powermeter )
        if powermeter.status == 0:
            powermeter.status = 1
            str_status = "Activo"
        elif powermeter.status == 1:
            powermeter.status = 0
            str_status = "Inactivo"

        powermeter.save()
        mensaje = "El estatus del medidor "+powermeter.powermeter_anotation +" ha cambiado a "+str_status
        type="n_success"

        return HttpResponseRedirect("/buildings/medidores/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def see_powermeter(request, id_powermeter):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver medidores eléctricos"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        location = ''
        powermeter = Powermeter.objects.get(pk = id_powermeter)
        profile_powermeter_objs = ProfilePowermeter.objects.filter(powermeter = powermeter).filter(profile_powermeter_status = 1)
        if profile_powermeter_objs:
            profile = profile_powermeter_objs[0]

            consumer_unit_objs = ConsumerUnit.objects.filter(profile_powermeter = profile)
            c_unit = consumer_unit_objs[0]
            location = c_unit.building.building_name

        template_vars = dict(
            datacontext=datacontext,
            powermeter = powermeter,
            location = location,
            empresa=empresa)

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/see_powermeter.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

"""
Electric Device Types
"""

def add_electric_device_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta de dispositivos y sistemas eléctricos"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        post = ''

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            post=post
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            edt_name = request.POST.get('devicetypename')
            edt_description = request.POST.get('devicetypedescription')

            continuar = True
            if edt_name == '':
                message = "El nombre del Tipo de Equipo Eléctrico no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'devicetypename': edt_name, 'devicetypedescription': edt_description}


            if continuar:

                newElectricDeviceType = ElectricDeviceType(
                    electric_device_type_name = edt_name,
                    electric_device_type_description = edt_description
                )
                newElectricDeviceType.save()

                template_vars["message"] = "Tipo de Equipo Eléctrico creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW, "Ver medidores eléctricos"):
                    return HttpResponseRedirect("/buildings/tipos_equipo_electrico?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_electricdevicetype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def edit_electric_device_type(request, id_edt):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar dispositivos y sistemas eléctricos"):
        edt_obj = get_object_or_404(ElectricDeviceType, pk = id_edt)

        post = {'devicetypename': edt_obj.electric_device_type_name, 'devicetypedescription': edt_obj.electric_device_type_description}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        message = ''
        type = ''

        if request.method == "POST":
            post = request.POST
            edt_name = request.POST.get('devicetypename')
            edt_description = request.POST.get('devicetypedescription')

            continuar = True
            if edt_name == '':
                message = "El nombre del Tipo de Equipo Eléctrico no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'devicetypename': edt_name, 'devicetypedescription': edt_description}

            if continuar:
                edt_obj.electric_device_type_name = edt_name
                edt_obj.electric_device_type_description = edt_description
                edt_obj.save()

                message = "Tipo de Equipo Eléctrico editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW, "Ver dispositivos y sistemas eléctricos"):
                    return HttpResponseRedirect("/buildings/tipos_equipo_electrico?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            post=post,
            operation="edit",
            message=message,
            type=type
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_electricdevicetype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_electric_device_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver dispositivos y sistemas eléctricos"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_description = 'asc'
        order_status = 'asc'
        order = "electric_device_type_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-electric_device_type_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_description" in request.GET:
                if request.GET["order_description"] == "asc":
                    order = "electric_device_type_description"
                    order_description = "desc"
                else:
                    order = "-electric_device_type_description"
                    order_description = "asc"
            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "electric_device_type_status"
                    order_status = "desc"
                else:
                    order = "-electric_device_type_status"
                    order_status = "asc"

        if search:
            lista = ElectricDeviceType.objects.filter(Q(electric_device_type_name__icontains=request.GET['search'])|Q(
                electric_device_type_description__icontains=request.GET['search'])).exclude(electric_device_type_status = 2).order_by(order)

        else:
            lista = ElectricDeviceType.objects.all().exclude(electric_device_type_status = 2).order_by(order)


        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_description=order_description, order_status=order_status,
            datacontext=datacontext, empresa=empresa)
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
        return render_to_response("consumption_centers/buildings/electricdevicetype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_electric_device_type(request, id_edt):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de dispositivos y sistemas eléctricos"):
        edt_obj = get_object_or_404(ElectricDeviceType, pk=id_edt)
        edt_obj.electric_device_type_status = 2
        edt_obj.save()
        mensaje = "El Tipo de Equipo Eléctrico ha sido dado de baja correctamente"
        type="n_success"

        return HttpResponseRedirect("/buildings/tipos_equipo_electrico/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_batch_electric_device_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de dispositivos y sistemas eléctricos"):
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^edt_\w+', key):
                    r_id = int(key.replace("edt_",""))
                    edt_obj = get_object_or_404(ElectricDeviceType, pk=r_id)
                    edt_obj.electric_device_type_status = 2
                    edt_obj.save()

            mensaje = "Los Tipos de Equipo Eléctrico han sido dado de baja correctamente"
            return HttpResponseRedirect("/buildings/tipos_equipo_electrico/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/tipos_equipo_electrico/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def status_electric_device_type(request, id_edt):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar dispositivos y sistemas eléctricos"):
        edt_obj = get_object_or_404(ElectricDeviceType, pk=id_edt)
        if edt_obj.electric_device_type_status == 0:
            edt_obj.electric_device_type_status = 1
            str_status = "Activo"
        elif edt_obj.electric_device_type_status == 1:
            edt_obj.electric_device_type_status = 0
            str_status = "Inactivo"

        edt_obj.save()
        mensaje = "El estatus del tipo de equipo eléctrico ha cambiado a "+str_status
        type="n_success"

        return HttpResponseRedirect("/buildings/tipos_equipo_electrico/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

"""
Companies
"""

def add_company(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta compañía"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        post = ''

        #Get Clusters
        clusters = Cluster.objects.all().exclude(cluster_status = 2)

        #Get Sectors
        sectors = SectoralType.objects.all().exclude(sectoral_type_status = 2)

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            post=post,
            clusters=clusters,
            sectors=sectors,
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            cmp_name = request.POST.get('company_name')
            cmp_description = request.POST.get('company_description')
            cmp_cluster = request.POST.get('company_cluster')
            cmp_sector = request.POST.get('company_sector')

            continuar = True
            if cmp_name == '':
                message = "El nombre de la empresa no puede quedar vacío"
                type = "n_notif"
                continuar = False

            if cmp_cluster == '':
                message = "La empresa debe pertenencer a un grupo de empresas"
                type = "n_notif"
                continuar = False

            if cmp_sector == '':
                message = "La empresa debe pertenencer a un sector"
                type = "n_notif"
                continuar = False

            post = {'cmp_name': cmp_name, 'cmp_description': cmp_description, 'cmp_cluster': cmp_cluster, 'cmp_sector': cmp_sector}

            if continuar:
                #Se obtiene el objeto del sector
                sectorObj = SectoralType.objects.get(pk=cmp_sector)

                newCompany = Company(
                    sectoral_type = sectorObj,
                    company_name = cmp_name,
                    company_description = cmp_description
                )
                newCompany.save()

                #Se relaciona la empresa con el cluster
                #Se obtiene el objeto del cluster
                clusterObj = Cluster.objects.get(pk=cmp_cluster)

                newCompanyCluster = ClusterCompany(
                    cluster = clusterObj,
                    company = newCompany
                )
                newCompanyCluster.save()

                #Guarda la foto
                if 'logo' in request.FILES:
                    handle_company_logo(request.FILES['logo'], newCompany)


                template_vars["message"] = "Empresa creada exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW, "Ver empresas"):
                    return HttpResponseRedirect("/buildings/empresas?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_company.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def edit_company(request, id_cpy):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar empresas"):
        company_clusters = ClusterCompany.objects.filter(id = id_cpy)

        post = {'cmp_id': company_clusters[0].company.id,'cmp_name': company_clusters[0].company.company_name, 'cmp_description': company_clusters[0].company.company_description, 'cmp_cluster': company_clusters[0].cluster.pk, 'cmp_sector': company_clusters[0].company.sectoral_type.pk, 'cmp_logo': company_clusters[0].company.company_logo}

        #Get Clusters
        clusters = Cluster.objects.all().exclude(cluster_status = 2)

        #Get Sectors
        sectors = SectoralType.objects.all().exclude(sectoral_type_status = 2)

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        message = ''
        type = ''

        if request.method == "POST":
            post = request.POST
            cmp_name = request.POST.get('company_name')
            cmp_description = request.POST.get('company_description')
            cmp_cluster = request.POST.get('company_cluster')
            cmp_sector = request.POST.get('company_sector')

            continuar = True
            if cmp_name == '':
                message = "El nombre de la empresa no puede quedar vacío"
                type = "n_notif"
                continuar = False

            if cmp_cluster == '':
                message = "La empresa debe pertenencer a un grupo de empresas"
                type = "n_notif"
                continuar = False

            if cmp_sector == '':
                message = "La empresa debe pertenencer a un sector"
                type = "n_notif"
                continuar = False

            post = {'cmp_id': company_clusters[0].company.id, 'cmp_name': cmp_name, 'cmp_description': cmp_description, 'cmp_cluster': cmp_cluster, 'cmp_sector': cmp_sector, 'cmp_logo': company_clusters[0].company.company_logo}

            if continuar:
                #Actualiza la empresa
                companyObj = Company.objects.get(pk = company_clusters[0].company.pk)
                companyObj.company_name = cmp_name
                companyObj.company_description = cmp_description
                #Se obtiene el objeto del sector
                sectorObj = SectoralType.objects.get(pk=cmp_sector)
                companyObj.sectoral_type = sectorObj
                companyObj.save()

                #Se relaciona la empresa con el cluster
                ComCluster = ClusterCompany.objects.get(pk = company_clusters[0].pk)
                ComCluster.delete()

                #Se obtiene el objeto del cluster
                clusterObj = Cluster.objects.get(pk=cmp_cluster)
                newCompanyCluster = ClusterCompany(
                    cluster = clusterObj,
                    company = companyObj
                )
                newCompanyCluster.save()

                #Guarda la foto
                if 'logo' in request.FILES:
                    handle_company_logo(request.FILES['logo'], companyObj)


                message = "Empresa editada exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW, "Ver empresas"):
                    return HttpResponseRedirect("/buildings/empresas?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            post=post,
            operation="edit",
            message=message,
            clusters = clusters,
            sectors = sectors,
            type=type
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_company.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_companies(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver empresas"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_company = 'asc'
        order_cluster = 'asc'
        order_sector = 'asc'
        order_status = 'asc'
        order = "company__company_name" #default order
        if "order_company" in request.GET:
            if request.GET["order_company"] == "desc":
                order = "-company__company_name"
                order_company = "asc"
            else:
                order_company = "desc"
        else:
            if "order_cluster" in request.GET:
                if request.GET["order_cluster"] == "asc":
                    order = "cluster__cluster_name"
                    order_cluster = "desc"
                else:
                    order = "-cluster__cluster_name"
                    order_cluster = "asc"
            if "order_sector" in request.GET:
                if request.GET["order_sector"] == "asc":
                    order = "company__sectoral_type__sectorial_type_name"
                    order_sector = "desc"
                else:
                    order = "-company__sectoral_type__sectorial_type_name"
                    order_sector = "asc"
            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "company__company_status"
                    order_status = "desc"
                else:
                    order = "-company__company_status"
                    order_status = "asc"

        if search:
            lista = ClusterCompany.objects.filter(Q(company__company_name__icontains=request.GET['search'])|Q(
                company__company_description__icontains=request.GET['search'])|Q(cluster__cluster_name__icontains=request.GET['search'])|Q(
                company__sectoral_type__sectorial_type_name__icontains=request.GET['search'])).exclude(company__company_status = 2).order_by(order)

        else:
            lista = ClusterCompany.objects.all().exclude(company__company_status = 2).order_by(order)

        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_company=order_company, order_cluster=order_cluster, order_sector=order_sector, order_status=order_status,
            datacontext=datacontext, empresa=empresa)
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
        return render_to_response("consumption_centers/buildings/companies.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_company(request, id_cpy):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de empresas"):
        cpy_obj = get_object_or_404(Company, pk = id_cpy)
        cpy_obj.company_status = 2
        cpy_obj.save()
        mensaje = "La empresa ha sido dada de baja correctamente"
        type="n_success"

        return HttpResponseRedirect("/buildings/empresas/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_batch_companies(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de empresas"):
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^cmpy_\w+', key):
                    r_id = int(key.replace("cmpy_",""))
                    cpy_obj = get_object_or_404(Company, pk = r_id)
                    cpy_obj.company_status = 2
                    cpy_obj.save()

            mensaje = "Las empresas han sido dadas de baja correctamente"
            return HttpResponseRedirect("/buildings/empresas/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/empresas/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def status_company(request, id_cpy):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar empresas"):
        company = get_object_or_404(Company, pk = id_cpy)
        if company.company_status == 0:
            company.company_status = 1
            str_status = "Activo"
        elif company.company_status == 1:
            company.company_status = 0
            str_status = "Inactivo"

        company.save()
        mensaje = "El estatus de la empresa " + company.company_name +" ha cambiado a "+str_status
        type="n_success"

        return HttpResponseRedirect("/buildings/empresas/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def see_company(request, id_cpy):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver empresas"):
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        company_cluster_objs = ClusterCompany.objects.filter(company__pk = id_cpy)
        company = company_cluster_objs[0]

        template_vars = dict(
            datacontext=datacontext,
            company = company,
            empresa=empresa)

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/see_company.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def scale_dimensions(width, height, longest_side):
    """
    para calcular la proporcion en la que se redimencionara la imagen
    """
    if width > height:
        if width > longest_side:
            ratio = longest_side*1./width
            return (int(width*ratio), int(height*ratio))
    elif height > longest_side:
        ratio = longest_side*1./height
        return (int(width*ratio), int(height*ratio))
    return (width, height)


def handle_company_logo(i, company):
    dir_fd=os.open(os.path.join(settings.PROJECT_PATH, "templates/static/media/company_logos/"),os.O_RDONLY)
    os.fchdir(dir_fd)
    #Revisa si la carpeta de la empresa existe.
    dir_name = 'templates/static/media/company_logos/company_'+str(company.pk)+'/'
    dir_path = os.path.join(settings.PROJECT_PATH, dir_name)
    if not os.path.isdir(dir_path):
        os.mkdir("company_"+str(company.pk))
    else:
        dir_name = "company_" + str(company.pk)
        dir_path = os.path.join(settings.PROJECT_PATH, 'templates/static/media/company_logos/')
        files = os.listdir(dir_path+dir_name)
        dir_fd = os.open(dir_path+dir_name, os.O_RDONLY)
        os.fchdir(dir_fd)
        for file in files:
            if file==company.company_logo:
                os.remove(file)
        os.close(dir_fd)

    dir_fd = os.open(os.path.join(settings.PROJECT_PATH, "templates/static/media/company_logos/"+"company_"+str(company.pk)),os.O_RDONLY)
    os.fchdir(dir_fd)

    imagefile  = cStringIO.StringIO(i.read())
    imagefile.seek(0)
    imageImage = Image.open(imagefile)

    if imageImage.mode != "RGB":
        imageImage = imageImage.convert("RGB")

    (width, height) = imageImage.size
    (width, height) = scale_dimensions(width, height, longest_side=128)

    resizedImage = imageImage.resize((width, height))

    imagefile = cStringIO.StringIO()
    resizedImage.save(imagefile,'JPEG')
    filename = hashlib.md5(imagefile.getvalue()).hexdigest()+'.jpg'

    # #save to disk
    imagefile = open(os.path.join('',filename), 'w')
    resizedImage.save(imagefile,'JPEG')
    company.company_logo=filename
    company.save()
    os.close(dir_fd)
    return True
