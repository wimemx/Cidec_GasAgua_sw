# -*- coding: utf-8 -*-
#standard library imports
from datetime import  timedelta, datetime
from dateutil.relativedelta import relativedelta
import Image
import cStringIO
import os
from django.core.files import File
import hashlib
import csv
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
from c_center.calculations import *
from c_center.models import *
from location.models import *
from electric_rates.models import ElectricRatesDetail
from rbac.models import Operation, DataContextPermission, UserRole, Object, PermissionAsigment
from rbac.rbac_functions import  has_permission, get_buildings_context, default_consumerUnit

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

def get_all_profiles_for_user(user):
    contexts = DataContextPermission.objects.filter(user_role__user=user)
    c_us = []
    for context in contexts:
        consumer_units = ConsumerUnit.objects.filter(building=context.building)
        #cu, user, building
        for consumerUnit in consumer_units:
            if consumerUnit.profile_powermeter.powermeter.powermeter_anotation != "Medidor Virtual":
                if context.part_of_building:
                    #if the user has permission over a part of building, and the consumer unit is
                    #the cu for the part of building
                    if consumerUnit.part_of_building == context.part_of_building:
                        c_us.append(consumerUnit)
                    elif is_in_part_of_building(consumerUnit, context.part_of_building):
                        c_us.append(consumerUnit)
                elif context.building == consumerUnit.building:
                    c_us.append(consumerUnit)

    return c_us



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
        except ObjectDoesNotExist:
            request.session['main_building'] = None
        except IndexError:
            request.session['main_building'] = None
    if "company" not in request.session and request.session['main_building']:
        c_b = CompanyBuilding.objects.get(building=request.session['main_building'])
        request.session['company'] = c_b.company

    if 'consumer_unit' not in request.session and request.session['main_building']:
        #sets the default ConsumerUnit (the first in ConsumerUnit for the main building)
        request.session['consumer_unit'] = default_consumerUnit(request.user, request.session['main_building'])
        #try:
        #    c_unit = ConsumerUnit.objects.filter(building=request.session['main_building'])
        #    request.session['consumer_unit'] = c_unit[0]
        #except ObjectDoesNotExist:
        #    request.session['main_building'] = None
        #except IndexError:
        #    request.session['main_building'] = None


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


def get_sons(parent, part, user, building):
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
                sons = get_sons(son.part_of_building_leaf, "part", user, building)
                cu = ConsumerUnit.objects.get(part_of_building=son.part_of_building_leaf)
                _class = "part_of_building"
            else:
                tag = son.consumer_unit_leaf.electric_device_type.electric_device_type_name
                sons = get_sons(son.consumer_unit_leaf, "consumer", user, building)
                cu = son.consumer_unit_leaf
                _class = "consumer_unit"
            if allowed_cu(cu, user, building):
                list += '<li><a href="#" rel="' + str(cu.pk) + '" class="' + _class + '">'
                list +=  tag + '</a>' + sons
            else:
                list += '<li>'
                list +=  tag + sons
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
        electric_device_type__electric_device_type_name="Total Edificio")
    hierarchy_list = "<ul id='org'>"\
                     "<li>"
    if allowed_cu(main_cu, request.user, building):
        hierarchy_list += "<a href='#' rel='" + str(main_cu.pk) + "'>"+\
                         building.building_name +\
                         "<br/>(Total)</a>"
    else:
        hierarchy_list += building.building_name +"<br/>(Total)"

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
                  Q(electric_device_type__electric_device_type_name="Total Edificio") )
        try:
            parents[0]
        except IndexError:
            #si no hay ninguno, es un edificio sin partes, o sin partes anidadas
            pass
        else:
            hierarchy_list += "<ul>"
            for parent in parents:
                if allowed_cu(parent, request.user, building):
                    hierarchy_list += "<li> <a href='#' rel='" + str(parent.pk) + "'>" +\
                                      parent.electric_device_type.electric_device_type_name + \
                                      "</a>"
                else:
                    hierarchy_list += "<li>" +\
                                      parent.electric_device_type.electric_device_type_name
                #obtengo la jerarquia de cada rama del arbol
                hierarchy_list += get_sons(parent, "consumer", request.user, building)
                hierarchy_list +="</li>"
            hierarchy_list +="</ul>"
    else:
        hierarchy_list += "<ul>"
        for parent in parents:

            c_unit_parent = ConsumerUnit.objects.filter(building=building,
                            part_of_building=parent).exclude(
                            electric_device_type__electric_device_type_name="Total Edificio")
            if allowed_cu(c_unit_parent[0], request.user, building):
                hierarchy_list += "<li> <a href='#' rel='" + str(c_unit_parent[0].pk) + "'>" +\
                                  parent.part_of_building_name + "</a>"
            else:
                hierarchy_list += "<li>" +\
                                  parent.part_of_building_name
            #obtengo la jerarquia de cada rama del arbol
            hierarchy_list += get_sons(parent, "part", request.user, building)
            hierarchy_list +="</li>"
        hierarchy_list +="</ul>"
    hierarchy_list +="</li></ul>"
    template_vars = dict(hierarchy=hierarchy_list)
    template_vars_template = RequestContext(request, template_vars)

    return render_to_response("consumption_centers/choose_hierarchy.html", template_vars_template)


def get_total_consumer_unit(consumerUnit, total):
    """gets the (physical)sons of a cu"""
    c_units = []
    if not total:

        if consumerUnit.part_of_building:
            #es el consumer_unit de una parte de un edificio, saco sus hijos
            leafs = HierarchyOfPart.objects.filter(part_of_building_composite =
                                                   consumerUnit.part_of_building)

        else:
            #es un consumer unit de algún electric device, saco sus hijos
            leafs = HierarchyOfPart.objects.filter(consumer_unit_composite = consumerUnit)


        for leaf in leafs:
            if leaf.part_of_building_leaf:
                leaf_cu = ConsumerUnit.objects.get(part_of_building=leaf.part_of_building_leaf)
            else:
                leaf_cu = leaf.consumer_unit_leaf
            if leaf.ExistsPowermeter:
                c_units.append(leaf_cu)
            else:
                c_units_leaf=get_total_consumer_unit(leaf_cu, False)
                c_units.extend(c_units_leaf)
        return c_units
    else:
        hierarchy = HierarchyOfPart.objects.filter(Q(part_of_building_composite__building=
                                                    consumerUnit.building)
                                                   |Q(consumer_unit_composite__building=
                                                    consumerUnit.building))
        ids_hierarchy = [] #arreglo donde guardo los hijos
        ids_hierarchy_cu = [] #arreglo donde guardo los hijos (consumerunits)
        for hy in hierarchy:
            if hy.part_of_building_leaf:
                ids_hierarchy.append(hy.part_of_building_leaf.pk)
            if hy.consumer_unit_leaf:
                ids_hierarchy_cu.append(hy.consumer_unit_leaf.pk)

        #sacar los padres(partes de edificios y consumerUnits que no son hijos de nadie)
        parents = PartOfBuilding.objects.filter(building=consumerUnit.building).exclude(
                                                                        pk__in=ids_hierarchy)

        for parent in parents:
            par_cu=ConsumerUnit.objects.get(part_of_building=parent)
            if par_cu.profile_powermeter.powermeter.powermeter_anotation == "Medidor Virtual":
                c_units_leaf=get_total_consumer_unit(par_cu, False)
                c_units.extend(c_units_leaf)
            else:
                c_units.append(par_cu)
    return c_units



def get_consumer_units(consumerUnit):
    """ Gets an array of consumer units which sum equals the given consumerUnit"""
    if consumerUnit.profile_powermeter.powermeter.powermeter_anotation == "Medidor Virtual":
        if consumerUnit.electric_device_type.electric_device_type_name == "Total Edificio":
            total = True
        else:
            total = False
        c_units = get_total_consumer_unit(consumerUnit, total)
    else:
        c_units = [consumerUnit]
    return c_units


def allowed_cu(consumerUnit, user, building):
    """returns true or false if the user has permission over the consumerUnit or not
    consumerUnit = ConsumerUnit instance
    user = auth.User instance
    building = Building instance
    """
    if consumerUnit.electric_device_type.electric_device_type_name == "Total Edificio":
        context = DataContextPermission.objects.filter(user_role__user=user, building=building, part_of_building=None)
        if context:
            return True
        else:
            return False
    else:
        context = DataContextPermission.objects.filter(user_role__user=user, building=building)
        for cntx in context:
            if cntx.part_of_building:
                #if the user has permission over a part of building, and the consumer unit is
                #the cu for the part of building
                if consumerUnit.part_of_building == cntx.part_of_building:
                    return True
                elif is_in_part_of_building(consumerUnit, cntx.part_of_building):
                    return True
            elif cntx.building == consumerUnit.building:
                return True
        return False

