#coding:utf-8

# Python imports
import pdb
import datetime
import logging
import numpy
import sys
import time
import json


# Django imports
import django.http
import django.shortcuts
import django.utils.timezone
import django.template.context

import alarms
from data_warehouse_extended.models import ElectricalParameter
from data_warehouse_extended.views import get_electrical_parameter, \
    get_consumer_unit_electrical_parameter_data_list, get_instant_delta_all, \
    get_consumer_unit_profile,get_instant_delta,get_instants_list
from c_center.c_center_functions import get_consumer_units
from c_center.calculations import factorpotencia
from c_center.graphics import get_consumer_unit_electric_data_raw
from c_center.calculations import obtenerTipoPeriodoObj

import reports.globals

from c_center.models import ConsumerUnit

logger = logging.getLogger("reports")

################################################################################
#
# Utility Scripts
#
################################################################################


def get_axis_dictionary_stored(
        data_clusters_list_normalized,
        column_units_list
):
    """
    It generate a dicitonary with the axis, based in the data and
    the units

    :param data_clusters_list_normalized: A list of the data cluster
    :param column_units_list: A list of the units
    :return: A dictionary with the axis
    """
    data_clusters_list_length = len(data_clusters_list_normalized[0])
    column_units_list_length = len(column_units_list)
    if data_clusters_list_length != column_units_list_length:
        return None

    axis_dictionary = dict()
    for data_cluster_index in range(0, data_clusters_list_length):
        column_units = column_units_list[data_cluster_index]
        data_cluster = data_clusters_list_normalized[data_cluster_index]
        data_cluster_values_list =\
            [float(data_dictionary['value']) for data_dictionary in data_cluster]

        if data_cluster_values_list:
            data_cluster_max_value = max(data_cluster_values_list)
            data_cluster_min_value = min(data_cluster_values_list)
            if axis_dictionary.has_key(column_units):
                axis_dictionary_value = axis_dictionary[column_units]
                axis_max_value = axis_dictionary_value['max']
                axis_dictionary_value['max'] = \
                    max(axis_max_value, data_cluster_max_value)

                axis_min_value = axis_dictionary_value['min']
                axis_dictionary_value['min'] = \
                    min(axis_min_value, data_cluster_min_value)

                axis_dictionary[column_units] = axis_dictionary_value

            else:
                axis_dictionary[column_units] = {
                    'name': column_units,
                    'max': data_cluster_max_value,
                    'min': data_cluster_min_value
                }

    return axis_dictionary


def get_axis_dictionary(
        data_clusters_list_normalized,
        column_units_list
):
    """
    It generate a dicitonary with the axis, based in the data and
    the units

    :param data_clusters_list_normalized: A list of the data cluster
    :param column_units_list: A list of the units
    :return: A dictionary with the axis
    """
    data_clusters_list_length = len(data_clusters_list_normalized)
    column_units_list_length = len(column_units_list)
    if data_clusters_list_length != column_units_list_length:
        return None

    axis_dictionary = dict()
    for data_cluster_index in range(0, data_clusters_list_length):
        column_units = column_units_list[data_cluster_index]
        data_cluster = data_clusters_list_normalized[data_cluster_index]
        data_cluster_values_list =\
            [float(data_dictionary['value']) for data_dictionary in data_cluster]

        if data_cluster_values_list:
            data_cluster_max_value = max(data_cluster_values_list)
            data_cluster_min_value = min(data_cluster_values_list)
            if axis_dictionary.has_key(column_units):
                axis_dictionary_value = axis_dictionary[column_units]
                axis_max_value = axis_dictionary_value['max']
                axis_dictionary_value['max'] = \
                    max(axis_max_value, data_cluster_max_value)

                axis_min_value = axis_dictionary_value['min']
                axis_dictionary_value['min'] = \
                    min(axis_min_value, data_cluster_min_value)

                axis_dictionary[column_units] = axis_dictionary_value

            else:
                axis_dictionary[column_units] = {
                    'name': column_units,
                    'max': data_cluster_max_value,
                    'min': data_cluster_min_value
                }

    return axis_dictionary


def get_axis_dictionaries_list (
        axis_dictionary
):
    """
    It change the dicitonary of axis to a list of axis

    :param axis_dictionary: A dictionary with the axis
    :return: A list with the axis
    """

    axis_dictionaries_list = []
    if axis_dictionary:
        for _, value in axis_dictionary.items():
            axis_dictionaries_list.append(value)

    return axis_dictionaries_list


def get_column_strings_electrical_parameter(
        request_data_list_normalized,
):
    """
    Returns a list with the electrical parameters name

    :param request_data_list_normalized: A list with data
    :return A list with the electrical parameters name
    """

    column_strings_list = []
    for _, _, _, electrical_parameter_name\
            in request_data_list_normalized:

        column_strings_list.append(electrical_parameter_name)

    return column_strings_list


def get_series_legends(
        request_data_list_normalized,
):
    """
    Returns a list with the electrical parameters label

    :param request_data_list_normalized: A list with data
    :return A list with the electrical parameters name
    """

    column_strings_list = []
    cont = 0
    f_i = None
    f_f = None
    for _, fi, ff, electrical_parameter_name\
            in request_data_list_normalized:
        if f_i is None and f_f is None:
            f_i, f_f = fi, ff
            cont += 1
        elif (f_i, f_f) != (fi, ff):
            f_i, f_f = fi, ff
            cont += 1
        str_append = ''
        if cont > 1:
            str_append = ' Periodo ' + str(cont)

        column_strings_list.append(electrical_parameter_name + str_append)

    return column_strings_list


