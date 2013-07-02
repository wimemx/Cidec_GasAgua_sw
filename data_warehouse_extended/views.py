#coding:utf-8

# Python imports
import datetime
import decimal
import logging
import pylab
import scipy.interpolate
import sys

# Django imports
import django.core.exceptions
import django.utils.timezone
from django.db import connection, transaction

# Data Warehouse Extended imports
import data_warehouse_extended.globals
import data_warehouse_extended.models

# CCenter imports
import c_center.models

import variety

logger = logging.getLogger("data_warehouse")


################################################################################
#
# Tables Fill Scripts
#
################################################################################

def create_instant_instances(
        datetime_from,
        datetime_to,
        instant_delta
):
    """
        Description:
            This function creates Instants in the specified interval.

        Arguments:
            datetime_form - Datetime that specifies the start of the Instants
                creation.

            datetime_to - Datetime that specifies the end of the Instants
                creation

        Return:
            None.
    """

    logger.info(create_instant_instances.__name__)
    time_delta = datetime.timedelta(seconds=instant_delta.delta_seconds)
    timezone_utc = django.utils.timezone.utc

    #
    # Check if datetime_from is naive and make it UTC
    #
    if datetime_from.tzinfo is None:
        datetime_from_utc = timezone_utc.localize(datetime_from)

    else:
        datetime_from_utc =  datetime_from.astimezone(timezone_utc)

    #
    # Check if datetime_from is naive and make it UTC
    #
    if datetime_to.tzinfo is None:
        datetime_to_utc = timezone_utc.localize(datetime_to)

    else:
        datetime_to_utc =  datetime_to.astimezone(timezone_utc)

    #
    # Iterate and create Instants
    #
    datetime_current_utc = datetime_from_utc
    while datetime_current_utc <= datetime_to_utc:
        instant_current = data_warehouse_extended.models.Instant(
                              instant_delta=instant_delta,
                              instant_datetime=datetime_current_utc)

        try:
            instant_current.full_clean()

        except django.core.exceptions.ValidationError:
            logger.error(
                data_warehouse_extended.globals.SystemError.
                INSTANT_ALREADY_EXISTS)

            datetime_current_utc += time_delta
            continue

        instant_current.save()
        logger.info(data_warehouse_extended.globals.SystemInfo.INSTANT_SAVED +\
                    " " + str(instant_current))

        datetime_current_utc += time_delta

    return


def update_consumer_units():
    """
        Description:
            This function creates new Consumer Unit Profiles and updates the
            information of the existent ones using the transactional database.

        Arguments:
            None

        Return:
            None.
    """

    consumer_units = c_center.models.ConsumerUnit.objects.all()
    for consumer_unit in consumer_units:
        building_name = consumer_unit.building.building_name
        electric_device_type_name =\
            consumer_unit.electric_device_type.electric_device_type_name

        if consumer_unit.part_of_building is None:
            part_of_building_name = None

        else:
            part_of_building_name =\
                consumer_unit.part_of_building.part_of_building_name

        #
        # If the Consumer Unit exists, update it. Otherwise, create a new one.
        #
        try:
            consumer_unit_profile =\
                data_warehouse_extended.models.ConsumerUnitProfile.objects.get(
                    pk=consumer_unit.pk)

        except data_warehouse_extended.models.ConsumerUnitProfile.DoesNotExist:
            consumer_unit_profile =\
                data_warehouse_extended.models.ConsumerUnitProfile(
                    transactional_id=consumer_unit.pk)

        consumer_unit_profile.building_name = building_name
        consumer_unit_profile.electric_device_type_name =\
            electric_device_type_name

        consumer_unit_profile.part_of_building_name = part_of_building_name
        try:
            consumer_unit_profile.full_clean()

        except django.core.exceptions.ValidationError as\
                consumer_unit_profile_validation_error:

            logger.error(str(consumer_unit_profile_validation_error))
            continue

        #
        # Save the Consumer Unit Profile with up-to-date information.
        #
        consumer_unit_profile.save()
        logger.info(
            data_warehouse_extended.globals.SystemInfo.
                CONSUMER_UNIT_PROFILE_SAVED +\
            " " + str(consumer_unit_profile))

    return


################################################################################
#
# Data Processing Scripts
#
################################################################################

