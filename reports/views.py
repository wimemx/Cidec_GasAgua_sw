#coding:utf-8

# Python imports
import datetime
import logging
import numpy
import time
import sys
import csv
import decimal
import ast
import json

# Django imports
import django.http
import django.shortcuts
import django.utils.timezone
import django.template.context
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models.aggregates import *

# Reports imports
import reports.globals

# CCenter imports
import c_center.models
import c_center.c_center_functions
import c_center.calculations
import c_center.graphics

from c_center.models import  IndustrialEquipment

from gas_agua.models import WaterGasData


from reports.reports_functions import get_data_cluster_consumed_normalized, \
    rates_for_data_cluster, get_request_data_list_normalized, \
    get_column_strings_electrical_parameter, get_column_units_list, \
    get_data_clusters_list, normalize_data_clusters_list,\
    get_data_clusters_json, get_data_statistics, get_data_clusters_list_limits,\
    get_axis_dictionary, get_axis_dictionaries_list, \
    get_column_units_axis_indexes, get_data_cluster_limits, \
    get_data_clusters_statistics, get_series_legends

# Other imports
import variety
from time import mktime
from datetime import timedelta
################################################################################
#
# Render Scripts
#
################################################################################
@login_required(login_url="/")
def render_instant_measurements(
        request
):

    template_variables = {
        'axis_list': None,
        'columns': None,
        'columns_statistics': None,
        'column_units': None,
        'column_unit_axis_indexes': None,
        'max': None,
        'min': None,
        'rows': None
    }

    if not request.method == "GET":
        raise django.http.Http404

    if not "electrical-parameter-name01" in request.GET:
        return django.http.HttpResponse(content="", status=200)

    if "month" in request.GET and "year" in request.GET:
        return render_report_powerprofile_by_month(request)
    #
    # Build a request data list in order to normalize it.
    #
    request_data_list = []
    consumer_unit_counter = 1
    consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
    graph_available = True
    while request.GET.has_key(consumer_unit_get_key):
        date_from_get_key = "date-from%02d" % consumer_unit_counter
        date_to_get_key = "date-to%02d" % consumer_unit_counter
        electrical_parameter_name_get_key =\
            "electrical-parameter-name%02d" % consumer_unit_counter

        try:
            consumer_unit_id = request.GET[consumer_unit_get_key]
            date_from_string = request.GET[date_from_get_key]
            date_to_string = request.GET[date_to_get_key]
            electrical_parameter_name =\
                request.GET[electrical_parameter_name_get_key]

        except KeyError:
            logger.error(
                reports.globals.SystemError.RENDER_INSTANT_MEASUREMENTS_ERROR)

            raise django.http.Http404

        virtual = c_center.models.ConsumerUnit.objects.filter(
            pk=int(request.GET[consumer_unit_get_key])
        ).values("profile_powermeter__powermeter__powermeter_anotation")
        virtual = virtual[0]\
            ['profile_powermeter__powermeter__powermeter_anotation']

        if virtual == "Medidor Virtual":
            if electrical_parameter_name == "PF" or \
                    electrical_parameter_name.startswith("V"):
                consumer_unit_counter += 1
                consumer_unit_get_key = "consumer-unit%02d" % \
                                        consumer_unit_counter
                graph_available = False
                continue

        datetime_from = datetime.datetime.strptime(date_from_string, "%Y-%m-%d")
        datetime_to = datetime.datetime.strptime(date_to_string, "%Y-%m-%d")
        datetime_from = datetime_from.replace(hour=00, minute=00, second=00)
        datetime_to = datetime_to.replace(hour=23, minute=59, second=59)
        request_data_list_item =\
            (consumer_unit_id,
             datetime_from,
             datetime_to,
             electrical_parameter_name)

        request_data_list.append(request_data_list_item)
        consumer_unit_counter += 1
        consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter

    #
    # Normalize the data list.
    #
    request_data_list_normalized =\
        get_request_data_list_normalized(request_data_list)

    #
    # Build the columns list.
    #
    column_strings =\
        get_column_strings_electrical_parameter(request_data_list_normalized)

    template_variables['columns'] = column_strings

    column_strings2 =\
        get_series_legends(request_data_list_normalized)

    template_variables['columns_labels'] = column_strings2

    columns_units_list = get_column_units_list(request_data_list_normalized)
    template_variables['column_units'] = zip(columns_units_list, column_strings)

    #
    # Build and normalize the data clusters list.
    #
    granularity = None
    if "granularity" in request.GET:
        if request.GET['granularity'] == "raw":
            granularity = "raw"
            template_variables['granularity'] = "raw_data"

    data_clusters_list = get_data_clusters_list(request_data_list_normalized,
                                                granularity)

    normalize_data_clusters_list(data_clusters_list)

    #get the raw data for statistics
    if granularity == "raw":
        statistics_clusters_list = data_clusters_list
    else:
        statistics_clusters_list = get_data_clusters_list(
            request_data_list_normalized, "raw")

    normalize_data_clusters_list(statistics_clusters_list)

    #data_clusters_list para csv

    axis_dictionary = \
        get_axis_dictionary(data_clusters_list, columns_units_list)

    axis_dictionaries_list = get_axis_dictionaries_list(axis_dictionary)
    template_variables['axis_list'] = axis_dictionaries_list

    column_units_axis_indexes =\
        get_column_units_axis_indexes(
            columns_units_list,
            axis_dictionaries_list)

    template_variables['column_unit_axis_indexes'] = column_units_axis_indexes

    #
    # Create the json using the data clusters list normalized
    #
    data_clusters_json = get_data_clusters_json(data_clusters_list)

    if data_clusters_json is None:
        if graph_available:
            return django.http.HttpResponse(
                "<h2 style='font-family: helvetica;"
                "text-align: center;display: block;"
                " margin: 0 auto;color: #666;'> "
                "No se han encontrado datos para el "
                "reporte, Por favor espere unos minutos,"
                "o verifique que el sistema de adquisición"
                "se encuentra funcionando correctamente"
                "</h2>")
        else:
            return django.http.HttpResponse("<h1 style='font-family: helvetica;"
                                            "text-align: center;display: block;"
                                            " margin: 0 auto;color: #666;'> "
                                            "Reporte no disponible para la "
                                            "unidad de consumo seleccionada "
                                            "</h1>")
    else:
        template_variables['rows_len'] = len(data_clusters_json)

    template_variables['rows'] = data_clusters_json



    #
    # Get statistical values
    #
    maximum, minimum = get_data_clusters_list_limits(data_clusters_list)
    data_clusters_statistics = get_data_clusters_statistics(
        statistics_clusters_list)

    template_variables['max'] = maximum
    template_variables['min'] = minimum
    template_variables['columns_statistics'] = data_clusters_statistics
    template_context =\
        django.template.context.RequestContext(request, template_variables)

    return django.shortcuts.render_to_response(
               "reports/instant-measurements.html",
               template_context)

