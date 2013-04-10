#coding:utf-8

#
# Python imports
#
import datetime
import time
from datetime import timedelta
import json
import string
import sys

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
import variety


def build_electric_data_json(consumer_units_ids, electric_data, granularity,
                             from_dates, to_dates):
    if not variety.are_array_same_length(consumer_units_ids, from_dates, to_dates):
        return []

    data_arrays = []
    for index in range(0, len(consumer_units_ids)):
        consumer_unit_id = consumer_units_ids[index]
        from_date = from_dates[index]
        from_datetime = datetime.datetime(
            year=from_date.year,
            month=from_date.month,
            day=from_date.day,
            tzinfo=django.utils.timezone.get_current_timezone())

        to_date = to_dates[index]
        to_datetime = datetime.datetime(
            year=to_date.year,
            month=to_date.month,
            day=to_date.day,
            tzinfo=django.utils.timezone.get_current_timezone())

        data_array = data_warehouse.views.get_consumer_unit_electric_data(
            consumer_unit_id,
            electric_data,
            granularity,
            from_datetime,
            to_datetime)

        if data_array is not None and len(data_array) > 0:
            data_arrays.append(data_array)


def get_consumer_unit_electric_data_raw(
        electric_data_name,
        id,
        start,
        end
):
    electric_data_raw = []
    try:
        consumer_unit = c_center.models.ConsumerUnit.objects.get(pk=id)

    except c_center.models.ConsumerUnit.DoesNotExist:
        return electric_data_raw

    current_timezone = django.utils.timezone.get_current_timezone()
    start_localtime = current_timezone.localize(start)
    start_utc = start_localtime.astimezone(django.utils.timezone.utc)
    end_localtime = current_timezone.localize(end)
    end_utc = end_localtime.astimezone(django.utils.timezone.utc)
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

    for electric_data_value in electric_data_values:
        electric_data = electric_data_value[electric_data_name]
        medition_date = electric_data_value['medition_date']
        electric_data_raw.append(
            dict(datetime=int(time.mktime(
                     django.utils.timezone.localtime(medition_date).timetuple())),
                 value=abs(electric_data),
                 certainty=True))

    return electric_data_raw


def get_consumer_unit_electric_data_interval_raw(
        electric_data_name,
        id,
        start,
        end
):
    electric_data_raw = []
    try:
        electric_data_name_local =\
            data_warehouse.views.CUMULATIVE_ELECTRIC_DATA_INVERSE[
                electric_data_name]

    except KeyError:
        return  electric_data_raw

    try:
        consumer_unit = c_center.models.ConsumerUnit.objects.get(pk=id)

    except c_center.models.ConsumerUnit.DoesNotExist:
        return electric_data_raw

    hour_delta = timedelta(hours=1)
    current_datetime = django.utils.timezone.localtime(
        datetime.datetime(year=start.year,
                          month=start.month,
                          day=start.day,
                          hour=start.hour))

    while current_datetime <= end:
        electric_data_values_prev =\
        c_center.models.ElectricDataTemp.objects.filter(
            profile_powermeter=consumer_unit.profile_powermeter,
            medition_date__gte=current_datetime - (hour_delta / 2),
            medition_date__lte=current_datetime
        ).order_by(
            'medition_date'
        ).reverse().values(
            'medition_date',
            electric_data_name_local
        )[:1]

        electric_data_values_next = \
            c_center.models.ElectricDataTemp.objects.filter(
                    profile_powermeter=consumer_unit.profile_powermeter,
                    medition_date__gte=current_datetime,
                    medition_date__lte=current_datetime + (hour_delta / 2)
                ).order_by(
                    'medition_date'
                ).values(
                    'medition_date',
                    electric_data_name_local
                )[:1]

        electric_data = 0
        if len(electric_data_values_prev) > 0 and len(electric_data_values_next) > 0:
            electric_data =\
                electric_data_values_next[0][electric_data_name_local] -\
                electric_data_values_prev[0][electric_data_name_local]

        medition_date = current_datetime
        electric_data_raw.append(
            dict(datetime=int(time.mktime(
                django.utils.timezone.localtime(medition_date).timetuple())),
                 electric_data=electric_data,
                 certainty=True))

        current_datetime += hour_delta

    return electric_data_raw