def build_curve_fit_function_interpolation(
        independent_data_list,
        dependent_data_list
):
    """
        Description:
            This function generates a function using a cubic interpolation in a
            set of points.

        Arguments:
            independent_data_list - A list that contains the independent axis
                values of a set of points.

            dependent_data_list - A list that contains the dependent axis values
                of a set of points.

        Return:
            A function of the form f(x).
    """

    if (len(independent_data_list) <= \
        data_warehouse_extended.globals.Constant.MINIMUM_POINTS_NUMBER) or\
       (len(dependent_data_list) <= \
        data_warehouse_extended.globals.Constant.MINIMUM_POINTS_NUMBER):

        return None

    try:
        curve_fit_function =\
            scipy.interpolate.interp1d(
                independent_data_list,
                dependent_data_list,
                'nearest')
        print "nearest"

    except:
        logger.error(
            data_warehouse_extended.globals.SystemError.INTERPOLATION_FAILED)

        return None

    return curve_fit_function


def build_curve_fit_function_regression(
        independent_data_list,
        dependent_data_list
):
    """
        Description:
            This function generates a function using a quadratic regression in a
            set of points.

        Arguments:
            independent_data_list - A list that contains the independent axis
                values of a set of points.

            dependent_data_list - A list that contains the dependent axis values
                of a set of points.

        Return:
            A function of the form f(x).
    """

    if (len(independent_data_list) <=\
        data_warehouse_extended.globals.Constant.MINIMUM_POINTS_NUMBER) or\
       (len(dependent_data_list) <=\
        data_warehouse_extended.globals.Constant.MINIMUM_POINTS_NUMBER):

        return None

    try:
        curve_fit_coefficients =\
            pylab.polyfit(independent_data_list, dependent_data_list, 2)

    except:
        logger.error(
            data_warehouse_extended.globals.SystemError.REGRESSION_FAILED)

        return None

    a_coefficient = curve_fit_coefficients[0]
    b_coefficient = curve_fit_coefficients[1]
    c_coefficient = curve_fit_coefficients[2]

    curve_fit_function =\
        lambda x, a=a_coefficient, b=b_coefficient, c=c_coefficient:\
            (a*x**2)+(b*x)+c

    return curve_fit_function


def build_instants_groups(
        instants_list,
        group_size
):
    """
        Description:
            This function generates a List of Instant Lists that groups Instants
            into groups of the specified size.

        Arguments:
            instants_list - A List that contains Instants.

            group_size - The size of the Instant groups that are generated.

        Return:
            A List of Instant Lists.
    """

    instants_number = len(instants_list)
    groups_number = instants_number / group_size
    instants_groups = []

    for group_index in range(0, groups_number):
        lower_index = group_index * group_size
        upper_index = lower_index + group_size
        if upper_index > instants_number:
            upper_index = instants_number

        instants_groups.append(instants_list[lower_index:upper_index])

    return instants_groups


@variety.timed
def process_consumer_unit_electrical_parameter(
        consumer_unit,
        datetime_from,
        datetime_to,
        electrical_parameter,
        instant_delta
):
    """
        Description:
            This function processes data for the specified Consumer Unit, in the
            specified time interval for the specified parameter and saves the
            processed information in the Data Warehouse Extended database
            according to the specified granularity.

        Arguments:
            consumer_unit - A Consumer Unit object (from the transactional
                database).

            datetime_from - A Datetime object.

            datetime_to - A Datetime object.

            electrical_parameter - An Electrical Parameter object.

            instant_delta - An Instant Delta object.

        Return:
            None.
    """

    #
    # Get a consumer unit profile object
    #
    try:
        consumer_unit_profile =\
            data_warehouse_extended.models.ConsumerUnitProfile.objects.get(
                pk=consumer_unit.pk)

    except data_warehouse_extended.models.ConsumerUnitProfile.DoesNotExist:
        logger.error(
            data_warehouse_extended.globals.SystemError.
                CONSUMER_UNIT_PROFILE_DOES_NOT_EXIST +\
            " " + str(consumer_unit.pk))

        return

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

    instants =\
        data_warehouse_extended.models.Instant.objects.filter(
            instant_delta=instant_delta,
            instant_datetime__gte=datetime_from_utc,
            instant_datetime__lte=datetime_to_utc
        ).order_by(
            'instant_datetime'
        ).values("pk", "instant_delta__delta_seconds", "instant_datetime")

    #
    # Divide instants into fixed-size groups.
    #
    instants_groups =\
        build_instants_groups(
            instants,
            data_warehouse_extended.globals.Constant.INSTANT_GROUP_SIZE)

    for instants_group in instants_groups:
        process_consumer_unit_electrical_parameter_instant_group(
            consumer_unit,
            consumer_unit_profile,
            electrical_parameter,
            instants_group)

    return


