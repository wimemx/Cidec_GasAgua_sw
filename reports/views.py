#coding:utf-8

# Python imports
import datetime
import logging

# Django imports
import django.http
import django.shortcuts
import django.utils.timezone
import django.template.context

# Reports imports
import reports.globals

# Data Warehouse Extended imports
import data_warehouse_extended.views

# CCenter imports
import c_center.models
import c_center.c_center_functions

logger = logging.getLogger("reports")

################################################################################
#
# Utility Scripts
#
################################################################################

def get_data_cluster_normalized(
        data_cluster
):
    """
        Description:


        Arguments:
            data_cluster -

        Return:

    """

    invalid_index_first = None
    invalid_index_last = None
    for data_dictionary in data_cluster:
        data_dictionary_value =\
            data_dictionary.pop(
                reports.globals.Constant.DATA_DICTIONARY_KEY_VALUE,
                None)


def get_data_clusters_json(
        data_clusters_list_normalized
):
    """
        Description:


        Arguments:
            data_clusters_list_normalized -

        Return:

    """

    # To-Do implement this function
    pass


def get_data_clusters_list(
        request_data_list_normalized
):
    """
        Description:


        Arguments:
            request_data_list_normalized -

        Return:

    """

    data_clusters_list = []
    for consumer_unit_id, datetime_from, datetime_to, electrical_parameter_name\
        in request_data_list_normalized:

        try:
            consumer_unit =\
                c_center.models.ConsumerUnit.objects.get(pk=consumer_unit_id)

        except c_center.models.ConsumerUnit.DoesNotExist:
            logger.error(
                reports.globals.SystemError.GET_DATA_CLUSTERS_LIST_ERROR)

            return None

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


def get_data_clusters_list_normalized(
        data_clusters_list
):
    """
        Description:


        Arguments:
            data_clusters_list -

        Return:

    """

    # To-Do implement this function
    pass


def get_instant_delta_from_timedelta(
        timedelta
):
    """
        Description:
            To-Do

        Arguments:
            timedelta -

        Return:

    """

    timedelta_seconds = timedelta.seconds + (timedelta.days * 24 * 3600)
    instant_deltas = data_warehouse_extended.views.get_instant_delta_all()
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
        Description:
            To-Do

        Arguments:
            request_data_list

        Return:

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

        request_data_list_normalized.append(request_data_list_item_normalized)

    return request_data_list_normalized


def get_timedelta_from_normalized_request_data_list(
        request_data_list_normalized
):
    """
        Description:
            To-Do

        Arguments:
            request_data_list

        Return:

    """
    if not len(request_data_list_normalized) > 0:
        logger.error(
            reports.globals.SystemError.
            GET_TIMEDELTA_FROM_NORMALIZED_REQUEST_DATA_LIST_ERROR)

        return None

    consumer_unit_id, datetime_from, datetime_to, electrical_parameter_name =\
        request_data_list_normalized[0]

    return datetime_to - datetime_from


################################################################################
#
# Data Retrieve Scripts
#
################################################################################