def get_consumer_unit_electric_data_interval_raw_optimized(
        electric_data_name,
        id,
        start,
        end
):
    electric_data_raw = []
    try:
        electric_data_name_local =\
            data_warehouse.views.CUMULATIVE_ELECTRIC_DATA_INVERSE[electric_data_name]

    except KeyError:
        return  electric_data_raw

    try:
        consumer_unit = c_center.models.ConsumerUnit.objects.get(pk=id)

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

    electric_data_raw_results_length = len(electric_data_raw_dictionaries)
    if not electric_data_raw_results_length:
        return electric_data_raw

    electric_data_raw_hours_dictionary = dict()
    timedelta_tolerance = timedelta(minutes=10)
    for electric_data_raw_dictionary in electric_data_raw_dictionaries:
        medition_date_current = electric_data_raw_dictionary['medition_date']
        electric_data_current = electric_data_raw_dictionary[electric_data_name_local]
        datetime_hour_current = variety.get_hour_from_datetime(medition_date_current)
        timedelta_current = abs(medition_date_current - datetime_hour_current)
        if timedelta_current < timedelta_tolerance:
            datetime_hour_current_string = datetime_hour_current.strftime("%Y-%m-%d-%H")
            medition_date_current_stored, electric_data_current_stored =\
                electric_data_raw_hours_dictionary.get(
                    datetime_hour_current_string,
                    (datetime.datetime.max.replace(tzinfo=django.utils.timezone.utc),
                     None)
                )

            if abs(medition_date_current_stored - datetime_hour_current) > timedelta_current:
                electric_data_raw_hours_dictionary[datetime_hour_current_string] =\
                    (medition_date_current, electric_data_current)

        datetime_hour_next = datetime_hour_current + timedelta(hours=1)
        timedelta_next = abs(medition_date_current - datetime_hour_next)
        if timedelta_next < timedelta_tolerance:
            datetime_hour_next_string = datetime_hour_next.strftime("%Y-%m-%d-%H")
            medition_date_next_stored, electric_data_next_stored =\
            electric_data_raw_hours_dictionary.get(
                datetime_hour_next_string,
                (datetime.datetime.max.replace(tzinfo=django.utils.timezone.utc),
                 None)
            )

            if abs(medition_date_next_stored - datetime_hour_next) > timedelta_next:
                electric_data_raw_hours_dictionary[datetime_hour_next_string] =\
                    (medition_date_current, electric_data_current)

    hour_delta = timedelta(hours=1)
    datetime_current_utc = datetime.datetime(year=start_utc.year,
                                             month=start_utc.month,
                                             day=start_utc.day,
                                             hour=start_utc.hour,
                                             tzinfo=django.utils.timezone.utc)

    while datetime_current_utc <= end_utc:
        datetime_current_utc_string = datetime_current_utc.strftime("%Y-%m-%d-%H")
        datetime_next_utc = datetime_current_utc + hour_delta
        datetime_next_utc_string = datetime_next_utc.strftime("%Y-%m-%d-%H")
        electric_data_value = 0
        if electric_data_raw_hours_dictionary.has_key(datetime_current_utc_string) and\
           electric_data_raw_hours_dictionary.has_key(datetime_next_utc_string):

            medition_date_value_current, electric_data_value_current =\
                electric_data_raw_hours_dictionary.get(datetime_current_utc_string)

            medition_date_value_next, electric_data_value_next =\
                electric_data_raw_hours_dictionary.get(datetime_next_utc_string)

            electric_data_value = electric_data_value_next - electric_data_value_current

        datetime_current_localtime = datetime_current_utc.astimezone(current_timezone)
        electric_data_raw_item = dict(datetime=int(time.mktime(datetime_current_localtime.timetuple())),
                                      electric_data=abs(electric_data_value),
                                      certainty=True)

        electric_data_raw.append(electric_data_raw_item)
        datetime_current_utc += hour_delta

    return electric_data_raw


