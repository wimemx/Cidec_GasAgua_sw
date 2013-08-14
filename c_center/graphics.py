# -*- coding: utf-8 -*-
#
# Python imports
#
import datetime
import time
from datetime import timedelta

#
# Django imports
#
import django.http
import django.shortcuts
import django.utils.timezone
import django.template.context


#
# cidec imports
#
import c_center.c_center_functions
import c_center.models
import data_warehouse.views
import data_warehouse_extended.models
import variety



def render_graphics(request):
    """ Serves a placeholder for graphs

    :param request: request object
    :return:
    """
    return django.http.HttpResponse("")


def get_consumer_unit_electric_data_raw(
        electric_data_name,
        cu_id,
        start,
        end
):
    """Gets the electric data info for a consumer unit, for a parameter in
    a given time frame, formated to display in graphs

    :param electric_data_name:Electrical Parameter name
    :param cu_id: int ConsumerUnit id
    :param start: datetime
    :param end: datetime
    :return: Array of electrical parameter data
    """
    electric_data_raw = []
    try:
        consumer_unit = c_center.models.ConsumerUnit.objects.get(pk=cu_id)

    except c_center.models.ConsumerUnit.DoesNotExist:
        return electric_data_raw

    current_timezone = django.utils.timezone.get_current_timezone()
    start_localtime = current_timezone.localize(start)
    start_utc = start_localtime.astimezone(django.utils.timezone.utc)
    end_localtime = current_timezone.localize(end)
    end_utc = end_localtime.astimezone(django.utils.timezone.utc)

    param = data_warehouse_extended.models.ElectricalParameter.objects.get(
        name=electric_data_name
    )
    electric_data_name = param.name_transactional

    electric_data_values = c_center.models.ElectricDataTemp.objects.filter(
        profile_powermeter=consumer_unit.profile_powermeter,
        medition_date__gte=start_utc,
        medition_date__lte=end_utc
    ).order_by(
        'medition_date'
    ).values(
        'medition_date',
        electric_data_name
    )

    def get_first_two(electric_data_values):
        cont = 0
        first_m = electric_data_values[cont]['medition_date']
        second_m = electric_data_values[cont + 1]['medition_date']
        while first_m == second_m:
            cont += 1
            second_m = electric_data_values[cont]['medition_date']
        return first_m, second_m

    if electric_data_values:
        consumer_unit_data_len = len(electric_data_values)
        first_m, second_m = get_first_two(electric_data_values)
        #first_m = electric_data_values[0]['medition_date']
        #second_m = electric_data_values[1]['medition_date']

        delta_m = second_m - first_m

        time_m = start_localtime
        cont = 0
        while time_m < end_localtime:
            #difference between readings default to delta_m
            adj_time = delta_m
            try:
                #real difference between readings
                adj_time = electric_data_values[cont]['medition_date'] - time_m
            except IndexError:
                adj_time += delta_m

            time_m += delta_m
            #add a margin of 3 seconds between readings
            if adj_time > (delta_m + datetime.timedelta(seconds=3)):
                #probably an empty spot
                electric_data_raw.append(
                    dict(datetime=int(time.mktime(
                             django.utils.timezone.localtime(time_m).timetuple())),
                         value=None,
                         certainty=False))
            elif cont < consumer_unit_data_len:
                electric_data = abs(
                    electric_data_values[cont][electric_data_name])
                if electric_data_name == "PF" and electric_data > 1:
                    electric_data = 1
                medition_date = electric_data_values[cont]['medition_date']

                electric_data_raw.append(
                    dict(datetime=
                         int(time.mktime(
                             django.utils.timezone.localtime(
                                 medition_date).timetuple())),
                         value=abs(electric_data),
                         certainty=True))
                cont += 1
            else:
                break
    return electric_data_raw