def process_consumer_unit_electrical_parameter_instant_group(
        consumer_unit,
        consumer_unit_profile,
        electrical_parameter,
        instants_group
):
    """
        Description:
            This function processes data for the specified Consumer Unit, in the
            time interval given by the instants' group for the specified
            parameter and saves the processed information in the Data Warehouse
            Extended database.

        Arguments:
            consumer_unit - A Consumer Unit object (from the transactional
                database).

            consumer_unit_profile - A Consumer Unit Profile object.

            electrical_parameter - An Electrical Parameter object.

            instants_group - A list of Instants (which cannot be naive).

        Return:
            None.
    """

    if len(instants_group) < 1:
        logger.error(
            data_warehouse_extended.globals.SystemError.INSTANTS_GROUP_EMPTY)

        return

    #
    # Get all the data based on the first and last Instants in the list.
    #
    timedelta = datetime.timedelta(
        seconds=instants_group[0]['instant_delta__delta_seconds'])
    datetime_from = instants_group[0]['instant_datetime'] - timedelta
    datetime_to = instants_group[-1]['instant_datetime'] + timedelta
    try:
        electric_data_raw_dictionaries_list =\
            c_center.models.ElectricDataTemp.objects.filter(
                profile_powermeter=consumer_unit.profile_powermeter,
                medition_date__gte=datetime_from,
                medition_date__lte=datetime_to
            ).order_by(
                'medition_date'
            ).values(
                'medition_date',
                electrical_parameter.name_transactional
            )

    except django.core.exceptions.FieldError:
        logger.error(data_warehouse_extended.globals.SystemError.FIELD_ERROR)
        return

    #
    # Get independent and dependent values.
    #
    independent_data_list = []
    dependent_data_list = []
    for electric_data_raw_dictionary in electric_data_raw_dictionaries_list:
        timedelta_current =\
            electric_data_raw_dictionary['medition_date'] - datetime_from

        timedelta_current_seconds =\
            timedelta_current.seconds + (timedelta_current.days * 24 * 3600)

        independent_data_list.append(timedelta_current_seconds)
        dependent_data_list.append(
            float(
                electric_data_raw_dictionary[
                    electrical_parameter.name_transactional]
            )
        )

    #
    # Generate a function based on the points (interpolation for cumulative
    # data and regression for instant data).
    #
    if electrical_parameter.type ==\
           data_warehouse_extended.models.ElectricalParameter.INSTANT:

        curve_fit_function =\
            build_curve_fit_function_regression(
                independent_data_list,
                dependent_data_list)

    elif electrical_parameter.type ==\
             data_warehouse_extended.models.ElectricalParameter.CUMULATIVE:

        curve_fit_function =\
            build_curve_fit_function_interpolation(
                independent_data_list,
                dependent_data_list)

    else:
        logger.error(
            data_warehouse_extended.globals.SystemError.
            ELECTRICAL_PARAMETER_TYPE_NOT_SUPPORTED)

        return

    #
    # Get the independent data limits in order to know if the curve fit function
    # can be evaluated.
    #
    if len(independent_data_list) > 0:
        independent_data_lower_limit = independent_data_list[0]
        independent_data_upper_limit = independent_data_list[-1]

    else:
        independent_data_lower_limit = sys.maxint
        independent_data_upper_limit = -sys.maxint

    #
    # Evaluate the generated function on each Instant datetime and save the
    # result in the Data Warehouse Extended.
    #
    for instant in instants_group:
        instant_timedelta_current = instant['instant_datetime'] - datetime_from
        instant_timedelta_current_seconds =\
            instant_timedelta_current.seconds + \
            (instant_timedelta_current.days * 24 * 3600)

        is_instant_between_limits =\
            instant_timedelta_current_seconds >= independent_data_lower_limit and\
            instant_timedelta_current_seconds <= independent_data_upper_limit

        curve_fit_function_evaluation = None
        if curve_fit_function is not None and is_instant_between_limits:
            curve_fit_function_evaluation =\
                curve_fit_function(instant_timedelta_current_seconds)

        try:
            consumer_unit_instant_electric_data = \
                data_warehouse_extended.models.\
                    ConsumerUnitInstantElectricalData.objects.get(
                        consumer_unit_profile=consumer_unit_profile,
                        instant__pk=instant["pk"],
                        electrical_parameter=electrical_parameter)
        except data_warehouse_extended.models.\
                ConsumerUnitInstantElectricalData.DoesNotExist:
            if curve_fit_function_evaluation is not None:
                try:
                    curve_fit_function_evaluation =\
                        decimal.Decimal(str(curve_fit_function_evaluation))
                except decimal.InvalidOperation:
                    curve_fit_function_evaluation = None
            cursor = connection.cursor()
            sql = "INSERT INTO " \
                  "data_warehouse_extended_consumerunitinstantelectricaldata " \
                  "(`consumer_unit_profile_id`, `instant_id`, " \
                  "electrical_parameter_id, `value`) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, [consumer_unit_profile.pk,
                                 instant["pk"],
                                 electrical_parameter.pk,
                                 curve_fit_function_evaluation])
            transaction.commit_unless_managed()
            logger.info(data_warehouse_extended.globals.SystemInfo.
                        CONSUMER_UNIT_INSTANT_ELECTRIC_DATA_SAVED + " - " +\
                        "RAW SQL SAVED" + str(instant['instant_datetime']) + \
                        electrical_parameter.name_transactional + \
                        str(curve_fit_function_evaluation))
        else:
            consumer_unit_instant_electric_data.value =\
                curve_fit_function_evaluation

            if curve_fit_function_evaluation is not None:
                consumer_unit_instant_electric_data.value =\
                    decimal.Decimal(str(curve_fit_function_evaluation))

            try:
                consumer_unit_instant_electric_data.full_clean()

            except django.core.exceptions.ValidationError:
                logger.error(
                    data_warehouse_extended.globals.SystemError.
                    CONSUMER_UNIT_INSTANT_ELECTRIC_DATA_VALIDATION_ERROR + " - " +
                    str(consumer_unit_instant_electric_data))

                continue

            try:
                consumer_unit_instant_electric_data.save()

            except decimal.InvalidOperation:
                consumer_unit_instant_electric_data.value = None
                logger.error(
                    data_warehouse_extended.globals.SystemError.
                    CONSUMER_UNIT_INSTANT_ELECTRIC_DATA_DECIMAL_ERROR + " - " +
                    str(consumer_unit_instant_electric_data))

            consumer_unit_instant_electric_data.save()
            logger.info(data_warehouse_extended.globals.SystemInfo.
                        CONSUMER_UNIT_INSTANT_ELECTRIC_DATA_SAVED + " - " +\
                        str(consumer_unit_instant_electric_data))

    return