def get_consumer_unit_electric_data_interval_raw_verification(
        electric_data_name,
        id,
        start,
        end
):
    electric_data_raw = []
    try:
        electric_data_name_local =\
        data_warehouse.views.CUMULATIVE_ELECTRIC_DATA_INVERSE[electric_data_name]

    except KeyError:
        return  electric_data_raw

    try:
        consumer_unit = c_center.models.ConsumerUnit.objects.get(pk=id)

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
    ).values('id', electric_data_name_local, 'medition_date')

    electric_data_raw_results_length = len(electric_data_raw_dictionaries)
    if not electric_data_raw_results_length:
        return electric_data_raw

    electric_data_raw_hours_dictionary = dict()
    timedelta_tolerance = timedelta(minutes=10)
    for electric_data_raw_dictionary in electric_data_raw_dictionaries:
        medition_id_current = electric_data_raw_dictionary['id']
        medition_date_current = electric_data_raw_dictionary['medition_date']
        electric_data_current = electric_data_raw_dictionary[electric_data_name_local]
        datetime_hour_current = variety.get_hour_from_datetime(medition_date_current)
        timedelta_current = abs(medition_date_current - datetime_hour_current)
        if timedelta_current < timedelta_tolerance:
            datetime_hour_current_string = datetime_hour_current.strftime("%Y-%m-%d-%H")
            medition_id_current_stored, medition_date_current_stored, electric_data_current_stored =\
            electric_data_raw_hours_dictionary.get(
                datetime_hour_current_string,
                (None,
                 datetime.datetime.max.replace(tzinfo=django.utils.timezone.utc),
                 None)
            )

            if abs(medition_date_current_stored - datetime_hour_current) > timedelta_current:
                electric_data_raw_hours_dictionary[datetime_hour_current_string] =\
                (medition_id_current, medition_date_current, electric_data_current)

        datetime_hour_next = datetime_hour_current + timedelta(hours=1)
        timedelta_next = abs(medition_date_current - datetime_hour_next)
        if timedelta_next < timedelta_tolerance:
            datetime_hour_next_string = datetime_hour_next.strftime("%Y-%m-%d-%H")
            medition_id_next_stored, medition_date_next_stored, electric_data_next_stored =\
            electric_data_raw_hours_dictionary.get(
                datetime_hour_next_string,
                (None,
                 datetime.datetime.max.replace(tzinfo=django.utils.timezone.utc),
                 None)
            )

            if abs(medition_date_next_stored - datetime_hour_next) > timedelta_next:
                electric_data_raw_hours_dictionary[datetime_hour_next_string] =\
                (medition_id_current, medition_date_current, electric_data_current)

    hour_delta = timedelta(hours=1)
    datetime_current_utc = datetime.datetime(year=start_utc.year,
        month=start_utc.month,
        day=start_utc.day,
        hour=start_utc.hour,
        tzinfo=django.utils.timezone.utc)

    while datetime_current_utc <= end_utc:
        datetime_current_utc_string = datetime_current_utc.strftime("%Y-%m-%d-%H")
        datetime_next_utc = datetime_current_utc + hour_delta
        datetime_next_utc_string = datetime_next_utc.strftime("%Y-%m-%d-%H")
        medition_pk_current = None
        medition_pk_next = None
        medition_date_value_current_localtime_string = "NULA"
        medition_date_value_next_localtime_string = "NULA"
        electric_data_value_current = None
        electric_data_value_next = None
        electric_data_value = 0
        if electric_data_raw_hours_dictionary.has_key(datetime_current_utc_string) and\
           electric_data_raw_hours_dictionary.has_key(datetime_next_utc_string):

            medition_pk_current, medition_date_value_current, electric_data_value_current =\
                electric_data_raw_hours_dictionary.get(datetime_current_utc_string)

            medition_pk_next, medition_date_value_next, electric_data_value_next =\
                electric_data_raw_hours_dictionary.get(datetime_next_utc_string)

            electric_data_value = electric_data_value_next - electric_data_value_current

            medition_date_value_current_localtime =\
                medition_date_value_current.astimezone(current_timezone)

            medition_date_value_current_localtime_string =\
                medition_date_value_current_localtime.strftime("%Y-%m-%d %H:%M")

            medition_date_value_next_localtime =\
                medition_date_value_next.astimezone(current_timezone)

            medition_date_value_next_localtime_string =\
                medition_date_value_next_localtime.strftime("%Y-%m-%d %H:%M")

        datetime_current_localtime = datetime_current_utc.astimezone(current_timezone)
        datetime_current_localtime_string =\
            datetime_current_localtime.strftime("%Y-%m-%d %H:%M")

        datetime_next_localtime = datetime_next_utc.astimezone(current_timezone)
        datetime_next_localtime_string =\
            datetime_next_localtime.strftime("%Y-%m-%d %H:%M")

        electric_data_raw_item =\
            (datetime_current_localtime_string,
             medition_pk_current,
             medition_date_value_current_localtime_string,
             electric_data_value_current,
             datetime_next_localtime_string,
             medition_pk_next,
             medition_date_value_next_localtime_string,
             electric_data_value_next,
             datetime_current_localtime_string,
             electric_data_value)

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


