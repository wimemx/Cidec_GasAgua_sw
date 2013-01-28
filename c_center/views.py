# -*- coding: utf-8 -*-
#standard library imports
from datetime import  timedelta, datetime
from dateutil.relativedelta import relativedelta
import Image
import cStringIO
import os
from django.core.files import File
import csv
import re
import time
import calendar
#related third party imports
import variety

#from PIL import *

#local application/library specific imports
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.context import RequestContext
from django.utils import timezone
from django.db.models.aggregates import *
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.contrib.auth.decorators import login_required

from cidec_sw import settings
from c_center.calculations import *
from c_center.models import *
from location.models import *
from electric_rates.models import ElectricRatesDetail
from rbac.models import Operation, DataContextPermission, UserRole, Object,\
    PermissionAsigment, GroupObject
from rbac.rbac_functions import  has_permission, get_buildings_context,\
    default_consumerUnit
from c_center_functions import *

from c_center.graphics import *
from data_warehouse.views import get_consumer_unit_electric_data_csv,\
    get_consumer_unit_electric_data_interval_csv,\
    DataWarehouseInformationRetrieveException,\
    get_consumer_unit_by_id as get_data_warehouse_consumer_unit_by_id,\
    get_consumer_unit_electric_data_interval_tuple_list

import json as simplejson
import sys
from tareas.tasks import datawarehouse_run

VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")

GRAPHS_ENERGY = [ob.object for ob in GroupObject.objects.filter(
    group__group_name="Energía")]
GRAPHS_I = [ob.object for ob in GroupObject.objects.filter(
    group__group_name="Corriente")]
GRAPHS_V = [ob.object for ob in GroupObject.objects.filter(
    group__group_name="Voltaje")]
GRAPHS_PF = [ob.object for ob in GroupObject.objects.filter(
    group__group_name="Factor de Potencia")]

GRAPHS = dict(energia=GRAPHS_ENERGY, corriente=GRAPHS_I, voltaje=GRAPHS_V,
              factor_potencia=GRAPHS_PF)

VIRTUAL_PROFILE = ProfilePowermeter.objects.get(
    powermeter__powermeter_anotation = "Medidor Virtual")

def call_celery_delay(request):
    if request.user.is_superuser:
        if request.method == "POST":
            text = '<h3>Se calcular&aacute;n: </h3>'
            almenosuno = False
            if "instantes" in request.POST:
                fill_instants = True
                text += "instantes<br/>"
                almenosuno = True
            else:
                fill_instants = None
            if "intervalos" in request.POST:
                fill_intervals = True
                text += "intervalos<br/>"
                almenosuno = True
            else:
                fill_intervals = None
            if "consumer_units" in request.POST:
                _update_consumer_units = True
                text += "consumer_units<br/>"
                almenosuno = True
            else:
                _update_consumer_units = None
            if "instant_facts" in request.POST:
                populate_instant_facts = True
                text += "instant_facts<br/>"
                almenosuno = True
            else:
                populate_instant_facts = None
            if "interval_facts" in request.POST:
                populate_interval_facts = True
                text += "interval_facts<br/>"
                almenosuno = True
            else:
                populate_interval_facts = None
            if almenosuno:
                datawarehouse_run.delay(
                    fill_instants,
                    fill_intervals,
                    _update_consumer_units,
                    populate_instant_facts,
                    populate_interval_facts
                )
                pass
            else:
                text = "No se realizar&aacute; ninguna acci&oacute;n"
        else:
            text = ''
        template_vars = dict(text=text)
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("tasks/datawarehouse_populate.html",
                                  template_vars_template)
    else:
        raise Http404


def set_default_building(request, id_building):
    """Sets the default building for reports"""
    request.session['main_building'] = Building.objects.get(pk=id_building)
    c_b = CompanyBuilding.objects.get(building=request.session['main_building'])
    request.session['company'] = c_b.company
    request.session['consumer_unit'] =\
    default_consumerUnit(request.user, request.session['main_building'])

    if request.session['consumer_unit']:
        dicc = dict(edificio=request.session['main_building'].building_name,
                    electric_device_type=request.session['consumer_unit']
                    .electric_device_type.electric_device_type_name)
        data = simplejson.dumps(dicc)
        if 'referer' in request.GET:
            if request.GET['referer'] == "cfe":
                return HttpResponseRedirect("/reportes/cfe/")
    else:
        data = ""
    return HttpResponse(content=data, content_type="application/json")


def set_consumer_unit(request):
    building = request.session['main_building']

    hierarchy_list = get_hierarchy_list(building, request.user)
    template_vars = dict(hierarchy=hierarchy_list)
    template_vars_template = RequestContext(request, template_vars)

    return render_to_response("consumption_centers/choose_hierarchy.html",
                              template_vars_template)


def set_default_consumer_unit(request, id_c_u):
    """Sets the consumer_unit for all the reports"""
    c_unit = ConsumerUnit.objects.get(pk=id_c_u)
    request.session['consumer_unit'] = c_unit
    return HttpResponse(status=200)


def week_report_kwh(request):
    """ Index page?
    shows a report of the consumed kwh in the current week
    """
    datacontext = get_buildings_context(request.user)
    if not datacontext:
        request.session['consumer_unit'] = None
        print "set consumer unit to none"
    set_default_session_vars(request, datacontext)

    if request.session['consumer_unit'] and request.session['main_building']:
        graphs = graphs_permission(request.user,
                                   request.session['consumer_unit'],
                                   GRAPHS['energia'])
        if graphs:
            consumer_unit = request.session['consumer_unit']
            datetime_current = datetime.datetime.now()
            year_current = datetime_current.year
            month_current = datetime_current.month
            week_current = variety.get_week_of_month_from_datetime(datetime_current)
            week_report_cumulative, week_report_cumulative_total =\
                get_consumer_unit_week_report_cumulative(consumer_unit,
                                                         year_current,
                                                         month_current,
                                                         week_current,
                                                         "kWh")

            week_start_datetime, week_end_datetime =\
                variety.get_week_start_datetime_end_datetime_tuple(year_current,
                                                                   month_current,
                                                                   week_current)

            template_vars = {"datacontext": datacontext,
                             'fi': week_start_datetime.date(),
                             'ff': (week_end_datetime -timedelta(days=1)).date(),
                             'empresa': request.session['main_building'],
                             'company': request.session['company'],
                             'consumer_unit': request.session['consumer_unit'],
                             'sidebar': request.session['sidebar'],
                             'electric_data_name': "kWh",
                             'week_report_cumulative': week_report_cumulative,
                             'week_report_cumulative_total': week_report_cumulative_total
            }

            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/main.html",
                                      template_vars_template)
        else:
            return render_to_response("generic_error.html",
                                      RequestContext(request,
                                                     {
                                                         "datacontext": datacontext}
                                      ))
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("empty.html", template_vars_template)

def main_page(request):
    """Main Page
    in the mean time the main view is the graphics view
    sets the session variables needed to show graphs
    """
    datacontext = get_buildings_context(request.user)
    if not datacontext:
        request.session['consumer_unit'] = None
        print "set consumer unit to none"
    set_default_session_vars(request, datacontext)

    if request.session['consumer_unit'] and request.session['main_building']:
        if "g_type" not in request.GET:
            graphs_type = GRAPHS['energia']
        else:
            try:
                graphs_type = GRAPHS[request.GET['g_type']]
            except KeyError:
                graphs_type = GRAPHS['energia']
        graphs = graphs_permission(request.user,
                                   request.session['consumer_unit'],
                                   graphs_type)
        if graphs:
            #valid years for reporting
            request.session['years'] = [__date.year for __date in
                                        ElectricDataTemp.objects.all().
                                        dates('medition_date', 'year')]

            template_vars = {"graphs": graphs, "datacontext": datacontext,
                             'empresa': request.session['main_building'],
                             'company': request.session['company'],
                             'consumer_unit': request.session['consumer_unit'],
                             'sidebar': request.session['sidebar']
            }
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/graphs/main.html",
                                      template_vars_template)
        else:
            return render_to_response("generic_error.html",
                                      RequestContext(request,
                                                     {
                                                         "datacontext": datacontext}
                                      ))
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("empty.html", template_vars_template)


def cfe_bill(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, VIEW, "Consultar recibo CFE") or\
       request.user.is_superuser:
        set_default_session_vars(request, datacontext)

        today = datetime.datetime.today().replace(hour=0, minute=0, second=0,
                                                  tzinfo=timezone.
                                                  get_current_timezone())
        month = int(today.month)
        year = int(today.year)
        dict(one=1, two=2)
        month_list = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
                      5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
                      9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre',
                      12: 'Diciembre'}
        year_list = {2010: 2010, 2011: 2011, 2012: 2012, 2013: 2013}

        template_vars = {"type": "cfe", "datacontext": datacontext,
                         'empresa': request.session['main_building'],
                         'company': request.session['company'],
                         'month': month, 'year': year, 'month_list': month_list,
                         'year_list': year_list,
                         'sidebar': request.session['sidebar']
        }

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/cfe.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html",
                                  RequestContext(request,
                                                 {"datacontext": datacontext}))