@login_required(login_url='/')
def render_gas_consumed(
        request
):
    template_variables = {}
    rows = []
    building = request.session['main_building']
    ie = IndustrialEquipment.objects.get(pk=building.pk)
    if request.GET:
        start_date = datetime.datetime.strptime(request.GET['init-date'],
                                                '%Y-%m-%d')
        end_date = datetime.datetime.strptime(request.GET['end-date'],
                                              '%Y-%m-%d')

        if end_date - start_date >= datetime.timedelta(days=30):

            while start_date <= end_date + datetime.timedelta(days=1):
                meditions = WaterGasData.objects.filter(
                    industrial_equipment=ie,
                    medition_date__gte=start_date,
                    medition_date__lte=start_date + datetime.timedelta(days=1)
                ).order_by('medition_date').values('gas_consumed', 'gas_entered')
                medition_number = len(meditions)
                entered = sum(meditions["gas_entered"])
                if medition_number > 0:
                    data_dictionary_json = {
                    'datetime': str(mktime(start_date.timetuple())),
                    'value1': float(meditions[medition_number - 1]['gas_consumed'] - meditions[0]
                    ['gas_consumed']),
                    'value2': float(entered)
                    }
                else:
                    date = mktime(start_date.timetuple())
                    data_dictionary_json = {
                    'datetime': str(date),
                    'value1': float(0),
                    'value2': float(0)
                    }
                rows.append(data_dictionary_json)
                start_date = start_date + datetime.timedelta(days = 1)

            if end_date > datetime.datetime.now():
                end_date = datetime.datetime.now()

            template_variables['rows'] = rows
            template_variables['ff'] = end_date
            template_variables['fi'] = end_date - datetime.timedelta(days = 7)

        elif end_date - start_date < datetime.timedelta(days=30):

            while start_date <= end_date + datetime.timedelta(days=1):
                meditions = WaterGasData.objects.filter(industrial_equipment=ie,
                                                  medition_date__gte=start_date,
                                                  medition_date__lte=start_date +
                                                                     datetime.timedelta(minutes = 60))\
                    .order_by('medition_date')
                medition_number = meditions.count()
                consumed = WaterGasData.objects.filter(industrial_equipment=ie,
                                                       medition_date__gte=start_date,
                                                       medition_date__lte=start_date +
                                                                          datetime.timedelta(minutes = 60))\
                    .aggregate(Sum('gas_entered'))
                if medition_number > 0:
                    data_dictionary_json = {
                    'datetime': str(mktime(start_date.timetuple())),
                    'value1': float(meditions[medition_number - 1].gas_consumed - meditions[0]
                    .gas_consumed),
                    'value2': float(consumed['gas_entered__sum'])
                    }
                    rows.append(data_dictionary_json)
                    start_date = start_date + datetime.timedelta(minutes = 60)
                else:
                    date = mktime(start_date.timetuple())
                    data_dictionary_json = {
                    'datetime': str(date),
                    'value1': float(0),
                    'value2': float(0)
                    }
                    rows.append(data_dictionary_json)
                    start_date = start_date + datetime.timedelta(minutes = 60)

            if end_date > datetime.datetime.now():
                end_date = datetime.datetime.now()

            template_variables['rows'] = rows
            template_variables['ff'] = end_date
            template_variables['fi'] = end_date - datetime.timedelta(minutes = 120)

    else:
        now = datetime.datetime.now()
        start_date = now - datetime.timedelta(days=7)
        end_date = now

        while start_date <= end_date + datetime.timedelta(days=1):
            meditions = WaterGasData.objects.filter(industrial_equipment=ie,
                                                  medition_date__gte=start_date,
                                                  medition_date__lte=start_date +
                                                                     datetime.timedelta(minutes = 60))\
                    .order_by('medition_date')
            medition_number = meditions.count()
            consumed = WaterGasData.objects.filter(industrial_equipment=ie,
                                                       medition_date__gte=start_date,
                                                       medition_date__lte=start_date +
                                                                          datetime.timedelta(minutes = 60))\
                    .aggregate(Sum('gas_entered'))
            if medition_number > 0:
                data_dictionary_json = {
                'datetime': str(mktime(start_date.timetuple())),
                'value1': float(meditions[medition_number - 1].gas_consumed - meditions[0]
                .gas_consumed),
                'value2': float(consumed['gas_entered__sum'])
                }
                rows.append(data_dictionary_json)
                start_date = start_date + datetime.timedelta(minutes = 60)
            else:
                date = mktime(start_date.timetuple())
                data_dictionary_json = {
                'datetime': str(date),
                'value1': float(0),
                'value2': float(0)
                }
                rows.append(data_dictionary_json)
                start_date = start_date + datetime.timedelta(minutes = 60)

            if end_date > datetime.datetime.now():
                end_date = datetime.datetime.now()

            template_variables['rows'] = rows
            template_variables['ff'] = end_date
            template_variables['fi'] = end_date - datetime.timedelta(minutes = 120)
    template_context =\
        django.template.context.RequestContext(request, template_variables)
    return django.shortcuts.render_to_response(
               "reports/consumed_gas.html",template_context)