def cut_electric_data_list_values(electric_data_list, data_values_length):
    for index in range(0, len(electric_data_list)):
        electric_data_list[index] = electric_data_list[index][
                                    :data_values_length]

    return True


def get_default_datetime_end():
    return datetime.datetime.combine(
        datetime.date.today() - datetime.timedelta(days=1),
        datetime.time(0))


def get_default_datetime_start():
    return get_default_datetime_end() - datetime.timedelta(days=1)


def get_electric_data_list_json(electric_data_list, limits=None):
    domains_number = len(electric_data_list)
    if domains_number < 1:
        return json.dumps([])

    electric_data_max_value = sys.float_info.min
    electric_data_min_value = sys.float_info.max
    rows = []
    rows_number = len(electric_data_list[0])
    for row_index in range(0, rows_number):
        row_data = []
        for domain_index in range(0, domains_number):
            current_datetime = electric_data_list[domain_index][row_index][
                               "datetime"]
            current_electric_data =\
            float(electric_data_list[domain_index][row_index]["electric_data"])

            current_certainty = electric_data_list[domain_index][row_index][
                                "certainty"]
            row_data.append(dict(datetime=current_datetime,
                                 electric_data=current_electric_data,
                                 certainty=current_certainty))

            if electric_data_max_value < current_electric_data:
                electric_data_max_value = current_electric_data

            if electric_data_min_value > current_electric_data:
                electric_data_min_value = current_electric_data

        rows.append(row_data)

    if electric_data_max_value < electric_data_min_value:
        electric_data_max_value = 100.0
        electric_data_min_value = -100.0

    elif electric_data_max_value == electric_data_min_value:
        electric_data_max_value += abs(electric_data_max_value * 0.1)
        electric_data_min_value -= abs(electric_data_min_value * 0.1)

    if limits is not None:
        electric_data_max_min_delta_value =\
        float(electric_data_max_value - electric_data_min_value)

        limits['max'] =\
        float(electric_data_max_value) + (
        electric_data_max_min_delta_value * 0.1)

        limits['min'] =\
        float(electric_data_min_value) - (
        electric_data_max_min_delta_value * 0.1)

    return json.dumps(rows)


def normalize_electric_data_list(electric_data_list):
    if len(electric_data_list) < 1:
        return 0

    minimum_length = len(electric_data_list[0])
    for electric_data_values in electric_data_list:
        current_length = len(electric_data_values)
        minimum_length = min(current_length, minimum_length)
        is_prepare_electric_data_successful = prepare_electric_data(
            electric_data_values)
        if not is_prepare_electric_data_successful:
            return 0

    return minimum_length


def prepare_electric_data(electric_data_values):
    electric_data_values_length = len(electric_data_values)
    first_valid_value_index = None
    last_valid_value_index = None
    for index in range(0, electric_data_values_length):
        try:
            if electric_data_values[index]['electric_data'] is not None:
                last_valid_value_index = index
                if first_valid_value_index is None:
                    first_valid_value_index = index

        except  KeyError:
            return False

    if first_valid_value_index is None or last_valid_value_index is None:
        return False

    for index_first in range(0, first_valid_value_index):
        electric_data_values[index_first]['electric_data'] =\
        electric_data_values[first_valid_value_index]['electric_data']

    for index_last in range(last_valid_value_index,
                            electric_data_values_length):
        electric_data_values[index_last]['electric_data'] =\
        electric_data_values[last_valid_value_index]['electric_data']

    index_patch = first_valid_value_index + 1
    while index_patch < last_valid_value_index:
        if electric_data_values[index_patch]['electric_data'] is None:
            lower_index = index_patch - 1
            lower_value = electric_data_values[lower_index]['electric_data']
            while electric_data_values[index_patch]['electric_data'] is None \
            and\
                  index_patch < last_valid_value_index:
                index_patch += 1

            upper_index = index_patch
            upper_value = electric_data_values[upper_index]['electric_data']
            none_count = upper_index - lower_index
            delta_value = (upper_value - lower_value) / float(none_count)
            for i in range(0, none_count):
                electric_data_values[lower_index + i]['electric_data'] =\
                lower_value + (i * delta_value)

        else:
            index_patch += 1

    return True