def cfe_calculations(request):
    """Renders the cfe bill and the historic data chart"""
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, VIEW, "Consultar recibo CFE") or\
       request.user.is_superuser:
        if not request.session['consumer_unit']:
            content = "<h2 style='font-family: helvetica; color: #878787;"\
                      " font-size:14px;' text-align: center;>"\
                      "No hay unidades de consumo asignadas, por favor ponte "\
                      "en contacto con el administrador para remediar esta"\
                      " situaci&oacute;n</h2>"
            return HttpResponse(content)
        set_default_session_vars(request, datacontext)

        template_vars = {"type": "cfe", "datacontext": datacontext,
                         'empresa': request.session['main_building']
        }

        if request.GET:
            month = int(request.GET['month'])
            year = int(request.GET['year'])

        else: #Obtener la fecha actual
            today = datetime.datetime.today().replace(hour=0, minute=0,
                                                      second=0,
                                                      tzinfo=timezone.
                                                      get_current_timezone())
            month = int(today.month)
            year = int(today.year)

        powermeter = request.session['consumer_unit'].profile_powermeter.\
        powermeter

        #Se obtiene el tipo de tarifa del edificio (HM o DAC)
        tipo_tarifa = request.session['main_building'].electric_rate

        if tipo_tarifa.pk == 1: #Tarifa HM
            resultado_mensual = tarifaHM(request.session['main_building'],
                                         powermeter, month, year)

        else: #if tipo_tarifa.pk == 2: #Tarifa DAC
            resultado_mensual = tarifaDAC(request.session['main_building'],
                                          powermeter, month, year)

        if resultado_mensual['status'] == 'OK':
            template_vars['resultados'] = resultado_mensual
            template_vars['tipo_tarifa'] = tipo_tarifa

            template_vars['historico'] = obtenerHistoricoHM
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response(
                "consumption_centers/graphs/cfe_bill.html",
                template_vars_template)
        if resultado_mensual['status'] == 'ERROR':
            template_vars['mensaje'] = resultado_mensual['mensaje']
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response(
                "consumption_centers/graphs/cfe_bill_error.html",
                template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def grafica_datoscsv(request):
    if request.method == "GET":
        #electric_data = ""
        #granularity = "day"
        try:
            electric_data = request.GET['graph']
            granularity = request.GET['granularity']

        except KeyError:
            return Http404

        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename="datos_' +\
                                          electric_data + '.csv"'
        writer = csv.writer(response)

        suffix_consumed = "_consumido"
        is_interval = False
        suffix_index = string.find(electric_data, suffix_consumed)
        if suffix_index >= 0:
            electric_data = electric_data[:suffix_index]
            is_interval = True

        data = []
        consumer_unit_counter = 1
        consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
        date_start_get_key = "date-start%02d" % consumer_unit_counter
        date_end_get_key = "date-end%02d" % consumer_unit_counter
        while request.GET.has_key(consumer_unit_get_key):
            consumer_unit_id = request.GET[consumer_unit_get_key]

            if request.GET.has_key(date_start_get_key) and\
               request.GET.has_key(date_end_get_key):
                datetime_start = datetime.datetime.strptime(
                    request.GET[date_start_get_key],
                    "%Y-%m-%d")
                datetime_end =\
                    datetime.datetime.strptime(request.GET[date_end_get_key], "%Y-%m-%d") +\
                        timedelta(days=1)

            else:
                datetime_start = get_default_datetime_start()
                datetime_end = get_default_datetime_end() + timedelta(days=1)

            try:
                consumer_unit = get_data_warehouse_consumer_unit_by_id(
                    consumer_unit_id)

            except DataWarehouseInformationRetrieveException as\
            consumer_unit_information_exception:
                print str(consumer_unit_information_exception)
                continue

            if is_interval:
                electric_data_csv_rows =\
                get_consumer_unit_electric_data_interval_csv(
                    electric_data,
                    granularity,
                    consumer_unit,
                    datetime_start,
                    datetime_end)
            else:
                electric_data_csv_rows = get_consumer_unit_electric_data_csv(
                    electric_data,
                    granularity,
                    consumer_unit,
                    datetime_start,
                    datetime_end)

            data.extend(electric_data_csv_rows)
            consumer_unit_counter += 1
            consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
            date_start_get_key = "date-start%02d" % consumer_unit_counter
            date_end_get_key = "date-end%02d" % consumer_unit_counter

        for data_item in data:
            writer.writerow(data_item)

        return response

    else:
        return Http404


def render_cumulative_comparison_in_week(request):
    if request.GET:
        try:
            electric_data = request.GET['electric-data']
            if electric_data == 'TotalkWhIMPORT':
                electric_data = "kWh"
        except KeyError:
            return HttpResponse("")
        else:
            consumer_unit_counter = 1
            consumer_units_data_tuple_list = []
            consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
            year_get_key = "year%02d" % consumer_unit_counter
            month_get_key = "month%02d" % consumer_unit_counter
            week_get_key = "week%02d" % consumer_unit_counter
            while request.GET.has_key(consumer_unit_get_key):
                consumer_unit_id_current = request.GET[consumer_unit_get_key]
                if request.GET.has_key(year_get_key) and\
                   request.GET.has_key(month_get_key) and\
                   request.GET.has_key(week_get_key):
                    year_current = int(request.GET[year_get_key])
                    month_current = int(request.GET[month_get_key])
                    week_current = int(request.GET[week_get_key])
                    start_datetime, end_datetime = variety.\
                    get_week_start_datetime_end_datetime_tuple(
                        year_current,
                        month_current,
                        week_current)

                    try:
                        consumer_unit_current =\
                            ConsumerUnit.objects.get(pk=consumer_unit_id_current)

                    except ConsumerUnit.DoesNotExist:
                        return HttpResponse("")

                    (electric_data_days_tuple_list,
                     consumer_unit_electric_data_tuple_list_current) =\
                        get_consumer_unit_week_report_cumulative(
                            consumer_unit_current,
                            year_current,
                            month_current,
                            week_current,
                            electric_data)

                    week_day_date = start_datetime.date()
                    for index in range(0, 7):
                        week_day_name, electric_data_value =\
                            consumer_unit_electric_data_tuple_list_current[index]

                        consumer_unit_electric_data_tuple_list_current[index] =\
                            (week_day_date, electric_data_value)

                        week_day_date += timedelta(days=1)

                    consumer_units_data_tuple_list.append(
                        (consumer_unit_current,
                         consumer_unit_electric_data_tuple_list_current))

                    consumer_unit_counter += 1
                    consumer_unit_get_key = "consumer-unit%02d" %\
                                            consumer_unit_counter
                    year_get_key = "year%02d" % consumer_unit_counter
                    month_get_key = "month%02d" % consumer_unit_counter
                    week_get_key = "week%02d" % consumer_unit_counter

            week_days_data_tuple_list = [("Lunes", []),
                                         ("Martes", []),
                                         ("Miercoles", []),
                                         ("Jueves", []),
                                         ("Viernes", []),
                                         ("Sabado", []),
                                         ("Domingo", [])]

            consumer_unit_electric_data_total_tuple_list = []
            all_meditions = True
            for consumer_unit, electric_data_tuple_list in\
                consumer_units_data_tuple_list:

                consumer_unit_total =\
                reduce(lambda x, y: x + y,
                       [electric_data_value for week_day_date, electric_data_value in
                        electric_data_tuple_list])

                consumer_unit_electric_data_total_tuple_list.append(
                    (consumer_unit, consumer_unit_total))

                week_day_index = 0
                for week_day_date, electric_data_value in electric_data_tuple_list:
                    electric_data_percentage =\
                    0 if consumer_unit_total == 0 else electric_data_value /\
                                                       consumer_unit_total\
                                                       * 100

                    week_days_data_tuple_list[week_day_index][1].append(
                        (consumer_unit,
                         week_day_date,
                         electric_data_value,
                         electric_data_percentage))
                    if not electric_data_percentage:
                        all_meditions = False
                    week_day_index += 1

            template_variables = dict()
            template_variables["week_days_data_tuple_list"] =\
                week_days_data_tuple_list

            template_variables['all_meditions'] = all_meditions
            template_variables["consumer_unit_electric_data_total_tuple_list"] =\
                consumer_unit_electric_data_total_tuple_list

            template_context = RequestContext(request, template_variables)
            return render_to_response(
                'consumption_centers/graphs/week_comparison.html',
                template_context)
    else:
        return Http404


def add_building_attr(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, CREATE, "Alta de atributos de edificios")\
    or request.user.is_superuser:
        empresa = request.session['main_building']
        company = request.session['company']
        type = ""
        message = ""
        attributes = BuildingAttributesType.objects.all().order_by(
            "building_attributes_type_sequence")
        template_vars = dict(datacontext=datacontext, empresa=empresa,
                             company=company,
                             type=type,
                             message=message,
                             attributes=attributes,
                             sidebar=request.session['sidebar'])
        if request.method == "POST":
            template_vars['post'] = variety.get_post_data(request.POST)

            valid = True
            attr_name = template_vars['post']['attr_name']
            attr = get_object_or_404(BuildingAttributesType,
                                     pk=template_vars['post']['attr_type'])
            desc = template_vars['post']['description']
            if not variety.validate_string(attr_name):
                valid = False
                template_vars['message'] =\
                "Por favor solo ingrese caracteres v&aacute;lidos"
            if desc != '':
                if not variety.validate_string(desc):
                    valid = False
                    template_vars['message'] =\
                    "Por favor solo ingrese caracteres v&aacute;lidos"

            if int(template_vars['post']['value_boolean']) == 1:
                bool = True
                unidades = template_vars['post']['unidades']
                if not unidades:
                    valid = False
                else:
                    if not variety.validate_string(unidades):
                        valid = False
                        template_vars['message'] = "Por favor solo ingrese"\
                                                   " caracteres v&aacute;lidos"
            else:
                bool = False
                unidades = ""
            if attr_name and valid:
                b_attr = BuildingAttributes(
                    building_attributes_type=attr,
                    building_attributes_name=attr_name,
                    building_attributes_description=desc,
                    building_attributes_value_boolean=bool,
                    building_attributes_units_of_measurement=unidades
                )
                b_attr.save()
                template_vars['message'] = "El atributo fue dado de alta"\
                                           " correctamente"
                template_vars['type'] = "n_success"
                if not(not has_permission(request.user,
                                          VIEW,
                                          "Ver atributos de edificios") and
                       not request.user.is_superuser):
                    return HttpResponseRedirect("/buildings/atributos?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            else:
                template_vars['type'] = "n_error"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_building_attr.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def b_attr_list(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, VIEW, "Ver atributos de edificios") or\
       request.user.is_superuser:
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
        order_status = 'asc'
        order = "building_attributes_name" #default order
        if "order_attrname" in request.GET:
            if request.GET["order_attrname"] == "desc":
                order = "-building_attributes_name"
                order_attrname = "asc"
            else:
                order_attrname = "desc"
        elif "order_type" in request.GET:
            if request.GET["order_type"] == "asc":
                order =\
                "building_attributes_type__building_attributes_type_name"
                order_type = "desc"
            else:
                order =\
                "-building_attributes_type__building_attributes_type_name"
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
        elif "order_status" in request.GET:
            if request.GET["order_status"] == "asc":
                order = "building_attributes_status"
                order_status = "desc"
            else:
                order = "-building_attributes_status"
                order_status = "asc"

        if search:
            lista = BuildingAttributes.objects.filter(
                Q(building_attributes_name__icontains=
                request.GET['search']) |
                Q(building_attributes_description__icontains=
                request.GET['search'])).order_by(order)
        else:
            lista = BuildingAttributes.objects.all().order_by(order)
        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(roles=paginator, order_attrname=order_attrname,
                             order_type=order_type, order_units=order_units,
                             order_sequence=order_sequence, empresa=empresa,
                             order_status=order_status, company=company,
                             datacontext=datacontext,
                             sidebar=request.session['sidebar'])
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

        template_vars['paginacion'] = pag_role

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/building_attr_list.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def delete_b_attr(request, id_b_attr):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, DELETE, "Eliminar atributos de edificios")\
    or request.user.is_superuser:
        b_attr = get_object_or_404(BuildingAttributes, pk=id_b_attr)

        if b_attr.building_attributes_status:
            b_attr.building_attributes_status = False
        else:
            b_attr.building_attributes_status = True

        b_attr.save()

        mensaje = "El atributo ha cambiado de status correctamente"
        type = "n_success"
        return HttpResponseRedirect("/buildings/atributos/?msj=" + mensaje +
                                    "&ntype=" + type)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def editar_b_attr(request, id_b_attr):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, VIEW, "Ver atributos de edificios") or\
       request.user.is_superuser:
        b_attr = get_object_or_404(BuildingAttributes, pk=id_b_attr)
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
        template_vars = dict(datacontext=datacontext, empresa=empresa,
                             message=message, post=post, type=type,
                             operation="edit", company=company,
                             attributes=attributes,
                             sidebar=request.session['sidebar'])
        if request.method == "POST":
            template_vars['post'] = variety.get_post_data(request.POST)

            valid = True
            attr_name = template_vars['post']['attr_name']
            attr = get_object_or_404(BuildingAttributesType,
                                     pk=template_vars['post']['attr_type'])
            desc = template_vars['post']['description']
            if not variety.validate_string(desc) or not\
            variety.validate_string(attr_name):
                valid = False
                template_vars['message'] = "Por favor solo ingrese "\
                                           "caracteres v&aacute;lidos"

            if template_vars['post']['value_boolean'] == 1:
                bool = True
                unidades = template_vars['post']['unidades']
                if not unidades:
                    valid = False
                else:
                    if not variety.validate_string(unidades):
                        valid = False
                        template_vars['message'] = "Por favor solo ingrese"\
                                                   " caracteres v&aacute;lidos"
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
                template_vars['message'] = "El atributo fue editado"\
                                           " correctamente"
                template_vars['type'] = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver atributos de edificios") or\
                   request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/atributos?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            else:
                template_vars['type'] = "n_error"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_building_attr.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def ver_b_attr(request, id_b_attr):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, VIEW, "Ver atributos de edificios") or\
       request.user.is_superuser:
        b_attr = get_object_or_404(BuildingAttributes, pk=id_b_attr)
        empresa = request.session['main_building']
        company = request.session['company']
        if b_attr.building_attributes_value_boolean:
            bool = "1"
        else:
            bool = "0"
        post = {'attr_name': b_attr.building_attributes_name,
                'description': b_attr.building_attributes_description,
                'attr_type': b_attr.building_attributes_type.
                building_attributes_type_name,
                'value_boolean': bool,
                'unidades': b_attr.building_attributes_units_of_measurement}
        message = ''
        type = ''
        attributes = BuildingAttributesType.objects.all().order_by(
            "building_attributes_type_sequence")
        template_vars = dict(datacontext=datacontext, empresa=empresa,
                             message=message, company=company, post=post,
                             type=type, operation="edit", attributes=attributes,
                             sidebar=request.session['sidebar'])

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/see_building_attr.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_batch_building_attr(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user,
                      UPDATE,
                      "Modificar atributos de edificios") or\
       request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] != '0':
            for key in request.POST:
                if re.search('^attr_\w+', key):
                    r_id = int(key.replace("attr_", ""))
                    atributo = get_object_or_404(BuildingAttributes, pk=r_id)

                    if request.POST['actions'] == "activate":
                        atributo.building_attributes_status = True
                    else:
                        atributo.building_attributes_status = False
                    atributo.save()

            mensaje = "Los atributos seleccionados han cambiado su estatus"\
                      " correctamente"
            return HttpResponseRedirect("/buildings/atributos/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/atributos/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

#====

def add_cluster(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, CREATE, "Alta de grupos de empresas") or\
       request.user.is_superuser:
        empresa = request.session['main_building']
        message = ''
        type = ''
        #Se obtienen los sectores
        sectores = SectoralType.objects.filter(sectoral_type_status=1)
        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             sectores=sectores,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            clustername = request.POST.get('clustername').strip()
            clusterdescription = request.POST.get('clusterdescription').strip()
            clustersector = request.POST.get('clustersector')

            continuar = True
            if clustername == '':
                message = "El nombre del Cluster no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(clustername):
                message = "El nombre del Cluster contiene caracteres inválidos"
                type = "n_notif"
                clustername = ""
                continuar = False

            if clustersector == '':
                message = "El Cluster debe pertenecer a un tipo de sector"
                type = "n_notif"
                continuar = False


            #Valida por si le da muchos clics al boton
            clusterValidate = Cluster.objects.filter(cluster_name=clustername)
            if clusterValidate:
                message = "Ya existe un cluster con ese nombre"
                type = "n_notif"
                continuar = False

            post = {'clustername': clustername,
                    'clusterdescription': clusterdescription,
                    'clustersector': int(clustersector)}
            template_vars['post'] = post

            if continuar:
                sector_type = SectoralType.objects.get(pk=clustersector)

                newCluster = Cluster(
                    sectoral_type=sector_type,
                    cluster_description=clusterdescription,
                    cluster_name=clustername,
                )
                newCluster.save()

                template_vars["message"] = "Cluster de Empresas creado "\
                                           "exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW, "Ver clusters") or\
                   request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/clusters?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")

            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_cluster.html",
            template_vars_template)

    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_cluster(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, VIEW, "Ver grupos de empresas") or\
       request.user.is_superuser:
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_sector = 'asc'
        order_status = 'asc'
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
            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "cluster_status"
                    order_status = "desc"
                else:
                    order = "-cluster_status"
                    order_status = "asc"

        if search:
            lista = Cluster.objects.filter(
                Q(cluster_name__icontains=request.GET['search']) |
                Q(sectoral_type__sectorial_type_name__icontains=
                request.GET['search'])).exclude(
                cluster_status=2).order_by(order)

        else:
            lista = Cluster.objects.all().exclude(cluster_status=2).\
            order_by(order)
        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_sector=order_sector,
                             order_status=order_status,
                             datacontext=datacontext,
                             empresa=empresa,
                             company=request.session['company'],
                             sidebar=request.session['sidebar'])
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
            "consumption_centers/buildings/clusters.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_cluster(request, id_cluster):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar cluster de empresas")\
    or request.user.is_superuser:
        cluster = get_object_or_404(Cluster, pk=id_cluster)
        if cluster.cluster_status == 1:
            cluster.cluster_status = 0
            action = "inactivo"
        else: #if cluster.cluster_status == 0:
            cluster.cluster_status = 1
            action = "activo"
        cluster.save()
        mensaje = "El estatus del cluster " + cluster.cluster_name +\
                  " ha cambiado a " + action
        type = "n_success"

        return HttpResponseRedirect("/buildings/clusters/?msj=" + mensaje +
                                    "&ntype=" + type)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_batch_cluster(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE, "Modificar cluster de empresas")\
    or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^cluster_\w+', key):
                    r_id = int(key.replace("cluster_", ""))
                    cluster = get_object_or_404(Cluster, pk=r_id)
                    if cluster.cluster_status == 1:
                        cluster.cluster_status = 0
                    elif cluster.cluster_status == 0:
                        cluster.cluster_status = 1
                    cluster.save()

            mensaje = "Los clusters seleccionados han cambiado su status "\
                      "correctamente"
            return HttpResponseRedirect("/buildings/clusters/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/clusters/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def edit_cluster(request, id_cluster):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, UPDATE, "Modificar cluster de empresas")\
    or request.user.is_superuser:
        cluster = get_object_or_404(Cluster, pk=id_cluster)

        #Se obtienen los sectores
        sectores = SectoralType.objects.filter(sectoral_type_status=1)

        post = {'clustername': cluster.cluster_name,
                'clusterdescription': cluster.cluster_description,
                'clustersector': cluster.sectoral_type.pk}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        message = ''
        type = ''

        if request.method == "POST":
            clustername = request.POST.get('clustername')
            clusterdescription = request.POST.get('clusterdescription')
            clustersector = request.POST.get('clustersector')
            continuar = True
            if clustername == '':
                message = "El nombre del cluster no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(clustername):
                message = "El nombre del Cluster contiene caracteres inválidos"
                type = "n_notif"
                clustername = ""
                continuar = False

            if clustersector == '':
                message = "El sector del cluster no puede quedar vacío"
                type = "n_notif"
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if cluster.cluster_name != clustername:
                #Valida por si le da muchos clics al boton
                clusterValidate = Cluster.objects.filter(
                    cluster_name=clustername)
                if clusterValidate:
                    message = "Ya existe un cluster con ese nombre"
                    type = "n_notif"
                    continuar = False

            post = {'clustername': cluster.cluster_name,
                    'clusterdescription': clusterdescription,
                    'clustersector': int(clustersector)}

            if continuar:
                sector_type = SectoralType.objects.get(pk=clustersector)

                cluster.cluster_name = clustername
                cluster.cluster_description = clusterdescription
                cluster.sectoral_type = sector_type
                cluster.save()

                message = "Cluster editado exitosamente"
                type = "n_success"
                if has_permission(request.user,
                                  VIEW,
                                  "Ver grupos de empresas") or\
                   request.user.is_superuser:
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
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_cluster.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def see_cluster(request, id_cluster):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, VIEW, "Ver grupos de empresas") or\
       request.user.is_superuser:
        empresa = request.session['main_building']

        cluster = Cluster.objects.get(pk=id_cluster)
        cluster_companies = ClusterCompany.objects.filter(cluster=cluster)

        template_vars = dict(
            datacontext=datacontext,
            cluster=cluster,
            cluster_companies=cluster_companies,
            empresa=empresa,
            company=request.session['company'],
            sidebar=request.session['sidebar']
        )

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/see_cluster.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

###################
#POWERMETER MODELS#
###################