@login_required(login_url='/')
def render_water_consumed(
        request
):
    template_variables = {}
    rows = []
    building = request.session['main_building']
    ie = IndustrialEquipment.objects.get(pk=building.pk)
    if request.GET:
        start_date = datetime.datetime.strptime(request.GET['init-date'],
                                                '%Y-%m-%d')
        end_date = datetime.datetime.strptime(request.GET['end-date'],
                                              '%Y-%m-%d')

        if end_date - start_date >= datetime.timedelta(days=30):

            while start_date <= end_date + datetime.timedelta(days=1):
                meditions = WaterGasData.objects.filter(industrial_equipment=ie,
                                                  medition_date__gte=start_date,
                                                  medition_date__lte=start_date +
                                                                     datetime.timedelta(days = 1))\
                    .order_by('medition_date')
                medition_number = meditions.count()
                consumed = WaterGasData.objects.filter(industrial_equipment=ie,
                                                       medition_date__gte=start_date,
                                                       medition_date__lte=start_date +
                                                                          datetime.timedelta(days = 1))\
                    .aggregate(Sum('water_entered'))
                if medition_number > 0:
                    data_dictionary_json = {
                    'datetime': str(mktime(start_date.timetuple())),
                    'value1': float(meditions[medition_number - 1].water_consumed - meditions[0]
                    .water_consumed),
                    'value2': float(consumed['water_entered__sum'])
                    }
                    rows.append(data_dictionary_json)
                    start_date = start_date + datetime.timedelta(days = 1)
                else:
                    date = mktime(start_date.timetuple())
                    data_dictionary_json = {
                    'datetime': str(date),
                    'value1': float(0),
                    'value2': float(0)
                    }
                    rows.append(data_dictionary_json)
                    start_date = start_date + datetime.timedelta(days = 1)

            if end_date > datetime.datetime.now():
                end_date = datetime.datetime.now()

            template_variables['rows'] = rows
            template_variables['ff'] = end_date
            template_variables['fi'] = end_date - datetime.timedelta(days = 7)

        elif end_date - start_date < datetime.timedelta(days=30):

            while start_date <= end_date + datetime.timedelta(days=1):
                meditions = WaterGasData.objects.filter(industrial_equipment=ie,
                                                  medition_date__gte=start_date,
                                                  medition_date__lte=start_date +
                                                                     datetime.timedelta(minutes = 60))\
                    .order_by('medition_date')
                medition_number = meditions.count()
                consumed = WaterGasData.objects.filter(industrial_equipment=ie,
                                                       medition_date__gte=start_date,
                                                       medition_date__lte=start_date +
                                                                          datetime.timedelta(minutes = 60))\
                    .aggregate(Sum('water_entered'))
                if medition_number > 0:
                    data_dictionary_json = {
                    'datetime': str(mktime(start_date.timetuple())),
                    'value1': float(meditions[medition_number - 1].water_consumed - meditions[0]
                    .water_consumed),
                    'value2': float(consumed['water_entered__sum'])
                    }
                    rows.append(data_dictionary_json)
                    start_date = start_date + datetime.timedelta(minutes = 60)
                else:
                    date = mktime(start_date.timetuple())
                    data_dictionary_json = {
                    'datetime': str(date),
                    'value1': float(0),
                    'value2': float(0)
                    }
                    rows.append(data_dictionary_json)
                    start_date = start_date + datetime.timedelta(minutes = 60)

            if end_date > datetime.datetime.now():
                end_date = datetime.datetime.now()

            template_variables['rows'] = rows
            template_variables['ff'] = end_date
            template_variables['fi'] = end_date - datetime.timedelta(minutes = 120)

    else:
        now = datetime.datetime.now()
        start_date = now - datetime.timedelta(days=7)
        end_date = now

        while start_date <= end_date + datetime.timedelta(days=1):
            meditions = WaterGasData.objects.filter(industrial_equipment=ie,
                                                  medition_date__gte=start_date,
                                                  medition_date__lte=start_date +
                                                                     datetime.timedelta(minutes = 60))\
                    .order_by('medition_date')
            medition_number = meditions.count()
            consumed = WaterGasData.objects.filter(industrial_equipment=ie,
                                                       medition_date__gte=start_date,
                                                       medition_date__lte=start_date +
                                                                          datetime.timedelta(minutes = 60))\
                    .aggregate(Sum('water_entered'))
            if medition_number > 0:
                data_dictionary_json = {
                'datetime': str(mktime(start_date.timetuple())),
                'value1': float(meditions[medition_number - 1].water_consumed - meditions[0]
                .water_consumed),
                'value2': float(consumed['water_entered__sum'])
                }
                rows.append(data_dictionary_json)
                start_date = start_date + datetime.timedelta(minutes = 60)
            else:
                date = mktime(start_date.timetuple())
                data_dictionary_json = {
                'datetime': str(date),
                'value1': float(0),
                'value2': float(0)
                }
                rows.append(data_dictionary_json)
                start_date = start_date + datetime.timedelta(minutes = 60)

            if end_date > datetime.datetime.now():
                end_date = datetime.datetime.now()

            template_variables['rows'] = rows
            template_variables['ff'] = end_date
            template_variables['fi'] = end_date - datetime.timedelta(minutes = 120)
    template_context =\
        django.template.context.RequestContext(request, template_variables)
    return django.shortcuts.render_to_response(
               "reports/consumed_gas.html",template_context)