def merge_electric_data_values_lists(
        list_main,
        list_main_contributions,
        list_temporary,
        list_temporary_consumer_unit_id,
        consumer_units_read_rate_dictionary
):
    list_temporary_length = len(list_temporary)
    list_main_index = 0
    list_temporary_index = 0
    continue_processing = list_main_index < len(list_main) or\
                          list_temporary_index < list_temporary_length

    while continue_processing:
        list_temporary_item_current =\
            list_temporary[list_temporary_index] if list_temporary_length > list_temporary_index\
            else None

        if list_temporary_item_current is None:
            return

        list_main_item_current =\
            list_main[list_main_index] if len(list_main) > list_main_index else None

        if list_main_item_current is None:
            list_main.insert(list_main_index, list_temporary_item_current)
            list_temporary_index += 1

        else:
            if list_temporary_item_current['datetime'] < list_main_item_current['datetime']:
                list_main.insert(list_main_index, list_temporary_item_current)
                list_temporary_index += 1

            elif list_temporary_item_current['datetime'] > list_main_item_current['datetime']:
                list_main_index += 1

            else:
                list_main_item_current['electric_data'] +=\
                    list_temporary_item_current['electric_data']

                list_main_index += 1
                list_temporary_index += 1

        continue_processing = list_main_index < len(list_main) or\
                              list_temporary_index < list_temporary_length

    return


def render_graphics(request):
    if request.method == "GET":
        try:
            electric_data = request.GET['graph']
            granularity = request.GET['granularity']

        except KeyError:
            return django.http.HttpResponse("")

        template_variables = dict()
        parameter_units = dict(kWh_consumido="kWh/h",
                               TotalkWhIMPORT="kW/h",
                               kWL3="kW",
                               kWL2="kW",
                               kWL1="kW",
                               kW="kW",
                               I1="I",
                               I2="I",
                               I3="I",
                               V1="V",
                               V2="V",
                               V3="V",
                               PF="%",
                               )
        template_variables['electric_param'] = parameter_units[electric_data]
        cumulative_electric_data = (
        "TotalkWhIMPORT", "TotalkvarhIMPORT", "kWh", "kvarh")
        suffix_consumed = "_consumido"
        is_interval_graphic = False
        suffix_index = string.find(electric_data, suffix_consumed)
        if suffix_index >= 0:
            electric_data = electric_data[:suffix_index]
            is_interval_graphic = True

        template_variables["is_cumulative_electric_data"] =\
            electric_data in cumulative_electric_data

        template_variables["is_interval_graphic"] = is_interval_graphic

        template_variables['electric_data'] = electric_data

        data = []
        consumer_unit_counter = 1
        consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
        date_start_get_key = "date-start%02d" % consumer_unit_counter
        date_end_get_key = "date-end%02d" % consumer_unit_counter
        while request.GET.has_key(consumer_unit_get_key):
            consumer_unit_id = request.GET[consumer_unit_get_key]
            template_variables['consumer_unit_id'] = consumer_unit_id
            if request.GET.has_key(date_start_get_key) and\
               request.GET.has_key(date_end_get_key):
                datetime_start = datetime.datetime.strptime(
                    request.GET[date_start_get_key],
                    "%Y-%m-%d")

                datetime_end =\
                datetime.datetime.strptime(request.GET[date_end_get_key],
                                           "%Y-%m-%d") +\
                datetime.timedelta(days=1)

            else:
                datetime_start = get_default_datetime_start()
                datetime_end = get_default_datetime_end()

            data.append((consumer_unit_id, datetime_start, datetime_end))
            consumer_unit_counter += 1
            consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
            date_start_get_key = "date-start%02d" % consumer_unit_counter
            date_end_get_key = "date-end%02d" % consumer_unit_counter

        electric_data_list = []
        consumer_unit_and_time_interval_information_list = []
        electric_data_datetime_first = None
        for id, start, end in data:
            try:
                consumer_unit_current = c_center.models.ConsumerUnit.objects.get(pk=id)

            except c_center.models.ConsumerUnit.DoesNotExist:
                raise django.http.Http404