def add_powermetermodel(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user,
                      CREATE,
                      "Alta de modelos de medidores eléctricos")\
    or request.user.is_superuser:
        empresa = request.session['main_building']

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            pw_brand = request.POST.get('pw_brand').strip()
            pw_model = request.POST.get('pw_model').strip()
            message = ''
            type = ''

            continuar = True

            if pw_brand == '':
                message = "El nombre de la Marca no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(pw_brand):
                message = "El nombre de la Marca contiene caracteres inválidos"
                type = "n_notif"
                pw_brand = ""
                continuar = False

            if pw_model == '':
                message = "El nombre del Modelo no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(pw_model):
                message = "El nombre del Modelo contiene caracteres inválidos"
                type = "n_notif"
                pw_model = ""
                continuar = False

            #Valida no puede haber empresas con el mismo nombre
            p_modelValidate = PowermeterModel.objects.filter(
                powermeter_brand=pw_brand
            ).filter(powermeter_model=pw_model)
            if p_modelValidate:
                message = "Ya existe una Marca y un Modelo con esos datos"
                type = "n_notif"
                continuar = False

            post = {'pw_brand': pw_brand, 'pw_model': pw_model}

            if continuar:
                newPowerMeterModel = PowermeterModel(
                    powermeter_brand=pw_brand,
                    powermeter_model=pw_model
                )
                newPowerMeterModel.save()

                template_vars["message"] = "Modelo de Medidor creado "\
                                           "exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user,
                                  VIEW,
                                  "Ver modelos de medidores eléctricos") or\
                   request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/modelos_medidor?msj=" +
                        template_vars["message"] + "&ntype=n_success")

            template_vars['post'] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_powermetermodel.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def edit_powermetermodel(request, id_powermetermodel):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user,
                      UPDATE,
                      "Modificar modelos de medidores eléctricos")\
    or request.user.is_superuser:
        powermetermodel = get_object_or_404(PowermeterModel,
                                            pk=id_powermetermodel)

        post = {'pw_brand': powermetermodel.powermeter_brand,
                'pw_model': powermetermodel.powermeter_model}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        message = ''
        type = ''

        if request.method == "POST":
            pw_brand = request.POST.get('pw_brand')
            pw_model = request.POST.get('pw_model')

            continuar = True
            if pw_brand == '':
                message = "El nombre de la Marca no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(pw_brand):
                message = "El nombre de la Marca contiene caracteres inválidos"
                type = "n_notif"
                pw_brand = ""
                continuar = False

            if pw_model == '':
                message = "El nombre del Modelo no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(pw_model):
                message = "El nombre del Modelo contiene caracteres inválidos"
                type = "n_notif"
                pw_model = ""
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if powermetermodel.powermeter_brand != pw_brand or\
               powermetermodel.powermeter_model != pw_model:
                p_modelValidate = PowermeterModel.objects.filter(
                    powermeter_brand=pw_brand).filter(
                    powermeter_model=pw_model)
                if p_modelValidate:
                    message = "Ya existe una Marca y un Modelo con esos datos"
                    type = "n_notif"
                    continuar = False

            post = {'pw_brand': pw_brand, 'pw_model': pw_model}

            if continuar:
                powermetermodel.powermeter_brand = pw_brand
                powermetermodel.powermeter_model = pw_model
                powermetermodel.save()

                message = "Modelo de Medidor editado exitosamente"
                type = "n_success"
                if has_permission(request.user,
                                  VIEW,
                                  "Ver modelos de medidores eléctricos")\
                or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/modelos_medidor?msj=" + message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             post=post,
                             operation="edit",
                             message=message,
                             type=type,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_powermetermodel.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_powermetermodels(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, VIEW,
                      "Ver modelos de medidores eléctricos") or\
       request.user.is_superuser:
        empresa = request.session['main_building']
        company = request.session['company']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_brand = 'asc'
        order_model = 'asc'
        order_status = 'asc'
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

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "status"
                    order_status = "desc"
                else:
                    order = "-status"
                    order_status = "asc"

        if search:
            lista = PowermeterModel.objects.filter(Q(
                powermeter_brand__icontains=request.GET['search']) | Q(
                powermeter_model__icontains=request.GET['search'])).\
            order_by(order)

        else:
            lista = PowermeterModel.objects.all().order_by(order)
        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_brand=order_brand,
                             order_model=order_model,
                             order_status=order_status,
                             datacontext=datacontext,
                             empresa=empresa,
                             company=company,
                             sidebar=request.session['sidebar'])
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
            "consumption_centers/buildings/powermetermodels.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_batch_powermetermodel(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user,
                      UPDATE,
                      "Modificar modelos de medidores eléctricos") or\
       request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^model_\w+', key):
                    r_id = int(key.replace("model_", ""))
                    powermetermodel = get_object_or_404(PowermeterModel,
                                                        pk=r_id)
                    if powermetermodel.status == 0:
                        powermetermodel.status = 1
                    elif powermetermodel.status == 1:
                        powermetermodel.status = 0
                    powermetermodel.save()

            mensaje = "Los modelos seleccionados han cambiado su estatus"\
                      " correctamente"
            return HttpResponseRedirect("/buildings/modelos_medidor/?msj=" +
                                        mensaje + "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/modelos_medidor/?msj=" +
                                        mensaje + "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_powermetermodel(request, id_powermetermodel):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user,
                      UPDATE,
                      "Modificar modelos de medidores eléctricos") or\
       request.user.is_superuser:
        powermetermodel = get_object_or_404(PowermeterModel,
                                            pk=id_powermetermodel)
        if powermetermodel.status == 0:
            powermetermodel.status = 1
            str_status = "Activo"
        else: #if powermetermodel.status == 1:
            powermetermodel.status = 0
            str_status = "Inactivo"
        powermetermodel.save()

        mensaje = "El estatus del modelo ha cambiado a " + str_status
        type = "n_success"

        return HttpResponseRedirect("/buildings/modelos_medidor/?msj=" +
                                    mensaje + "&ntype=" + type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

#############
#POWERMETERS#
#############

def add_powermeter(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, CREATE,
                      "Alta de medidor electrico") or request.user.is_superuser:
        empresa = request.session['main_building']
        post = ''
        pw_models_list = PowermeterModel.objects.all().exclude(
            status=0).order_by("powermeter_brand")
        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             modelos=pw_models_list,
                             post=post,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            pw_alias = request.POST.get('pw_alias').strip()
            pw_model = request.POST.get('pw_model')
            pw_serial = request.POST.get('pw_serial').strip()
            message = ''
            type = ''

            continuar = True
            if pw_alias == '':
                message = "El Alias del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(pw_alias):
                message = "El Alias del medidor contiene caracteres inválidos"
                type = "n_notif"
                pw_alias = ""
                continuar = False

            if pw_model == '':
                message = "El modelo del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False

            if pw_serial == '':
                message = "El número serial del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False

            #Valida por si le da muchos clics al boton
            pwValidate = Powermeter.objects.filter(
                powermeter_model__pk=pw_model).filter(
                powermeter_serial=pw_serial)
            if pwValidate:
                message = "Ya existe un Medidor con ese Modelo y ese Número de Serie"
                type = "n_notif"
                continuar = False

            post = {'pw_alias': pw_alias, 'pw_model': int(pw_model),
                    'pw_serial': pw_serial}

            if continuar:
                pw_model = PowermeterModel.objects.get(pk=pw_model)

                newPowerMeter = Powermeter(
                    powermeter_model=pw_model,
                    powermeter_anotation=pw_alias,
                    powermeter_serial=pw_serial

                )
                newPowerMeter.save()
                ProfilePowermeter(powermeter=newPowerMeter).save()

                template_vars["message"] = "Medidor creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver medidores eléctricos") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/medidores?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_powermeter.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def edit_powermeter(request, id_powermeter):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, UPDATE,
                      "Modificar medidores eléctricos") or request.user.is_superuser:
        powermeter = get_object_or_404(Powermeter, pk=id_powermeter)

        pw_models_list = PowermeterModel.objects.all().exclude(
            status=0).order_by("powermeter_brand")

        post = {'pw_alias': powermeter.powermeter_anotation,
                'pw_model': powermeter.powermeter_model.pk,
                'pw_serial': powermeter.powermeter_serial}

        empresa = request.session['main_building']
        message = ''
        type = ''

        if request.method == "POST":
            pw_alias = request.POST.get('pw_alias').strip()
            pw_model = request.POST.get('pw_model')
            pw_serial = request.POST.get('pw_serial').strip()

            continuar = True
            if pw_alias == '':
                message = "El Alias del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(pw_alias):
                message = "El Alias del medidor contiene caracteres inválidos"
                type = "n_notif"
                pw_alias = ""
                continuar = False

            if pw_model == '':
                message = "El modelo del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False
            if pw_serial == '':
                message = "El número serial del medidor no puede quedar vacío"
                type = "n_notif"
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if powermeter.powermeter_model_id != pw_model and powermeter.powermeter_serial != pw_serial:
                #Valida por si le da muchos clics al boton
                pwValidate = Powermeter.objects.filter(
                    powermeter_model__pk=pw_model).filter(
                    powermeter_serial=pw_serial)
                if pwValidate:
                    message = "Ya existe un Medidor con ese Modelo y ese Número de Serie"
                    type = "n_notif"
                    continuar = False

            post = {'pw_alias': pw_alias, 'pw_model': int(pw_model),
                    'pw_serial': pw_serial}

            if continuar:
                pw_model = PowermeterModel.objects.get(pk=pw_model)

                powermeter.powermeter_anotation = pw_alias
                powermeter.powermeter_serial = pw_serial
                powermeter.powermeter_model = pw_model
                powermeter.save()

                message = "Medidor editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver medidores eléctricos") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/medidores?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             post=post,
                             modelos=pw_models_list,
                             operation="edit",
                             message=message,
                             type=type,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_powermeter.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_powermeter(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if has_permission(request.user, VIEW,
                      "Ver medidores eléctricos") or request.user.is_superuser:
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_alias = 'asc'
        order_serial = 'asc'
        order_model = 'asc'
        order_status = 'asc'

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
            lista = Powermeter.objects.filter(
                Q(powermeter_anotation__icontains=request.GET['search']) | Q(
                    powermeter_model__powermeter_brand__icontains=request.GET[
                                                                  'search']) | Q(
                    powermeter_model__powermeter_model__icontains=request.GET[
                                                                  'search'])).order_by(
                order)
        else:
            #powermeter_objs = Powermeter.objects.all()
            #powermeter_ids = [pw.pk for pw in powermeter_objs]
            #profiles_pw_objs = ProfilePowermeter.objects.filter(powermeter__pk__in = powermeter_ids).filter(profile_powermeter_status = 1)
            lista = Powermeter.objects.all().order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_alias=order_alias, order_model=order_model,
                             order_serial=order_serial,
                             order_status=order_status,
                             datacontext=datacontext, empresa=empresa,
                             company=request.session['company'],
                             sidebar=request.session['sidebar'])
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
            "consumption_centers/buildings/powermeters.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_batch_powermeter(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar medidores eléctricos") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^powermeter_\w+', key):
                    r_id = int(key.replace("powermeter_", ""))
                    powermeter = get_object_or_404(Powermeter, pk=r_id)
                    if powermeter.status == 0:
                        powermeter.status = 1
                    elif powermeter.status == 1:
                        powermeter.status = 0
                    powermeter.save()

            mensaje = "Los medidores seleccionados han cambiado su estatus correctamente"
            if "ref" in request.GET:
                return HttpResponseRedirect("/buildings/editar_ie/" +
                                            request.GET['ref'] + "/?msj=" +
                                            mensaje +
                                            "&ntype=n_success")

            return HttpResponseRedirect("/buildings/medidores/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/medidores/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_powermeter(request, id_powermeter):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar medidores eléctricos") or request.user.is_superuser:
        powermeter = get_object_or_404(Powermeter, pk=id_powermeter)
        if powermeter.status == 0:
            powermeter.status = 1
            str_status = "Activo"
        else:
            powermeter.status = 0
            str_status = "Inactivo"

        powermeter.save()
        mensaje = "El estatus del medidor " + powermeter.powermeter_anotation \
                  + " ha cambiado a " + str_status
        type = "n_success"
        if 'ref' in request.GET:
            if 'see' in request.GET:
                return HttpResponseRedirect("/buildings/ver_ie/" +
                                            request.GET['ref'] + "/?msj=" +
                                            mensaje +
                                            "&ntype=" + type)
            return HttpResponseRedirect("/buildings/editar_ie/" +
                                        request.GET['ref'] + "/?msj=" + mensaje +
                                        "&ntype=" + type)
        return HttpResponseRedirect("/buildings/medidores/?msj=" + mensaje +
                                    "&ntype=" + type)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def see_powermeter(request, id_powermeter):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW,
                      "Ver medidores eléctricos") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        location = ''
        powermeter = Powermeter.objects.get(pk=id_powermeter)
        profile_powermeter_objs = ProfilePowermeter.objects.filter(
            powermeter=powermeter).filter(profile_powermeter_status=1)
        if profile_powermeter_objs:
            profile = profile_powermeter_objs[0]

            consumer_unit_objs = ConsumerUnit.objects.filter(
                profile_powermeter=profile)
            c_unit = consumer_unit_objs[0]
            location = c_unit.building.building_name

        template_vars = dict(
            datacontext=datacontext,
            powermeter=powermeter,
            location=location,
            empresa=empresa,
            company=request.session['company'],
            sidebar=request.session['sidebar']
        )

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/see_powermeter.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

#######################
#Electric Device Types#
#######################

def add_electric_device_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE,
                      "Alta de dispositivos y sistemas eléctricos") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        post = ''

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             post=post,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            edt_name = request.POST.get('devicetypename').strip()
            edt_description = request.POST.get('devicetypedescription').strip()
            message = ''
            type = ''

            continuar = True
            if edt_name == '':
                message = "El nombre del Tipo de Equipo Eléctrico no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(edt_name):
                message = "El nombre del Tipo de Equipo Eléctrico contiene caracteres inválidos"
                type = "n_notif"
                edt_name = ""
                continuar = False

            #Valida por si le da muchos clics al boton
            b_electric_typeValidate = ElectricDeviceType.objects.filter(
                electric_device_type_name=edt_name)
            if b_electric_typeValidate:
                message = "Ya existe un Tipo de Equipo Eléctrico con ese nombre"
                type = "n_notif"
                continuar = False

            post = {'devicetypename': edt_name,
                    'devicetypedescription': edt_description}

            if continuar:
                newElectricDeviceType = ElectricDeviceType(
                    electric_device_type_name=edt_name,
                    electric_device_type_description=edt_description
                )
                newElectricDeviceType.save()

                template_vars[
                "message"] = "Tipo de Equipo Eléctrico creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver medidores eléctricos") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_equipo_electrico?msj=" +
                        template_vars["message"] +
                        "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_electricdevicetype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def edit_electric_device_type(request, id_edt):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar dispositivos y sistemas eléctricos") or request.user.is_superuser:
        edt_obj = get_object_or_404(ElectricDeviceType, pk=id_edt)

        post = {'devicetypename': edt_obj.electric_device_type_name,
                'devicetypedescription': edt_obj.electric_device_type_description}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        message = ''
        type = ''

        if request.method == "POST":
            edt_name = request.POST.get('devicetypename').strip()
            edt_description = request.POST.get('devicetypedescription').strip()

            continuar = True
            if edt_name == '':
                message = "El nombre del Tipo de Equipo Eléctrico no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(edt_name):
                message = "El nombre del Tipo de Equipo Eléctrico contiene caracteres inválidos"
                type = "n_notif"
                edt_name = ""
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if edt_obj.electric_device_type_name != edt_name:
                #Valida por si le da muchos clics al boton
                e_typeValidate = ElectricDeviceType.objects.filter(
                    electric_device_type_name=edt_name)
                if e_typeValidate:
                    message = "Ya existe un Tipo de Equipo Eléctrico con ese nombre"
                    type = "n_notif"
                    continuar = False

            post = {'devicetypename': edt_name,
                    'devicetypedescription': edt_description}

            if continuar:
                edt_obj.electric_device_type_name = edt_name
                edt_obj.electric_device_type_description = edt_description
                edt_obj.save()

                message = "Tipo de Equipo Eléctrico editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver dispositivos y sistemas eléctricos") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_equipo_electrico?msj=" +
                        message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             post=post,
                             operation="edit",
                             message=message,
                             type=type,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_electricdevicetype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_electric_device_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW,
                      "Ver dispositivos y sistemas eléctricos") or request.user.is_superuser:
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
            lista = ElectricDeviceType.objects.filter(Q(
                electric_device_type_name__icontains=request.GET['search']) | Q(
                electric_device_type_description__icontains=request.GET[
                                                            'search'])).exclude(
                electric_device_type_status=2).order_by(order)

        else:
            lista = ElectricDeviceType.objects.all().exclude(
                electric_device_type_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_description=order_description,
                             order_status=order_status,
                             datacontext=datacontext, empresa=empresa,
                             company=request.session['company'],
                             sidebar=request.session['sidebar'])
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
            "consumption_centers/buildings/electricdevicetype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def delete_batch_electric_device_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar dispositivos y sistemas eléctricos") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^edt_\w+', key):
                    r_id = int(key.replace("edt_", ""))
                    edt_obj = get_object_or_404(ElectricDeviceType, pk=r_id)
                    if edt_obj.electric_device_type_status == 0:
                        edt_obj.electric_device_type_status = 1
                    elif edt_obj.electric_device_type_status == 1:
                        edt_obj.electric_device_type_status = 0
                    edt_obj.save()

            mensaje = "Los Tipos de Equipo Eléctrico han cambiado su estatus correctamente"
            return HttpResponseRedirect(
                "/buildings/tipos_equipo_electrico/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/tipos_equipo_electrico/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_batch_electric_device_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar dispositivos y sistemas eléctricos") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^edt_\w+', key):
                    r_id = int(key.replace("edt_", ""))
                    edt_obj = get_object_or_404(ElectricDeviceType, pk=r_id)
                    if edt_obj.electric_device_type_status == 0:
                        edt_obj.electric_device_type_status = 1
                    elif edt_obj.electric_device_type_status == 1:
                        edt_obj.electric_device_type_status = 0
                    edt_obj.save()

            mensaje = "Los Tipos de Equipo Eléctrico han cambiado su estatus correctamente"
            return HttpResponseRedirect(
                "/buildings/tipos_equipo_electrico/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/tipos_equipo_electrico/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def status_electric_device_type(request, id_edt):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar dispositivos y sistemas eléctricos") or request.user.is_superuser:
        edt_obj = get_object_or_404(ElectricDeviceType, pk=id_edt)
        if edt_obj.electric_device_type_status == 0:
            edt_obj.electric_device_type_status = 1
            str_status = "Activo"
        else: #if edt_obj.electric_device_type_status == 1:
            edt_obj.electric_device_type_status = 0
            str_status = "Inactivo"

        edt_obj.save()
        mensaje = "El estatus del tipo de equipo eléctrico ha cambiado a " + str_status
        type = "n_success"

        return HttpResponseRedirect(
            "/buildings/tipos_equipo_electrico/?msj=" + mensaje +
            "&ntype=" + type)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

###########
#Companies#
###########

