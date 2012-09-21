#standard library imports
from datetime import  timedelta, datetime
from dateutil.relativedelta import relativedelta
import re
import time
import calendar
#related third party imports

#local application/library specific imports
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.context import RequestContext
from django.utils import timezone
from django.db.models.aggregates import *
from django.core.exceptions import ObjectDoesNotExist

from c_center.calculations import tarifaHM_mensual, tarifaHM_total, obtenerHistorico, \
    fechas_corte
from c_center.models import ConsumerUnit, Building, ElectricData, ProfilePowermeter, \
    Powermeter, PartOfBuilding, HierarchyOfPart
from electric_rates.models import ElectricRatesDetail
from rbac.models import Operation, DataContextPermission
from rbac.rbac_functions import  has_permission

import json as simplejson

from tareas.tasks import add

VIEW = Operation.objects.get(operation_name="view")
CREATE = Operation.objects.get(operation_name="create")
DELETE = Operation.objects.get(operation_name="delete")
UPDATE = Operation.objects.get(operation_name="update")

def call_celery_delay():
    add.delay()
    return "Task set to execute."

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
        request.session['main_building'] = datacontext[0].building
    if 'consumer_unit' not in request.session:
        #sets the default ConsumerUnit (the first in ConsumerUnit for the main building)
        c_unit = ConsumerUnit.objects.filter(building=request.session['main_building'])
        request.session['consumer_unit'] = c_unit[0]

def set_default_building(request, id_building):
    """Sets the default building for reports"""
    request.session['main_building'] = Building.objects.get(pk=id_building)
    c_unit = ConsumerUnit.objects.filter(building=request.session['main_building'])
    request.session['consumer_unit'] = c_unit[0]
    dicc = dict(edificio=request.session['main_building'].building_name,
        electric_device_type=c_unit[0].electric_device_type.electric_device_type_name)
    data = simplejson.dumps( dicc )
    if 'referer' in request.GET:
        if request.GET['referer'] == "cfe":
            return HttpResponseRedirect("/reportes/cfe/")
    return HttpResponse(content=data,content_type="application/json")

#def set_consumer_unit(request):
#    """Shows a lightbox with all the profiles asociated for the main building """
#    c_units = ConsumerUnit.objects.filter(building=request.session['main_building'])
#    template_vars=dict(c_units=c_units)
#    template_vars_template = RequestContext(request, template_vars)
#    return render_to_response("consumption_centers/choose.html", template_vars_template)

def set_consumer_unit(request):

    building=request.session['main_building']

    hierarchy = HierarchyOfPart.objects.filter(part_of_building_composite__building=building)
    ids_hierarchy = []
    for hy in hierarchy:
        ids_hierarchy.append(hy.part_of_building_leaf.pk)
    hierarchy_array="[['Name','Parent','Tooltip'],['"+building.building_name+"', null, null],"
    #sacar el padre(partes de edificios que no son hijos de nadie)
    parent = PartOfBuilding.objects.filter(building=building).exclude(pk__in=ids_hierarchy)
    try:
        parent[0]
    except IndexError:
        #si no hay ninguno, es un edificio sin partes, o sin partes anidadas
        c_unit_parent = ConsumerUnit.objects.filter(building=building,
            part_of_building__isnull=True)
        for c_u_p in c_unit_parent:
            hierarchy_array += """[{
                                    v: '%s',
                                    f:'<a href="#" rel="%s" style="color:#9ebfc6;">%s</a>'},
                                    null,'Top Level'],""" % (str(c_u_p.pk), str(c_u_p.pk),
                                                             c_u_p.building.building_name)
    else:
        c_unit_parent = ConsumerUnit.objects.filter(building=building,
            part_of_building__isnull=True)
        for c_u_p in c_unit_parent:
            hierarchy_array += """[{
                                    v: '%s',
                                    f:'<a href="#" rel="%s" style="color:#9ebfc6;">%s</a>'},
                                    null,'Top Level'],""" % (str(c_u_p.pk), str(c_u_p.pk),
                                                             c_u_p.electric_device_type
                                                             .electric_device_type_name)
        for par in parent:
            try:
                c_unit_parent = ConsumerUnit.objects.get(part_of_building = par)
            except ObjectDoesNotExist:
                label = """{v: '%s',f: '%s'}""" % (str(par.pk),
                                                   par.part_of_building_name)
            else:
                label = """{v: '%s',f: '<a href="#" rel="%s" style="color:#9ebfc6;">%s</a>'}"""\
                        % (str(par.pk), str(c_unit_parent.pk), par.part_of_building_name)
            hierarchy_array += "["+label+",'"+building.building_name+"','Top Level'],"
        for leaf in hierarchy:
            try:
                c_unit = ConsumerUnit.objects.get(part_of_building=leaf.part_of_building_leaf)
            except ObjectDoesNotExist:

                label = """{v: '%s',f: '%s'}""" % (str(leaf.part_of_building_leaf.pk),
                                                   leaf.part_of_building_leaf.part_of_building_name)
            else:
                label = """{v: '%s',f: '<a href="#" rel="%s" style="color:#9ebfc6;">%s</a>'}"""\
                        % (str(leaf.part_of_building_leaf.pk), str(c_unit.pk),
                           leaf.part_of_building_leaf.part_of_building_name)
            hierarchy_array += "\n["+label+",'"+\
                               str(leaf.part_of_building_composite.pk)+\
                               "',null],"
    hierarchy_array += "]"
    template_vars=dict(array=hierarchy_array, building=building)
    template_vars_template = RequestContext(request, template_vars)
    return render_to_response("consumption_centers/choose_hierarchy.html", template_vars_template)