def get_column_units_axis_indexes(
        column_units_list,
        axis_dictionaries_list
):
    """
    It make a list with the units and the axis

    :param column_units_list: A list with the column units
    :param axis_dictionaries_list: A dictionary with the axis
    :return: A list with the unit and the indexes
    """
    column_units_axis_indexes = []
    for column_unit in column_units_list:
        for axis_dictionary_index in range(0, len(axis_dictionaries_list)):
            axis_dictionary = axis_dictionaries_list[axis_dictionary_index]
            if column_unit == axis_dictionary['name']:
                column_units_axis_indexes.append(axis_dictionary_index)

    if len(column_units_axis_indexes) != len(column_units_list):
        return None

    return column_units_axis_indexes


def get_column_units_list(
        request_data_list_normalized
):
    """
    Gets the column units if the data

    :param request_data_list_normalized: A list of data
    :return: a list of the units of the column
    """
    column_units_list = []
    for _, _, _, electrical_parameter_name\
        in request_data_list_normalized:

        try:
            nm = ElectricalParameter.objects.get(
                name=electrical_parameter_name
            )
            nm = nm.name_transactional
            electrical_parameter_info =\
                alarms.models.ElectricParameters.objects.get(
                    name=nm)

        except alarms.models.ElectricParameters.DoesNotExist:
            logger.error()
            return None

        column_units_list.append(electrical_parameter_info.param_units)

    return column_units_list


def get_data_cluster_consumed_normalized(
        consumer_unit_id,
        datetime_from,
        datetime_to,
        electrical_parameter_name,
        granularity_seconds
):
    """
    It make a JSON with the data cluster consumed normalized

    :param consumer_unit_id: An int with the id of the consumer unit
    :param datetime_from: A Datetime object
    :param datetime_to: A Datetime object
    :param electrical_parameter_name: An string with the name of the ep
    :param granularity_seconds: An Integer that represents the number of
                seconds between the points to be retrieved.
    :return: A JSON with the Data Cluster
    """
    #
    # Localize datetimes (if neccesary) and convert to UTC
    #
    timezone_current = django.utils.timezone.get_current_timezone()
    datetime_from_local = datetime_from
    if datetime_from_local.tzinfo is None:
        datetime_from_local = timezone_current.localize(datetime_from)

    datetime_from_utc =\
        datetime_from_local.astimezone(django.utils.timezone.utc)

    datetime_to_local = datetime_to
    if datetime_to_local.tzinfo is None:
        datetime_to_local = timezone_current.localize(datetime_to)

    datetime_to_utc = datetime_to_local.astimezone(django.utils.timezone.utc)

    #
    # Get the Electrical Parameter
    #
    electrical_parameter =\
        get_electrical_parameter(
            electrical_parameter_name=electrical_parameter_name)

    if electrical_parameter is None:
        logger.error(
            reports.globals.SystemError.GET_DATA_CLUSTER_CONSUMED_JSON_ERROR)

        return None

    if electrical_parameter.type !=\
        ElectricalParameter.CUMULATIVE:

        logger.error(
            reports.globals.SystemError.GET_DATA_CLUSTER_CONSUMED_JSON_ERROR)

        return None

    try:
        consumer_unit =\
            ConsumerUnit.objects.get(pk=consumer_unit_id)

    except ConsumerUnit.DoesNotExist:
        logger.error(
            reports.globals.SystemError.GET_DATA_CLUSTER_CONSUMED_JSON_ERROR)

        return None

    #
    # Get the data cluster.
    #
    data_cluster =\
        get_consumer_unit_electrical_parameter_data_clustered(
            consumer_unit,
            datetime_from_utc,
            datetime_to_utc,
            electrical_parameter_name,
            granularity_seconds)

    normalize_data_cluster(data_cluster)
    #
    # Build the json.
    #
    data_cluster_json = []
    datos_len = len(data_cluster)
    for data_index in range(0, datos_len - 1, 12):
        data_dictionary_current = data_cluster[data_index]
        data_dictionary_next = data_cluster[data_index + 12]
        datetime_current = data_dictionary_current['datetime']
        value_current =\
            data_dictionary_next['value'] - \
            data_dictionary_current['value']

        certainty_current = \
            data_dictionary_current['certainty'] and \
            data_dictionary_next['certainty']

        data_dictionary_json = {
            'datetime': datetime_current,
            'value': round(float(value_current), 2),
            'certainty': certainty_current
        }

        data_cluster_json.append(data_dictionary_json)

    return data_cluster_json


def get_data_cluster_limits(
        data_cluster_normalized
):

    maximum = sys.float_info.min
    minimum = sys.float_info.max

    for data_dictionary in data_cluster_normalized:
        if data_dictionary['value'] is None:
            data_dictionary_value = float(0)
        else:
            data_dictionary_value = round(float(data_dictionary['value']), 2)
        maximum = max(data_dictionary_value, maximum)
        minimum = min(data_dictionary_value, minimum)

    if maximum == sys.float_info.min or minimum == sys.float_info.max:
        maximum = 1
        minimum = 0

    return maximum, minimum


def get_data_clusters_json(
        data_clusters_list_normalized
):
    """
    Change the list of data clusters to a JSON.

    :param data_clusters_list_normalized: A list of data
    :return: A json of data clusters
    """

    data_clusters_length = len(data_clusters_list_normalized)
    if data_clusters_length < 1:
        return None

    data_cluster_instants_number = len(data_clusters_list_normalized[0])
    if data_cluster_instants_number < 1:
        return None

    data_clusters_json = []
    for instant_index in range(0, data_cluster_instants_number):
        instant_json = []
        for data_cluster_index in range(0, data_clusters_length):
            data_cluster_dictionary =\
                data_clusters_list_normalized[data_cluster_index][instant_index]

            data_cluster_dictionary_copy = data_cluster_dictionary.copy()
            float_data_value = float(data_cluster_dictionary['value'])
            data_cluster_dictionary_copy['value'] = float_data_value
            instant_json.append(data_cluster_dictionary_copy)

        data_clusters_json.append(instant_json)

    return data_clusters_json