def add_company(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE,
                      "Alta de empresas") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        post = ''
        message = ''
        type = ''

        #Get Clusters
        clusters = get_clusters_for_operation("Alta de empresas", CREATE,
                                              request.user)
        #clusters = Cluster.objects.all().exclude(cluster_status = 2)

        #Get Sectors
        sectors = SectoralType.objects.filter(sectoral_type_status=1)

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             post=post,
                             clusters=clusters,
                             sectors=sectors,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            cmp_name = request.POST.get('company_name').strip()
            cmp_description = request.POST.get('company_description').strip()
            cmp_cluster = request.POST.get('company_cluster')
            cmp_sector = request.POST.get('company_sector')

            continuar = True
            if cmp_name == '':
                message = "El nombre de la empresa no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(cmp_name):
                message = "El nombre de la empresa contiene caracteres inválidos"
                type = "n_notif"
                cmp_name = ""
                continuar = False

            if cmp_cluster == '':
                message = "La empresa debe pertenencer a un grupo de empresas"
                type = "n_notif"
                continuar = False

            if cmp_sector == '':
                message = "La empresa debe pertenencer a un sector"
                type = "n_notif"
                continuar = False

            #Valida no puede haber empresas con el mismo nombre
            companyValidate = Company.objects.filter(company_name=cmp_name)
            if companyValidate:
                message = "Ya existe una empresa con ese nombre"
                type = "n_notif"
                continuar = False

            post = {'cmp_name': cmp_name, 'cmp_description': cmp_description,
                    'cmp_cluster': int(cmp_cluster),
                    'cmp_sector': int(cmp_sector)}

            if continuar:
                #Se obtiene el objeto del sector
                sectorObj = SectoralType.objects.get(pk=cmp_sector)

                newCompany = Company(
                    sectoral_type=sectorObj,
                    company_name=cmp_name,
                    company_description=cmp_description
                )
                newCompany.save()

                #Se relaciona la empresa con el cluster
                #Se obtiene el objeto del cluster
                clusterObj = Cluster.objects.get(pk=cmp_cluster)

                newCompanyCluster = ClusterCompany(
                    cluster=clusterObj,
                    company=newCompany
                )
                newCompanyCluster.save()

                #Guarda la foto
                if 'logo' in request.FILES:
                    handle_company_logo(request.FILES['logo'], newCompany, True)

                template_vars["message"] = "Empresa creada exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver empresas") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/empresas?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_company.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def edit_company(request, id_cpy):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar empresas") or request.user.is_superuser:
        company_clusters = ClusterCompany.objects.filter(id=id_cpy)

        post = {'cmp_id': company_clusters[0].company.id,
                'cmp_name': company_clusters[0].company.company_name,
                'cmp_description': company_clusters[
                                   0].company.company_description,
                'cmp_cluster': company_clusters[0].cluster.pk,
                'cmp_sector': company_clusters[0].company.sectoral_type.pk,
                'cmp_logo': company_clusters[0].company.company_logo}

        #Get Clusters
        #clusters = Cluster.objects.all().exclude(cluster_status = 2)
        clusters = get_clusters_for_operation("Modificar empresas", UPDATE,
                                              request.user)
        #Get Sectors
        sectors = SectoralType.objects.filter(sectoral_type_status=1)

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        message = ''
        type = ''

        if request.method == "POST":
            cmp_name = request.POST.get('company_name').strip()
            cmp_description = request.POST.get('company_description').strip()
            cmp_cluster = request.POST.get('company_cluster')
            cmp_sector = request.POST.get('company_sector')

            continuar = True
            if cmp_name == '':
                message = "El nombre de la empresa no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(cmp_name):
                message = "El nombre de la empresa contiene caracteres inválidos"
                type = "n_notif"
                cmp_name = ""
                continuar = False

            if cmp_cluster == '':
                message = "La empresa debe pertenencer a un grupo de empresas"
                type = "n_notif"
                continuar = False

            if cmp_sector == '':
                message = "La empresa debe pertenencer a un sector"
                type = "n_notif"
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if company_clusters[0].company.company_name != cmp_name:
                companyValidate = Company.objects.filter(company_name=cmp_name)
                if companyValidate:
                    message = "Ya existe una empresa con ese nombre"
                    type = "n_notif"
                    continuar = False

            post = {'cmp_id': company_clusters[0].company.id,
                    'cmp_name': cmp_name, 'cmp_description': cmp_description,
                    'cmp_cluster': int(cmp_cluster),
                    'cmp_sector': int(cmp_sector),
                    'cmp_logo': company_clusters[0].company.company_logo}

            if continuar:
                #Actualiza la empresa
                companyObj = Company.objects.get(
                    pk=company_clusters[0].company.pk)
                companyObj.company_name = cmp_name
                companyObj.company_description = cmp_description
                #Se obtiene el objeto del sector
                sectorObj = SectoralType.objects.get(pk=cmp_sector)
                companyObj.sectoral_type = sectorObj
                companyObj.save()

                #Se relaciona la empresa con el cluster
                ComCluster = ClusterCompany.objects.get(
                    pk=company_clusters[0].pk)
                ComCluster.delete()

                #Se obtiene el objeto del cluster
                clusterObj = Cluster.objects.get(pk=cmp_cluster)
                newCompanyCluster = ClusterCompany(
                    cluster=clusterObj,
                    company=companyObj
                )
                newCompanyCluster.save()

                #Guarda la foto
                if 'logo' in request.FILES:
                    handle_company_logo(request.FILES['logo'], companyObj,
                                        False)

                message = "Empresa editada exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver empresas") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/empresas?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             company=request.session['company'],
                             post=post,
                             operation="edit",
                             message=message,
                             clusters=clusters,
                             sectors=sectors,
                             type=type, sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_company.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_companies(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW,
                      "Ver empresas") or request.user.is_superuser:
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
            lista = ClusterCompany.objects.filter(
                Q(company__company_name__icontains=request.GET['search']) | Q(
                    company__company_description__icontains=request.GET[
                                                            'search']) | Q(
                    cluster__cluster_name__icontains=request.GET['search']) | Q(
                    company__sectoral_type__sectorial_type_name__icontains=
                    request.GET['search'])).exclude(
                company__company_status=2).order_by(order)

        else:
            lista = ClusterCompany.objects.all().exclude(
                company__company_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_company=order_company,
                             order_cluster=order_cluster,
                             order_sector=order_sector,
                             order_status=order_status,
                             datacontext=datacontext, empresa=empresa,
                             company=request.session['company'],
                             sidebar=request.session['sidebar'])
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
            "consumption_centers/buildings/companies.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_batch_companies(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, DELETE,
                      "Baja de empresas") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^cmpy_\w+', key):
                    r_id = int(key.replace("cmpy_", ""))
                    cpy_obj = get_object_or_404(Company, pk=r_id)
                    if cpy_obj.company_status == 0:
                        cpy_obj.company_status = 1
                    elif cpy_obj.company_status == 1:
                        cpy_obj.company_status = 0
                    cpy_obj.save()

            mensaje = "Las empresas seleccionadas han cambiado su estatus correctamente"
            return HttpResponseRedirect("/buildings/empresas/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/empresas/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_company(request, id_cpy):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar empresas") or request.user.is_superuser:
        company = get_object_or_404(Company, pk=id_cpy)
        if company.company_status == 0:
            company.company_status = 1
            str_status = "Activo"
        else: #if company.company_status == 1:
            company.company_status = 0
            str_status = "Inactivo"

        company.save()
        mensaje = "El estatus de la empresa " + company.company_name + " ha cambiado a " + str_status
        type = "n_success"

        return HttpResponseRedirect("/buildings/empresas/?msj=" + mensaje +
                                    "&ntype=" + type)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def see_company(request, id_cpy):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW,
                      "Ver empresas") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        company_cluster_objs = ClusterCompany.objects.filter(company__pk=id_cpy)
        company = company_cluster_objs[0]

        template_vars = dict(
            datacontext=datacontext,
            companies=company,
            company=request.session['company'],
            empresa=empresa, sidebar=request.session['sidebar'])

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/see_company.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def c_center_structures(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW,
                      "Ver empresas") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']

        clustersObjs = Cluster.objects.all()
        visualizacion = "<div class='hierarchy_container'>"
        for clst in clustersObjs:
            visualizacion += "<div class='hrchy_cluster'><span class='hrchy_cluster_label'>" + clst.cluster_name + "</span>"
            companiesObjs = ClusterCompany.objects.filter(cluster=clst)
            visualizacion += "<div>"
            for comp in companiesObjs:
                visualizacion += "<div class='hrchy_company'><span class='hrchy_company_label'>" + comp.company.company_name + "</span>"
                buildingsObjs = CompanyBuilding.objects.filter(company=comp)
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
            visualizacion=visualizacion,
            empresa=empresa, company=request.session['company'],
            sidebar=request.session['sidebar'])

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/c_centers_structure.html",
            template_vars_template)

    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


###############
#Building Type#
###############


def add_buildingtype(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE,
                      "Alta de tipos de edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''
        message = ""
        type = ""
        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             company=company,
                             post=post, sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            btype_name = request.POST.get('btype_name').strip()
            btype_description = request.POST.get('btype_description').strip()

            continuar = True
            if btype_name == '':
                message = "El nombre del Tipo de Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(btype_name):
                message = "El nombre del Tipo de Edificio contiene caracteres inválidos"
                type = "n_notif"
                btype_name = ""
                continuar = False

            #Valida por si le da muchos clics al boton
            b_typeValidate = BuildingType.objects.filter(
                building_type_name=btype_name)
            if b_typeValidate:
                message = "Ya existe un Tipo de Edificio con ese nombre"
                type = "n_notif"
                continuar = False

            post = {'btype_name': btype_name,
                    'btype_description': btype_description}

            if continuar:
                newBuildingType = BuildingType(
                    building_type_name=btype_name,
                    building_type_description=btype_description
                )
                newBuildingType.save()

                template_vars[
                "message"] = "Tipo de Edificio creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver empresas") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_edificios?msj=" +
                        template_vars["message"] +
                        "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_buildingtype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def edit_buildingtype(request, id_btype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar tipo de edificio") or request.user.is_superuser:
        building_type = BuildingType.objects.get(id=id_btype)

        post = {'btype_name': building_type.building_type_name,
                'btype_description': building_type.building_type_description}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        type = ''

        if request.method == "POST":
            btype_name = request.POST.get('btype_name')
            btype_description = request.POST.get('btype_description')

            continuar = True
            if btype_name == '':
                message = "El nombre del Tipo de Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(btype_name):
                message = "El nombre del Tipo de Edificio contiene caracteres inválidos"
                type = "n_notif"
                btype_name = ""
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if building_type.building_type_name != btype_name:
                #Valida por si le da muchos clics al boton
                b_typeValidate = BuildingType.objects.filter(
                    building_type_name=btype_name)
                if b_typeValidate:
                    message = "Ya existe un Tipo de Edificio con ese nombre"
                    type = "n_notif"
                    continuar = False

            post = {'btype_name': btype_name,
                    'btype_description': btype_description}

            if continuar:
                building_type.building_type_name = btype_name
                building_type.building_type_description = btype_description
                building_type.save()

                message = "Tipo de Edificio editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver tipos de edificios") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_edificios?msj=" +
                        message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             company=company,
                             post=post,
                             operation="edit",
                             message=message,
                             type=type, sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_buildingtype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_buildingtypes(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW,
                      "Ver tipos de edificios") or request.user.is_superuser:
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
            lista = BuildingType.objects.filter(
                Q(building_type_name__icontains=request.GET['search']) | Q(
                    building_type_description__icontains=request.GET[
                                                         'search'])).exclude(
                building_type_status=2).order_by(order)

        else:
            lista = BuildingType.objects.all().exclude(
                building_type_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_description=order_description,
                             order_status=order_status,
                             datacontext=datacontext, empresa=empresa,
                             company=company,
                             sidebar=request.session['sidebar'])
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
            "consumption_centers/buildings/buildingtype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_batch_buildingtypes(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar tipo de edificio") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^btype_\w+', key):
                    r_id = int(key.replace("btype_", ""))
                    btype_obj = get_object_or_404(BuildingType, pk=r_id)
                    if btype_obj.building_type_status == 0:
                        btype_obj.building_type_status = 1
                    elif btype_obj.building_type_status == 1:
                        btype_obj.building_type_status = 0
                    btype_obj.save()

            mensaje = "Los tipos de edificios han cambiado su estatus correctamente"
            return HttpResponseRedirect(
                "/buildings/tipos_edificios/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/tipos_edificios/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_buildingtype(request, id_btype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar tipo de edificio") or request.user.is_superuser:
        building_type = get_object_or_404(BuildingType, pk=id_btype)
        if building_type.building_type_status == 0:
            building_type.building_type_status = 1
            str_status = "Activo"
        else: #if building_type.building_type_status == 1:
            building_type.building_type_status = 0
            str_status = "Inactivo"

        building_type.save()
        mensaje = "El estatus del tipo de edificio " + building_type.building_type_name + " ha cambiado a " + str_status
        type = "n_success"

        return HttpResponseRedirect(
            "/buildings/tipos_edificios/?msj=" + mensaje +
            "&ntype=" + type)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


###############
#Sectoral Type#
###############


def add_sectoraltype(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE,
                      "Alta de sectores") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             company=company,
                             post=post, sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            message = ''
            type = ''
            stype_name = request.POST.get('stype_name')
            stype_description = request.POST.get('stype_description')

            continuar = True
            if stype_name == '':
                message = "El nombre del tipo de sector no puede quedar vacío"
                type = "n_notif"
                continuar = False

            if not variety.validate_string(stype_name):
                message = "El nombre del tipo de sector contiene caracteres inválidos"
                type = "n_notif"
                stype_name = ""
                continuar = False

            #Valida por si le da muchos clics al boton
            sectorValidate = SectoralType.objects.filter(
                sectorial_type_name=stype_name)
            if sectorValidate:
                message = "Ya existe un tipo de sector con ese nombre"
                type = "n_notif"
                continuar = False

            post = {'stype_name': stype_name,
                    'stype_description': stype_description}

            if continuar:
                newSectoralType = SectoralType(
                    sectorial_type_name=stype_name,
                    sectoral_type_description=stype_description
                )
                newSectoralType.save()

                template_vars["message"] = "Tipo de Sector creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver tipos de sectores") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_sectores?msj=" +
                        template_vars["message"] +
                        "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_sectoraltype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def edit_sectoraltype(request, id_stype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de sectores") or request.user.is_superuser:
        sectoral_type = SectoralType.objects.get(id=id_stype)

        post = {'stype_name': sectoral_type.sectorial_type_name,
                'stype_description': sectoral_type.sectoral_type_description}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        type = ''

        if request.method == "POST":
            stype_name = request.POST.get('stype_name')
            stype_description = request.POST.get('stype_description')

            continuar = True
            if stype_name == '':
                message = "El nombre del tipo de sector no puede quedar vacío"
                type = "n_notif"
                continuar = False

            if not variety.validate_string(stype_name):
                message = "El nombre del tipo de sector contiene caracteres inválidos"
                type = "n_notif"
                stype_name = ""
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if sectoral_type.sectorial_type_name != stype_name:
                #Valida por si le da muchos clics al boton
                sectorValidate = SectoralType.objects.filter(
                    sectorial_type_name=stype_name)
                if sectorValidate:
                    message = "Ya existe un tipo de sector con ese nombre"
                    type = "n_notif"
                    continuar = False

            post = {'stype_name': stype_name,
                    'stype_description': stype_description}

            if continuar:
                sectoral_type.sectorial_type_name = stype_name
                sectoral_type.sectoral_type_description = stype_description
                sectoral_type.save()

                message = "Tipo de Sector editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver tipos de sectores") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_sectores?msj=" +
                        message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             company=company,
                             post=post,
                             operation="edit",
                             message=message,
                             type=type, sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_sectoraltype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_sectoraltypes(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW,
                      "Ver tipos de sectores") or request.user.is_superuser:
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
            lista = SectoralType.objects.filter(
                Q(sectorial_type_name__icontains=request.GET['search']) | Q(
                    sectoral_type_description__icontains=request.GET[
                                                         'search'])).exclude(
                sectoral_type_status=2).order_by(order)
        else:
            lista = SectoralType.objects.all().exclude(
                sectoral_type_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_description=order_description,
                             order_status=order_status,
                             datacontext=datacontext, empresa=empresa,
                             company=company,
                             sidebar=request.session['sidebar'])
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
            "consumption_centers/buildings/sectoraltype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_batch_sectoraltypes(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de sectores") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^stype_\w+', key):
                    r_id = int(key.replace("stype_", ""))
                    stype_obj = get_object_or_404(SectoralType, pk=r_id)
                    if stype_obj.sectoral_type_status == 0:
                        stype_obj.sectoral_type_status = 1
                    else:
                        stype_obj.sectoral_type_status = 0
                    stype_obj.save()

            mensaje = "Los tipos de sectores seleccionados han cambiado su estatus correctamente"
            return HttpResponseRedirect(
                "/buildings/tipos_sectores/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/tipos_sectores/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_sectoraltype(request, id_stype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de sectores") or request.user.is_superuser:
        sectoral_type = get_object_or_404(SectoralType, pk=id_stype)
        if sectoral_type.sectoral_type_status == 0:
            sectoral_type.sectoral_type_status = 1
            str_status = "Activo"
        else: #if sectoral_type.sectoral_type_status == 1:
            sectoral_type.sectoral_type_status = 0
            str_status = "Inactivo"

        sectoral_type.save()
        mensaje = "El estatus del sector " + sectoral_type.sectorial_type_name + " ha cambiado a " + str_status
        type = "n_success"

        return HttpResponseRedirect(
            "/buildings/tipos_sectores/?msj=" + mensaje +
            "&ntype=" + type)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


##########################
#Building Attributes Type#
##########################