def is_in_part_of_building(consumerUnit, part_of_building):
    """ checks if consumerUnit is part of the part_of_building
    returns True if consumerUnit is inside the part
    consumerUnit = ConsumerUnit instance *without part_of_building*
    part_of_building = PartOfBuilding instance
    """
    part_parent = HierarchyOfPart.objects.filter(part_of_building_composite=part_of_building)
    if part_parent:
        for parent_part in part_parent:
            if parent_part.consumer_unit_leaf:
                if parent_part.consumer_unit_leaf == consumerUnit:
                    return True
                else:
                    if is_in_consumer_unit(consumerUnit, parent_part.consumer_unit_leaf):
                        return True
            else:
                if parent_part.part_of_building_leaf == consumerUnit.part_of_building:
                    return True
                elif is_in_part_of_building(consumerUnit, parent_part.part_of_building_leaf):
                    return True
        return False
    else:
        return False

def is_in_consumer_unit(cunit, cuParent):
    """ checks if consumerUnit is part of an electric system (another consumer unit)
    returns True if consumerUnit is inside the system
    cunit = ConsumerUnit instance *without part_of_building*
    cuParent = ConsumerUnit instance
    """
    part_parent = HierarchyOfPart.objects.filter(consumer_unit_composite=cuParent)
    if part_parent:
        for parent_part in part_parent:
            if parent_part.consumer_unit_leaf == cunit:
                return True
            else:
                if is_in_consumer_unit(cunit, parent_part.consumer_unit_leaf):
                    return True
        return False
    else:
        return False


def graphs_permission(user, consumer_unit):
    """ Checks what kind of graphs can a user see for a consumer_unit
    user.- django auth user object
    consumer_unit.- ConsumerUnit object

    returns an array of objects of permission, False if user is not allowed to see graphs

    """
    operation = Operation.objects.get(operation_name="Ver")

    context = DataContextPermission.objects.filter(user_role__user=user,
        building=consumer_unit.building)
    contextos = []
    for cntx in context:
        if cntx.part_of_building:
            #if the user has permission over a part of building, and the consumer unit is
            #the cu for the part of building
            if consumer_unit.part_of_building == cntx.part_of_building:
                contextos.append(cntx)
            elif is_in_part_of_building(consumer_unit, cntx.part_of_building):
                contextos.append(cntx)
        elif cntx.building == consumer_unit.building:
            contextos.append(cntx)
    user_roles = [cntx.user_role.pk for cntx in contextos]

    user_role = UserRole.objects.filter(user=user, pk__in=user_roles)

    graphs = []
    for u_role in user_role:
        for object in GRAPHS:
            ob = Object.objects.get(object_name=object)
            permission = PermissionAsigment.objects.filter(object=ob, role=u_role.role,
                operation=operation)
            if permission or user.is_superuser:
                graphs.append(ob)
    if graphs:
        return graphs
    else:
        return False


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

    graphs = graphs_permission(request.user, request.session['consumer_unit'])

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
    if has_permission(request.user, VIEW, "Consultar recibo CFE") or request.user.is_superuser:
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
    if has_permission(request.user, VIEW, "Consultar recibo CFE") or request.user.is_superuser:
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