def get_consumer_unit_electric_data_interval_raw_optimized(
        electric_data_name,
        cu_id,
        start,
        end
):
    """Gets an array of dicts containing electrical data for a consumer_unit
    used in the index page graph

    :param electric_data_name: Electrical parameter name
    :param cu_id: int consumer unit id
    :param start:datetime
    :param end:datetime
    :return:array od dicts
    """
    electric_data_raw = []
    try:
        electric_data_name_local =\
            data_warehouse.views.CUMULATIVE_ELECTRIC_DATA_INVERSE[electric_data_name]

    except KeyError:
        return electric_data_raw

    try:
        consumer_unit = c_center.models.ConsumerUnit.objects.get(pk=cu_id)

    except c_center.models.ConsumerUnit.DoesNotExist:
        return electric_data_raw

    current_timezone = django.utils.timezone.get_current_timezone()
    start_localtime = current_timezone.localize(start)
    start_utc = start_localtime.astimezone(django.utils.timezone.utc)
    end_localtime = current_timezone.localize(end)
    end_utc = end_localtime.astimezone(django.utils.timezone.utc)
    electric_data_raw_dictionaries = c_center.models.ElectricDataTemp.objects.filter(
            profile_powermeter=consumer_unit.profile_powermeter,
            medition_date__gte=start_utc,
            medition_date__lte=end_utc
        ).order_by(
            'medition_date'
        ).values(electric_data_name_local, 'medition_date')

    electric_data_raw_results_length = electric_data_raw_dictionaries.count()
    if not electric_data_raw_results_length:
        return electric_data_raw

    electric_data_raw_hours_dictionary = dict()
    timedelta_tolerance = timedelta(minutes=10)
    for electric_data_raw_dictionary in electric_data_raw_dictionaries:
        medition_date_current = electric_data_raw_dictionary['medition_date']
        electric_data_current = \
            electric_data_raw_dictionary[electric_data_name_local]
        datetime_hour_current = \
            variety.get_hour_from_datetime(medition_date_current)
        timedelta_current = abs(medition_date_current - datetime_hour_current)
        if timedelta_current < timedelta_tolerance:
            datetime_hour_current_string = \
                datetime_hour_current.strftime("%Y-%m-%d-%H")
            medition_date_current_stored, electric_data_current_stored =\
                electric_data_raw_hours_dictionary.get(
                    datetime_hour_current_string,
                    (datetime.datetime.max.replace(tzinfo=django.utils.timezone.utc),
                     None)
                )

            if abs(medition_date_current_stored - datetime_hour_current) > \
                    timedelta_current:
                electric_data_raw_hours_dictionary[datetime_hour_current_string] =\
                    (medition_date_current, electric_data_current)

        datetime_hour_next = datetime_hour_current + timedelta(hours=1)
        timedelta_next = abs(medition_date_current - datetime_hour_next)
        if timedelta_next < timedelta_tolerance:
            datetime_hour_next_string = \
                datetime_hour_next.strftime("%Y-%m-%d-%H")
            medition_date_next_stored, electric_data_next_stored =\
            electric_data_raw_hours_dictionary.get(
                datetime_hour_next_string,
                (datetime.datetime.max.replace(tzinfo=django.utils.timezone.utc),
                 None)
            )

            if abs(medition_date_next_stored - datetime_hour_next) > \
                    timedelta_next:
                electric_data_raw_hours_dictionary[datetime_hour_next_string] =\
                    (medition_date_current, electric_data_current)

    hour_delta = timedelta(hours=1)
    datetime_current_utc = datetime.datetime(year=start_utc.year,
                                             month=start_utc.month,
                                             day=start_utc.day,
                                             hour=start_utc.hour,
                                             tzinfo=django.utils.timezone.utc)

    while datetime_current_utc <= end_utc:
        datetime_current_utc_string = \
            datetime_current_utc.strftime("%Y-%m-%d-%H")
        datetime_next_utc = datetime_current_utc + hour_delta
        datetime_next_utc_string = datetime_next_utc.strftime("%Y-%m-%d-%H")
        electric_data_value = 0
        if datetime_current_utc_string in \
                electric_data_raw_hours_dictionary and \
                datetime_next_utc_string in \
                electric_data_raw_hours_dictionary:

            medition_date_value_current, electric_data_value_current =\
                electric_data_raw_hours_dictionary.get(
                    datetime_current_utc_string)

            medition_date_value_next, electric_data_value_next =\
                electric_data_raw_hours_dictionary.get(datetime_next_utc_string)

            electric_data_value = \
                electric_data_value_next - electric_data_value_current

        datetime_current_localtime = \
            datetime_current_utc.astimezone(current_timezone)
        electric_data_raw_item = dict(
            datetime=int(time.mktime(datetime_current_localtime.timetuple())),
            electric_data=abs(electric_data_value),
            certainty=True)

        electric_data_raw.append(electric_data_raw_item)
        datetime_current_utc += hour_delta

    return electric_data_raw