def add_b_attributes_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE,
                      "Alta de tipos de atributos de edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             company=company,
                             post=post, sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            b_attr_type_name = request.POST.get('b_attr_type_name').strip()
            b_attr_type_description = request.POST.get(
                'b_attr_type_description').strip()
            message = ''
            type = ''

            continuar = True
            if b_attr_type_name == '':
                message = "El nombre del tipo de atributo no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(b_attr_type_name):
                message = "El nombre del Tipo de Atributo contiene caracteres inválidos"
                type = "n_notif"
                b_attr_type_name = ""
                continuar = False

            #Valida por si le da muchos clics al boton
            b_attribute_typeValidate = BuildingAttributesType.objects.filter(
                building_attributes_type_name=b_attr_type_name)
            if b_attribute_typeValidate:
                message = "Ya existe un Tipo de Atributo con ese nombre"
                type = "n_notif"
                continuar = False

            post = {'stype_name': b_attr_type_name,
                    'stype_description': b_attr_type_description}

            if continuar:
                newBuildingAttrType = BuildingAttributesType(
                    building_attributes_type_name=b_attr_type_name,
                    building_attributes_type_description=b_attr_type_description
                )
                newBuildingAttrType.save()

                template_vars[
                "message"] = "Tipo de Atributo de Edificio creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver tipos de atributos") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_atributos_edificios?msj=" +
                        template_vars["message"] +
                        "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_buildingattributetype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def edit_b_attributes_type(request, id_batype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de atributos de edificios") or request.user.is_superuser:
        b_attr_typeObj = BuildingAttributesType.objects.get(id=id_batype)

        post = {'batype_name': b_attr_typeObj.building_attributes_type_name,
                'batype_description': b_attr_typeObj.building_attributes_type_description}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        type = ''

        if request.method == "POST":
            b_attr_type_name = request.POST.get('b_attr_type_name').strip()
            b_attr_type_description = request.POST.get(
                'b_attr_type_description').strip()

            continuar = True
            if b_attr_type_name == '':
                message = "El nombre del tipo de atributo no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(b_attr_type_name):
                message = "El nombre del Tipo de Atributo contiene caracteres inválidos"
                type = "n_notif"
                b_attr_type_name = ""
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if b_attr_typeObj.building_attributes_type_name != b_attr_type_name:
                #Valida por si le da muchos clics al boton
                b_attribute_typeValidate = BuildingAttributesType.objects.filter(
                    building_attributes_type_name=b_attr_type_name)
                if b_attribute_typeValidate:
                    message = "Ya existe un Tipo de Atributo con ese nombre"
                    type = "n_notif"
                    continuar = False

            post = {'batype_name': b_attr_type_name,
                    'batype_description': b_attr_type_description}

            if continuar:
                b_attr_typeObj.building_attributes_type_name = b_attr_type_name
                b_attr_typeObj.building_attributes_type_description = b_attr_type_description
                b_attr_typeObj.save()

                message = "Tipo de Atributo de Edificio editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver tipos de atributos") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_atributos_edificios?msj=" +
                        message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             company=company,
                             post=post,
                             operation="edit",
                             message=message,
                             type=type, sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_buildingattributetype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_b_attributes_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW,
                      "Ver tipos de atributos") or request.user.is_superuser:
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

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "building_attributes_type_status"
                    order_status = "desc"
                else:
                    order = "-building_attributes_type_status"

        if search:
            lista = BuildingAttributesType.objects.filter(Q(
                building_attributes_type_name__icontains=request.GET[
                                                         'search']) | Q(
                building_attributes_type_description__icontains=request.GET[
                                                                'search'])).\
            exclude(building_attributes_type_status=2).order_by(order)
        else:
            lista = BuildingAttributesType.objects.all().exclude(
                building_attributes_type_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_description=order_description,
                             order_status=order_status,
                             datacontext=datacontext, empresa=empresa,
                             company=company,
                             sidebar=request.session['sidebar'])
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
            "consumption_centers/buildings/buildingattributetype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_b_attributes_type(request, id_batype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de atributos de edificios") or request.user.is_superuser:
        b_att_type = get_object_or_404(BuildingAttributesType, pk=id_batype)
        if b_att_type.building_attributes_type_status == 0:
            b_att_type.building_attributes_type_status = 1
            str_status = "Activo"
        else: #if b_att_type.building_attributes_type_status == 1:
            b_att_type.building_attributes_type_status = 0
            str_status = "Inactivo"
        b_att_type.save()

        mensaje = "El estatus del Tipo de Atributo " + b_att_type.building_attributes_type_name + " ha cambiado a " + str_status
        type = "n_success"

        return HttpResponseRedirect(
            "/buildings/tipos_atributos_edificios/?msj=" + mensaje +
            "&ntype=" + type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def status_batch_b_attributes_type(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de atributos de edificios") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^batype_\w+', key):
                    r_id = int(key.replace("batype_", ""))
                    b_att_type = get_object_or_404(BuildingAttributesType,
                                                   pk=r_id)
                    if b_att_type.building_attributes_type_status == 0:
                        b_att_type.building_attributes_type_status = 1
                    elif b_att_type.building_attributes_type_status == 1:
                        b_att_type.building_attributes_type_status = 0
                    b_att_type.save()

            mensaje = "Los Tipos de Atributos seleccionados han cambiado su estatus correctamente"
            return HttpResponseRedirect(
                "/buildings/tipos_atributos_edificios/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/tipos_atributos_edificios/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


#######################
#Part of Building Type#
#######################


def add_partbuildingtype(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE,
                      "Alta de tipos de partes de edificio") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             company=company,
                             post=post, sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            b_part_type_name = request.POST.get('b_part_type_name').strip()
            b_part_type_description = request.POST.get(
                'b_part_type_description').strip()
            message = ''
            type = ''

            continuar = True
            if b_part_type_name == '':
                message = "El nombre del Tipo de Parte de Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(b_part_type_name):
                message = "El nombre del Tipo de Parte de Edificio contiene caracteres inválidos"
                type = "n_notif"
                b_part_type_name = ""
                continuar = False

            #Valida por si le da muchos clics al boton
            partTypeValidate = PartOfBuildingType.objects.filter(
                part_of_building_type_name=b_part_type_name)
            if partTypeValidate:
                message = "Ya existe un Tipo de Parte de Edificio con ese nombre"
                type = "n_notif"
                continuar = False

            post = {'b_part_type_name': b_part_type_name,
                    'b_part_type_description': b_part_type_description}

            if continuar:
                newPartBuildingType = PartOfBuildingType(
                    part_of_building_type_name=b_part_type_name,
                    part_of_building_type_description=b_part_type_description
                )
                newPartBuildingType.save()

                template_vars[
                "message"] = "Tipo de Parte de Edificio creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver tipos de partes de un edificio") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_partes_edificio?msj=" +
                        template_vars["message"] +
                        "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_partbuilding_type.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def edit_partbuildingtype(request, id_pbtype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de atributos de edificios") or request.user.is_superuser:
        building_part_type = PartOfBuildingType.objects.get(id=id_pbtype)

        post = {
            'b_part_type_name': building_part_type.part_of_building_type_name,
            'b_part_type_description': building_part_type.part_of_building_type_description}

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        type = ''

        if request.method == "POST":
            b_part_type_name = request.POST.get('b_part_type_name').strip()
            b_part_type_description = request.POST.get(
                'b_part_type_description').strip()

            continuar = True
            if b_part_type_name == '':
                message = "El nombre del Tipo de Parte de Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if building_part_type.part_of_building_type_name != b_part_type_name:
                #Valida por si le da muchos clics al boton
                partTypeValidate = PartOfBuildingType.objects.filter(
                    part_of_building_type_name=b_part_type_name)
                if partTypeValidate:
                    message = "Ya existe un Tipo de Parte de Edificio con ese nombre"
                    type = "n_notif"
                    continuar = False

            post = {
                'b_part_type_name': building_part_type.part_of_building_type_name,
                'b_part_type_description': building_part_type.part_of_building_type_description}

            if continuar:
                building_part_type.part_of_building_type_name = b_part_type_name
                building_part_type.part_of_building_type_description = b_part_type_description
                building_part_type.save()

                message = "Tipo de Parte de Edificio editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver tipos de partes de un edificio") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_partes_edificio?msj=" +
                        message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             company=company,
                             post=post,
                             operation="edit",
                             message=message,
                             type=type, sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_partbuilding_type.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_partbuildingtype(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW,
                      "Ver tipos de partes de un edificio") or request.user.is_superuser:
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
            lista = PartOfBuildingType.objects.filter(Q(
                part_of_building_type_name__icontains=request.GET[
                                                      'search']) | Q(
                part_of_building_type_description__icontains=request.GET[
                                                             'search'])).exclude(
                part_of_building_type_status=2).\
            order_by(order)
        else:
            lista = PartOfBuildingType.objects.all().exclude(
                part_of_building_type_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_description=order_description,
                             order_status=order_status,
                             datacontext=datacontext, empresa=empresa,
                             company=company,
                             sidebar=request.session['sidebar'])
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
            "consumption_centers/buildings/partofbuildingtype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_batch_partbuildingtype(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de atributos de edificios") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^pb_type_\w+', key):
                    r_id = int(key.replace("pb_type_", ""))
                    part_building_type = get_object_or_404(PartOfBuildingType,
                                                           pk=r_id)
                    if part_building_type.part_of_building_type_status == 0:
                        part_building_type.part_of_building_type_status = 1
                    elif part_building_type.part_of_building_type_status == 1:
                        part_building_type.part_of_building_type_status = 0
                    part_building_type.save()

            mensaje = "Los Tipos de Partes de Edificio han cambiado su estatus correctamente"
            return HttpResponseRedirect(
                "/buildings/tipos_partes_edificio/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/tipos_partes_edificio/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_partbuildingtype(request, id_pbtype):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de atributos de edificios") or request.user.is_superuser:
        part_building_type = get_object_or_404(PartOfBuildingType, pk=id_pbtype)

        if part_building_type.part_of_building_type_status == 0:
            part_building_type.part_of_building_type_status = 1
            str_status = "Activo"
        else: #if part_building_type.part_of_building_type_status == 1:
            part_building_type.part_of_building_type_status = 0
            str_status = "Inactivo"
        part_building_type.save()

        mensaje = "El estatus del tipo de edificio " + part_building_type.part_of_building_type_name + " ha cambiado a " + str_status
        type = "n_success"

        return HttpResponseRedirect(
            "/buildings/tipos_partes_edificio/?msj=" + mensaje +
            "&ntype=" + type)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


##################
#Part of Building#
##################