#            consumer_unit_list = c_center.c_center_functions.get_consumer_units(
#                                     consumer_unit_current)
#
#            consumer_unit_electric_data_values = []
#            for consumer_unit_item in consumer_unit_list:
#                pass

            if is_interval_graphic:
                electric_data_values =\
                    data_warehouse.views.get_consumer_unit_electric_data_interval(
                        electric_data,
                        granularity,
                        #consumer_unit_item.pk,
                        id,
                        start,
                        end)

                if electric_data_values is None:
                    electric_data_values = \
                        get_consumer_unit_electric_data_interval_raw_optimized(
                            electric_data,
                            #consumer_unit_item.pk,
                            id,
                            start,
                            end)

            else:
                electric_data_values =\
                    data_warehouse.views.get_consumer_unit_electric_data(
                        electric_data,
                        granularity,
                        #consumer_unit_item.pk,
                        id,
                        start,
                        end)

                if electric_data_values is None:
                    electric_data_values = get_consumer_unit_electric_data_raw(
                                               electric_data,
                                               #consumer_unit_item.pk,
                                               id,
                                               start,
                                               end)

#                data_warehouse.views.logger.info(consumer_unit_item)
#                merge_electric_data_values_lists(consumer_unit_electric_data_values,
#                                                 electric_data_values)

            electric_data_list.append(electric_data_values)
            consumer_unit_and_time_interval_information =\
                data_warehouse.views.get_consumer_unit_and_time_interval_information(
                    id,
                    start,
                    end)

            consumer_unit_and_time_interval_information_list.append(
                consumer_unit_and_time_interval_information)


        minimum_values_number = normalize_electric_data_list(electric_data_list)
        is_cut_electric_data_list_successful = cut_electric_data_list_values(
                                                   electric_data_list,
                                                   minimum_values_number)

        if len(electric_data_list) > 0 and len(electric_data_list[0]) > 0:
            template_variables['fi'] =\
                datetime.datetime.fromtimestamp(electric_data_list[0][0]['datetime'])

        limits = dict()
        template_variables['rows_data'] = get_electric_data_list_json(
                                              electric_data_list,
                                              limits)

        print template_variables['rows_data']

        template_variables['columns'] = consumer_unit_and_time_interval_information_list
        template_variables['limits'] = limits
        template_variables['granularity'] = granularity
        template_variables['years'] = request.session['years']

        template_context = django.template.context.RequestContext(request,
                                                                  template_variables)

        return django.shortcuts.render_to_response(
            "consumption_centers/graphs/graphics.html",
            template_context)

    else:
        raise django.http.Http404