def get_consumer_unit_week_report_cumulative(
        consumer_unit,
        year,
        month,
        week,
        electric_data_name
):
    """Gets an array of electrical data for a given week of month

    :param consumer_unit: ConsumerUnit object
    :param year: int, the year of the week
    :param month: int, the month of the week
    :param week: int, the week number of the month
    :param electric_data_name:string, electrical parameter name
    :return: tuple containing data to graph and for display
    """
    week_start_datetime, week_end_datetime =\
        variety.get_week_start_datetime_end_datetime_tuple(year, month, week)

    def build_day_tuple_list(week_start, day_index):
        hour_delta = datetime.timedelta(hours=1)
        day_delta = datetime.timedelta(days=1)
        day_tuple_list = []
        for index in range(0, 24):
            hour_start_current = week_start + (day_index * day_delta) + (index * hour_delta)
            hour_end_current = week_start + (day_index * day_delta) + (index * hour_delta) + hour_delta
            day_tuple_list.append((hour_start_current, hour_end_current, 0.0))

        return day_tuple_list

    electric_data_days_tuple_list = [
        (u"Lunes", build_day_tuple_list(week_start_datetime, 0)),
        (u"Martes", build_day_tuple_list(week_start_datetime, 1)),
        (u"Miércoles", build_day_tuple_list(week_start_datetime, 2)),
        (u"Jueves", build_day_tuple_list(week_start_datetime, 3)),
        (u"Viernes", build_day_tuple_list(week_start_datetime, 4)),
        (u"Sábado", build_day_tuple_list(week_start_datetime, 5)),
        (u"Domingo", build_day_tuple_list(week_start_datetime, 6))
    ]

    electric_data_days_cumulative_total_tuple_list = [
        (u"Lunes", 0.0),
        (u"Martes", 0.0),
        (u"Miércoles", 0.0),
        (u"Jueves", 0.0),
        (u"Viernes", 0.0),
        (u"Sábado", 0.0),
        (u"Domingo", 0.0)
    ]

    consumer_unit_list = c_center.c_center_functions.get_consumer_units(consumer_unit)
    for consumer_unit_item in consumer_unit_list:
        consumer_unit_electric_data_interval_raw =\
            get_consumer_unit_electric_data_interval_raw_optimized(
                electric_data_name,
                consumer_unit_item.pk,
                week_start_datetime,
                week_end_datetime)

        hours_in_week = 7 * 24
        if len(consumer_unit_electric_data_interval_raw) < hours_in_week:
            continue

        for index in range(0, hours_in_week):
            day_index = index / 24
            hour_index = index % 24
            consumer_unit_electric_data_interval_raw_dictionary =\
                consumer_unit_electric_data_interval_raw[index]

            electric_data_value_current =\
                consumer_unit_electric_data_interval_raw_dictionary.get("electric_data",
                                                                        0.0)

            day_current, hours_tuple_list_current =\
                electric_data_days_tuple_list[day_index]

            hour_datetime_start, hour_datetime_end, electric_data_value =\
                hours_tuple_list_current[hour_index]

            hours_tuple_list_current[hour_index] =\
                (hour_datetime_start,
                 hour_datetime_end,
                 electric_data_value + float(electric_data_value_current))

            day_cumulative_current, electric_data_value_cumulative_total_current =\
                electric_data_days_cumulative_total_tuple_list[day_index]

            electric_data_value_cumulative_total_current +=\
                float(electric_data_value_current)

            electric_data_days_cumulative_total_tuple_list[day_index] =\
                (day_cumulative_current, electric_data_value_cumulative_total_current)

    return electric_data_days_tuple_list, electric_data_days_cumulative_total_tuple_list


def get_default_datetime_end():
    """ Return a new datetime object whose date components are equal to the
    given date object’s, and whose time components and tzinfo attributes are
    equal to the given time object’s

    :return: datetime, the first time instant of today
    """
    return datetime.datetime.combine(
        datetime.date.today() - datetime.timedelta(days=1),
        datetime.time(0))


def get_default_datetime_start():
    """ gets the first time instant of yesterday

    :return: datetime
    """
    return get_default_datetime_end() - datetime.timedelta(days=1)