################################################################################
#
# Data Retrieve Scripts
#
################################################################################

def get_consumer_unit_electrical_parameter_data_list(
        consumer_unit_profile,
        datetime_from,
        datetime_to,
        electrical_parameter,
        instant_delta
):
    """
        Description:
            To-Do

        Arguments:
            consumer_unit_profile - A Consumer Unit Profile object.

            datetime_from - A Datetime object.

            datetime_to - A Datetime object.

            electrical_parameter - An Electrical Parameter object.

            instant_delta - An Instant Delta object.

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
    # Get the data for the Consumer Unit Profile and the Electrical
    # Parameter in the specified time range.
    #
    consumer_unit_data_list =\
        data_warehouse_extended.models.\
            ConsumerUnitInstantElectricalData.objects.filter(
                consumer_unit_profile=consumer_unit_profile,
                instant__instant_delta=instant_delta,
                instant__instant_datetime__gte=datetime_from_utc,
                instant__instant_datetime__lte=datetime_to_utc,
                electrical_parameter=electrical_parameter
            ).order_by(
                "instant__instant_datetime"
            ).values("instant__instant_datetime", "value")

    return consumer_unit_data_list


def get_consumer_unit_profile (
        consumer_unit_id
):
    """
        Description:
            Gets a Consumer Unit Profile object for the specified id.

        Arguments:
            consumer_unit_id - PK of the Consumer Unit Profile to be retrieved.

        Return:
            A Consumer Unit Profile object if found.
            None if the object is not found.
    """

    #
    # Get a Consumer Unit Profile object
    #
    try:
        consumer_unit_profile =\
            data_warehouse_extended.models.ConsumerUnitProfile.objects.get(
                pk=consumer_unit_id)

    except data_warehouse_extended.models.ConsumerUnitProfile.DoesNotExist:
        logger.error(
            data_warehouse_extended.globals.SystemError.
            CONSUMER_UNIT_PROFILE_DOES_NOT_EXIST +\
            " " + str(consumer_unit_id))

        return None

    return consumer_unit_profile


def get_electrical_parameter(
        electrical_parameter_name=None,
        electrical_parameter_name_transactional=None,
):
    """
        Description:
            Gets an Electrical Parameter object.

        Arguments:


        Return:

    """

    if electrical_parameter_name is not None:
        try:
            electrical_parameter =\
                data_warehouse_extended.models.ElectricalParameter.objects.get(
                    name=electrical_parameter_name)

        except data_warehouse_extended.models.ElectricalParameter.DoesNotExist:
            logger.error(
                data_warehouse_extended.globals.SystemError.
                ELECTRICAL_PARAMETER_DOES_NOT_EXIST)

            return None

    elif electrical_parameter_name_transactional is not None:
        try:
            electrical_parameter =\
                data_warehouse_extended.models.ElectricalParameter.objects.get(
                    name_transactional=electrical_parameter_name_transactional)

        except data_warehouse_extended.models.ElectricalParameter.DoesNotExist:
            logger.error(
                data_warehouse_extended.globals.SystemError.
                ELECTRICAL_PARAMETER_DOES_NOT_EXIST)

            return None

    else:
        electrical_parameter = None

    return electrical_parameter


def get_instant_delta (
        name=None,
        delta_seconds=None
):
    """
        Description:
            Gets an Instant Delta object.

        Arguments:
            name - A String representing the name of the Instant Delta.

            delta_seconds - An Integer representing the delta in seconds.

        Return:
            An Instant Delta object if found.
            None if the object is not found.
    """

    if name is not None:
        try:
            instant_delta =\
                data_warehouse_extended.models.InstantDelta.objects.get(
                    name=name)

        except data_warehouse_extended.models.InstantDelta.DoesNotExist:
            logger.error(
                data_warehouse_extended.globals.SystemError.
                INSTANT_DELTA_DOES_NOT_EXIST)

            return None

    elif delta_seconds is not None:
        try:
            instant_delta =\
                data_warehouse_extended.models.InstantDelta.objects.get(
                    delta_seconds=delta_seconds)

        except data_warehouse_extended.models.InstantDelta.DoesNotExist:
            logger.error(
                data_warehouse_extended.globals.SystemError.
                INSTANT_DELTA_DOES_NOT_EXIST)

            return None

    else:
        instant_delta = None

    return instant_delta


def get_instant_delta_all():

    return data_warehouse_extended.models.InstantDelta.objects.all()


def get_instants_list(
        datetime_from,
        datetime_to,
        instant_delta
):

    """
        Description:
            Gets a list of Instants given the time range and an Instant Delta
            object.

        Arguments:
            datetime_from - A Datetime object.

            datetime_to - A Datetime object.

            instant_delta - An Instant Delta object.

        Return:
            A list of Instants ordered by instant datetime.
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
    # Get the Instants between the from and to datetime according to the Instant
    # Delta and create a dictionary with them.
    #
    instants =\
        data_warehouse_extended.models.Instant.objects.filter(
            instant_datetime__gte=datetime_from_utc,
            instant_datetime__lte=datetime_to_utc,
            instant_delta=instant_delta
        ).order_by(
            "instant_delta"
        ).values("instant_datetime")
    return instants


################################################################################
#
# Test Scripts
#
################################################################################

def test_process_consumer_unit_electrical_parameter():

    consumer_unit = c_center.models.ConsumerUnit.objects.get(pk=7)
    datetime_from = datetime.datetime(year=2013, month=1, day=31)
    datetime_to = datetime.datetime(year=2013, month=3, day=1)
    electrical_parameter =\
        data_warehouse_extended.models.ElectricalParameter.objects.get(name="TotalkWhIMPORT")

    instant_deltas = data_warehouse_extended.models.InstantDelta.objects.all()
    for instant_delta in instant_deltas:
        process_consumer_unit_electrical_parameter(
            consumer_unit,
            datetime_from,
            datetime_to,
            electrical_parameter,
            instant_delta
        )

    #get_consumer_unit_electrical_parameter_data_list(
    #    consumer_unit,
    #    datetime_from,
    #    datetime_to,
    #    electrical_parameter,
    #    instant_delta
    #)