def get_data_clusters_list(
        request_data_list_normalized,
        granularity
):
    """
    Based on the granularity and the data normalized it made a
    list of data with the clusters

    :param request_data_list_normalized: A list of data
    :param granularity: An Integer that represents the number of
                seconds between the points to be retrieved.
    :return a list of data with the clusters
    """

    data_clusters_list = []
    for consumer_unit_id, datetime_from, datetime_to, electrical_parameter_name\
        in request_data_list_normalized:

        try:
            consumer_unit =\
                ConsumerUnit.objects.get(pk=consumer_unit_id)

        except ConsumerUnit.DoesNotExist:
            logger.error(
                reports.globals.SystemError.GET_DATA_CLUSTERS_LIST_ERROR)

            return None
        if granularity == "raw" \
            and consumer_unit.profile_powermeter\
                .powermeter.powermeter_anotation != "Medidor Virtual":
            data_cluster = \
                get_consumer_unit_electric_data_raw(
                    electrical_parameter_name,
                    consumer_unit_id,
                    datetime_from,
                    datetime_to)
        elif granularity == "raw" and \
                        consumer_unit.profile_powermeter.powermeter\
                    .powermeter_anotation == "Medidor Virtual":
                seconds = 300
                data_cluster = \
                    get_consumer_unit_electrical_parameter_data_virtual(
                        consumer_unit,
                        datetime_from,
                        datetime_to,
                        electrical_parameter_name,
                        seconds)
        else:
            data_cluster =\
                get_consumer_unit_electrical_parameter_data_clustered(
                    consumer_unit,
                    datetime_from,
                    datetime_to,
                    electrical_parameter_name)

        if data_cluster is None:
            logger.error(
                reports.globals.SystemError.GET_DATA_CLUSTERS_LIST_ERROR)

            return None

        data_clusters_list.append(data_cluster)

    return data_clusters_list


def get_data_clusters_list_limits(
        data_clusters_list_normalized
):

    """
    It returns the maximum and minimum value of the list

    :param data_clusters_list_normalized: A list of data
    :return 2 Floats, , maximum, minimum

    """
    maximum = sys.float_info.min
    minimum = sys.float_info.max
    for data_cluster in data_clusters_list_normalized:
        for data_dictionary in data_cluster:
            data_dictionary_value = float(data_dictionary['value'])
            maximum = max(data_dictionary_value, maximum)
            minimum = min(data_dictionary_value, minimum)

    return maximum, minimum


def get_instant_delta_from_timedelta(
        timedelta
):
    """
    Returns a list for generate the number of points. If the Instant Delta
    that generates the number of points closest to the
    ideal number of points generates a number of points between the maximum
    and the minimum number of points, return the Instant Delta, Otherwise,
    return the Instant Delta which generates the number of points
    closest to the minimum number of points or the maximum number of points.

    :param timedelta: A Datetime object.
    :return a list that generates the number of points
    """

    timedelta_seconds = timedelta.seconds + (timedelta.days * 24 * 3600)
    instant_deltas = get_instant_delta_all()
    if len(instant_deltas) < 1:
        logger.error(
            reports.globals.SystemError.GET_INSTANT_DELTA_FROM_TIMEDELTA_ERROR)

        return None

    #
    # Get the Instant Deltas which the number of points it'll generate is the
    # closest to the ideal number of points, to the maximum number of points and
    # to the minimum number of points.
    #
    ideal_closest_instant_delta = instant_deltas[0]
    ideal_closest_points =\
        abs(reports.globals.Constant.POINTS_IN_GRAPHICS_IDEAL -
            (timedelta_seconds / ideal_closest_instant_delta.delta_seconds))

    max_closest_instant_delta = instant_deltas[0]
    max_closest_points =\
        abs(reports.globals.Constant.POINTS_IN_GRAPHICS_MAX -
            (timedelta_seconds / max_closest_instant_delta.delta_seconds))

    min_closest_instant_delta = instant_deltas[0]
    min_closest_points =\
        abs(reports.globals.Constant.POINTS_IN_GRAPHICS_MIN -
            (timedelta_seconds / min_closest_instant_delta.delta_seconds))

    for instant_delta in instant_deltas:
        instant_delta_points_count =\
            timedelta_seconds / instant_delta.delta_seconds

        distance_to_ideal =\
            abs(reports.globals.Constant.POINTS_IN_GRAPHICS_IDEAL -
                instant_delta_points_count)

        if distance_to_ideal < ideal_closest_points:
            ideal_closest_instant_delta = instant_delta
            ideal_closest_points = distance_to_ideal

        distance_to_max =\
            abs(reports.globals.Constant.POINTS_IN_GRAPHICS_MAX -
                instant_delta_points_count)

        if distance_to_max < max_closest_points:
            max_closest_instant_delta = instant_delta
            max_closest_points = distance_to_max

        distance_to_min =\
            abs(reports.globals.Constant.POINTS_IN_GRAPHICS_MIN -
                instant_delta_points_count)

        if distance_to_min < min_closest_points:
            min_closest_instant_delta = instant_delta
            min_closest_points = distance_to_min

    is_instant_delta_lesser_than_max =\
        (reports.globals.Constant.POINTS_IN_GRAPHICS_IDEAL + ideal_closest_points) <\
        reports.globals.Constant.POINTS_IN_GRAPHICS_MAX

    is_instant_delta_greater_than_min =\
        (reports.globals.Constant.POINTS_IN_GRAPHICS_IDEAL - ideal_closest_points) >\
        reports.globals.Constant.POINTS_IN_GRAPHICS_MIN

    #
    # If the Instant Delta that generates the number of points closest to the
    # ideal number of points generates a number of points between the maximum
    # and the minimum number of points, return the Instant Delta
    #
    if is_instant_delta_greater_than_min and is_instant_delta_lesser_than_max:
        return ideal_closest_instant_delta

    #
    # Otherwise, return the Instant Delta which generates the number of points
    # closest to the minimum number of points or the maximum number of points.
    #
    else:
        if max_closest_points < min_closest_points:
            return max_closest_instant_delta

        return min_closest_instant_delta