def add_partbuilding(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE,
                      "Alta de partes de edificio") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        #Se obtienen los tipos de partes de edificios
        tipos_parte = PartOfBuildingType.objects.all().exclude(
            part_of_building_type_status=0).order_by(
            'part_of_building_type_name')

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.all().exclude(
            building_attributes_type_status=0).order_by(
            'building_attributes_type_name')

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             company=company,
                             post=post,
                             tipos_parte=tipos_parte,
                             tipos_atributos=tipos_atributos,
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            b_part_name = request.POST.get('b_part_name').strip()
            b_part_description = request.POST.get('b_part_description').strip()
            b_part_type_id = request.POST.get('b_part_type')
            b_part_building_name = request.POST.get('b_building_name').strip()
            b_part_building_id = request.POST.get('b_building_id')
            b_part_mt2 = request.POST.get('b_part_mt2').strip()
            message = ""
            type = ""

            continuar = True
            if not b_part_name:
                message = "El nombre de la Parte de Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False

            if not b_part_type_id:
                message = "Se debe seleccionar un tipo de parte de edificio"
                type = "n_notif"
                continuar = False

            if not b_part_building_id:
                message = "Se debe seleccionar un edificio ya registrado"
                type = "n_notif"
                continuar = False
            if continuar:
                #Valida por si le da muchos clics al boton
                partValidate = PartOfBuilding.objects.filter(
                    part_of_building_name=b_part_name).filter(
                    part_of_building_type__pk=b_part_type_id).filter(
                    building__pk=b_part_building_id)
                if partValidate:
                    message = "Ya existe una Parte de Edificio con ese nombre, ese tipo de parte y en ese edificio"
                    type = "n_notif"
                    continuar = False

                post = {'b_part_name': b_part_name,
                        'b_part_description': b_part_description,
                        'b_part_building_name': b_part_building_name,
                        'b_part_building_id': b_part_building_id,
                        'b_part_type': int(b_part_type_id),
                        'b_part_mt2': b_part_mt2}

            if continuar:
                #Se obtiene la instancia del edificio
                buildingObj = get_object_or_404(Building, pk=b_part_building_id)

                #Se obtiene la instancia del tipo de parte de edificio
                part_building_type_obj = get_object_or_404(PartOfBuildingType,
                                                           pk=b_part_type_id)

                if not bool(b_part_mt2):
                    b_part_mt2 = '0'
                else:
                    b_part_mt2 = b_part_mt2.replace(",", "")

                newPartBuilding = PartOfBuilding(
                    building=buildingObj,
                    part_of_building_type=part_building_type_obj,
                    part_of_building_name=b_part_name,
                    part_of_building_description=b_part_description,
                    mts2_built=b_part_mt2
                )
                newPartBuilding.save()
                deviceType = ElectricDeviceType.objects.get(electric_device_type_name="Total parte de un edificio")
                newConsumerUnit = ConsumerUnit(
                    building = buildingObj,
                    part_of_building = newPartBuilding,
                    electric_device_type = deviceType,
                    profile_powermeter = VIRTUAL_PROFILE
                )
                newConsumerUnit.save()
                #Add the consumer_unit instance for the DW
                datawarehouse_run.delay(
                    fill_instants=None,
                    fill_intervals=None,
                    _update_consumer_units=True,
                    populate_instant_facts=None,
                    populate_interval_facts=None
                )

                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')
                        #Se obtiene el objeto tipo de atributo
                        #attribute_type_obj = BuildingAttributesType.objects.get(pk = atr_value_arr[0])
                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(
                            pk=atr_value_arr[1])

                        newBldPartAtt = BuilAttrsForPartOfBuil(
                            part_of_building=newPartBuilding,
                            building_attributes=attribute_obj,
                            building_attributes_value=atr_value_arr[2]
                        )
                        newBldPartAtt.save()

                template_vars[
                "message"] = "Parte de Edificio creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver partes de un edificio") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/partes_edificio?msj=" +
                        template_vars["message"] +
                        "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_partbuilding.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def edit_partbuilding(request, id_bpart):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar partes de un edificio") or request.user.is_superuser:
        #Se obtienen los tipos de partes de edificios
        tipos_parte = PartOfBuildingType.objects.all().exclude(
            part_of_building_type_status=0).order_by(
            'part_of_building_type_name')

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.all().exclude(
            building_attributes_type_status=0).order_by(
            'building_attributes_type_name')

        building_part = get_object_or_404(PartOfBuilding, pk=id_bpart)

        #Se obtienen todos los atributos
        building_part_attributes = BuilAttrsForPartOfBuil.objects.filter(
            part_of_building=building_part)
        string_attributes = ''
        if building_part_attributes:
            for bp_att in building_part_attributes:
                string_attributes += '<div  class="extra_attributes_div"><span class="delete_attr_icon"><a href="#eliminar" class="delete hidden_icon" ' +\
                                     'title="eliminar atributo"></a></span>' +\
                                     '<span class="tip_attribute_part">' +\
                                     bp_att.building_attributes.building_attributes_type.building_attributes_type_name +\
                                     '</span>' +\
                                     '<span class="attribute_part">' +\
                                     bp_att.building_attributes.building_attributes_name +\
                                     '</span>' +\
                                     '<span class="attribute_value_part">' +\
                                     str(bp_att.building_attributes_value) +\
                                     '</span>' +\
                                     '<input type="hidden" name="atributo_' + str(
                    bp_att.building_attributes.building_attributes_type.pk) +\
                                     '_' + str(
                    bp_att.building_attributes.pk) + '" ' +\
                                     'value="' + str(
                    bp_att.building_attributes.building_attributes_type.pk) + ',' + str(
                    bp_att.building_attributes.pk) + ',' + str(
                    bp_att.building_attributes_value) +\
                                     '"/></div>'

        post = {'b_part_name': building_part.part_of_building_name,
                'b_part_description': building_part.part_of_building_description,
                'b_part_building_name': building_part.building.building_name,
                'b_part_building_id': str(building_part.building.pk),
                'b_part_type': building_part.part_of_building_type.id,
                'b_part_mt2': building_part.mts2_built,
                'b_part_attributes': string_attributes,
        }

        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        type = ''

        if request.method == "POST":
            b_part_name = request.POST.get('b_part_name').strip()
            b_part_description = request.POST.get('b_part_description').strip()
            b_part_type_id = request.POST.get('b_part_type')
            b_part_building_name = request.POST.get('b_building_name').strip()
            b_part_building_id = request.POST.get('b_building_id')
            b_part_mt2 = request.POST.get('b_part_mt2').strip()

            if not bool(b_part_mt2):
                b_part_mt2 = '0'
            else:
                b_part_mt2 = b_part_mt2.replace(",", "")

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

            if building_part.part_of_building_name != b_part_name and building_part.building_id != b_part_building_id and building_part.part_of_building_type_id != b_part_type_id:
                #Valida por si le da muchos clics al boton
                partValidate = PartOfBuilding.objects.filter(
                    part_of_building_name=b_part_name).filter(
                    part_of_building_type__pk=b_part_type_id).filter(
                    building__pk=b_part_building_id)
                if partValidate:
                    message = "Ya existe una Parte de Edificio con ese nombre, ese tipo de parte y en ese edificio"
                    type = "n_notif"
                    continuar = False

            post = {'b_part_name': b_part_name,
                    'b_part_description': b_part_description,
                    'b_part_building_name': b_part_building_name,
                    'b_part_building_id': b_part_building_id,
                    'b_part_type': int(b_part_type_id),
                    'b_part_mt2': b_part_mt2}

            if continuar:
                #Se obtiene la instancia del edificio
                buildingObj = get_object_or_404(Building, pk=b_part_building_id)

                #Se obtiene la instancia del tipo de parte de edificio
                part_building_type_obj = get_object_or_404(PartOfBuildingType,
                                                           pk=b_part_type_id)

                building_part.building = buildingObj
                building_part.part_of_building_name = b_part_name
                building_part.part_of_building_description = b_part_description
                building_part.part_of_building_type = part_building_type_obj
                building_part.mts2_built = b_part_mt2
                building_part.save()

                #Se eliminan todos los atributos existentes
                builAttrsElim = BuilAttrsForPartOfBuil.objects.filter(
                    part_of_building=building_part)
                builAttrsElim.delete()

                #Se insertan los nuevos
                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')

                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(
                            pk=atr_value_arr[1])

                        newBldPartAtt = BuilAttrsForPartOfBuil(
                            part_of_building=building_part,
                            building_attributes=attribute_obj,
                            building_attributes_value=atr_value_arr[2]
                        )
                        newBldPartAtt.save()

                message = "Parte de Edificio editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver partes de un edificio") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/partes_edificio?msj=" +
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
                             type=type, sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_partbuilding.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_partbuilding(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW,
                      "Ver partes de un edificio") or request.user.is_superuser:
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
        order_status = 'asc'
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

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "part_of_building_status"
                    order_status = "desc"
                else:
                    order = "-part_of_building_status"
                    order_status = "asc"

        if search:
            lista = PartOfBuilding.objects.filter(
                Q(part_of_building_name__icontains=request.GET['search']) | Q(
                    part_of_building_type__part_of_building_type_name__icontains=
                    request.GET['search']) | Q(
                    building__building_name__icontains=request.GET[
                                                       'search'])).order_by(
                order)
        else:
            lista = PartOfBuilding.objects.all().order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_type=order_type,
                             order_building=order_building,
                             order_status=order_status,
                             datacontext=datacontext, empresa=empresa,
                             company=company,
                             sidebar=request.session['sidebar'])
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
            "consumption_centers/buildings/partofbuilding.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_batch_partofbuilding(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar partes de un edificio") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^pb_\w+', key):
                    r_id = int(key.replace("pb_", ""))
                    building_part = get_object_or_404(PartOfBuilding, pk=r_id)

                    if building_part.part_of_building_status == 0:
                        building_part.part_of_building_status = 1
                    elif building_part.part_of_building_status == 1:
                        building_part.part_of_building_status = 0

                    building_part.save()

            mensaje = "Las partes de edificios han cambiado su estatus correctamente"
            return HttpResponseRedirect(
                "/buildings/partes_edificio/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/partes_edificio/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def status_partofbuilding(request, id_bpart):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar partes de un edificio") or request.user.is_superuser:
        building_part = get_object_or_404(PartOfBuilding, pk=id_bpart)

        if building_part.part_of_building_status == 0:
            building_part.part_of_building_status = 1
            str_status = "activo"
        else: #if building_part.part_of_building_status == 1:
            building_part.part_of_building_status = 0
            str_status = "inactivo"

        building_part.save()

        mensaje = "El estatus de la parte de edificio " + \
                  building_part.part_of_building_name + " ha cambiado a " + \
                  str_status
        type = "n_success"

        return HttpResponseRedirect(
            "/buildings/partes_edificio/?msj=" + mensaje +
            "&ntype=" + type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def search_buildings(request):
    """ recieves three parameters in request.GET:
    term = string, the name of the building to search
    perm = string, the complete name of the operation we want to check if the user has permission
    op = string, the operation to check the permission (view, create, update, delete)
    """

    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if "term" in request.GET and "perm" in request.GET and "op" in request.GET:
        operation = {
            'view': VIEW,
            'create': CREATE,
            'update': UPDATE,
            'delete': DELETE
        }

        op = operation[request.GET['op']]
        term = request.GET['term']
        perm = request.GET['perm']

        buildings = get_all_buildings_for_operation(perm, op, request.user)
        b_pks = [b.pk for b in buildings]
        buildings = Building.objects.filter(building_name__icontains=term,
                                            pk__in=b_pks).exclude(
            building_status=0)
        buildings_arr = []
        for building in buildings:
            buildings_arr.append(
                dict(value=building.building_name, pk=building.pk,
                     label=building.building_name))

        data = simplejson.dumps(buildings_arr)
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404


def get_select_attributes(request, id_attribute_type):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
        #print "ID Att:", id_attribute_type

    building_attributes = BuildingAttributes.objects.filter(
        building_attributes_type__pk=id_attribute_type)
    string_to_return = ''
    if building_attributes:
        for b_attr in building_attributes:
            string_to_return += """<li rel="%s">
                                    %s
                                </li>""" % (
                b_attr.pk, b_attr.building_attributes_name)
    else:
        string_to_return = '<li rel="">Sin atributos</li>'

    return HttpResponse(content=string_to_return, content_type="text/html")


###########
#EDIFICIOS#
###########
def add_building(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, CREATE,
                      "Alta de edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''
        message = ''
        type = ''
        #Se obtienen las empresas
        #empresas_lst = Company.objects.all().exclude(company_status=0).order_by('company_name')
        empresas_lst = get_all_companies_for_operation("Alta de edificios",
                                                       CREATE, request.user)
        #Se obtienen las tarifas
        tarifas = ElectricRates.objects.all()

        #Se obtienen los tipos de edificios
        tipos_edificio_lst = BuildingType.objects.filter(
            building_type_status=1).order_by('building_type_name')

        #Se obtienen las regiones
        regiones_lst = Region.objects.all()

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.filter(
            building_attributes_type_status=1).order_by(
            'building_attributes_type_name')

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             company=company,
                             post=post,
                             empresas_lst=empresas_lst,
                             tipos_edificio_lst=tipos_edificio_lst,
                             tarifas=tarifas,
                             regiones_lst=regiones_lst,
                             tipos_atributos=tipos_atributos,
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            b_name = request.POST.get('b_name').strip()
            b_description = request.POST.get('b_description').strip()
            b_company = request.POST.get('b_company')
            b_type_arr = request.POST.getlist('b_type')
            b_mt2 = request.POST.get('b_mt2').strip()
            b_electric_rate_id = request.POST.get('b_electric_rate')
            b_country_id = request.POST.get('b_country_id')
            b_country_name = request.POST.get('b_country').strip()
            b_state_id = request.POST.get('b_state_id')
            b_state_name = request.POST.get('b_state').strip()
            b_municipality_id = request.POST.get('b_municipality_id')
            b_municipality_name = request.POST.get('b_municipality').strip()
            b_neighborhood_id = request.POST.get('b_neighborhood_id')
            b_neighborhood_name = request.POST.get('b_neighborhood').strip()
            b_street_id = request.POST.get('b_street_id')
            b_street_name = request.POST.get('b_street').strip()
            b_ext = request.POST.get('b_ext').strip()
            b_int = request.POST.get('b_int').strip()
            b_zip = request.POST.get('b_zip').strip()
            b_long = request.POST.get('b_longitude')
            b_lat = request.POST.get('b_latitude')
            b_region_id = request.POST.get('b_region')

            if not bool(b_int):
                b_int = '0'

            if not bool(b_mt2):
                b_mt2 = '0'
            else:
                b_mt2 = b_mt2.replace(",", "")

            continuar = True
            if b_name == '':
                message += "El nombre del Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(b_name):
                message += "El nombre del Edificio contiene caracteres inválidos"
                type = "n_notif"
                b_name = ""
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

            #Valida por si le da muchos clics al boton
            buildingValidate = Building.objects.filter(building_name=b_name)
            if buildingValidate:
                message = "Ya existe un Edificio con ese nombre"
                type = "n_notif"
                continuar = False

            post = {
                'b_name': b_name,
                'b_description': b_description,
                'b_company': int(b_company),
                'b_type_arr': b_type_arr,
                'b_mt2': b_mt2,
                'b_electric_rate_id': int(b_electric_rate_id),
                'b_country_id': b_country_id,
                'b_country': b_country_name,
                'b_state_id': b_state_id,
                'b_state': b_state_name,
                'b_municipality_id': b_municipality_id,
                'b_municipality': b_municipality_name,
                'b_neighborhood_id': b_neighborhood_id,
                'b_neighborhood': b_neighborhood_name,
                'b_street_id': b_street_id,
                'b_street': b_street_name,
                'b_ext': b_ext,
                'b_int': b_int,
                'b_zip': b_zip,
                'b_long': b_long,
                'b_lat': b_lat,
                'b_region_id': int(b_region_id)
            }

            if continuar:
                #se obtiene el objeto de la tarifa
                tarifaObj = get_object_or_404(ElectricRates,
                                              pk=b_electric_rate_id)

                #Se obtiene la compañia
                companyObj = get_object_or_404(Company, pk=b_company)

                #Se obtiene el objeto de la region
                regionObj = get_object_or_404(Region, pk=b_region_id)

                countryObj, stateObj, municipalityObj, neighborhoodObj, \
                streetObj = location_objects(
                    b_country_id, b_country_name,
                    b_state_id, b_state_name, b_municipality_id,
                    b_municipality_name, b_neighborhood_id, b_neighborhood_name,
                    b_street_id, b_street_name)

                #Se crea la cadena con la direccion concatenada
                formatted_address = streetObj.calle_name + " " + b_ext
                if b_int:
                    formatted_address += "-" + b_int
                formatted_address += " Colonia: " + \
                                     neighborhoodObj.colonia_name + " " + \
                                     municipalityObj.municipio_name
                formatted_address += " " + stateObj.estado_name + " " + \
                                     countryObj.pais_name + "C.P." + b_zip

                #Se da de alta el edificio
                newBuilding = Building(
                    building_name=b_name,
                    building_description=b_description,
                    building_formatted_address=formatted_address,
                    pais=countryObj,
                    estado=stateObj,
                    municipio=municipalityObj,
                    colonia=neighborhoodObj,
                    calle=streetObj,
                    region=regionObj,
                    building_external_number=b_ext,
                    building_internal_number=b_int,
                    building_code_zone=b_zip,
                    building_long_address=b_long,
                    building_lat_address=b_lat,
                    electric_rate=tarifaObj,
                    mts2_built=b_mt2,
                )
                newBuilding.save()

                #Se relaciona la compania con el edificio
                newBldComp = CompanyBuilding(
                    company=companyObj,
                    building=newBuilding,
                )
                newBldComp.save()

                #Se dan de alta los tipos de edificio
                for b_type in b_type_arr:
                    #Se obtiene el objeto del tipo de edificio
                    typeObj = get_object_or_404(BuildingType, pk=b_type)
                    newBuildingTypeBuilding = BuildingTypeForBuilding(
                        building=newBuilding,
                        building_type=typeObj,
                        building_type_for_building_name=newBuilding.building_name + " - " + typeObj.building_type_name
                    )
                    newBuildingTypeBuilding.save()

                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')
                        #Se obtiene el objeto tipo de atributo
                        #attribute_type_obj = BuildingAttributesType.objects.get(pk = atr_value_arr[0])
                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(
                            pk=atr_value_arr[1])

                        newBldAtt = BuildingAttributesForBuilding(
                            building=newBuilding,
                            building_attributes=attribute_obj,
                            building_attributes_value=atr_value_arr[2]
                        )
                        newBldAtt.save()

                electric_device_type = ElectricDeviceType.objects.get(electric_device_type_name="Total Edificio")
                cu =  ConsumerUnit(
                    building=newBuilding,
                    electric_device_type=electric_device_type,
                    profile_powermeter=VIRTUAL_PROFILE
                )
                cu.save()
                #Add the consumer_unit instance for the DW
                datawarehouse_run.delay(
                    fill_instants=None,
                    fill_intervals=None,
                    _update_consumer_units=True,
                    populate_instant_facts=None,
                    populate_interval_facts=None
                )


                template_vars["message"] = "Edificio creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver edificios") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/edificios?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_building.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def edit_building(request, id_bld):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        type = ''

        #Se obtienen las empresas
        #empresas_lst = Company.objects.all().exclude(company_status=0).order_by('company_name')
        empresas_lst = get_all_companies_for_operation("Modificar edificios",
                                                       UPDATE, request.user)

        #Se obtienen las tarifas
        tarifas = ElectricRates.objects.all()

        #Se obtienen los tipos de edificios
        tipos_edificio_lst = BuildingType.objects.filter(
            building_type_status=1).order_by('building_type_name')

        #Se obtienen las regiones
        regiones_lst = Region.objects.all()

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.filter(
            building_attributes_type_status=1).order_by(
            'building_attributes_type_name')

        #Se obtiene la información del edificio
        buildingObj = get_object_or_404(Building, pk=id_bld)

        #Se obtiene la compañia
        companyBld = CompanyBuilding.objects.filter(building=buildingObj)

        #Se obtienen los tipos de edificio
        b_types = BuildingTypeForBuilding.objects.filter(building=buildingObj)
        b_type_arr = [b_tp.building_type.pk for b_tp in b_types]

        #Se obtienen todos los atributos
        building_attributes = BuildingAttributesForBuilding.objects.filter(
            building=buildingObj)
        string_attributes = ''
        if building_attributes:
            for bp_att in building_attributes:
                string_attributes += '<div  class="extra_attributes_div">' \
                                     '<span class="delete_attr_icon">' \
                                     '<a href="#eliminar" class="delete hidden_icon" ' +\
                                     'title="eliminar atributo"></a></span>' +\
                                     '<span class="tip_attribute_part">' +\
                                     bp_att.building_attributes.building_attributes_type.building_attributes_type_name +\
                                     '</span>' +\
                                     '<span class="attribute_part">' +\
                                     bp_att.building_attributes.building_attributes_name +\
                                     '</span>' +\
                                     '<span class="attribute_value_part">' +\
                                     str(bp_att.building_attributes_value) +\
                                     '</span>' +\
                                     '<input type="hidden" name="atributo_' + str(
                    bp_att.building_attributes.building_attributes_type.pk) +\
                                     '_' + str(
                    bp_att.building_attributes.pk) + '" ' +\
                                     'value="' + str(
                    bp_att.building_attributes.building_attributes_type.pk) + ',' + str(
                    bp_att.building_attributes.pk) + ',' + str(
                    bp_att.building_attributes_value) +\
                                     '"/></div>'

        post = {
            'b_name': buildingObj.building_name,
            'b_description': buildingObj.building_description,
            'b_company': companyBld[0].company.pk,
            'b_type_arr': b_type_arr,
            'b_mt2': buildingObj.mts2_built,
            'b_electric_rate_id': buildingObj.electric_rate.pk,
            'b_country_id': buildingObj.pais_id,
            'b_country': buildingObj.pais.pais_name,
            'b_state_id': buildingObj.estado_id,
            'b_state': buildingObj.estado.estado_name,
            'b_municipality_id': buildingObj.municipio_id,
            'b_municipality': buildingObj.municipio.municipio_name,
            'b_neighborhood_id': buildingObj.colonia_id,
            'b_neighborhood': buildingObj.colonia.colonia_name,
            'b_street_id': buildingObj.calle_id,
            'b_street': buildingObj.calle.calle_name,
            'b_ext': buildingObj.building_external_number,
            'b_int': buildingObj.building_internal_number,
            'b_zip': buildingObj.building_code_zone,
            'b_long': buildingObj.building_long_address,
            'b_lat': buildingObj.building_lat_address,
            'b_region_id': buildingObj.region_id,
            'b_attributes': string_attributes
        }

        if request.method == "POST":
            b_name = request.POST.get('b_name').strip()
            b_description = request.POST.get('b_description').strip()
            b_company = request.POST.get('b_company').strip()
            b_type_arr = request.POST.getlist('b_type')
            b_mt2 = request.POST.get('b_mt2').strip()
            b_electric_rate_id = request.POST.get('b_electric_rate')
            b_country_id = request.POST.get('b_country_id')
            b_state_id = request.POST.get('b_state_id')
            b_municipality_id = request.POST.get('b_municipality_id')
            b_neighborhood_id = request.POST.get('b_neighborhood_id')
            b_street_id = request.POST.get('b_street_id')
            b_ext = request.POST.get('b_ext').strip()
            b_int = request.POST.get('b_int').strip()
            b_zip = request.POST.get('b_zip').strip()
            b_long = request.POST.get('b_longitude')
            b_lat = request.POST.get('b_latitude')
            b_region_id = request.POST.get('b_region')

            continuar = True
            if b_name == '':
                message = "El nombre del Edificio no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(b_name):
                message = "El nombre del Edificio contiene caracteres inválidos"
                type = "n_notif"
                b_name = ""
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

            #Valida el nombre (para el caso de los repetidos)

            if buildingObj.building_name != b_name:
                #Valida por si le da muchos clics al boton
                buildingValidate = Building.objects.filter(building_name=b_name)
                if buildingValidate:
                    message = "Ya existe un Edificio con ese nombre"
                    type = "n_notif"
                    continuar = False

            post = {
                'b_name': buildingObj.building_name,
                'b_description': buildingObj.building_description,
                'b_company': companyBld[0].company.pk,
                'b_type_arr': b_type_arr, 'b_mt2': buildingObj.mts2_built,
                'b_electric_rate_id': buildingObj.electric_rate.pk,
                'b_country_id': buildingObj.pais_id,
                'b_country': buildingObj.pais.pais_name,
                'b_state_id': buildingObj.estado_id,
                'b_state': buildingObj.estado.estado_name,
                'b_municipality_id': buildingObj.municipio_id,
                'b_municipality': buildingObj.municipio.municipio_name,
                'b_neighborhood_id': buildingObj.colonia_id,
                'b_neighborhood': buildingObj.colonia.colonia_name,
                'b_street_id': buildingObj.calle_id,
                'b_street': buildingObj.calle.calle_name,
                'b_ext': buildingObj.building_external_number,
                'b_int': buildingObj.building_internal_number,
                'b_zip': buildingObj.building_code_zone,
                'b_long': buildingObj.building_long_address,
                'b_lat': buildingObj.building_lat_address,
                'b_region_id': buildingObj.region_id
            }

            if continuar:
                #se obtiene el objeto de la tarifa
                tarifaObj = get_object_or_404(ElectricRates,
                                              pk=b_electric_rate_id)

                #Se obtiene la compañia
                companyObj = get_object_or_404(Company, pk=b_company)

                #Se obtiene el objeto de la region
                regionObj = get_object_or_404(Region, pk=b_region_id)

                countryObj, stateObj, municipalityObj, neighborhoodObj, \
                streetObj = location_objects(
                    b_country_id, request.POST.get('b_country'),
                    b_state_id, request.POST.get('b_state'), b_municipality_id,
                    request.POST.get('b_municipality'), b_neighborhood_id,
                    request.POST.get('b_neighborhood'),
                    b_street_id, request.POST.get('b_street'))

                #Se crea la cadena con la direccion concatenada
                formatted_address = streetObj.calle_name + " " + b_ext
                if b_int:
                    formatted_address += "-" + b_int
                formatted_address += " Colonia: " + \
                                     neighborhoodObj.colonia_name + " " + \
                                     municipalityObj.municipio_name
                formatted_address += " " + stateObj.estado_name + " " + \
                                     countryObj.pais_name + "C.P." + b_zip
                if b_mt2 == '':
                    b_mt2 = 0
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
                bld_comp = CompanyBuilding.objects.filter(building=buildingObj)
                bld_comp.delete()

                #Se relaciona la compania con el edificio
                newBldComp = CompanyBuilding(
                    company=companyObj,
                    building=buildingObj,
                )
                newBldComp.save()

                #Se eliminan todas las relaciones edificio - tipo
                bld_type = BuildingTypeForBuilding.objects.filter(
                    building=buildingObj)
                bld_type.delete()

                #Se dan de alta los tipos de edificio
                for b_type in b_type_arr:
                    #Se obtiene el objeto del tipo de edificio
                    typeObj = get_object_or_404(BuildingType, pk=b_type)
                    b_name = buildingObj.building_name + " - " + \
                             typeObj.building_type_name
                    newBuildingTypeBuilding = BuildingTypeForBuilding(
                        building=buildingObj,
                        building_type=typeObj,
                        building_type_for_building_name=b_name
                    )
                    newBuildingTypeBuilding.save()

                #Se eliminan los atributos del edificio y se dan de alta los nuevos

                oldAtttributes = BuildingAttributesForBuilding.objects.filter(
                    building=buildingObj)
                oldAtttributes.delete()

                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')
                        #Se obtiene el objeto tipo de atributo
                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(
                            pk=atr_value_arr[1])

                        newBldAtt = BuildingAttributesForBuilding(
                            building=buildingObj,
                            building_attributes=attribute_obj,
                            building_attributes_value=atr_value_arr[2]
                        )
                        newBldAtt.save()

                message = "Edificio editado exitosamente"
                type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver edificios") or request.user.is_superuser:
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
                             type=type, sidebar=request.session['sidebar']
        )

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_building.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_building(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, VIEW,
                      "Ver edificios") or request.user.is_superuser:
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
            lista = CompanyBuilding.objects.filter(
                Q(building__building_name__icontains=request.GET['search']) | Q(
                    building__estado__estado_name__icontains=request.GET[
                                                             'search']) | Q(
                    building__municipio__municipio_name__icontains=request.GET[
                                                                   'search']) | Q(
                    company__company_name__icontains=request.GET[
                                                     'search'])).exclude(
                building__building_status=2).order_by(order)

        else:
            lista = CompanyBuilding.objects.all().exclude(
                building__building_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_state=order_state,
                             order_municipality=order_municipality,
                             order_company=order_company,
                             order_status=order_status,
                             datacontext=datacontext, empresa=empresa,
                             company=company,
                             sidebar=request.session['sidebar'])
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
        return render_to_response("consumption_centers/buildings/building.html",
                                  template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def status_batch_building(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar edificios") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^bld_\w+', key):
                    r_id = int(key.replace("bld_", ""))
                    building = get_object_or_404(Building, pk=r_id)
                    if building.building_status == 0:
                        building.building_status = 1
                    elif building.building_status == 1:
                        building.building_status = 0
                    building.save()

            mensaje = "Los Edificios han cambiado su estatus correctamente"
            return HttpResponseRedirect("/buildings/edificios/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/edificios/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)
        context = {}
        if datacontext:
            context = {"datacontext": datacontext}
        return render_to_response("generic_error.html",
                                  RequestContext(request, context))


def status_building(request, id_bld):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if has_permission(request.user, UPDATE,
                      "Modificar edificios") or request.user.is_superuser:
        building = get_object_or_404(Building, pk=id_bld)

        if building.building_status == 0:
            building.building_status = 1
            str_status = "Activo"
        else: #if building.building_status == 1:
            building.building_status = 0
            str_status = "Inactivo"

        building.save()

        mensaje = "El estatus del edificio " + building.building_name + \
                  " ha cambiado a " + str_status
        type = "n_success"

        return HttpResponseRedirect("/buildings/edificios/?msj=" + mensaje +
                                    "&ntype=" + type)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

####################################################
#          CONSUMER UNITS
####################################################

@login_required(login_url='/')
def add_ie(request):
    datacontext = get_buildings_context(request.user)
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']

    if has_permission(request.user, CREATE,
                      "Alta de equipos industriales") or request.user.is_superuser:
        if request.method == 'POST':
            template_vars["post"] = request.POST
            ie = IndustrialEquipment(
                alias=request.POST['ie_alias'].strip(),
                description=request.POST['ie_desc'].strip(),
                server=request.POST['ie_server'].strip()
                )
            ie.save()
            message = "El equipo industrial se ha creado exitosamente"
            type = "n_success"
            if has_permission(request.user, VIEW,
                              "Ver equipos industriales") or request.user.is_superuser:
                return HttpResponseRedirect("/buildings/industrial_equipments?msj=" +
                                            message +
                                            "&ntype=" + type)
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/consumer_units/ind_eq.html", template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def edit_ie(request, id_ie):
    datacontext = get_buildings_context(request.user)
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']
    template_vars["operation"] = "edit"
    industrial_eq = get_object_or_404(IndustrialEquipment, pk=int(id_ie))
    template_vars["id_ie"] = id_ie
    if has_permission(request.user, UPDATE,
                      "Modificar equipos industriales") or request.user.is_superuser:
        #Asociated powermeters
        if has_permission(
            request.user,
            CREATE,
            "Asignación de medidores eléctricos a equipos industriales")\
        or request.user.is_superuser:
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
                        order = "-powermeter__powermeter_model__powermeter_brand"
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
                industrial_equipment=industrial_eq).order_by(order)
            template_vars['order_alias'] = order_alias
            template_vars['order_model'] = order_model
            template_vars['order_serial'] = order_serial
            template_vars['order_status'] = order_status
            template_vars['powermeters'] = [pm.powermeter for pm in lista]

            if 'msj' in request.GET:
                template_vars['message'] = request.GET['msj']
                template_vars['msg_type'] = request.GET['ntype']

            template_vars['ver_medidores'] = True
        else:
            template_vars['ver_medidores'] = False

        if request.method == 'POST':

            industrial_eq.alias = request.POST['ie_alias'].strip()
            industrial_eq.description = request.POST['ie_desc'].strip()
            industrial_eq.server = request.POST['ie_server'].strip()
            industrial_eq.save()
            message = "El equipo industrial se ha actualizado exitosamente"
            type = "n_success"
            if has_permission(request.user, VIEW,
                              "Ver equipos industriales") or request.user.is_superuser:
                return HttpResponseRedirect("/buildings/industrial_equipments?msj=" +
                                            message +
                                            "&ntype=" + type)
            template_vars["message"] = message
            template_vars["type"] = type
        template_vars["post"] = dict(ie_alias=industrial_eq.alias,
                                     ie_desc=industrial_eq.description,
                                     ie_server=industrial_eq.server)


        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/consumer_units/ind_eq.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def see_ie(request, id_ie):
    datacontext = get_buildings_context(request.user)
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
                          "Ver medidores eléctricos") or request.user.is_superuser:
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
                        order = "-powermeter__powermeter_model__powermeter_brand"
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
                "Asignación de medidores eléctricos a equipos industriales")\
            or request.user.is_superuser:
                template_vars['show_asign'] = True
            else:
                template_vars['show_asign'] = False


        else:
            template_vars['ver_medidores'] = False
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/consumer_units/see_ie.html",
                                  template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def status_ie(request, id_ie):
    if has_permission(request.user,
                      UPDATE,
                      "Modificar equipos industriales") or\
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
        type = "n_success"

        return HttpResponseRedirect(
            "/buildings/industrial_equipments/?msj=" + mensaje +
            "&ntype=" + type)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def status_batch_ie(request):
    if has_permission(request.user,
                      UPDATE,
                      "Modificar equipos industriales") or\
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

            mensaje = "Los equipos industriales seleccionados han "\
                      "cambiado su estatus correctamente"
            type = "n_success"
        else:
            mensaje = str("No se ha seleccionado una acción").decode("utf-8")
            type = "n_notif"
        return HttpResponseRedirect("/buildings/industrial_equipments/?msj="+
                                    mensaje+"&ntype="+type)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def view_ie(request):
    datacontext = get_buildings_context(request.user)
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
        return render_to_response("consumption_centers/consumer_units/ie_list.html",
                                  template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def search_pm(request):
    """Search for a powermeter wich have an alias or serial number containing
     'term'
     returns a json for jquery automplete
    """
    if "term" in request.GET:
        term = request.GET['term']
        ie_pm = PowermeterForIndustrialEquipment.objects.all()
        pm_in_ie = [ip.powermeter.pk for ip in ie_pm]
        powermeters = Powermeter.objects.exclude(
            pk__in=pm_in_ie
        ).filter(
            Q(powermeter_anotation__icontains=term)|
            Q(powermeter_serial__icontains=term)
        ).filter(status=1)
        medidores = []
        for medidor in powermeters:
            texto = medidor.powermeter_anotation + " - " + medidor.powermeter_serial
            medidores.append(dict(value=texto, pk=medidor.pk, label=texto))
        data = simplejson.dumps(medidores)
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404

@login_required(login_url='/')
def asign_pm(request, id_ie):
    if (not(not has_permission(
        request.user,
        CREATE,
        "Asignación de medidores eléctricos a equipos industriales") and not
    request.user.is_superuser)) and "pm" in request.GET:
        ie = get_object_or_404(IndustrialEquipment, pk=int(id_ie))
        pm = get_object_or_404(Powermeter, pk=int(request.GET['pm']))
        pm_ie = PowermeterForIndustrialEquipment(powermeter=pm,
                                                 industrial_equipment=ie)
        pm_ie.save()
        pm_data = dict(pm=pm.pk,
                       alias=pm.powermeter_anotation,
                       modelo=pm.powermeter_model.powermeter_model,
                       marca=pm.powermeter_model.powermeter_brand,
                       serie=pm.powermeter_serial,
                       status=pm.status)
        data = simplejson.dumps([pm_data])
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404

@login_required(login_url='/')
def detach_pm(request, id_ie):
    if (not(not has_permission(
        request.user,
        UPDATE,
        "Modificar asignaciones de medidores eléctricos a equipos industriales")
            and not request.user.is_superuser)) and "pm" in request.GET:
        pm = get_object_or_404(Powermeter, pk=int(request.GET['pm']))
        ie = get_object_or_404(IndustrialEquipment, pk=int(id_ie))
        PowermeterForIndustrialEquipment.objects.\
        filter(powermeter=pm,industrial_equipment=ie).delete()
        mensaje = "El medidor se ha desvinculado"
        return HttpResponseRedirect("/buildings/editar_ie/" +
                                    id_ie + "/?msj=" + mensaje +
                                    "&ntype=n_success")
    else:
        raise Http404

@login_required(login_url='/')
def configure_ie(request, id_ie):
    datacontext = get_buildings_context(request.user)
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']

    if has_permission(request.user, VIEW,
                      "Ver equipos industriales") or request.user.is_superuser:
        ie = get_object_or_404(IndustrialEquipment, pk=id_ie)
        template_vars['ie'] = ie
        template_vars['last_changed'] = ie.last_changed
        ie_pm = PowermeterForIndustrialEquipment.objects.filter(
            industrial_equipment=ie)
        pms = [pm.powermeter.pk for pm in ie_pm]
        powermeters = ProfilePowermeter.objects.filter(
            pk__in=pms)
        tz = timezone.get_current_timezone()
        if request.method == "POST":
            settings_pm = []
            template_vars['powermeters'] = []
            for pm in powermeters:

                read_time_rate = request.POST['read_time_rate_' + str(pm.pk)]
                send_time_rate = request.POST['send_time_rate_' + str(pm.pk)]
                initial_send_time = request.POST['initial_send_time_h_' +
                                                 str(pm.pk)]
                send_time_duration = request.POST['send_time_duration_' +
                                                  str(pm.pk)]
                pm.read_time_rate = read_time_rate
                pm.send_time_rate = send_time_rate
                h = initial_send_time.split(":")
                hora_ = datetime.time(int(h[0]), int(h[1]))
                hora = variety.convert_to_utc(hora_, tz)
                pm.initial_send_time = hora[0]
                pm.send_time_duration = send_time_duration
                pm.save()
                template_vars['powermeters'].append(
                    dict(pk=pm.pk,
                         anotation=pm.powermeter.powermeter_anotation,
                         read_time_rate=pm.read_time_rate,
                         send_time_rate=pm.send_time_rate,
                         initial_send_time=hora_,
                         send_time_duration=pm.send_time_duration
                        ))

                settings_pm.append(dict(identifier = pm.identifier,
                                        read_time_rate=read_time_rate,
                                        send_time_rate=send_time_rate,
                                        initial_send_time=str(hora[0]),
                                        send_time_duration=send_time_duration
                                        ))
            ie.monitor_time_rate = request.POST['monitor_time_rate']
            ie.check_config_time_rate = request.POST['check_config_time_rate']
            ie.has_new_config = True
            ie.save()
            settings_ie = [dict(monitor_time_rate=ie.monitor_time_rate,
                                check_config_time_rate=ie.check_config_time_rate,
                                powermeters=settings_pm)]
            ie.new_config = simplejson.dumps(settings_ie)
            ie.save()
            template_vars['message'] = "El equipo industrial ha guardado su" \
                                       " configuración correctamente"
            template_vars['msg_type'] = "n_success"
        else:
            template_vars['powermeters'] = []
            for pm in powermeters:
                time = variety.convert_from_utc(pm.initial_send_time, tz)
                template_vars['powermeters'].append(
                    dict(pk=pm.pk,
                         anotation=pm.powermeter.powermeter_anotation,
                         read_time_rate=pm.read_time_rate,
                         send_time_rate=pm.send_time_rate,
                         initial_send_time=time,
                         send_time_duration=pm.send_time_duration
                ))
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/consumer_units/configure_times.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def create_hierarchy(request, id_building):
    datacontext = get_buildings_context(request.user)
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']

    if has_permission(request.user, CREATE,
                      "Alta de jerarquía de partes") or \
       request.user.is_superuser:
        building = get_object_or_404(Building, pk=id_building)
        list = get_hierarchy_list(building, request.user)
        template_vars['list'] = list
        template_vars['building'] = building

        cus = ConsumerUnit.objects.all()
        ids_prof = [cu.profile_powermeter.pk for cu in cus]
        profs = ProfilePowermeter.objects.exclude(
            pk__in=ids_prof).exclude(
            powermeter__powermeter_anotation="No Registrado").exclude(
            powermeter__powermeter_anotation="Medidor Virtual"
        )
        template_vars['electric_devices'] = ElectricDeviceType.objects.all()
        template_vars['prof_pwmeters'] = profs
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/create_hierarchy.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def add_partbuilding_pop(request, id_building):
    if has_permission(request.user, CREATE,
                      "Alta de partes de edificio") or request.user.is_superuser:
        #Se obtienen los tipos de partes de edificios
        tipos_parte = PartOfBuildingType.objects.all().exclude(
            part_of_building_type_status=0).order_by(
            'part_of_building_type_name')

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.all().exclude(
            building_attributes_type_status=0).order_by(
            'building_attributes_type_name')

        template_vars = dict(
                             tipos_parte=tipos_parte,
                             tipos_atributos=tipos_atributos,
                             building = get_object_or_404(Building,
                                                          pk=id_building),
                             operation = "pop_add"
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/popup_add_partbuilding.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def save_add_part_popup(request):
    if (has_permission(
        request.user,
        CREATE,
        "Alta de partes de edificio") or request.user.is_superuser) \
    and request.method == "POST":
        b_part_name = request.POST.get('b_part_name').strip()
        b_part_description = request.POST.get('b_part_description').strip()
        b_part_type_id = request.POST.get('b_part_type')
        b_part_building_id = request.POST.get('b_building_id')
        b_part_mt2 = request.POST.get('b_part_mt2').strip()

        continuar = True
        if not b_part_name and not b_part_type_id and not b_part_building_id:
            continuar = False
        if continuar:
            #Valida por si le da muchos clics al boton
            partValidate = PartOfBuilding.objects.filter(
                part_of_building_name=b_part_name).filter(
                part_of_building_type__pk=b_part_type_id).filter(
                building__pk=b_part_building_id)
            if partValidate:
                return HttpResponse(status=400)
            else:
                #Se obtiene la instancia del edificio
                buildingObj = get_object_or_404(Building, pk=b_part_building_id)

                #Se obtiene la instancia del tipo de parte de edificio
                part_building_type_obj = get_object_or_404(PartOfBuildingType,
                                                           pk=b_part_type_id)

                if not bool(b_part_mt2):
                    b_part_mt2 = '0'
                else:
                    b_part_mt2 = b_part_mt2.replace(",", "")

                newPartBuilding = PartOfBuilding(
                    building=buildingObj,
                    part_of_building_type=part_building_type_obj,
                    part_of_building_name=b_part_name,
                    part_of_building_description=b_part_description,
                    mts2_built=b_part_mt2
                )
                newPartBuilding.save()
                deviceType = ElectricDeviceType.objects.get(electric_device_type_name="Total parte de un edificio")
                newConsumerUnit = ConsumerUnit(
                    building = buildingObj,
                    part_of_building = newPartBuilding,
                    electric_device_type = deviceType,
                    profile_powermeter = VIRTUAL_PROFILE
                )
                newConsumerUnit.save()
                #Add the consumer_unit instance for the DW
                datawarehouse_run.delay(
                    fill_instants=None,
                    fill_intervals=None,
                    _update_consumer_units=True,
                    populate_instant_facts=None,
                    populate_interval_facts=None
                )


                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')
                        #Se obtiene el objeto tipo de atributo
                        #attribute_type_obj = BuildingAttributesType.objects.get(pk = atr_value_arr[0])
                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(
                            pk=atr_value_arr[1])

                        newBldPartAtt = BuilAttrsForPartOfBuil(
                            part_of_building=newPartBuilding,
                            building_attributes=attribute_obj,
                            building_attributes_value=atr_value_arr[2]
                        )
                        newBldPartAtt.save()
                return HttpResponse(content=newConsumerUnit.pk,
                             content_type="text/plain",
                             status=200)
        else:
            return HttpResponse(status=400)
    raise Http404

@login_required(login_url='/')
def add_powermeter_popup(request):
    if has_permission(request.user, CREATE,
                      "Alta de medidor electrico") or request.user.is_superuser:
        pw_models_list = PowermeterModel.objects.all().exclude(
            status=0).order_by("powermeter_brand")
        template_vars = dict(modelos=pw_models_list)

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/popup_add_powermeter.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def save_add_powermeter_popup(request):
    if (has_permission(request.user,
                       CREATE,
                      "Alta de medidor electrico") or
        request.user.is_superuser) and request.method == "POST":

        pw_alias = request.POST.get('pw_alias').strip()
        pw_model = request.POST.get('pw_model')
        pw_serial = request.POST.get('pw_serial').strip()

        continuar = True
        if pw_alias == '':
            continuar = False
        elif not variety.validate_string(pw_alias):
            pw_alias = ""
            continuar = False

        if pw_model == '':
            continuar = False

        if pw_serial == '':
            continuar = False

        #Valida por si le da muchos clics al boton
        pwValidate = Powermeter.objects.filter(
            powermeter_model__pk=pw_model).filter(
            powermeter_serial=pw_serial)
        if pwValidate:
            continuar = False

        if continuar:
            pw_model = PowermeterModel.objects.get(pk=pw_model)

            newPowerMeter = Powermeter(
                powermeter_model=pw_model,
                powermeter_anotation=pw_alias,
                powermeter_serial=pw_serial

            )
            newPowerMeter.save()
            profile = ProfilePowermeter(powermeter=newPowerMeter)
            profile.save()

            return HttpResponse(content=profile.pk,
                                content_type="text/plain",
                                status=200)
        else:
            return HttpResponse(status=400)
    else:
        raise Http404

@login_required(login_url='/')
def add_electric_device_popup(request):
    if has_permission(request.user, CREATE,
                      "Alta de dispositivos y sistemas eléctricos") or \
       request.user.is_superuser:

        template_vars_template = RequestContext(request,
                                                {"operation":"add_popup"})
        return render_to_response(
            "consumption_centers/buildings/popup_add_electric_device.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def save_add_electric_device_popup(request):
    if has_permission(request.user, CREATE,
                      "Alta de dispositivos y sistemas eléctricos") or \
           request.user.is_superuser and request.method == "POST":

        edt_name = request.POST['devicetypename'].strip()
        edt_description = request.POST['devicetypedescription'].strip()

        continuar = True
        if edt_name == '':
            continuar = False
        elif not variety.validate_string(edt_name):
            edt_name = ""
            continuar = False

        #Valida por si le da muchos clics al boton
        b_electric_typeValidate = ElectricDeviceType.objects.filter(
            electric_device_type_name=edt_name)
        if b_electric_typeValidate:
            continuar = False

        if continuar:
            newElectricDeviceType = ElectricDeviceType(
                electric_device_type_name=edt_name,
                electric_device_type_description=edt_description
            )
            newElectricDeviceType.save()

            return HttpResponse(content=newElectricDeviceType.pk,
                                content_type="text/plain",
                                status=200)
        else:
            return HttpResponse(status=400)
    else:
        raise Http404

@login_required(login_url='/')
def add_cu(request):
    if (has_permission(request.user, UPDATE,
                       "Modificar unidades de consumo") or has_permission(
        request.user, CREATE, "Alta de unidades de consumo") or
        request.user.is_superuser) and request.method == "POST":
        post = request.POST
        if post['type_node'] == "1":
            cu = post["node_part"].split("_")
            consumer_unit = get_object_or_404(ConsumerUnit,
                                              pk=int(cu[0]))
            if cu[1] == "cu":
                profile = get_object_or_404(ProfilePowermeter,
                                            pk=int(post['prof_pwr']))
                consumer_unit.profile_powermeter = profile
                consumer_unit.save()
            c_type="*part"
        else:
            profile = get_object_or_404(ProfilePowermeter,
                                        pk=int(post['prof_pwr']))
            building = get_object_or_404(Building, pk=int(post['building']))
            electric_device_type = get_object_or_404(ElectricDeviceType,
                                                     pk=int(post['node_part']))
            consumer_unit = ConsumerUnit(
                building = building,
                electric_device_type = electric_device_type,
                profile_powermeter = profile
            )
            consumer_unit.save()
            #Add the consumer_unit instance for the DW
            datawarehouse_run.delay(
                fill_instants=None,
                fill_intervals=None,
                _update_consumer_units=True,
                populate_instant_facts=None,
                populate_interval_facts=None
            )

        c_type="*consumer_unit"
        content = str(consumer_unit.pk) + c_type
        return HttpResponse(content=content,
                        content_type="text/plain",
                        status=200)
    else:
        raise Http404

@login_required(login_url='/')
def del_cu(request, id_cu):
    if (has_permission(request.user, DELETE,
                       "Eliminar unidades de consumo")  or
        request.user.is_superuser):
        cu = get_object_or_404(ConsumerUnit, pk=int(id_cu))
        cu.delete()
        return HttpResponse(content="",
                            content_type="text/plain",
                            status=200)
    else:
        raise Http404

@login_required(login_url='/')
def popup_edit_partbuilding(request, cu_id):
    if has_permission(request.user, UPDATE,
                      "Modificar partes de un edificio") or request.user.is_superuser:
        #Se obtienen los tipos de partes de edificios
        tipos_parte = PartOfBuildingType.objects.all().exclude(
            part_of_building_type_status=0).order_by(
            'part_of_building_type_name')

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.all().exclude(
            building_attributes_type_status=0).order_by(
            'building_attributes_type_name')
        cu = get_object_or_404(ConsumerUnit, pk=int(cu_id))

        building_part = cu.part_of_building

        #Se obtienen todos los atributos
        building_part_attributes = BuilAttrsForPartOfBuil.objects.filter(
            part_of_building=building_part)
        string_attributes = ''
        if building_part_attributes:
            for bp_att in building_part_attributes:
                string_attributes += '<div  class="extra_attributes_div"><span class="delete_attr_icon"><a href="#eliminar" class="delete hidden_icon" ' +\
                                     'title="eliminar atributo"></a></span>' +\
                                     '<span class="tip_attribute_part">' +\
                                     bp_att.building_attributes.building_attributes_type.building_attributes_type_name +\
                                     '</span>' +\
                                     '<span class="attribute_part">' +\
                                     bp_att.building_attributes.building_attributes_name +\
                                     '</span>' +\
                                     '<span class="attribute_value_part">' +\
                                     str(bp_att.building_attributes_value) +\
                                     '</span>' +\
                                     '<input type="hidden" name="atributo_' + str(
                    bp_att.building_attributes.building_attributes_type.pk) +\
                                     '_' + str(
                    bp_att.building_attributes.pk) + '" ' +\
                                     'value="' + str(
                    bp_att.building_attributes.building_attributes_type.pk) + ',' + str(
                    bp_att.building_attributes.pk) + ',' + str(
                    bp_att.building_attributes_value) +\
                                     '"/></div>'

        post = {'b_part_name': building_part.part_of_building_name,
                'b_part_description': building_part.part_of_building_description,
                'b_part_building_id': str(building_part.building.pk),
                'b_part_type': building_part.part_of_building_type.id,
                'b_part_mt2': building_part.mts2_built,
                'b_part_attributes': string_attributes,
                }
        template_vars = dict(post=post,
                             tipos_parte=tipos_parte,
                             tipos_atributos=tipos_atributos,
                             operation="pop_edit",
                             building=building_part.building,
                             cu = cu.pk
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/popup_add_partbuilding.html",
            template_vars_template)
    else:
        raise Http404

@login_required(login_url='/')
def save_edit_part_popup(request, cu_id):
    if (has_permission(request.user, UPDATE,
                      "Modificar partes de un edificio") or
        request.user.is_superuser) and request.method == "POST":
        b_part_name = request.POST.get('b_part_name').strip()
        b_part_description = request.POST.get('b_part_description').strip()
        b_part_type_id = request.POST.get('b_part_type')

        b_part_mt2 = request.POST.get('b_part_mt2').strip()

        cu = get_object_or_404(ConsumerUnit, pk=int(cu_id))
        building_part = cu.part_of_building

        if not bool(b_part_mt2):
            b_part_mt2 = '0'
        else:
            b_part_mt2 = b_part_mt2.replace(",", "")

        continuar = True
        if b_part_name == '':
            continuar = False

        if b_part_type_id == '':
            continuar = False

        if continuar:
            #Se obtiene la instancia del tipo de parte de edificio
            part_building_type_obj = get_object_or_404(PartOfBuildingType,
                                                       pk=b_part_type_id)

            building_part.part_of_building_name = b_part_name
            building_part.part_of_building_description = b_part_description
            building_part.part_of_building_type = part_building_type_obj
            building_part.mts2_built = b_part_mt2
            building_part.save()

            #Se eliminan todos los atributos existentes
            builAttrsElim = BuilAttrsForPartOfBuil.objects.filter(
                part_of_building=building_part)
            builAttrsElim.delete()

            #Se insertan los nuevos
            for key in request.POST:
                if re.search('^atributo_\w+', key):
                    atr_value_complete = request.POST.get(key)
                    atr_value_arr = atr_value_complete.split(',')

                    #Se obtiene el objeto atributo
                    attribute_obj = BuildingAttributes.objects.get(
                        pk=atr_value_arr[1])

                    newBldPartAtt = BuilAttrsForPartOfBuil(
                        part_of_building=building_part,
                        building_attributes=attribute_obj,
                        building_attributes_value=atr_value_arr[2]
                    )
                    newBldPartAtt.save()

            return HttpResponse(content=cu.pk,
                                content_type="text/plain",
                                status=200)
        else:
            return HttpResponse(status=400)
    else:
        raise Http404

@login_required(login_url='/')
def edit_cu(request, cu_id):
    if (has_permission(request.user, UPDATE,
                       "Modificar unidades de consumo") or has_permission(
        request.user, CREATE, "Alta de unidades de consumo") or
        request.user.is_superuser) and request.method == "POST":
        post = request.POST

        consumer_unit = get_object_or_404(ConsumerUnit, pk=int(cu_id))

        if post['prof_pwr_edit'] != "0":
            if post['prof_pwr_edit'] == "del_pw":
                profile = VIRTUAL_PROFILE
            else:
                profile = get_object_or_404(ProfilePowermeter,
                                            pk=int(post['prof_pwr_edit']))
            consumer_unit.profile_powermeter = profile

        if post['edit_part'] == "cu":
            if post['node_part_edit'] != "0":
                device_t = get_object_or_404(ElectricDeviceType,
                                             pk=int(post['node_part_edit']))
                consumer_unit.electric_device_type = device_t
        consumer_unit.save()
        return HttpResponse(status=200)
    else:
        raise Http404

@login_required(login_url='/')
def add_hierarchy_node(request):
    if (has_permission(request.user, CREATE,
                      "Alta de jerarquía de partes") or
       request.user.is_superuser) and request.method == "POST":
        parent_cu = get_object_or_404(ConsumerUnit, pk=int(request.POST['pp']))
        parent_part = parent_cu.part_of_building

        pp = True if request.POST['pp'] == "1" else False

        if request.POST['pl'] != '':
            cu_leaf = get_object_or_404(ConsumerUnit,
                                        pk=int(request.POST['pl']))
            part_leaf = cu_leaf.part_of_building

            h = HierarchyOfPart(part_of_building_composite=parent_part,
                                part_of_building_leaf=part_leaf,
                                ExistsPowermeter=pp)
            h.save()
            return HttpResponse(status=200)
        elif request.POST['cl'] != '':
            cu_leaf = get_object_or_404(ConsumerUnit,
                                        pk=int(request.POST['cl']))
            h = HierarchyOfPart(part_of_building_composite=parent_part,
                                consumer_unit_leaf=cu_leaf,
                                ExistsPowermeter=pp)
            h.save()

            return HttpResponse(status=200)
        else:
            raise Http404
    else:
        raise Http404

@login_required(login_url='/')
def reset_hierarchy(request):
    if (has_permission(request.user, UPDATE,
                       "Modificar jerarquía de partes de edificios") or
        request.user.is_superuser) and request.method == "POST":
        building = get_object_or_404(Building, pk=int(request.POST['building']))
        cus = ConsumerUnit.objects.filter(building=building)
        parts = []
        consumer_u = []
        for cu in cus:
            if cu.part_of_building:
                parts.append(cu.part_of_building.pk)
            else:
                consumer_u.append(cu.pk)
        h = HierarchyOfPart.objects.filter(
            Q(part_of_building_composite__pk__in=parts)|
            Q(part_of_building_leaf__pk__in=parts)|
            Q(consumer_unit_composite__pk__in=consumer_u)|
            Q(consumer_unit_leaf__pk__in=consumer_u)
        )
        if h:
            h.delete()
        return HttpResponse(status=200)

    else:
        raise Http404