@login_required(login_url="/")
def render_report_consumed_by_month(
        request
):
    template_variables = {
        'max': None,
        'min': None,
        'rows': None,
    }

    if not request.method == "GET":
        raise django.http.Http404
    if not "electrical-parameter-name" in request.GET:
        return django.http.HttpResponse(content="", status=200)
    try:
        consumer_unit_id = request.GET['consumer-unit-id']
        month = int(request.GET['month'])
        year = int(request.GET['year'])
        electrical_parameter_name = request.GET['electrical-parameter-name']

    except KeyError:
        raise django.http.Http404

    days = variety.getMonthDays(month, year)
    first_week_start_datetime = days[0] + datetime.timedelta(days=1)
    last_week_end_datetime = days[-1] + datetime.timedelta(days=2)

    #
    # For the purposes of this report, the granularity is an hour but this is
    # intended to be extended, it should be retrieved as GET parameter.
    #
    granularity_seconds = 300
    data_cluster_consumed =\
        get_data_cluster_consumed_normalized(
            consumer_unit_id,
            first_week_start_datetime,
            last_week_end_datetime,
            electrical_parameter_name,
            granularity_seconds)
    template_variables['rows'] = data_cluster_consumed

    maximun, minimun = get_data_cluster_limits(data_cluster_consumed)

    if maximun <= minimun:
        minimun = maximun - 1

    template_variables['max'] = maximun
    template_variables['min'] = minimun
    today = datetime.datetime.now()
    if today.month == month and today.year == year:
        current_week = variety.get_week_of_month_from_datetime(today)
        template_variables['course_week'] = True
        #number of weeks in month minus current_week = remaining weeks at
        #                                              the start of month
        template_variables['week'] = 6 - current_week
        template_variables['fi'], template_variables['ff'] = \
            variety.get_week_start_datetime_end_datetime_tuple(year,
                                                               month,
                                                               current_week)

    else:
        template_variables['ff'] = last_week_end_datetime
        template_variables['fi'] = last_week_end_datetime - \
                                   datetime.timedelta(days=7)
    template_variables['consumer_unit_id'] = request.GET['consumer-unit-id']
    template_variables['years'] = request.session['years']
    template_variables['current_week'] = variety.\
        get_week_of_month_from_datetime(first_week_start_datetime)
    template_variables['current_year'] = year
    template_variables['current_month'] = month

    cu = c_center.models.ConsumerUnit.objects.get(pk=consumer_unit_id)
    day_data = \
        c_center.c_center_functions.getDailyReports(cu, month, year, 1)

    formated_day_data = []
    cont = 1
    day_array = []
    for data in day_data:
        day_array.append(data)
        if cont % 7 == 0:
            fecha1 = datetime.datetime.strptime(day_array[0]['fecha'],
                                                "%Y-%m-%d %H:%M:%S")
            fecha2 = datetime.datetime.strptime(day_array[-1]['fecha'],
                                                "%Y-%m-%d %H:%M:%S")
            week_total = c_center.c_center_functions.consumoAcumuladoKWH(
                cu, fecha1, fecha2)
            day_array[0]["week_total"] = week_total

            for day in day_array:
                for key in day:
                    if day[key] and variety.is_number(day[key]):
                        day[key] = variety.moneyfmt(
                            decimal.Decimal(str(day[key])), 0, "", ",", "")
            formated_day_data.append(day_array)

            day_array = []

        cont += 1

    template_variables['day_data'] = formated_day_data

    month_data = \
        c_center.c_center_functions.getMonthlyReport(cu, month, year)

    for key in month_data:
        month_data[key] = variety.moneyfmt(
            decimal.Decimal(str(month_data[key])))

    template_variables['month_data'] = month_data
    template_variables['electric_data'] = electrical_parameter_name

    if cu.building.electric_rate.electric_rate_name == "H-M":
        #parse data_cluster_consumed
        template_variables['rows'] = rates_for_data_cluster(
            data_cluster_consumed, cu.building.region)
        template_variables['periods'] = True

    template_context =\
        django.template.context.RequestContext(request, template_variables)

    return django.shortcuts.render_to_response("reports/consumed-by-month.html",
                                               template_context)