def get_request_data_list_normalized(
        request_data_list
):
    """
    It sets all the deltas to the minimum delta, it normalized
    the data in the list

    :param request_data_list: A lis with the request data
    :return: A lis with the data normalized
    """
    #
    # Get the minimum time delta.
    #
    minimum_time_delta = datetime.timedelta.max
    for consumer_unit_id, datetime_from, datetime_to, electrical_parameter_name\
        in request_data_list:

        current_time_delta = datetime_to - datetime_from
        if current_time_delta < datetime.timedelta(0):
            logger.error(
                reports.globals.SystemError.GET_NORMALIZED_REQUEST_DATA_LIST_ERROR)

            return None

        if current_time_delta < minimum_time_delta:
            minimum_time_delta = current_time_delta

    #
    # Set all the time deltas to the minimun time delta.
    #
    request_data_list_normalized = []
    for consumer_unit_id, datetime_from, datetime_to, electrical_parameter_name\
        in request_data_list:

        request_data_list_item_normalized =\
            (consumer_unit_id,
             datetime_from,
             datetime_from + minimum_time_delta,
             electrical_parameter_name)

        request_data_list_normalized.append(
            request_data_list_item_normalized)

    return request_data_list_normalized


def get_data_statistics(
        data_list
):
    """
    Obtains all the statistics for that data list

    :param data_list: An Array of values
    :return A dictionary with the statistics

    """
    data_cluster_values_array = numpy.array(data_list)
    data_cluster_values_array.sort()
    data_cluster_mean = data_cluster_values_array.mean()
    data_cluster_maximum = data_cluster_values_array.max()
    data_cluster_minimum = data_cluster_values_array.min()
    data_cluster_median = numpy.median(data_cluster_values_array)
    data_cluster_standard_deviation = data_cluster_values_array.std()

    statistics = {
        "mean": data_cluster_mean,
        "maximum": data_cluster_maximum,
        "minimum": data_cluster_minimum,
        "median": data_cluster_median,
        "standard_deviation": data_cluster_standard_deviation
    }
    return statistics


def get_data_clusters_statistics(
        data_clusters_list_normalized
):
    """
    Obtains all the statistics for that cluster data list

    :param data_clusters_list_normalized: A list of data
    :return A dictionary with the statistics of that data

    """
    data_clusters_statistics = []
    for data_cluster in data_clusters_list_normalized:
        data_cluster_values_list = []
        for data_dictionary in data_cluster:
            data_cluster_values_list.append(float(data_dictionary['value']))

        if data_cluster_values_list:
            data_cluster_values_array = numpy.array(data_cluster_values_list)
            data_cluster_values_array.sort()
            data_cluster_mean = data_cluster_values_array.mean()
            data_cluster_maximum = data_cluster_values_array.max()
            data_cluster_minimum = data_cluster_values_array.min()
            data_cluster_median = numpy.median(data_cluster_values_array)
            data_cluster_standard_deviation = data_cluster_values_array.std()
        else:
            data_cluster_mean = 0
            data_cluster_maximum = 0
            data_cluster_minimum = 0
            data_cluster_median = 0
            data_cluster_standard_deviation = 0

        data_clusters_statistics.append({
            "mean": data_cluster_mean,
            "maximum": data_cluster_maximum,
            "minimum": data_cluster_minimum,
            "median": data_cluster_median,
            "standard_deviation": data_cluster_standard_deviation
        })

    return data_clusters_statistics


def get_timedelta_from_normalized_request_data_list(
        request_data_list_normalized
):
    """
    It returns a delta datetime object of the data list

    :param request_data_list_normalized: A list with data
    _:return A datetime object, delta of two dates
    """
    if not len(request_data_list_normalized) > 0:
        logger.error(
            reports.globals.SystemError.
            GET_TIMEDELTA_FROM_NORMALIZED_REQUEST_DATA_LIST_ERROR)

        return None

    consumer_unit_id, datetime_from, datetime_to, electrical_parameter_name =\
        request_data_list_normalized[0]

    return datetime_to - datetime_from


