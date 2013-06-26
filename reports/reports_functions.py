#coding:utf-8

# Python imports
import datetime
import logging
import numpy


# Django imports
import django.http
import django.shortcuts
import django.utils.timezone
import django.template.context

from c_center.models import ConsumerUnit

from reports.models import DataStoreMonthlyGraphs

from django.contrib.auth.decorators import login_required

from reports.views import get_data_cluster_consumed_normalized, rates_for_data_cluster,\
    get_request_data_list_normalized,get_column_strings_electrical_parameter, \
    get_column_units_list, get_data_clusters_list,normalize_data_clusters_list,\
    get_data_clusters_json,get_data_statistics,get_data_clusters_list_limits


# Other imports
import variety

logger = logging.getLogger("reports")


def Data_Store_Monthly_Graphs(consumer_unit_id,month, year):
    days = variety.getMonthDays(month, year)
    first_week_start_datetime = days[0] + datetime.timedelta(days=1)
    last_week_end_datetime = days[-1] + datetime.timedelta(days=2)
    electrical_parameter_name= "TotalkWhIMPORT"
    #
    # For the purposes of this report, the granularity is an hour but this is
    # intended to be extended, it should be retrieved as GET parameter.
    #
    granularity_seconds = 300
    data_cluster_consumed =\
        get_data_cluster_consumed_normalized (
            consumer_unit_id.id,
            first_week_start_datetime,
            last_week_end_datetime,
            electrical_parameter_name,
            granularity_seconds)


    if consumer_unit_id.building.electric_rate.electric_rate_name == "H-M":
        #parse data_cluster_consumed
        data_cluster_consumed = rates_for_data_cluster(
            data_cluster_consumed, consumer_unit_id.building.region)

#
    request_data_list = []

    days = variety.getMonthDays(month, year)
    datetime_from = days[0] + datetime.timedelta(days=1)
    datetime_to = days[-1] + datetime.timedelta(days=2)


    request_data_list_item =\
            (consumer_unit_id.id,
             datetime_from,
             datetime_to,
             "kW")
    request_data_list.append(request_data_list_item)
    request_data_list_item =\
            (consumer_unit_id.id,
             datetime_from,
             datetime_to,
             "kVAr")
    request_data_list.append(request_data_list_item)
    request_data_list_item =\
            (consumer_unit_id.id,
             datetime_from,
             datetime_to,
             "PF")
    request_data_list.append(request_data_list_item)



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


    columns_units_list = get_column_units_list(request_data_list_normalized)

    #
    # Build and normalize the data clusters list.
    #
    granularity = "raw"

    data_clusters_list = get_data_clusters_list(request_data_list_normalized,
                                                granularity)
    normalize_data_clusters_list(data_clusters_list)



    #
    # Create the json using the data clusters list normalized
    #
    data_clusters_json = get_data_clusters_json(data_clusters_list)

    #
    # Get statistical values
    #

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
            #print day
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

    return data_clusters_json,statistics, data_cluster_consumed


def calculate_month_graphs(cu, m, y):
    data_clusters_json, statistics, data_cluster_consumed = \
        Data_Store_Monthly_Graphs(cu, m, y)
    month_data, created = DataStoreMonthlyGraphs.objects.get_or_create\
            (year=y, month=m, consumer_unit=cu)
    month_data.instant_data = data_clusters_json
    month_data.data_consumed = data_cluster_consumed
    month_data.statistics = statistics
    month_data.save()


def insert_data_Graph_To_Model():
    cus = ConsumerUnit.objects.all()
    for cu in cus:
        today = datetime.date.today()
        calculate_month_graphs(cu, today.month, today.year)


def insert_rest_months(initial_month, initial_year, end_month, end_year):
    consumer_unit = ConsumerUnit.objects.all()
    for cu in consumer_unit:
        ym_start= 12*initial_year + initial_month - 1
        ym_end= 12*end_year + end_month
        for ym in range( ym_start, ym_end ):
                y, m = divmod( ym, 12 )
                calculate_month_graphs(cu, m+1, y)