@login_required(login_url="/")
def render_report_powerprofile_by_month(
        request
):
    template_variables = {
        'axis_list': None,
        'columns': None,
        'columns_statistics': None,
        'column_units': None,
        'column_unit_axis_indexes': None,
        'max': None,
        'min': None,
        'rows': None
    }

    if not request.method == "GET":
        raise django.http.Http404

    if not "electrical-parameter-name01" in request.GET:
        return django.http.HttpResponse(content="", status=200)

    #
    # Build a request data list in order to normalize it.
    #
    request_data_list = []
    parameter_counter = 1
    parameter_get_key = "electrical-parameter-name%02d" % parameter_counter
    consumer_unit_id = request.GET['consumer-unit-id']

    month = int(request.GET['month'])
    year = int(request.GET['year'])
    days = variety.getMonthDays(month, year)

    datetime_from = days[0] + datetime.timedelta(days=1)
    datetime_to = days[-1] + datetime.timedelta(days=2)

    today = datetime.datetime.now()
    if today.month == month and today.year == year:
        current_week = variety.get_week_of_month_from_datetime(today)
        template_variables['course_week'] = True
        #number of weeks in month minus current_week = remaining weeks at
        #                                              the start of month
        template_variables['week'] = 6 - current_week
        template_variables['fi'], template_variables['ff'] = \
            variety.get_week_start_datetime_end_datetime_tuple(year,
                                                               month,
                                                               current_week)

    else:
        template_variables['ff'] = datetime_to
        template_variables['fi'] = datetime_to - datetime.timedelta(days=7)
    template_variables['consumer_unit_id'] = request.GET['consumer-unit-id']
    template_variables['years'] = request.session['years']
    template_variables['current_year'] = year
    template_variables['current_month'] = month
    while request.GET.has_key(parameter_get_key):
        electrical_parameter_name_get_key =\
            "electrical-parameter-name%02d" % parameter_counter
        try:
            electrical_parameter_name =\
                request.GET[electrical_parameter_name_get_key]

        except KeyError:
            #logger.error(
            #    reports.globals.SystemError.RENDER_INSTANT_MEASUREMENTS_ERROR)
            raise django.http.Http404

        request_data_list_item =\
            (consumer_unit_id,
             datetime_from,
             datetime_to,
             electrical_parameter_name)

        request_data_list.append(request_data_list_item)
        parameter_counter += 1
        parameter_get_key = "electrical-parameter-name%02d" % parameter_counter

    #
    # Normalize the data list.
    #
    request_data_list_normalized =\
        get_request_data_list_normalized(request_data_list)

    #
    # Build the columns list.
    #
    column_strings =\
        get_column_strings_electrical_parameter(request_data_list_normalized)

    template_variables['columns'] = column_strings

    columns_units_list = get_column_units_list(request_data_list_normalized)
    template_variables['column_units'] = zip(columns_units_list, column_strings)

    #
    # Build and normalize the data clusters list.
    #
    granularity = "raw"

    data_clusters_list = get_data_clusters_list(request_data_list_normalized,
                                                granularity)
    normalize_data_clusters_list(data_clusters_list)

    #data_clusters_list para csv
    axis_dictionary = \
        get_axis_dictionary(data_clusters_list, columns_units_list)
    axis_dictionaries_list = get_axis_dictionaries_list(axis_dictionary)
    template_variables['axis_list'] = axis_dictionaries_list

    column_units_axis_indexes =\
        get_column_units_axis_indexes(
            columns_units_list,
            axis_dictionaries_list)

    template_variables['column_unit_axis_indexes'] = column_units_axis_indexes

    #
    # Create the json using the data clusters list normalized
    #
    data_clusters_json = get_data_clusters_json(data_clusters_list)

    if data_clusters_json is None:
        return django.http.HttpResponse("<h2 style='font-family: helvetica;"
                                            "text-align: center;display: block;"
                                            " margin: 0 auto;color: #666;'> "
                                            "No se han encontrado datos para el "
                                            "reporte, Por favor espere unos minutos,"
                                            "o verifique que el sistema de adquisición"
                                            "se encuentra funcionando correctamente"
                                            "</h2>")
    else:
        template_variables['rows_len'] = len(data_clusters_json)

    template_variables['rows'] = data_clusters_json

    #
    # Get statistical values
    #
    maximum, minimum = get_data_clusters_list_limits(data_clusters_list)

    weeks = []
    for cont in range(0, 6):
        if cont == 0:
            weeks.append(
                (datetime_from, datetime_from + datetime.timedelta(days=7)))

        else:
            weeks.append(
                (weeks[cont-1][1],
                 weeks[cont-1][1] + datetime.timedelta(days=7)))

    cont = 0
    statistics = []
    for day_data in data_clusters_list:
        #day_data = todos los datos de un parámetro para el mes
        param = column_strings[cont]

        cont += 1
        month_array = [[], [], [], [], [], []]
        for day in day_data:
            medition_date = datetime.datetime.fromtimestamp(day["datetime"])
            for i in range(0, len(weeks)):
                if weeks[i][0] <= medition_date < weeks[i][1]:
                    if param == "PF" and abs(day['value']) > 1:
                        day['value'] = 1
                    if day["certainty"]:
                        month_array[i].append(abs(float(day['value'])))

                    break
                else:
                    continue
        for i in range(0, len(month_array)):

            if month_array[i]:
                month_array[i] = get_data_statistics(month_array[i])

        statistics.append(dict(param=param, month_data=month_array))

    template_variables['max'] = maximum
    template_variables['min'] = minimum
    template_variables['columns_statistics'] = statistics
    template_context =\
        django.template.context.RequestContext(request, template_variables)

    return django.shortcuts.render_to_response("reports/instant_by_month.html",
                                               template_context)