def normalize_data_cluster(
        data_cluster
):
    """
    Normalize the data cluster

    :param data_cluster: A list with the data cluster
    :return: A normalize list of the data cluster
    """

    #
    # Get the first and last valid indexes
    #

    valid_index_first = None
    valid_index_last = None
    index_counter = 0
    for data_dictionary in data_cluster:
        data_dictionary_value =\
            data_dictionary['value']

        if data_dictionary_value is not None:
            if valid_index_first is None:
                valid_index_first = index_counter

            valid_index_last = index_counter

        index_counter += 1

    #
    # If any value is valid, set all the values to 0 and set a false certainty
    # for all of them.
    #
    if valid_index_first is None or valid_index_last is None:
        for data_dictionary in data_cluster:
            data_dictionary['value'] = 0
            data_dictionary['certainty'] = False

        return

    #
    # Fill the cluster with uncertain data until the first valid index is
    # reached.
    #
    if valid_index_first is not None:
        data_dictionary_valid_first = data_cluster[valid_index_first]
        data_dictionary_valid_first_value = data_dictionary_valid_first['value']

        for index in range(0, valid_index_first):
            data_dictionary_current = data_cluster[index]
            data_dictionary_current['value'] = data_dictionary_valid_first_value
            data_dictionary_current['certainty'] = False

    #
    # Fill the cluster with uncertain data from the last valid index until the
    # end is reached.
    #
    if valid_index_last is not None:
        data_dictionary_valid_last = data_cluster[valid_index_last]
        data_dictionary_valid_last_value = data_dictionary_valid_last['value']

        for index in range(valid_index_last, len(data_cluster)):
            data_dictionary_current = data_cluster[index]
            data_dictionary_current['value'] = data_dictionary_valid_last_value
            data_dictionary_current['certainty'] = False

    #
    # Patch all the invalid data using a linear interpolation and set certainty
    # as false for the patched data.
    #
    dictionary_index = valid_index_first + 1
    while dictionary_index < valid_index_last:
        data_dictionary_current = data_cluster[dictionary_index]
        data_dictionary_current_value = data_dictionary_current['value']

        if data_dictionary_current_value is None:
            #
            # Find the range that has invalid values
            #
            invalid_index = dictionary_index
            invalid_dictionary = data_cluster[invalid_index]
            invalid_dictionary_value = invalid_dictionary['value']
            while invalid_dictionary_value is None and invalid_index < valid_index_last:
                invalid_index += 1
                invalid_dictionary = data_cluster[invalid_index]
                invalid_dictionary_value = invalid_dictionary['value']

            #
            # Get the delta that will be used to patch the data.
            #
            valid_index_lower = dictionary_index - 1
            valid_dictionary_lower = data_cluster[valid_index_lower]
            valid_dictionary_lower_value = valid_dictionary_lower['value']

            valid_index_upper = invalid_index
            valid_dictionary_upper = data_cluster[valid_index_upper]
            valid_dictionary_upper_value = valid_dictionary_upper['value']

            value_difference =\
                valid_dictionary_upper_value - valid_dictionary_lower_value

            indexes_difference = valid_index_upper - valid_index_lower
            patch_delta = value_difference / indexes_difference

            #
            # Patch the data
            #
            for patch_index in range(1, indexes_difference):
                patch_dictionary = data_cluster[valid_index_lower + patch_index]
                patch_dictionary['value'] =\
                    valid_dictionary_lower_value + (patch_index * patch_delta)

        dictionary_index += 1

    return


def normalize_data_clusters_list(
        data_clusters_list
):
    """
    It normalize the data in the data cluster list

    :param data_clusters_list: A list of the data clusters
    :return:
    """

    for data_cluster in data_clusters_list:
        normalize_data_cluster(data_cluster)

    return

################################################################################
#
# Data Retrieve Scripts
#
################################################################################
DATETIME_FROM_UTC = None
DATETIME_TO_UTC = None
INSTANTS = None


