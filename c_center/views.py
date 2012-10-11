# -*- coding: utf-8 -*-
#standard library imports
from datetime import  timedelta, datetime
from dateutil.relativedelta import relativedelta
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

from c_center.calculations import tarifaHM_mensual, tarifaHM_total, obtenerHistorico, \
    fechas_corte
from c_center.models import ConsumerUnit, Building, ElectricDataTemp, ProfilePowermeter, \
    Powermeter, PartOfBuilding, HierarchyOfPart, Cluster, ClusterCompany, Company, \
    CompanyBuilding, BuildingAttributesType, BuildingAttributes, BuildingAttributesForBuilding
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
    first_day_of_month = datetime(year=datetime_variable.year,
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
    f1_init = datetime.today() - relativedelta( months = 1 )
    f1_end = datetime.today()

    if "f1_init" in get:
        if get["f1_init"] != '':
            f1_init = time.strptime(get['f1_init'], "%d/%m/%Y")
            f1_init = datetime(f1_init.tm_year, f1_init.tm_mon, f1_init.tm_mday)
        if get["f1_end"] != '':
            f1_end = time.strptime(get['f1_end'], "%d/%m/%Y")
            f1_end = datetime(f1_end.tm_year, f1_end.tm_mon, f1_end.tm_mday)

    return f1_init, f1_end

def get_intervals_fecha(get):
    """get the interval for the graphs
    by default we get the data from the last month
    returns f1_init, f1_end as formated strings
    """
    f1_init = datetime.today() - relativedelta( months = 1 )
    f1_init = str(f1_init.year)+"-"+str(f1_init.month)+"-"+str(f1_init.day)+" 00:00:00"
    f1_end = datetime.today()
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
    """Just sends the main template for the CFE Bill """
    if has_permission(request.user, VIEW, "Consultar recibo CFE"):
        datacontext = get_buildings_context(request.user)
        set_default_session_vars(request, datacontext)

        template_vars={"type":"cfe", "datacontext":datacontext,
                       'empresa':request.session['main_building'],
                       'company': request.session['company'],
        }
        #print template_vars
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/cfe.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def cfe_calculations(request):
    """Renders the cfe bill and the historic data chart"""
    template_vars = {}

    if request.GET:
        if request.method == "GET":

            month = int(request.GET['month'])+1
            year = int(request.GET['year'])

            powermeter = request.session['consumer_unit'].profile_powermeter.powermeter

            start_date, end_date = fechas_corte(request.session['main_building'].cutoff_day,
                                                month, year)
            t_hm=tarifaHM_mensual(powermeter, start_date, end_date,
                                  request.session['main_building'].region,
                                  request.session['main_building'].electric_rate)
            totales_meses = t_hm['meses']
            arr_historico=obtenerHistorico(powermeter, t_hm['ultima_tarifa'],
                                           request.session['main_building'].region, 3,
                                           request.session['main_building'].electric_rate)

            template_vars['tarifaHM'] = t_hm
            template_vars['totales_meses'] = totales_meses
            template_vars['historico'] = arr_historico

            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/graphs/cfe_bill.html",
                template_vars_template)

    return HttpResponse(content="", content_type="text/html")


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
                ahora = datetime.now()
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