def csv_report(request):
    template_variables = dict()
    if not request.method == "GET":
        raise django.http.Http404

    if not "electrical-parameter-name01" in request.GET:
        return django.http.HttpResponse(content="", status=200)

    #
    # Build a request data list in order to normalize it.
    #
    request_data_list = []
    consumer_unit_counter = 1
    consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
    while request.GET.has_key(consumer_unit_get_key):
        date_from_get_key = "date-from%02d" % consumer_unit_counter
        date_to_get_key = "date-to%02d" % consumer_unit_counter
        electrical_parameter_name_get_key = \
            "electrical-parameter-name%02d" % consumer_unit_counter

        try:
            consumer_unit_id = request.GET[consumer_unit_get_key]
            date_from_string = request.GET[date_from_get_key]
            date_to_string = request.GET[date_to_get_key]
            electrical_parameter_name = \
                request.GET[electrical_parameter_name_get_key]

        except KeyError:
            logger.error(
                reports.globals.SystemError.RENDER_INSTANT_MEASUREMENTS_ERROR)

            raise django.http.Http404

        datetime_from = datetime.datetime.strptime(date_from_string, "%Y-%m-%d")
        datetime_to = datetime.datetime.strptime(date_to_string, "%Y-%m-%d")
        datetime_from = datetime_from.replace(hour=00, minute=00, second=00)
        datetime_to = datetime_to.replace(hour=23, minute=59, second=59)
        request_data_list_item = \
            (consumer_unit_id,
             datetime_from,
             datetime_to,
             electrical_parameter_name)

        request_data_list.append(request_data_list_item)
        consumer_unit_counter += 1
        consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
    #
    # Normalize the data list.
    #
    request_data_list_normalized = \
        get_request_data_list_normalized(request_data_list)
    #
    # Build and normalize the data clusters list.
    #
    granularity = None
    if "granularity" in request.GET:
        if request.GET['granularity'] == "raw":
            granularity = "raw"
            template_variables['granularity'] = "raw_data"

    data_clusters_list = get_data_clusters_list(request_data_list_normalized,
                                                granularity)

    normalize_data_clusters_list(data_clusters_list)
    # todo encoding
    data_csv = [["Edificio", "Unidad de Consumo", "Parámetro", "Valor",
                 "Fecha/Hora"]]
    report_name = ""
    for row_data, cluster in zip(request_data_list_normalized, data_clusters_list):
        #row_data = (id_cu, datetime_init, datetime_end, electric_param)
        consumer_unit = c_center.models.ConsumerUnit.objects.get(
            pk=int(row_data[0]))
        electrical_parameter_name = row_data[3]
        report_name += electrical_parameter_name + "_" + \
                       consumer_unit.building.building_name + "."

        for data in cluster:
            date_time = datetime.datetime.fromtimestamp(data['datetime'])
            electric_data_row = [unicode(consumer_unit.building.building_name)
                                 .encode("utf-8"),
                                 consumer_unit.electric_device_type
                                 .electric_device_type_name.encode("utf-8"),
                                 electrical_parameter_name,
                                 str(data['value']),
                                 str(date_time)]
            data_csv.append(electric_data_row)
    response = django.shortcuts.HttpResponse(mimetype='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="datos_' + \
                                      report_name.encode("utf-8") + 'csv"'
    writer = csv.writer(response)
    for data_item in data_csv:
        writer.writerow(data_item)

    return response