def get_consumer_unit_electrical_parameter_data_virtual(
        consumer_unit,
        datetime_from,
        datetime_to,
        electrical_parameter_name,
        granularity_seconds=None
):
    """
    Get the data for the consumer unit, and the electrical parameter

    :param consumer_unit: A Consumer Unit object.
    :param datetime_from: A Datetime object
    :param datetime_to: A Datetime object
    :param electrical_parameter_name: A String that represents the name
    of the electrical parameter.
    :param granularity_seconds: An Integer that represents the number of
    seconds between the points to be retrieved.
    :return A list of dictionaries

    """

    #
    # Localize datetimes (if neccesary) and convert to UTC
    #
    timezone_current = django.utils.timezone.get_current_timezone()
    datetime_from_local = datetime_from
    if datetime_from_local.tzinfo is None:
        datetime_from_local = timezone_current.localize(datetime_from)

    datetime_from_utc =\
        datetime_from_local.astimezone(django.utils.timezone.utc)

    datetime_to_local = datetime_to
    if datetime_to_local.tzinfo is None:
        datetime_to_local = timezone_current.localize(datetime_to)

    datetime_to_utc = datetime_to_local.astimezone(django.utils.timezone.utc)

    #
    # Get the Electrical Parameter
    #
    electrical_parameter =\
        get_electrical_parameter(
            electrical_parameter_name=electrical_parameter_name)

    if electrical_parameter is None:
        logger.error(
            reports.globals.SystemError.
            GET_CONSUMER_UNIT_ELECTRICAL_PARAMETER_DATA_CLUSTERED_ERROR)

        return None

    #
    # Get the Instants between the from and to datetime according to the Instant
    # Delta and create a dictionary with them.
    #
    if granularity_seconds is None:
        instant_delta =\
            get_instant_delta_from_timedelta(datetime_to - datetime_from)

    else:
        instant_delta =\
            get_instant_delta(
                delta_seconds=granularity_seconds)


    if instant_delta is None:
        logger.error(
            reports.globals.SystemError.
            GET_CONSUMER_UNIT_ELECTRICAL_PARAMETER_DATA_CLUSTERED_ERROR)

        return None
    if DATETIME_FROM_UTC is None and DATETIME_TO_UTC is None:
        instants = set_instants(datetime_from_utc,
                                datetime_to_utc,
                                instant_delta)
    elif datetime_from_utc == DATETIME_FROM_UTC and \
            datetime_to_utc == DATETIME_TO_UTC:
        instants = INSTANTS
    else:
        instants = set_instants(datetime_from_utc,
                                datetime_to_utc,
                                instant_delta)

    instants_dictionary = dict()
    instants_kwh = dict()
    instants_kvarh = dict()

    instant_dictionary_generic_value = {
        'certainty': True,
        'value': None
    }

    for instant in instants:
        key_current = instant['instant_datetime'].strftime(
            reports.globals.Constant.DATETIME_STRING_KEY_FORMAT)

        instants_dictionary[key_current] =\
            instant_dictionary_generic_value.copy()
        if electrical_parameter_name == "PF":
            instants_kwh[key_current] =\
                instant_dictionary_generic_value.copy()
            instants_kvarh[key_current] =\
                instant_dictionary_generic_value.copy()
    #
    # Get the dependent Consumer Units List and retrieve their data.
    #
    consumer_units_list =\
        get_consumer_units(consumer_unit)

    if len(consumer_units_list) > 1 and electrical_parameter_name == "PF":
        #calcula factor potencia de medidor virtual
        kwh = get_electrical_parameter(electrical_parameter_name="kWh")

        kvarh = get_electrical_parameter(electrical_parameter_name="kVArh")

        for consumer_unit_item in consumer_units_list:
            consumer_unit_profile =\
                get_consumer_unit_profile(
                    consumer_unit_item.pk)

            #obtains the kwh electrical data for the cu
            cu_data_list_kwh = \
                get_consumer_unit_electrical_parameter_data_list(
                    consumer_unit_profile,
                    datetime_from_utc,
                    datetime_to_utc,
                    kwh,
                    instant_delta)
            #sums the kwh data for each CU
            for consumer_unit_data in cu_data_list_kwh:
                instant_key_current =\
                    consumer_unit_data['instant__instant_datetime'].strftime(
                        reports.globals.Constant.DATETIME_STRING_KEY_FORMAT)

                try:
                    instant_dictionary_current =\
                        instants_kwh[instant_key_current]

                except KeyError:
                    instant_dictionary_current = instant_dictionary_generic_value

                certainty_current = instant_dictionary_current['certainty']
                certainty_current =\
                    certainty_current and consumer_unit_data['value'] is not None

                instant_dictionary_current['certainty'] = certainty_current

                if certainty_current:
                    value_current = instant_dictionary_current['value']
                    if value_current is None:
                        value_current = abs(consumer_unit_data['value'])

                    else:
                        value_current += abs(consumer_unit_data['value'])

                    instant_dictionary_current['value'] = value_current
                else:
                    instant_dictionary_current['value'] = None
                instants_kwh[instant_key_current] =\
                    instant_dictionary_current.copy()

            #obtains the kvarh electrical data for the cu
            cu_data_list_kvarh = \
                get_consumer_unit_electrical_parameter_data_list(
                    consumer_unit_profile,
                    datetime_from_utc,
                    datetime_to_utc,
                    kvarh,
                    instant_delta)

            #sums the kvarh data for each CU

            for consumer_unit_data in cu_data_list_kvarh:
                instant_key_current =\
                    consumer_unit_data['instant__instant_datetime'].strftime(
                        reports.globals.Constant.DATETIME_STRING_KEY_FORMAT)

                try:
                    instant_dictionary_current =\
                        instants_kvarh[instant_key_current]

                except KeyError:
                    instant_dictionary_current = instant_dictionary_generic_value

                certainty_current = instant_dictionary_current['certainty']
                certainty_current =\
                    certainty_current and consumer_unit_data['value'] is not None

                instant_dictionary_current['certainty'] = certainty_current

                if certainty_current:
                    value_current = instant_dictionary_current['value']
                    if value_current is None:
                        value_current = abs(consumer_unit_data['value'])
                    else:
                        value_current += abs(consumer_unit_data['value'])

                    instant_dictionary_current['value'] = value_current
                else:
                    instant_dictionary_current['value'] = None
                instants_kvarh[instant_key_current] =\
                    instant_dictionary_current.copy()

        cont = 0
        keys = instants_kwh.keys()
        keys.sort()
        for key in keys:
            if instants_kwh[key]["value"] and \
                    instants_kvarh[key]["value"]:
                if cont == 0:
                    ini_kwh = float(instants_kwh[key]["value"])
                    ini_kvarh = float(instants_kvarh[key]["value"])
                    cont += 1
                else:
                    new_kwh = float(instants_kwh[key]["value"])
                    new_kvarh = float(instants_kvarh[key]["value"])

                    if new_kwh > ini_kwh:
                        kwh_dif = new_kwh - ini_kwh
                    else:
                        kwh_dif = ini_kwh - new_kwh

                    if new_kvarh > ini_kvarh:
                        kvarh_dif = new_kvarh - ini_kvarh
                    else:
                        kvarh_dif = ini_kvarh - new_kvarh

                    instants_dictionary[key]["value"] = factorpotencia(
                        kwh_dif,
                        kvarh_dif
                    )
                    ini_kwh = new_kwh
                    ini_kvarh = new_kvarh
            else:
                instants_dictionary[key] = instant_dictionary_generic_value
        #
        # Build the list of dictionaries that is to be retrieved.
        #
        consumer_units_data_dictionaries_list = []
        for instant in instants:
            key_current = instant['instant_datetime'].strftime(
                reports.globals.Constant.DATETIME_STRING_KEY_FORMAT)

            try:
                instant_dictionary_current = instants_dictionary[key_current]

            except KeyError:
                instant_dictionary_current = instant_dictionary_generic_value

            data_dictionary_current = instant_dictionary_current

            datetime_localtime_timetuple =\
                django.utils.timezone.localtime(
                    instant['instant_datetime']
                ).timetuple()

            data_dictionary_current['datetime'] =\
                    int(time.mktime(datetime_localtime_timetuple))

            consumer_units_data_dictionaries_list.append(
                data_dictionary_current.copy())

        return consumer_units_data_dictionaries_list

    else:
        for consumer_unit_item in consumer_units_list:
            #
            # Get a Consumer Unit Profile (from the app Data Warehouse Extended)
            #
            consumer_unit_profile =\
                get_consumer_unit_profile(
                    consumer_unit_item.pk)

            if consumer_unit_profile is None:
                logger.error(
                    reports.globals.SystemError.
                    GET_CONSUMER_UNIT_ELECTRICAL_PARAMETER_DATA_CLUSTERED_ERROR)

                return None

            consumer_unit_data_list =\
                get_consumer_unit_electrical_parameter_data_list(
                        consumer_unit_profile,
                        datetime_from_utc,
                        datetime_to_utc,
                        electrical_parameter,
                        instant_delta)

            #
            # Update the information in the Instants dictionary
            #
            for consumer_unit_data in consumer_unit_data_list:
                instant_key_current =\
                    consumer_unit_data['instant__instant_datetime'].strftime(
                        reports.globals.Constant.DATETIME_STRING_KEY_FORMAT)

                try:
                    instant_dictionary_current =\
                        instants_dictionary[instant_key_current]

                except KeyError:
                    instant_dictionary_current = instant_dictionary_generic_value

                certainty_current = instant_dictionary_current['certainty']
                certainty_current =\
                    certainty_current and consumer_unit_data['value'] is not None

                instant_dictionary_current['certainty'] = certainty_current

                if certainty_current:
                    value_current = instant_dictionary_current['value']
                    if value_current is None:
                        value_current = abs(consumer_unit_data['value'])

                    else:
                        value_current += abs(consumer_unit_data['value'])

                    if electrical_parameter_name == "PF" and value_current > 1:
                        instant_dictionary_current['value'] = 1
                    else:
                        instant_dictionary_current['value'] = value_current
                else:
                    instant_dictionary_current['value'] = None
                instants_dictionary[instant_key_current] =\
                    instant_dictionary_current.copy()

        #
        # Build the list of dictionaries that is to be retrieved.
        #
        consumer_units_data_dictionaries_list = []
        for instant in instants:
            key_current = instant['instant_datetime'].strftime(
                reports.globals.Constant.DATETIME_STRING_KEY_FORMAT)

            try:
                instant_dictionary_current = instants_dictionary[key_current]

            except KeyError:
                instant_dictionary_current = instant_dictionary_generic_value

            data_dictionary_current = instant_dictionary_current

            datetime_localtime_timetuple =\
                django.utils.timezone.localtime(
                    instant['instant_datetime']
                ).timetuple()

            data_dictionary_current['datetime'] =\
                    int(time.mktime(datetime_localtime_timetuple))

            consumer_units_data_dictionaries_list.append(
                data_dictionary_current.copy())

        return consumer_units_data_dictionaries_list