def set_default_consumer_unit(request, id_c_u):
    """Sets the consumer_unit for all the reports"""
    c_unit = ConsumerUnit.objects.filter(pk=id_c_u)
    request.session['consumer_unit'] = c_unit[0]
    return HttpResponse(status=200)

def main_page(request):
    """Main Page
    in the mean time the main view is the graphics view
    sets the session variables needed to show graphs
    """
    if has_permission(request.user, VIEW, "Ver graficas"):
        #has perm to view graphs, now check what can the user see
        datacontext = DataContextPermission.objects.filter(user_role__user=request.user)

        set_default_session_vars(request, datacontext)
        #valid years for reporting
        request.session['years'] = [__date.year for __date in
                                    ElectricData.objects.all().dates('medition_date', 'year')]

        template_vars = {"type":"graphs", "datacontext":datacontext,
                         'empresa': request.session['main_building'],
                         'consumer_unit': request.session['consumer_unit']
                         }
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/main.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def cfe_bill(request):
    """Just sends the main template for the CFE Bill """
    if has_permission(request.user, VIEW, "Consultar recibo CFE"):
        datacontext = DataContextPermission.objects.filter(user_role__user=request.user)
        set_default_session_vars(request, datacontext)

        template_vars={"type":"cfe", "datacontext":datacontext,
                       'empresa':request.session['main_building']
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

    meditions = ElectricData.objects.filter(profile_powermeter=profile_powermeter,
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
            meditions = ElectricData.objects.filter(profile_powermeter=profile,
                medition_date__gte=datetime_from,
                medition_date__lt=datetime_to)
            #all the meditions in a day for the second interval
            meditions2 = ElectricData.objects.filter(profile_powermeter=profile,
                medition_date__gte=datetime_from2,
                medition_date__lt=datetime_to2)

            meditions_last_index = len(meditions) - 1
            meditions_last_index2 = len(meditions2) - 1

            if meditions_last_index < 1:
                e_parameter=0

            else:
                if parameter == "kwh_consumido":
                    e_parameter = meditions[meditions_last_index].kWhIMPORT - \
                                  meditions[0].kWhIMPORT
                else:
                    e_parameter = meditions[meditions_last_index].kvarhIMPORT - \
                                  meditions[0].kvarhIMPORT

            if meditions_last_index2 < 1:
                e_parameter2=0

            else:
                if parameter == "kwh_consumido":
                    e_parameter2 = meditions2[meditions_last_index2].kWhIMPORT - \
                                   meditions2[0].kWhIMPORT
                else:
                    e_parameter2 = meditions2[meditions_last_index2].kvarhIMPORT - \
                                   meditions2[0].kvarhIMPORT
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
                    meditions.append(str(current_medition.kWhIMPORT))
                elif parameter == "kvarh":
                    meditions.append(str(current_medition.kvarhIMPORT))
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
            meditions = ElectricData.objects.filter(profile_powermeter=profile,
                                                    medition_date__gte=datetime_from,
                                                    medition_date__lt=datetime_to)

            meditions_last_index = len(meditions) - 1

            if meditions_last_index < 1:
                dayly_summary.append({"date":int(time.mktime(datetime_from.timetuple())),
                                      "meditions":[0], 'labels':[str(datetime_to)]})
            else:
                if parameter == "kwh_consumido":
                    e_parameter = meditions[meditions_last_index].kWhIMPORT - \
                                  meditions[0].kWhIMPORT
                else:
                    e_parameter = meditions[meditions_last_index].kvarhIMPORT - \
                                  meditions[0].kvarhIMPORT

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
                meditions.append(str(current_medition.kWhIMPORT))
            elif parameter == "kvarh":
                meditions.append(str(current_medition.kvarhIMPORT))
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
    week_measures = ElectricData.objects.filter(profile_powermeter=profile,
        medition_date__gte=week_start,
        medition_date__lt=week_end)

    week_measures_last_index = len(week_measures) - 1
    if week_measures_last_index < 1:
        week_measure = 0
    else:
        if type == "kwh" or type == "kwh_consumido":
            week_measure = week_measures[week_measures_last_index].kWhIMPORT -\
                           week_measures[0].kWhIMPORT

        else:
            week_measure = week_measures[week_measures_last_index].kvarhIMPORT -\
                           week_measures[0].kvarhIMPORT

    day_delta = timedelta(days=1)
    datetime_from = week_start
    datetime_to = datetime_from + day_delta
    for day_index in range(0,7):
        measures = ElectricData.objects.filter(profile_powermeter=profile,
            medition_date__gte=datetime_from,
            medition_date__lt=datetime_to)

        measures_last_index = len(measures) - 1
        if measures_last_index < 1:
            measure = 0
        else:
            if type == "kwh" or type == "kwh_consumido":
                measure = measures[measures_last_index].kWhIMPORT - measures[0].kWhIMPORT

            else:
                measure = measures[measures_last_index].kvarhIMPORT - measures[0].kvarhIMPORT

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