def get_consumer_unit_electrical_parameter_data_clustered(
        consumer_unit,
        datetime_from,
        datetime_to,
        electrical_parameter_name
):
    """
        Description:
            To-Do

        Arguments:
            consumer_unit - A Consumer Unit object.

            datetime_from - A Datetime object.

            datetime_to - A Datetime object.

            electrical_parameter - A String that represents the name of the
                electrical parameter.

            granularity_seconds - An Integer that represents the number of
                seconds between the points to be retrieved.

        Return:
            A list of dictionaries.
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
        data_warehouse_extended.views.get_electrical_parameter(
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
    instant_delta =\
        get_instant_delta_from_timedelta(datetime_to - datetime_from)

    if instant_delta is None:
        logger.error(
            reports.globals.SystemError.
            GET_CONSUMER_UNIT_ELECTRICAL_PARAMETER_DATA_CLUSTERED_ERROR)

        return None

    instants =\
        data_warehouse_extended.views.get_instants_list(
            datetime_from_utc,
            datetime_to_utc,
            instant_delta)

    instants_dictionary = dict()
    instant_dictionary_generic_value = {
        reports.globals.Constant.DATA_DICTIONARY_KEY_CERTAINTY : True,
        reports.globals.Constant.INSTANT_DICTIONARY_KEY_VALUE :None
    }

    for instant in instants:
        key_current = instant.instant_datetime.strftime(
            reports.globals.Constant.DATETIME_STRING_KEY_FORMAT)

        instants_dictionary[key_current] = instant_dictionary_generic_value

    #
    # Get the dependent Consumer Units List and retrieve their data.
    #
    consumer_units_list =\
        c_center.c_center_functions.get_consumer_units(consumer_unit)

    for consumer_unit_item in consumer_units_list:
        #
        # Get a Consumer Unit Profile (from the app Data Warehouse Extended)
        #
        consumer_unit_profile =\
            data_warehouse_extended.views.get_consumer_unit_profile(
                consumer_unit_item.pk)

        if consumer_unit_profile is None:
            logger.error(
                reports.globals.SystemError.
                GET_CONSUMER_UNIT_ELECTRICAL_PARAMETER_DATA_CLUSTERED_ERROR)

            return None

        consumer_unit_data_list =\
            data_warehouse_extended.views.\
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
                consumer_unit_data.instant.instant_datetime.strftime(
                    reports.globals.Constant.DATETIME_STRING_KEY_FORMAT)

            instant_dictionary_current =\
                instants_dictionary.pop(
                    instant_key_current,
                    instant_dictionary_generic_value)

            certainty_current =\
                instant_dictionary_current.pop(
                    reports.globals.Constant.INSTANT_DICTIONARY_KEY_CERTAINTY,
                    False)

            certainty_current =\
                certainty_current and consumer_unit_data.value is not None

            instant_dictionary_current\
                [reports.globals.Constant.INSTANT_DICTIONARY_KEY_CERTAINTY] =\
                    certainty_current

            if certainty_current:
                value_current =\
                    instant_dictionary_current.pop(
                        reports.globals.Constant.INSTANT_DICTIONARY_KEY_VALUE,
                        None)

                if value_current is None:
                    value_current = consumer_unit_data.value

                else:
                    value_current += consumer_unit_data.value

                instant_dictionary_current\
                    [reports.globals.Constant.INSTANT_DICTIONARY_KEY_VALUE] =\
                        value_current

            instants_dictionary[instant_key_current] =\
                instant_dictionary_current

    #
    # Build the list of dictionaries that is to be retrieved.
    #
    consumer_units_data_dictionaries_list = []
    for instant in instants:
        key_current = instant.instant_datetime.strftime(
            reports.globals.Constant.DATETIME_STRING_KEY_FORMAT)

        instant_dictionary_current =\
            instants_dictionary.pop(
                key_current,
                instant_dictionary_generic_value)

        data_dictionary_current = instant_dictionary_current

        datetime_localtime_timetuple =\
            django.utils.timezone.localtime(
                instant.instant_datetime
            ).timetuple()

        data_dictionary_current\
            [reports.globals.Constant.DATA_DICTIONARY_KEY_DATETIME] =\
                int(datetime.time.mktime(datetime_localtime_timetuple))

        consumer_units_data_dictionaries_list.append(
            data_dictionary_current)

    return consumer_units_data_dictionaries_list


################################################################################
#
# Render Scripts
#
################################################################################

def render_instant_measurements(
        request
):

    if not request.method == "GET":
        raise django.http.Http404

    template_variables = dict()

    #
    # Build a request data list in order to normalize it.
    #
    request_data_list = []
    consumer_unit_counter = 1
    consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
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

        datetime_from = datetime.datetime.strptime(date_from_string, "%Y-%m-%d")
        datetime_to = datetime.datetime.strptime(date_to_string, "%Y-%m-%d")

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
    # Build and normalize the data clusters list.
    #
    data_clusters_list = get_data_clusters_list(request_data_list_normalized)

    template_context =\
        django.template.context.RequestContext(request, template_variables)

    return django.shortcuts.render_to_response(
               "reports/instant-measurements.html",
               template_context)