def get_consumer_unit_electrical_parameter_data_clustered(
        consumer_unit,
        datetime_from,
        datetime_to,
        electrical_parameter_name,
        granularity_seconds=None
):
    """

    :param consumer_unit: A Consumer Unit object
    :param datetime_from: A Datetime object
    :param datetime_to: A Datetime object
    :param electrical_parameter_name: A String that represent the name of the electrical parameter.
    :param granularity_seconds: An Integer that represents the number of seconds between the points to be retrieved.
    :return A list of dictionaries

    """

    #
    # Localize datetimes (if neccesary) and convert to UTC
    #
    timezone_current = django.utils.timezone.get_current_timezone()
    datetime_from_local = datetime_from
    if datetime_from_local.tzinfo is None:
        datetime_from_local = timezone_current.localize(datetime_from)

    datetime_from_utc =\
        datetime_from_local.astimezone(django.utils.timezone.utc)

    datetime_to_local = datetime_to
    if datetime_to_local.tzinfo is None:
        datetime_to_local = timezone_current.localize(datetime_to)

    datetime_to_utc = datetime_to_local.astimezone(django.utils.timezone.utc)

    #
    # Get the Electrical Parameter
    #
    electrical_parameter =\
        get_electrical_parameter(
            electrical_parameter_name=electrical_parameter_name)

    if electrical_parameter is None:
        logger.error(
            reports.globals.SystemError.
            GET_CONSUMER_UNIT_ELECTRICAL_PARAMETER_DATA_CLUSTERED_ERROR)

        return None

    #
    # Get the Instants between the from and to datetime according to the Instant
    # Delta and create a dictionary with them.
    #
    if granularity_seconds is None:
        instant_delta =\
            get_instant_delta_from_timedelta(datetime_to - datetime_from)

    else:
        instant_delta =\
            get_instant_delta(
                delta_seconds=granularity_seconds)

    if instant_delta is None:
        logger.error(
            reports.globals.SystemError.
            GET_CONSUMER_UNIT_ELECTRICAL_PARAMETER_DATA_CLUSTERED_ERROR)

        return None
    if DATETIME_FROM_UTC is None and DATETIME_TO_UTC is None:
        instants = set_instants(datetime_from_utc,
                                datetime_to_utc,
                                instant_delta)
    elif datetime_from_utc == DATETIME_FROM_UTC and \
            datetime_to_utc == DATETIME_TO_UTC:
        instants = INSTANTS
    else:
        instants = set_instants(datetime_from_utc,
                                datetime_to_utc,
                                instant_delta)

    instants_dictionary = dict()
    instant_dictionary_generic_value = {
        'certainty': True,
        'value':None
    }

    for instant in instants:
        key_current = instant['instant_datetime'].strftime(
            reports.globals.Constant.DATETIME_STRING_KEY_FORMAT)

        instants_dictionary[key_current] =\
            instant_dictionary_generic_value.copy()

    #
    # Get the dependent Consumer Units List and retrieve their data.
    #
    consumer_units_list =\
        get_consumer_units(consumer_unit)

    for consumer_unit_item in consumer_units_list:
        #
        # Get a Consumer Unit Profile (from the app Data Warehouse Extended)
        #
        consumer_unit_profile =\
            get_consumer_unit_profile(
                consumer_unit_item.pk)

        if consumer_unit_profile is None:
            logger.error(
                reports.globals.SystemError.
                GET_CONSUMER_UNIT_ELECTRICAL_PARAMETER_DATA_CLUSTERED_ERROR)

            return None
        consumer_unit_data_list =\
            get_consumer_unit_electrical_parameter_data_list(
                consumer_unit_profile,
                datetime_from_utc,
                datetime_to_utc,
                electrical_parameter,
                instant_delta)

        #
        # Update the information in the Instants dictionary
        #
        for consumer_unit_data in consumer_unit_data_list:
            instant_key_current =\
                consumer_unit_data['instant__instant_datetime'].strftime(
                    reports.globals.Constant.DATETIME_STRING_KEY_FORMAT)

            try:
                instant_dictionary_current =\
                    instants_dictionary[instant_key_current]

            except KeyError:
                instant_dictionary_current = instant_dictionary_generic_value

            certainty_current = instant_dictionary_current['certainty']

            certainty_current =\
                certainty_current and consumer_unit_data['value'] is not None

            instant_dictionary_current['certainty'] = certainty_current

            if certainty_current:
                value_current = instant_dictionary_current['value']
                if value_current is None:
                    value_current = abs(consumer_unit_data['value'])

                else:
                    value_current += abs(consumer_unit_data['value'])

                if electrical_parameter_name == "PF" and value_current > 1:
                    instant_dictionary_current['value'] = 1
                else:
                    instant_dictionary_current['value'] = value_current
            else:
                instant_dictionary_current['value'] = None
            instants_dictionary[instant_key_current] =\
                instant_dictionary_current.copy()

    #
    # Build the list of dictionaries that is to be retrieved.
    #
    consumer_units_data_dictionaries_list = []
    for instant in instants:
        key_current = instant['instant_datetime'].strftime(
            reports.globals.Constant.DATETIME_STRING_KEY_FORMAT)

        try:
            instant_dictionary_current = instants_dictionary[key_current]

        except KeyError:
            instant_dictionary_current = instant_dictionary_generic_value

        data_dictionary_current = instant_dictionary_current

        datetime_localtime_timetuple =\
            django.utils.timezone.localtime(
                instant['instant_datetime']
            ).timetuple()

        data_dictionary_current['datetime'] =\
                int(time.mktime(datetime_localtime_timetuple))

        consumer_units_data_dictionaries_list.append(
            data_dictionary_current.copy())
    return consumer_units_data_dictionaries_list