def render_graphics_extended(request):
    print "render_graphics_extended"
    if request.method == "GET":
        try:
            granularity = request.GET['granularity']

        except KeyError:
            return django.http.HttpResponse("")

        template_variables = dict()
        parameter_units = dict(
            kWh_consumido="kWh/h",
            TotalkWhIMPORT="kW/h",
            kWL3="kW",
            kWL2="kW",
            kWL1="kW",
            kW="kW",
            I1="I",
            I2="I",
            I3="I",
            V1="V",
            V2="V",
            V3="V",
            PF="%",
        )

        data = []
        consumer_unit_counter = 1
        consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
        date_start_get_key = "date-start%02d" % consumer_unit_counter
        date_end_get_key = "date-end%02d" % consumer_unit_counter
        parameter_get_key = "parameter%02d" % consumer_unit_counter
        while request.GET.has_key(consumer_unit_get_key):
            consumer_unit_id = request.GET[consumer_unit_get_key]
            parameter = request.GET[parameter_get_key]
            if request.GET.has_key(date_start_get_key) and\
               request.GET.has_key(date_end_get_key):
                datetime_start = datetime.datetime.strptime(
                                     request.GET[date_start_get_key],
                                     "%Y-%m-%d")

                datetime_end =\
                    datetime.datetime.strptime(request.GET[date_end_get_key],
                                               "%Y-%m-%d") +\
                    datetime.timedelta(days=1)

            else:
                datetime_start = get_default_datetime_start()
                datetime_end = get_default_datetime_end()

            data.append((consumer_unit_id, datetime_start, datetime_end, parameter))
            consumer_unit_counter += 1
            consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
            date_start_get_key = "date-start%02d" % consumer_unit_counter
            date_end_get_key = "date-end%02d" % consumer_unit_counter
            parameter_get_key = "parameter%02d" % consumer_unit_counter

        electric_data_list = []
        consumer_unit_and_time_interval_information_list = []
        electric_data_datetime_first = None
        for id, start, end, electrical_parameter in data:
            try:
                consumer_unit_current = c_center.models.ConsumerUnit.objects.get(pk=id)

            except c_center.models.ConsumerUnit.DoesNotExist:
                raise django.http.Http404

            electric_data_values =\
            data_warehouse.views.get_consumer_unit_electric_data(
                electrical_parameter,
                granularity,
                #consumer_unit_item.pk,
                id,
                start,
                end)

            if electric_data_values is None:
                electric_data_values = get_consumer_unit_electric_data_raw(
                    electrical_parameter,
                    #consumer_unit_item.pk,
                    id,
                    start,
                    end)

            electric_data_list.append(electric_data_values)
            consumer_unit_and_time_interval_information =\
            data_warehouse.views.get_consumer_unit_and_time_interval_information(
                id,
                start,
                end)

            consumer_unit_and_time_interval_information['parameter'] =\
                parameter_units[electrical_parameter]

            consumer_unit_and_time_interval_information_list.append(
                consumer_unit_and_time_interval_information)


        minimum_values_number = normalize_electric_data_list(electric_data_list)
        is_cut_electric_data_list_successful = cut_electric_data_list_values(
            electric_data_list,
            minimum_values_number)

        if len(electric_data_list) > 0 and len(electric_data_list[0]) > 0:
            template_variables['fi'] =\
            datetime.datetime.fromtimestamp(electric_data_list[0][0]['datetime'])

        limits = dict()
        template_variables['rows_data'] = get_electric_data_list_json(
            electric_data_list,
            limits)

        print template_variables['rows_data']

        template_variables['columns'] = consumer_unit_and_time_interval_information_list
        template_variables['limits'] = limits
        template_variables['granularity'] = granularity

        template_context = django.template.context.RequestContext(request,
            template_variables)

        return django.shortcuts.render_to_response(
            "consumption_centers/graphs/graphics_extended.html",
            template_context)

    else:
        raise django.http.Http404


def render_graphics_interval_verification(
        request
):
    template_variables = dict()
    if request.method == "GET":
        try:
            consumer_unit_id = request.GET['consumer-unit-id']
            electric_data_name = request.GET['electric-data-name']
            datetime_start = datetime.datetime.strptime(request.GET['date-start'],
                                                        "%Y-%m-%d")

            datetime_end =\
                datetime.datetime.strptime(request.GET['date-end'], "%Y-%m-%d") +\
                datetime.timedelta(days=1)

        except KeyError:
            raise django.http.Http404

        cumulative_electric_data = ("TotalkWhIMPORT", "TotalkvarhIMPORT", "kWh", "kvarh")
        if electric_data_name in cumulative_electric_data:
            electric_data_interval_raw_verification_tuple_list =\
                get_consumer_unit_electric_data_interval_raw_verification(
                    electric_data_name,
                    consumer_unit_id,
                    datetime_start,
                    datetime_end)

            template_variables['electric_data_interval_raw_verification_tuple_list'] =\
                electric_data_interval_raw_verification_tuple_list

    template_context = django.template.context.RequestContext(request,
                                                              template_variables)

    return django.shortcuts.render_to_response(
               "consumption_centers/graphs/graphics_interval_verification.html",
               template_context)


def render_graphics_month_consumption_trend(
        request
):

    template_variables = dict()
    if request.method == "GET":
        try:
            consumer_unit_id = request.GET['consumer-unit-id']
            year = request.GET['year']
            month = request.GET['month']

        except KeyError:
            raise django.http.Http404

        weeks_number_in_month = variety.get_weeks_number_in_month(year, month)
        week_first_start_datetime, week_first_end_datetime =\
            variety.get_week_start_datetime_end_datetime_tuple(year, month, 1)

        week_last_start_datetime, week_last_end_datetime =\
            variety.get_week_start_datetime_end_datetime_tuple(
                year,
                month,
                weeks_number_in_month)

        electric_data_interval_raw_dictionary_list =\
            get_consumer_unit_electric_data_interval_raw_optimized(
                "TotalkWhIMPORT",
                consumer_unit_id,
                week_first_start_datetime,
                week_last_end_datetime
            )

    template_context = django.template.context.RequestContext(
                           request,
                           template_variables)

    return django.shortcuts.render_to_response(
               "consumption_centers/graphs/graphics_month_consumption_trend.html",
               template_context)