def grafica_datoscsv(request):
    f1_init, f1_end = get_intervals_1(request.GET)
    buildings = []
    profile=request.session['consumer_unit'].profile_powermeter
    for key in request.GET:
        if re.search('^building\d+', key):
            building = get_object_or_404(Building, pk=int(request.GET[key]))
            buildings.append(building)
    if buildings:
        data=simplejson.loads(get_json_data(buildings, f1_init, f1_end, request.GET['graph'],profile))
        parameter_type = request.GET['graph']
        building = request.session['main_building'].building_name
        c_u = request.session['consumer_unit'].electric_device_type.electric_device_type_name


        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename="datos_'+ parameter_type +'.csv"'

        writer = csv.writer(response)
        for dato in data:
            datostr = str(dato['meditions']).replace("[u'", "")
            datostr = datostr.replace("']", '')+parameter_type
            date = str(dato['labels']).replace("[u'", "")
            date = date.replace("-05:00']", '')
            writer.writerow([building, c_u, datostr, date])

        return response


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
    first_day_of_month = datetime.datetime(year=year, month=month, day=1)
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
    if has_permission(request.user, CREATE, "Alta de atributos de edificios") or request.user.is_superuser:
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
                if has_permission(request.user, VIEW, "Ver atributos de edificios") or request.user.is_superuser:
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
    if has_permission(request.user, VIEW, "Ver atributos de edificios") or request.user.is_superuser:
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
    if has_permission(request.user, DELETE, "Eliminar atributos de edificios") or request.user.is_superuser:
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
    if has_permission(request.user, VIEW, "Ver atributos de edificios") or request.user.is_superuser:
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
                if has_permission(request.user, VIEW, "Ver atributos de edificios") or request.user.is_superuser:
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
    if has_permission(request.user, VIEW, "Ver atributos de edificios") or request.user.is_superuser:
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
    if has_permission(request.user, CREATE, "Alta de clusters") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        #Se obtienen los sectores
        sectores = SectoralType.objects.all()
        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            sectores=sectores,
            company=request.session['company']
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

            if has_permission(request.user, VIEW, "Ver clusters") or request.user.is_superuser:
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
    if has_permission(request.user, VIEW, "Ver cluster de empresas") or request.user.is_superuser:
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
            datacontext=datacontext, empresa=empresa, company=request.session['company'])
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
    if has_permission(request.user, DELETE, "Baja de clusters") or request.user.is_superuser:
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
    if has_permission(request.user, DELETE, "Baja de clusters") or request.user.is_superuser:
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
    if has_permission(request.user, UPDATE, "Modificar cluster de empresas") or request.user.is_superuser:
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
                if has_permission(request.user, VIEW, "Ver cluster de empresas") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/clusters?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            sectores=sectores,
            post=post,
            operation="edit",
            message=message,
            type=type,
            company=request.session['company']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_cluster.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def see_cluster(request, id_cluster):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver cluster de empresas") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        cluster = Cluster.objects.get(pk = id_cluster)
        cluster_companies = ClusterCompany.objects.filter(cluster=cluster)

        template_vars = dict(
            datacontext=datacontext,
            cluster = cluster,
            cluster_companies = cluster_companies,
            empresa=empresa,
            company=request.session['company']
        )

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
    if has_permission(request.user, CREATE, "Alta de modelos de medidores eléctricos") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=request.session['company']
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

            if has_permission(request.user, VIEW, "Ver modelos de medidores eléctricos") or request.user.is_superuser:
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
    if has_permission(request.user, UPDATE, "Modificar modelos de medidores eléctricos") or request.user.is_superuser:
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
                if has_permission(request.user, VIEW, "Ver modelos de medidores eléctricos") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/modelos_medidor?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            post=post,
            operation="edit",
            message=message,
            type=type,
            company=request.session['company']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_powermetermodel.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_powermetermodels(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver modelos de medidores eléctricos") or request.user.is_superuser:
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
    if has_permission(request.user, DELETE, "Baja de clusters") or request.user.is_superuser:
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
    if has_permission(request.user, DELETE, "Baja de clusters") or request.user.is_superuser:
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
    if has_permission(request.user, CREATE, "Alta de medidor electrico") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        post = ''
        pw_models_list = PowermeterModel.objects.all().order_by("powermeter_brand")
        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            modelos=pw_models_list,
            post=post,
            company=request.session['company']
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

                if has_permission(request.user, VIEW, "Ver medidores eléctricos") or request.user.is_superuser:
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
    if has_permission(request.user, UPDATE, "Modificar medidores eléctricos") or request.user.is_superuser:
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
                if has_permission(request.user, VIEW, "Ver medidores eléctricos") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/medidores?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            post=post,
            modelos = pw_models_list,
            operation="edit",
            message=message,
            type=type,
            company=request.session['company']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_powermeter.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_powermeter(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver medidores eléctricos") or request.user.is_superuser:
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
            datacontext=datacontext, empresa=empresa, company=request.session['company'])
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
    if has_permission(request.user, DELETE, "Baja de medidores eléctricos") or request.user.is_superuser:
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
    if has_permission(request.user, DELETE, "Baja de medidores eléctricos") or request.user.is_superuser:
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
    if has_permission(request.user, UPDATE, "Modificar medidores eléctricos") or request.user.is_superuser:
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
    if has_permission(request.user, VIEW, "Ver medidores eléctricos") or request.user.is_superuser:
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
            empresa=empresa,
            company=request.session['company']
        )

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
    if has_permission(request.user, CREATE, "Alta de dispositivos y sistemas eléctricos") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        post = ''

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            post=post,
            company=request.session['company']
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

                if has_permission(request.user, VIEW, "Ver medidores eléctricos") or request.user.is_superuser:
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
    if has_permission(request.user, UPDATE, "Modificar dispositivos y sistemas eléctricos") or request.user.is_superuser:
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
                if has_permission(request.user, VIEW, "Ver dispositivos y sistemas eléctricos") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/tipos_equipo_electrico?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            post=post,
            operation="edit",
            message=message,
            type=type,
            company=request.session['company']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_electricdevicetype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_electric_device_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver dispositivos y sistemas eléctricos") or request.user.is_superuser:
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
            datacontext=datacontext, empresa=empresa, company=request.session['company'])
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
    if has_permission(request.user, DELETE, "Baja de dispositivos y sistemas eléctricos") or request.user.is_superuser:
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
    if has_permission(request.user, DELETE, "Baja de dispositivos y sistemas eléctricos") or request.user.is_superuser:
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
    if has_permission(request.user, UPDATE, "Modificar dispositivos y sistemas eléctricos") or request.user.is_superuser:
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
    if has_permission(request.user, CREATE, "Alta compañía") or request.user.is_superuser:
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
            company=request.session['company']
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

                if has_permission(request.user, VIEW, "Ver empresas") or request.user.is_superuser:
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
    if has_permission(request.user, UPDATE, "Modificar empresas") or request.user.is_superuser:
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
                if has_permission(request.user, VIEW, "Ver empresas") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/empresas?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=request.session['company'],
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
    if has_permission(request.user, VIEW, "Ver empresas") or request.user.is_superuser:
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
            datacontext=datacontext, empresa=empresa, company=request.session['company'])
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
    if has_permission(request.user, DELETE, "Baja de empresas") or request.user.is_superuser:
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
    if has_permission(request.user, DELETE, "Baja de empresas") or request.user.is_superuser:
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
    if has_permission(request.user, UPDATE, "Modificar empresas") or request.user.is_superuser:
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
    if has_permission(request.user, VIEW, "Ver empresas") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        company_cluster_objs = ClusterCompany.objects.filter(company__pk = id_cpy)
        company = company_cluster_objs[0]

        template_vars = dict(
            datacontext=datacontext,
            companies = company,
            company = request.session['company'],
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



def c_center_structures(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver empresas") or request.user.is_superuser:

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        clustersObjs = Cluster.objects.all()
        visualizacion = "<div class='hierarchy_container'>"
        for clst in clustersObjs:
            visualizacion += "<div class='hrchy_cluster'><span class='hrchy_cluster_label'>"+clst.cluster_name+"</span>"
            companiesObjs = ClusterCompany.objects.filter(cluster = clst)
            visualizacion += "<div>"
            for comp in companiesObjs:
                visualizacion += "<div class='hrchy_company'><span class='hrchy_company_label'>"+comp.company.company_name+"</span>"
                buildingsObjs = CompanyBuilding.objects.filter(company = comp)
                if buildingsObjs:
                    visualizacion += "<div>"
                    for bld in buildingsObjs:
                        visualizacion += "<div class='hrchy_building'><span> - Edificio: " + bld.building.building_name + "</span></div>"
                    visualizacion += "</div>"
                visualizacion += "</div>"
            visualizacion += "</div>"
            visualizacion += "</div>"
        visualizacion += "</div>"


        template_vars = dict(
            datacontext=datacontext,
            visualizacion = visualizacion,
            empresa=empresa, company=request.session['company'])

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/c_centers_structure.html", template_vars_template)

    else:
        return render_to_response("generic_error.html", RequestContext(request))


"""
Building Type
"""


def add_buildingtype(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta de tipos de edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''


        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            btype_name = request.POST.get('btype_name')
            btype_description = request.POST.get('btype_description')

            continuar = True
            if btype_name == '':
                message = "El nombre del tipo de edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'btype_name': btype_name, 'btype_description':btype_description}

            if continuar:

                newBuildingType = BuildingType(
                    building_type_name = btype_name,
                    building_type_description = btype_description
                )
                newBuildingType.save()

                template_vars["message"] = "Tipo de Edificio creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW, "Ver empresas") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/tipos_edificios?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_buildingtype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def edit_buildingtype(request, id_btype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar tipo de edificio") or request.user.is_superuser:

        building_type = BuildingType.objects.get(id = id_btype)

        post = {'btype_name': building_type.building_type_name, 'btype_description':building_type.building_type_description}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        type = ''

        if request.method == "POST":
            post = request.POST
            btype_name = request.POST.get('btype_name')
            btype_description = request.POST.get('btype_description')

            continuar = True
            if btype_name == '':
                message = "El nombre del tipo de edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'btype_name': btype_name, 'btype_description':btype_description}

            if continuar:
                building_type.building_type_name = btype_name
                building_type.building_type_description = btype_description
                building_type.save()

                message = "Tipo de Edificio editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW, "Ver tipos de edificios") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/tipos_edificios?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            operation="edit",
            message=message,
            type=type
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_buildingtype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_buildingtypes(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver tipos de edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']

        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_description = 'asc'
        order_status = 'asc'
        order = "building_type_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-building_type_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_description" in request.GET:
                if request.GET["order_description"] == "asc":
                    order = "building_type_description"
                    order_description = "desc"
                else:
                    order = "-building_type_description"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "building_type_status"
                    order_status = "desc"
                else:
                    order = "-building_type_status"
                    order_status = "asc"

        if search:
            lista = BuildingType.objects.filter(Q(building_type_name__icontains=request.GET['search'])|Q(
                building_type_description__icontains=request.GET['search'])).exclude(building_type_status = 2).order_by(order)

        else:
            lista = BuildingType.objects.all().exclude(building_type_status = 2).order_by(order)

        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_description=order_description, order_status=order_status,
            datacontext=datacontext, empresa=empresa, company=company)
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
        return render_to_response("consumption_centers/buildings/buildingtype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_buildingtype(request, id_btype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de tipos de edificios") or request.user.is_superuser:
        btype_obj = get_object_or_404(BuildingType, pk = id_btype)
        btype_obj.building_type_status = 2
        btype_obj.save()

        mensaje = "El tipo de edificio ha sido dado de baja correctamente"
        type="n_success"

        return HttpResponseRedirect("/buildings/tipos_edificios/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_batch_buildingtypes(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de tipos de edificios") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^btype_\w+', key):
                    r_id = int(key.replace("btype_",""))
                    btype_obj = get_object_or_404(BuildingType, pk = r_id)
                    btype_obj.building_type_status = 2
                    btype_obj.save()

            mensaje = "Los tipos de edificios han sido dados de baja correctamente"
            return HttpResponseRedirect("/buildings/tipos_edificios/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/tipos_edificios/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def status_buildingtype(request, id_btype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar tipo de edificio") or request.user.is_superuser:
        building_type = get_object_or_404(BuildingType, pk = id_btype)
        if building_type.building_type_status == 0:
            building_type.building_type_status = 1
            str_status = "Activo"
        elif building_type.building_type_status == 1:
            building_type.building_type_status = 0
            str_status = "Activo"

        building_type.save()
        mensaje = "El estatus del tipo de edificio " + building_type.building_type_name +" ha cambiado a "+str_status
        type="n_success"

        return HttpResponseRedirect("/buildings/tipos_edificios/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))



"""
Sectoral Type
"""


def add_sectoraltype(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta de sectores") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            stype_name = request.POST.get('stype_name')
            stype_description = request.POST.get('stype_description')

            continuar = True
            if stype_name == '':
                message = "El nombre del tipo de sector no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'stype_name': stype_name, 'stype_description':stype_description}

            if continuar:

                newSectoralType = SectoralType(
                    sectorial_type_name = stype_name,
                    sectoral_type_description = stype_description
                )
                newSectoralType.save()

                template_vars["message"] = "Tipo de Sector creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW, "Ver tipos de sectores") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/tipos_sectores?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_sectoraltype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def edit_sectoraltype(request, id_stype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar tipos de sectores") or request.user.is_superuser:

        sectoral_type = SectoralType.objects.get(id = id_stype)

        post = {'stype_name': sectoral_type.sectorial_type_name, 'stype_description': sectoral_type.sectoral_type_description}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        type = ''

        if request.method == "POST":
            post = request.POST
            stype_name = request.POST.get('stype_name')
            stype_description = request.POST.get('stype_description')

            continuar = True
            if stype_name == '':
                message = "El nombre del tipo de sector no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'stype_name': stype_name, 'stype_description':stype_description}

            if continuar:
                sectoral_type.sectorial_type_name = stype_name
                sectoral_type.sectoral_type_description = stype_description
                sectoral_type.save()

                message = "Tipo de Sector editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW, "Ver tipos de sectores") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/tipos_sectores?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            operation="edit",
            message=message,
            type=type
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_sectoraltype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_sectoraltypes(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver tipos de sectores") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']

        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_description = 'asc'
        order_status = 'asc'
        order = "sectorial_type_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-sectorial_type_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_description" in request.GET:
                if request.GET["order_description"] == "asc":
                    order = "sectoral_type_description"
                    order_description = "desc"
                else:
                    order = "-sectoral_type_description"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "sectoral_type_status"
                    order_status = "desc"
                else:
                    order = "-sectoral_type_status"
                    order_status = "asc"

        if search:
            lista = SectoralType.objects.filter(Q(sectorial_type_name__icontains=request.GET['search'])|Q(
                sectoral_type_description__icontains=request.GET['search'])).exclude(sectoral_type_status = 2).order_by(order)
        else:
            lista = SectoralType.objects.all().exclude(sectoral_type_status = 2).order_by(order)

        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_description=order_description, order_status=order_status,
            datacontext=datacontext, empresa=empresa, company=company)
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
        return render_to_response("consumption_centers/buildings/sectoraltype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_sectoraltype(request, id_stype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de tipos de sectores") or request.user.is_superuser:
        stype_obj = get_object_or_404(SectoralType, pk = id_stype)
        stype_obj.sectoral_type_status = 2
        stype_obj.save()

        mensaje = "El tipo de sector ha sido dado de baja correctamente"
        type="n_success"

        return HttpResponseRedirect("/buildings/tipos_sectores/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_batch_sectoraltypes(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de tipos de sectores") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^stype_\w+', key):
                    r_id = int(key.replace("stype_",""))
                    stype_obj = get_object_or_404(SectoralType, pk = r_id)
                    stype_obj.sectoral_type_status = 2
                    stype_obj.save()

            mensaje = "Los tipos de sectores han sido dados de baja correctamente"
            return HttpResponseRedirect("/buildings/tipos_sectores/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/tipos_sectores/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def status_sectoraltype(request, id_stype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar tipos de sectores") or request.user.is_superuser:
        sectoral_type = get_object_or_404(SectoralType, pk = id_stype)
        if sectoral_type.sectoral_type_status == 0:
            sectoral_type.sectoral_type_status = 1
            str_status = "Activo"
        elif sectoral_type.sectoral_type_status == 1:
            sectoral_type.sectoral_type_status = 0
            str_status = "Activo"

        sectoral_type.save()
        mensaje = "El estatus del sector " + sectoral_type.sectorial_type_name +" ha cambiado a "+str_status
        type="n_success"

        return HttpResponseRedirect("/buildings/tipos_sectores/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))




"""
Building Attributes Type
"""


def add_b_attributes_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta de tipos de atributos de edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            b_attr_type_name = request.POST.get('b_attr_type_name')
            b_attr_type_description = request.POST.get('b_attr_type_description')

            continuar = True
            if b_attr_type_name == '':
                message = "El nombre del tipo de atributo no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'stype_name': b_attr_type_name, 'stype_description':b_attr_type_description}

            if continuar:

                newBuildingAttrType = BuildingAttributesType(
                    building_attributes_type_name = b_attr_type_name,
                    building_attributes_type_description = b_attr_type_description
                )
                newBuildingAttrType.save()

                template_vars["message"] = "Tipo de Atributo de Edificio creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW, "Ver tipos de atributos") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/tipos_atributos_edificios?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_buildingattributetype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def edit_b_attributes_type(request, id_batype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar tipos de atributos de edificios") or request.user.is_superuser:

        b_attr_typeObj = BuildingAttributesType.objects.get(id = id_batype)

        post = {'batype_name': b_attr_typeObj.building_attributes_type_name, 'batype_description':b_attr_typeObj.building_attributes_type_description}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        type = ''

        if request.method == "POST":
            post = request.POST
            b_attr_type_name = request.POST.get('b_attr_type_name')
            b_attr_type_description = request.POST.get('b_attr_type_description')

            continuar = True
            if b_attr_type_name == '':
                message = "El nombre del tipo de atributo no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'batype_name':b_attr_type_name , 'batype_description':b_attr_type_description }

            if continuar:
                b_attr_typeObj.building_attributes_type_name = b_attr_type_name
                b_attr_typeObj.building_attributes_type_description = b_attr_type_description
                b_attr_typeObj.save()

                message = "Tipo de Atributo de Edificio editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW, "Ver tipos de atributos") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/tipos_atributos_edificios?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            operation="edit",
            message=message,
            type=type
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_buildingattributetype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_b_attributes_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver tipos de atributos") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']

        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_description = 'asc'
        order = "building_attributes_type_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-building_attributes_type_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_description" in request.GET:
                if request.GET["order_description"] == "asc":
                    order = "building_attributes_type_description"
                    order_description = "desc"
                else:
                    order = "-building_attributes_type_description"

        if search:
            lista = BuildingAttributesType.objects.filter(Q(building_attributes_type_name__icontains=request.GET['search'])|Q(
                building_attributes_type_description__icontains=request.GET['search'])).\
                exclude(building_attributes_type_status = 2).order_by(order)
        else:
            lista = BuildingAttributesType.objects.all().exclude(building_attributes_type_status = 2).order_by(order)

        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_description=order_description,
            datacontext=datacontext, empresa=empresa, company=company)
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
        return render_to_response("consumption_centers/buildings/buildingattributetype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))



"""
Part of Building Type
"""


def add_partbuildingtype(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta de tipos de partes de edificio") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            b_part_type_name = request.POST.get('b_part_type_name')
            b_part_type_description = request.POST.get('b_part_type_description')

            continuar = True
            if b_part_type_name == '':
                message = "El nombre del Tipo de Parte de Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'b_part_type_name': b_part_type_name, 'b_part_type_description':b_part_type_description}

            if continuar:

                newPartBuildingType = PartOfBuildingType(
                    part_of_building_type_name = b_part_type_name,
                    part_of_building_type_description = b_part_type_description
                )
                newPartBuildingType.save()

                template_vars["message"] = "Tipo de Parte de Edificio creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW, "Ver tipos de partes de un edificio") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/tipos_partes_edificio?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_partbuilding_type.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def edit_partbuildingtype(request, id_pbtype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar tipos de atributos de edificios") or request.user.is_superuser:

        building_part_type = PartOfBuildingType.objects.get(id=id_pbtype)

        post = {'b_part_type_name': building_part_type.part_of_building_type_name, 'b_part_type_description': building_part_type.part_of_building_type_description}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        type = ''

        if request.method == "POST":
            post = request.POST
            b_part_type_name = request.POST.get('b_part_type_name')
            b_part_type_description = request.POST.get('b_part_type_description')

            continuar = True
            if b_part_type_name == '':
                message = "El nombre del Tipo de Parte de Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False

            post = {'b_part_type_name': building_part_type.part_of_building_type_name, 'b_part_type_description': building_part_type.part_of_building_type_description}

            if continuar:
                building_part_type.part_of_building_type_name = b_part_type_name
                building_part_type.part_of_building_type_description = b_part_type_description
                building_part_type.save()

                message = "Tipo de Parte de Edificio editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW, "Ver tipos de partes de un edificio") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/tipos_partes_edificio?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            operation="edit",
            message=message,
            type=type
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_partbuilding_type.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_partbuildingtype(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver tipos de partes de un edificio") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']

        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_description = 'asc'
        order_status = 'asc'
        order = "part_of_building_type_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-part_of_building_type_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_description" in request.GET:
                if request.GET["order_description"] == "asc":
                    order = "part_of_building_type_description"
                    order_description = "desc"
                else:
                    order = "-part_of_building_type_description"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "part_of_building_type_status"
                    order_status = "desc"
                else:
                    order = "-part_of_building_type_status"
                    order_status = "asc"

        if search:
            lista = PartOfBuildingType.objects.filter(Q(part_of_building_type_name__icontains=request.GET['search'])|Q(
                part_of_building_type_description__icontains=request.GET['search'])).exclude(part_of_building_type_status = 2).\
                order_by(order)
        else:
            lista = PartOfBuildingType.objects.all().exclude(part_of_building_type_status = 2).order_by(order)

        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_description=order_description, order_status=order_status,
            datacontext=datacontext, empresa=empresa, company=company)
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
        return render_to_response("consumption_centers/buildings/partofbuildingtype.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_partbuildingtype(request, id_pbtype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de tipos de partes de edificios") or request.user.is_superuser:

        part_building_type = get_object_or_404(PartOfBuildingType, pk=id_pbtype)
        part_building_type.part_of_building_type_status = 2
        part_building_type.save()

        mensaje = "El Tipo de Parte de Edificio ha sido dado de baja correctamente"
        type="n_success"

        return HttpResponseRedirect("/buildings/tipos_partes_edificio/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_batch_partbuildingtype(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de tipos de partes de edificios") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^pb_type_\w+', key):
                    r_id = int(key.replace("pb_type_",""))
                    part_building_type = get_object_or_404(PartOfBuildingType, pk=r_id)
                    part_building_type.part_of_building_type_status = 2
                    part_building_type.save()

            mensaje = "Los Tipos de Partes de Edificio han sido dados de baja correctamente"
            return HttpResponseRedirect("/buildings/tipos_partes_edificio/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/tipos_partes_edificio/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def status_partbuildingtype(request, id_pbtype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar tipos de atributos de edificios") or request.user.is_superuser:
        part_building_type = get_object_or_404(PartOfBuildingType, pk = id_pbtype)

        if part_building_type.part_of_building_type_status == 0:
            part_building_type.part_of_building_type_status = 1
            str_status = "Activo"
        elif part_building_type.part_of_building_type_status == 1:
            part_building_type.part_of_building_type_status = 0
            str_status = "Activo"
        part_building_type.save()

        mensaje = "El estatus del tipo de edificio " + part_building_type.part_of_building_type_name +" ha cambiado a "+str_status
        type="n_success"

        return HttpResponseRedirect("/buildings/tipos_partes_edificio/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))





"""
Part of Building
"""


def add_partbuilding(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta de partes de edificio") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        #Se obtienen los tipos de partes de edificios
        tipos_parte = PartOfBuildingType.objects.all().exclude(part_of_building_type_status = 2).order_by('part_of_building_type_name')

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.all().exclude(building_attributes_type_status = 2).order_by('building_attributes_type_name')

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            tipos_parte=tipos_parte,
            tipos_atributos=tipos_atributos,
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            b_part_name = request.POST.get('b_part_name')
            b_part_description = request.POST.get('b_part_description')
            b_part_type_id = request.POST.get('b_part_type')
            b_part_building_name = request.POST.get('b_building_name')
            b_part_building_id = request.POST.get('b_building_id')
            b_part_mt2 = request.POST.get('b_part_mt2')

            continuar = True
            if b_part_name == '':
                message = "El nombre de la Parte de Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False

            if b_part_type_id == '':
                message = "Se debe seleccionar un tipo de parte de edificio"
                type = "n_notif"
                continuar = False

            if b_part_building_id == '':
                message = "Se debe seleccionar un edificio ya registrado"
                type = "n_notif"
                continuar = False

            post = {'b_part_name': b_part_name, 'b_part_description':b_part_description, 'b_part_building_name': b_part_building_name, 'b_part_building_id': b_part_building_id, 'b_part_type':b_part_type_id ,'b_part_mt2':b_part_mt2}

            if continuar:

                #Se obtiene la instancia del edificio
                buildingObj = get_object_or_404(Building, pk=b_part_building_id)

                #Se obtiene la instancia del tipo de parte de edificio
                part_building_type_obj = get_object_or_404(PartOfBuildingType, pk=b_part_type_id)


                newPartBuilding = PartOfBuilding(
                    building = buildingObj,
                    part_of_building_type = part_building_type_obj,
                    part_of_building_name = b_part_name,
                    part_of_building_description = b_part_description,
                    mts2_built = b_part_mt2
                )
                newPartBuilding.save()

                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')

                        #Se obtiene el objeto tipo de atributo
                        attribute_type_obj = BuildingAttributesType.objects.get(pk = atr_value_arr[0])

                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(pk = atr_value_arr[1])

                        newBldPartAtt = BuilAttrsForPartOfBuil(
                            part_of_building = newPartBuilding,
                            building_attributes = attribute_obj,
                            building_attributes_value = atr_value_arr[2]
                        )
                        newBldPartAtt.save()


                template_vars["message"] = "Parte de Edificio creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW, "Ver partes de un edificio") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/partes_edificio?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_partbuilding.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def edit_partbuilding(request, id_bpart):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar partes de un edificio") or request.user.is_superuser:

        #Se obtienen los tipos de partes de edificios
        tipos_parte = PartOfBuildingType.objects.all().exclude(part_of_building_type_status = 2).order_by('part_of_building_type_name')

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.all().exclude(building_attributes_type_status = 2).order_by('building_attributes_type_name')

        building_part = get_object_or_404(PartOfBuilding, pk=id_bpart)


        #Se obtienen todos los atributos
        building_part_attributes = BuilAttrsForPartOfBuil.objects.filter(part_of_building = building_part)
        string_attributes = ''
        if building_part_attributes:
            for bp_att in building_part_attributes:

                string_attributes += '<div  class="extra_attributes_div"><span class="delete_attr_icon"><a href="#eliminar" class="delete hidden_icon" ' + \
                'title="eliminar atributo"></a></span>' + \
                '<span class="tip_attribute_part">' + \
                bp_att.building_attributes.building_attributes_type.building_attributes_type_name + \
                '</span>' + \
                '<span class="attribute_part">' +\
                bp_att.building_attributes.building_attributes_name + \
                '</span>'+ \
                '<span class="attribute_value_part">'+\
                str(bp_att.building_attributes_value) + \
                '</span>' + \
                '<input type="hidden" name="atributo_' + str(bp_att.building_attributes.building_attributes_type.pk) + \
                '_' +str(bp_att.building_attributes.pk) +'" ' + \
                'value="' + str(bp_att.building_attributes.building_attributes_type.pk) +','+ str(bp_att.building_attributes.pk) + ','+ str(bp_att.building_attributes_value) + \
                '"/></div>';

        post = {'b_part_name': building_part.part_of_building_name,
                'b_part_description':building_part.part_of_building_description,
                'b_part_building_name':building_part.building.building_name,
                'b_part_building_id':str(building_part.building.pk),
                'b_part_type':building_part.part_of_building_type.id,
                'b_part_mt2':building_part.mts2_built,
                'b_part_attributes':string_attributes,
        }

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        type = ''

        if request.method == "POST":
            post = request.POST

            b_part_name = request.POST.get('b_part_name')
            b_part_description = request.POST.get('b_part_description')
            b_part_type_id = request.POST.get('b_part_type')
            b_part_building_name = request.POST.get('b_building_name')
            b_part_building_id = request.POST.get('b_building_id')
            b_part_mt2 = request.POST.get('b_part_mt2')

            continuar = True
            if b_part_name == '':
                message = "El nombre de la Parte de Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False

            if b_part_type_id == '':
                message = "Se debe seleccionar un tipo de parte de edificio"
                type = "n_notif"
                continuar = False

            if b_part_building_id == '':
                message = "Se debe seleccionar un edificio"
                type = "n_notif"
                continuar = False

            post = {'b_part_name': b_part_name, 'b_part_description':b_part_description, 'b_part_building_name': b_part_building_name, 'b_part_building_id': b_part_building_id, 'b_part_type':b_part_type_id ,'b_part_mt2':b_part_mt2}


            if continuar:
                #Se obtiene la instancia del edificio
                buildingObj = get_object_or_404(Building, pk=b_part_building_id)

                #Se obtiene la instancia del tipo de parte de edificio
                part_building_type_obj = get_object_or_404(PartOfBuildingType, pk=b_part_type_id)

                building_part.building = buildingObj
                building_part.part_of_building_name = b_part_name
                building_part.part_of_building_description = b_part_description
                building_part.part_of_building_type = part_building_type_obj
                building_part.mts2_built = b_part_mt2
                building_part.save()

                #Se eliminan todos los atributos existentes
                builAttrsElim = BuilAttrsForPartOfBuil.objects.filter(part_of_building = building_part)
                builAttrsElim.delete()

                #Se insertan los nuevos
                for key in request.POST:
                    if re.search('^atributo_\w+', key):

                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')

                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(pk = atr_value_arr[1])

                        newBldPartAtt = BuilAttrsForPartOfBuil(
                            part_of_building = building_part,
                            building_attributes = attribute_obj,
                            building_attributes_value = atr_value_arr[2]
                        )
                        newBldPartAtt.save()

                message = "Parte de Edificio editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW, "Ver partes de un edificio") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/partes_edificio?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            tipos_parte=tipos_parte,
            tipos_atributos=tipos_atributos,
            operation="edit",
            message=message,
            type=type
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_partbuilding.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def view_partbuilding(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver partes de un edificio") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']

        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_type = 'asc'
        order_building = 'asc'
        order = "part_of_building_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-part_of_building_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_type" in request.GET:
                if request.GET["order_type"] == "asc":
                    order = "part_of_building_type__part_of_building_type_name"
                    order_type = "desc"
                else:
                    order = "-part_of_building_type__part_of_building_type_name"

            if "order_building" in request.GET:
                if request.GET["order_building"] == "asc":
                    order = "building__building_name"
                    order_building = "desc"
                else:
                    order = "-building__building_name"
                    order_building = "asc"

        if search:
            lista = PartOfBuilding.objects.filter(Q(part_of_building_name__icontains=request.GET['search'])|Q(
                part_of_building_type__part_of_building_type_name__icontains=request.GET['search'])|Q(
                building__building_name__icontains=request.GET['search'])).order_by(order)
        else:
            lista = PartOfBuilding.objects.all().order_by(order)

        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_type=order_type, order_building=order_building,
            datacontext=datacontext, empresa=empresa, company=company)
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
        return render_to_response("consumption_centers/buildings/partofbuilding.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def search_buildings(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if "term" in request.GET:
        term = request.GET['term']
        buildings = Building.objects.filter(Q(building_name__icontains=term))
        buildings_arr = []
        for building in buildings:
            buildings_arr.append(dict(value=building.building_name, pk=building.pk, label=building.building_name))

        data=simplejson.dumps(buildings_arr)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def get_select_attributes(request, id_attribute_type):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    print "ID Att:", id_attribute_type

    building_attributes = BuildingAttributes.objects.filter(building_attributes_type__pk = id_attribute_type)
    string_to_return=''
    if building_attributes:
        for b_attr in building_attributes:
            string_to_return += """<li rel="%s">
                                    %s
                                </li>""" % (b_attr.pk, b_attr.building_attributes_name)
    else:
        string_to_return='<li rel="">Sin atributos</li>'

    return HttpResponse(content=string_to_return, content_type="text/html")


"""
EDIFICIOS
"""

def location_objects(country_id, country_name, state_id, state_name, municipality_id,municipality_name,neighborhood_id,neighborhood_name,street_id,street_name):
    #Se obtiene el objeto de Pais, sino esta Pais, se da de alta un pais nuevo.
    if country_id:
        countryObj = get_object_or_404(Pais, pk=country_id)
    else:
        countryObj = Pais(
            pais_name = country_name
        )
        countryObj.save()

    #Se obtiene el objeto de Estado, sino esta Estado, se da de alta un estado nuevo.
    if state_id:
        stateObj = get_object_or_404(Estado, pk=state_id)
    else:
        stateObj = Estado(
            estado_name = state_name
        )
        stateObj.save()

        #Se crea la relación Pais - Estado
        country_stateObj = PaisEstado(
            pais = countryObj,
            estado = stateObj,
        )
        country_stateObj.save()

    #Se obtiene el objeto de Municipio, sino esta Municipio, se da de alta un municipio nuevo.
    if municipality_id:
        municipalityObj = get_object_or_404(Municipio, pk=municipality_id)
    else:
        municipalityObj = Municipio(
            municipio_name = municipality_name
        )
        municipalityObj.save()

        #Se crea la relación Estado - Municipio
        state_munObj = EstadoMunicipio(
            estado = stateObj,
            municipio = municipalityObj,
        )
        country_stateObj.save()

    #Se obtiene el objeto de Colonia, sino esta Colonia, se da de alta una Colonia nueva.
    if neighborhood_id:
        neighborhoodObj = get_object_or_404(Colonia, pk=neighborhood_id)
    else:
        neighborhoodObj = Colonia(
            colonia_name = neighborhood_name
        )
        neighborhoodObj.save()

        #Se crea la relación Municipio - Colonia
        mun_neighObj = MunicipioColonia(
            municipio = municipalityObj,
            colonia = neighborhoodObj,
        )
        mun_neighObj.save()

    #Se obtiene el objeto de Calle, sino esta Calle, se da de alta una Calle nueva.
    if street_id:
        streetObj = get_object_or_404(Calle, pk=street_id)
    else:
        streetObj = Calle(
            calle_name = street_name
        )
        streetObj.save()

        #Se crea la relación Calle - Colonia
        neigh_streetObj = ColoniaCalle(
            colonia = neighborhoodObj,
            calle = streetObj,
        )
        neigh_streetObj.save()

    return countryObj, stateObj, municipalityObj, neighborhoodObj, streetObj



def add_building(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE, "Alta de edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        #Se obtienen las empresas
        empresas_lst = Company.objects.all().exclude(company_status=2).order_by('company_name')

        #Se obtienen las tarifas
        tarifas = ElectricRates.objects.all()

        #Se obtienen los tipos de edificios
        tipos_edificio_lst = BuildingType.objects.all().exclude(building_type_status = 2).order_by('building_type_name')

        #Se obtienen las regiones
        regiones_lst = Region.objects.all()

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.all().exclude(building_attributes_type_status = 2).order_by('building_attributes_type_name')


        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            empresas_lst=empresas_lst,
            tipos_edificio_lst=tipos_edificio_lst,
            tarifas=tarifas,
            regiones_lst=regiones_lst,
            tipos_atributos=tipos_atributos,
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            b_name = request.POST.get('b_name')
            b_description = request.POST.get('b_description')
            b_company = request.POST.get('b_company')
            b_type_arr = request.POST.getlist('b_type')
            b_mt2 = request.POST.get('b_mt2')
            b_electric_rate_id = request.POST.get('b_electric_rate')
            b_country_id = request.POST.get('b_country_id')
            b_state_id = request.POST.get('b_state_id')
            b_municipality_id = request.POST.get('b_municipality_id')
            b_neighborhood_id = request.POST.get('b_neighborhood_id')
            b_street_id = request.POST.get('b_street_id')
            b_ext = request.POST.get('b_ext')
            b_int = request.POST.get('b_int')
            b_zip = request.POST.get('b_zip')
            b_long = request.POST.get('b_longitude')
            b_lat = request.POST.get('b_latitude')
            b_region_id = request.POST.get('b_region')

            continuar = True
            if b_name == '':
                message = "El nombre del Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False

            if b_company == '':
                message += " - Se debe seleccionar una empresa"
                type = "n_notif"
                continuar = False

            if not b_type_arr:
                message += " - El edificio debe ser al menos de un tipo"
                type = "n_notif"
                continuar = False

            if b_electric_rate_id == '':
                message += " - Se debe seleccionar un tipo de tarifa"
                type = "n_notif"
                continuar = False

            if b_ext == '':
                message += " - El edificio debe tener un número exterior"
                type = "n_notif"
                continuar = False

            if b_zip == '':
                message += " - El edificio debe tener un código postal"
                type = "n_notif"
                continuar = False

            if b_long == '' and b_lat == '':
                message += " - Debes ubicar el edificio en el mapa"
                type = "n_notif"
                continuar = False

            if b_region_id == '':
                message += " - El edificio debe pertenecer a una región"
                type = "n_notif"
                continuar = False

            post = {
                'b_name':b_name,
                'b_description':b_description,
                'b_company':b_company,
                'b_type_arr':b_type_arr,
                'b_mt2':b_mt2,
                'b_electric_rate_id':b_electric_rate_id,
                'b_country_id':b_country_id,
                'b_state_id':b_state_id,
                'b_municipality_id':b_municipality_id,
                'b_neighborhood_id':b_neighborhood_id,
                'b_street_id':b_street_id,
                'b_ext':b_ext,
                'b_int':b_int,
                'b_zip':b_zip,
                'b_long':b_long,
                'b_lat':b_lat,
                'b_region_id':b_region_id
            }

            if continuar:

                #se obtiene el objeto de la tarifa
                tarifaObj = get_object_or_404(ElectricRates, pk=b_electric_rate_id)

                #Se obtiene la compañia
                companyObj = get_object_or_404(Company, pk=b_company)

                #Se obtiene el objeto de la region
                regionObj = get_object_or_404(Region, pk=b_region_id)

                countryObj, stateObj, municipalityObj, neighborhoodObj, streetObj = location_objects(b_country_id, request.POST.get('b_country'),
                    b_state_id, request.POST.get('b_state'), b_municipality_id, request.POST.get('b_municipality'), b_neighborhood_id, request.POST.get('b_neighborhood'),
                    b_street_id, request.POST.get('b_street'))

                #Se crea la cadena con la direccion concatenada
                formatted_address = streetObj.calle_name+" "+b_ext
                if b_int:
                    formatted_address += "-"+b_int
                formatted_address += " Colonia: "+ neighborhoodObj.colonia_name + " "+municipalityObj.municipio_name
                formatted_address += " " + stateObj.estado_name + " " + countryObj.pais_name +"C.P."+b_zip

                #Se da de alta el edificio
                newBuilding = Building(
                    building_name = b_name,
                    building_description = b_description,
                    building_formatted_address = formatted_address,
                    pais = countryObj,
                    estado = stateObj,
                    municipio = municipalityObj,
                    colonia = neighborhoodObj,
                    calle = streetObj,
                    region = regionObj,
                    building_external_number = b_ext,
                    building_internal_number = b_int,
                    building_code_zone = b_zip,
                    building_long_address = b_long,
                    building_lat_address = b_lat,
                    electric_rate = tarifaObj,
                    mts2_built = b_mt2,
                )
                newBuilding.save()

                #Se relaciona la compania con el edificio
                newBldComp = CompanyBuilding(
                    company = companyObj,
                    building = newBuilding,
                )
                newBldComp.save()

                #Se dan de alta los tipos de edificio
                for b_type in b_type_arr:
                    #Se obtiene el objeto del tipo de edificio
                    typeObj = get_object_or_404(BuildingType, pk=b_type)
                    newBuildingTypeBuilding = BuildingTypeForBuilding(
                        building = newBuilding,
                        building_type = typeObj,
                        building_type_for_building_name = newBuilding.building_name +" - " +typeObj.building_type_name
                    )
                    newBuildingTypeBuilding.save()


                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')

                        #Se obtiene el objeto tipo de atributo
                        attribute_type_obj = BuildingAttributesType.objects.get(pk = atr_value_arr[0])

                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(pk = atr_value_arr[1])

                        newBldAtt = BuildingAttributesForBuilding(
                            building = newBuilding,
                            building_attributes = attribute_obj,
                            building_attributes_value = atr_value_arr[2]
                        )
                        newBldAtt.save()

                template_vars["message"] = "Edificio creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW, "Ver edificios") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/edificios?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_building.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def edit_building(request, id_bld):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar edificios") or request.user.is_superuser:

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        post = ''
        type = ''

        #Se obtienen las empresas
        empresas_lst = Company.objects.all().exclude(company_status=2).order_by('company_name')

        #Se obtienen las tarifas
        tarifas = ElectricRates.objects.all()

        #Se obtienen los tipos de edificios
        tipos_edificio_lst = BuildingType.objects.all().exclude(building_type_status = 2).order_by('building_type_name')

        #Se obtienen las regiones
        regiones_lst = Region.objects.all()

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.all().exclude(building_attributes_type_status = 2).order_by('building_attributes_type_name')


        #Se obtiene la información del edificio
        buildingObj = get_object_or_404(Building, pk=id_bld)

        #Se obtiene la compañia
        companyBld = CompanyBuilding.objects.filter(building = buildingObj)

        #Se obtienen los tipos de edificio
        b_types = BuildingTypeForBuilding.objects.filter(building = buildingObj)

        #Se obtienen todos los atributos
        building_attributes = BuildingAttributesForBuilding.objects.filter(building = buildingObj)
        string_attributes = ''
        if building_attributes:
            for bp_att in building_attributes:
                string_attributes += '<div  class="extra_attributes_div"><span class="delete_attr_icon"><a href="#eliminar" class="delete hidden_icon" ' +\
                                     'title="eliminar atributo"></a></span>' +\
                                     '<span class="tip_attribute_part">' +\
                                        bp_att.building_attributes.building_attributes_type.building_attributes_type_name +\
                                     '</span>' +\
                                     '<span class="attribute_part">' +\
                                        bp_att.building_attributes.building_attributes_name +\
                                     '</span>'+\
                                     '<span class="attribute_value_part">'+\
                                        str(bp_att.building_attributes_value) +\
                                     '</span>' +\
                                     '<input type="hidden" name="atributo_' + str(bp_att.building_attributes.building_attributes_type.pk) +\
                                     '_' +str(bp_att.building_attributes.pk) +'" ' +\
                                     'value="' + str(bp_att.building_attributes.building_attributes_type.pk) +','+ str(bp_att.building_attributes.pk) + ','+ str(bp_att.building_attributes_value) +\
                                     '"/></div>';

        post = {
            'b_name':buildingObj.building_name,
            'b_description':buildingObj.building_description,
            'b_company':companyBld[0].company.pk,
            'b_type_arr':b_types,
            'b_mt2':buildingObj.mts2_built,
            'b_electric_rate_id':buildingObj.electric_rate.pk,
            'b_country_id':buildingObj.pais_id,
            'b_country':buildingObj.pais.pais_name,
            'b_state_id':buildingObj.estado_id,
            'b_state':buildingObj.estado.estado_name,
            'b_municipality_id':buildingObj.municipio_id,
            'b_municipality':buildingObj.municipio.municipio_name,
            'b_neighborhood_id':buildingObj.colonia_id,
            'b_neighborhood':buildingObj.colonia.colonia_name,
            'b_street_id':buildingObj.calle_id,
            'b_street':buildingObj.calle.calle_name,
            'b_ext':buildingObj.building_external_number,
            'b_int':buildingObj.building_internal_number,
            'b_zip':buildingObj.building_code_zone,
            'b_long':buildingObj.building_long_address,
            'b_lat':buildingObj.building_lat_address,
            'b_region_id':buildingObj.region_id,
            'b_attributes':string_attributes
        }

        if request.method == "POST":
            b_name = request.POST.get('b_name')
            b_description = request.POST.get('b_description')
            b_company = request.POST.get('b_company')
            b_type_arr = request.POST.getlist('b_type')
            b_mt2 = request.POST.get('b_mt2')
            b_electric_rate_id = request.POST.get('b_electric_rate')
            b_country_id = request.POST.get('b_country_id')
            b_state_id = request.POST.get('b_state_id')
            b_municipality_id = request.POST.get('b_municipality_id')
            b_neighborhood_id = request.POST.get('b_neighborhood_id')
            b_street_id = request.POST.get('b_street_id')
            b_ext = request.POST.get('b_ext')
            b_int = request.POST.get('b_int')
            b_zip = request.POST.get('b_zip')
            b_long = request.POST.get('b_longitude')
            b_lat = request.POST.get('b_latitude')
            b_region_id = request.POST.get('b_region')

            continuar = True
            if b_name == '':
                message = "El nombre del Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False

            if b_company == '':
                message += " - Se debe seleccionar una empresa"
                type = "n_notif"
                continuar = False

            if not b_type_arr:
                message += " - El edificio debe ser al menos de un tipo"
                type = "n_notif"
                continuar = False

            if b_electric_rate_id == '':
                message += " - Se debe seleccionar un tipo de tarifa"
                type = "n_notif"
                continuar = False

            if b_ext == '':
                message += " - El edificio debe tener un número exterior"
                type = "n_notif"
                continuar = False

            if b_zip == '':
                message += " - El edificio debe tener un código postal"
                type = "n_notif"
                continuar = False

            if b_long == '' and b_lat == '':
                message += " - Debes ubicar el edificio en el mapa"
                type = "n_notif"
                continuar = False

            if b_region_id == '':
                message += " - El edificio debe pertenecer a una región"
                type = "n_notif"
                continuar = False

            post = {
                'b_name':buildingObj.building_name,'b_description':buildingObj.building_description,'b_company':companyBld[0].company.pk,
                'b_type_arr':b_types,'b_mt2':buildingObj.mts2_built,'b_electric_rate_id':buildingObj.electric_rate.pk,
                'b_country_id':buildingObj.pais_id,'b_country':buildingObj.pais.pais_name,'b_state_id':buildingObj.estado_id,
                'b_state':buildingObj.estado.estado_name,'b_municipality_id':buildingObj.municipio_id,'b_municipality':buildingObj.municipio.municipio_name,
                'b_neighborhood_id':buildingObj.colonia_id,'b_neighborhood':buildingObj.colonia.colonia_name,
                'b_street_id':buildingObj.calle_id,'b_street':buildingObj.calle.calle_name,'b_ext':buildingObj.building_external_number,
                'b_int':buildingObj.building_internal_number,'b_zip':buildingObj.building_code_zone,'b_long':buildingObj.building_long_address,
                'b_lat':buildingObj.building_lat_address,'b_region_id':buildingObj.region_id
            }

            if continuar:

                #se obtiene el objeto de la tarifa
                tarifaObj = get_object_or_404(ElectricRates, pk=b_electric_rate_id)

                #Se obtiene la compañia
                companyObj = get_object_or_404(Company, pk=b_company)

                #Se obtiene el objeto de la region
                regionObj = get_object_or_404(Region, pk=b_region_id)

                countryObj, stateObj, municipalityObj, neighborhoodObj, streetObj = location_objects(b_country_id, request.POST.get('b_country'),
                b_state_id, request.POST.get('b_state'), b_municipality_id, request.POST.get('b_municipality'), b_neighborhood_id, request.POST.get('b_neighborhood'),
                b_street_id, request.POST.get('b_street'))

                #Se crea la cadena con la direccion concatenada
                formatted_address = streetObj.calle_name+" "+b_ext
                if b_int:
                    formatted_address += "-"+b_int
                formatted_address += " Colonia: "+ neighborhoodObj.colonia_name + " "+municipalityObj.municipio_name
                formatted_address += " " + stateObj.estado_name + " " + countryObj.pais_name +"C.P."+b_zip

                #Se edita la info el edificio
                buildingObj.building_name = b_name
                buildingObj.building_description = b_description
                buildingObj.building_formatted_address = formatted_address
                buildingObj.pais = countryObj
                buildingObj.estado = stateObj
                buildingObj.municipio = municipalityObj
                buildingObj.colonia = neighborhoodObj
                buildingObj.calle = streetObj
                buildingObj.region = regionObj
                buildingObj.building_external_number = b_ext
                buildingObj.building_internal_number = b_int
                buildingObj.building_code_zone = b_zip
                buildingObj.building_long_address = b_long
                buildingObj.building_lat_address = b_lat
                buildingObj.electric_rate = tarifaObj
                buildingObj.mts2_built = b_mt2
                buildingObj.save()

                #Se elimina la relacion compania - edificio
                bld_comp = CompanyBuilding.objects.filter(building = buildingObj)
                bld_comp.delete()

                #Se relaciona la compania con el edificio
                newBldComp = CompanyBuilding(
                    company = companyObj,
                    building = buildingObj,
                )
                newBldComp.save()

                #Se eliminan todas las relaciones edificio - tipo
                bld_type = BuildingTypeForBuilding.objects.filter(building = buildingObj)
                bld_type.delete()

                #Se dan de alta los tipos de edificio
                for b_type in b_type_arr:
                    #Se obtiene el objeto del tipo de edificio
                    typeObj = get_object_or_404(BuildingType, pk=b_type)
                    newBuildingTypeBuilding = BuildingTypeForBuilding(
                        building = buildingObj,
                        building_type = typeObj,
                        building_type_for_building_name = buildingObj.building_name +" - " +typeObj.building_type_name
                    )
                    newBuildingTypeBuilding.save()

                #Se eliminan los atributos del edificio y se dan de alta los nuevos

                oldAtttributes = BuildingAttributesForBuilding.objects.filter(building=buildingObj)
                oldAtttributes.delete()

                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')

                        #Se obtiene el objeto tipo de atributo
                        attribute_type_obj = BuildingAttributesType.objects.get(pk = atr_value_arr[0])

                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(pk = atr_value_arr[1])

                        newBldAtt = BuildingAttributesForBuilding(
                            building = buildingObj,
                            building_attributes = attribute_obj,
                            building_attributes_value = atr_value_arr[2]
                        )
                        newBldAtt.save()

                message = "Edificio editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW, "Ver edificios") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/edificios?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            empresas_lst=empresas_lst,
            tipos_edificio_lst=tipos_edificio_lst,
            tarifas=tarifas,
            regiones_lst=regiones_lst,
            tipos_atributos=tipos_atributos,
            operation="edit",
            message=message,
            type=type
        )

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/add_building.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def view_building(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW, "Ver edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']

        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_state = 'asc'
        order_municipality = 'asc'
        order_company = 'asc'
        order_status = 'asc'
        order = "building__building_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-building__building_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_state" in request.GET:
                if request.GET["order_state"] == "asc":
                    order = "building__estado__estado_name"
                    order_state = "desc"
                else:
                    order = "-building__estado__estado_name"

            if "order_municipality" in request.GET:
                if request.GET["order_municipality"] == "asc":
                    order = "building__municipio__municipio_name"
                    order_municipality = "desc"
                else:
                    order = "-building__municipio__municipio_name"
                    order_municipality = "asc"

            if "order_company" in request.GET:
                if request.GET["order_company"] == "asc":
                    order = "company__company_name"
                    order_company = "desc"
                else:
                    order = "-company__company_name"
                    order_company = "asc"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "building__building_status"
                    order_status = "desc"
                else:
                    order = "-building__building_status"
                    order_status = "asc"

        if search:
            lista = CompanyBuilding.objects.filter(Q(building__building_name__icontains=request.GET['search'])|Q(
                building__estado__estado_name__icontains=request.GET['search'])|Q(
                    building__municipio__municipio_name__icontains=request.GET['search'])|Q(
                        company__company_name__icontains=request.GET['search'])).exclude(building__building_status = 2).order_by(order)

        else:
            lista = CompanyBuilding.objects.all().exclude(building__building_status = 2).order_by(order)

        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_state=order_state, order_municipality=order_municipality, order_company=order_company, order_status=order_status,
            datacontext=datacontext, empresa=empresa, company=company)
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
        return render_to_response("consumption_centers/buildings/building.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def delete_building(request, id_bld):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de edificios") or request.user.is_superuser:

        building_obj = get_object_or_404(Building, pk=id_bld)
        building_obj.building_status = 2
        building_obj.save()

        mensaje = "El Edificio ha sido dado de baja correctamente"
        type="n_success"

        return HttpResponseRedirect("/buildings/edificios/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_batch_building(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE, "Baja de edificios") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^bld_\w+', key):
                    r_id = int(key.replace("bld_",""))
                    building = get_object_or_404(Building, pk=r_id)
                    building.building_status = 2
                    building.save()

            mensaje = "Los Edificios han sido dados de baja correctamente"
            return HttpResponseRedirect("/buildings/edificios/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/edificios/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def status_building(request, id_bld):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar edificios") or request.user.is_superuser:
        building = get_object_or_404(Building, pk = id_bld)

        if building.building_status == 0:
            building.building_status = 1
            str_status = "Activo"
        elif building.building_status == 1:
            building.building_status = 0
            str_status = "Activo"

        building.save()

        mensaje = "El estatus del edificio " + building.building_name +" ha cambiado a "+str_status
        type="n_success"

        return HttpResponseRedirect("/buildings/edificios/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def search_bld_country(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if "term" in request.GET:
        term = request.GET['term']
        countries = Pais.objects.filter(Q(pais_name__icontains=term))
        countries_arr = []
        for country in countries:
            countries_arr.append(dict(value=country.pais_name, pk=country.pk, label=country.pais_name))

        data=simplejson.dumps(countries_arr)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def search_bld_state(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if "term" in request.GET:
        term = request.GET['term']

        ctry_id = request.GET['country']
        #Se obtiene el país
        country = get_object_or_404(Pais, pk = ctry_id)

        states = PaisEstado.objects.filter(pais=country).filter(Q(estado__estado_name__icontains=term))
        states_arr = []
        for sts in states:
            states_arr.append(dict(value=sts.estado.estado_name, pk=sts.estado.pk, label=sts.estado.estado_name))

        data=simplejson.dumps(states_arr)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def search_bld_municipality(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if "term" in request.GET:
        term = request.GET['term']

        state_id = request.GET['state']
        #Se obtiene el país
        state = get_object_or_404(Estado, pk = state_id)

        municipalities = EstadoMunicipio.objects.filter(estado=state).filter(Q(municipio__municipio_name__icontains=term))
        mun_arr = []

        for mnp in municipalities:
            mun_arr.append(dict(value=mnp.municipio.municipio_name, pk=mnp.municipio.pk, label=mnp.municipio.municipio_name))

        data=simplejson.dumps(mun_arr)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404


def search_bld_neighborhood(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if "term" in request.GET:
        term = request.GET['term']

        mun_id = request.GET['municipality']
        #Se obtiene el municipio
        municipality = get_object_or_404(Municipio, pk=mun_id)

        neighborhoods = MunicipioColonia.objects.filter(municipio=municipality).filter(Q(colonia__colonia_name__icontains=term))
        ngh_arr = []

        for ng in neighborhoods:
            ngh_arr.append(dict(value=ng.colonia.colonia_name, pk=ng.colonia.pk, label=ng.colonia.colonia_name))

        data=simplejson.dumps(ngh_arr)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404


def search_bld_street(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if "term" in request.GET:
        term = request.GET['term']

        neigh_id = request.GET['neighborhood']
        #Se obtiene la colonia

        neighborhood = get_object_or_404(Colonia, pk=neigh_id)
        streets = ColoniaCalle.objects.filter(colonia=neighborhood).filter(Q(calle__calle_name__icontains=term))

        street_arr = []

        for st in streets:
            street_arr.append(dict(value=st.calle.calle_name, pk=st.calle.pk, label=st.calle.calle_name))

        data=simplejson.dumps(street_arr)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404