def set_instants(datetime_from_utc, datetime_to_utc, instant_delta):
    """
    It obtains a list with the instants order by instant datetime.

    :param datetime_from_utc: A datetime object
    :param datetime_to_utc:  A datetime object
    :param instant_delta:  An Instant Delta object
    :return: A list of Instants ordered by instant datetime.
    """
    global DATETIME_TO_UTC
    DATETIME_TO_UTC = datetime_to_utc
    global DATETIME_FROM_UTC
    DATETIME_FROM_UTC = datetime_from_utc
    global INSTANTS
    INSTANTS = get_instants_list(
        datetime_from_utc,
        datetime_to_utc,
        instant_delta)
    instants = INSTANTS
    return instants


def rates_for_data_cluster(data_cluster_consumed, region):
    """
    It generates a dictionary that have the id of the rates of
    the data.

    :param data_cluster_consumed: A list of data
    :param region: A string with the region
    :return: A list of dictionaries with the rates
    """
    data_cluster_cons = []
    for data_cluster in data_cluster_consumed:
        date_time = datetime.datetime.fromtimestamp(data_cluster["datetime"])
        periodo = obtenerTipoPeriodoObj(
            date_time, region)['period_type']

        if periodo == "base":
            arr_base = data_cluster
            arr_int = dict(certainty=False,
                           value=None,
                           datetime=data_cluster["datetime"])
            arr_punt = dict(certainty=False,
                            value=None,
                            datetime=data_cluster["datetime"])
        elif periodo == "intermedio":
            arr_base = dict(certainty=False,
                            value=None,
                            datetime=data_cluster["datetime"])
            arr_int = data_cluster
            arr_punt = dict(certainty=False,
                            value=None,
                            datetime=data_cluster["datetime"])

        else:
            #periodo == "punta"
            arr_base = dict(certainty=False,
                            value=None,
                            datetime=data_cluster["datetime"])
            arr_int = dict(certainty=False,
                           value=None,
                           datetime=data_cluster["datetime"])
            arr_punt = data_cluster
        data_cluster_cons.append([arr_base, arr_int, arr_punt])

    return data_cluster_cons