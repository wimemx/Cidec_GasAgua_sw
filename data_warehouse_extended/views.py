#coding:utf-8

# Python imports
import datetime
import logging
import pylab

# Django imports
import django.core.exceptions
import django.utils.timezone

# Data Warehouse Extended imports
import data_warehouse_extended.globals
import data_warehouse_extended.models

# CCenter imports
import c_center.models

logger = logging.getLogger("data_warehouse")

################################################################################
#
# Populate Data Warehouse Extended Script
#
################################################################################

def populate_data_warehouse_extended(
        populate_instants=None,
        populate_consumer_unit_profiles=None
):

    if populate_instants:
        datetime_from =\
            datetime.datetime(
                year=2012,
                month=1,
                day=1,
                tzinfo=django.utils.timezone.utc)

        datetime_to =\
            datetime.datetime(
                year=2015,
                month=12,
                day=31,
                tzinfo=django.utils.timezone.utc)

        instant_deltas =\
            data_warehouse_extended.models.InstantDelta.objects.all()

        for instant_delta in instant_deltas:
            create_instant_instances(datetime_from, datetime_to, instant_delta)

    if populate_consumer_unit_profiles:
        update_consumer_units()


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

    logger.info(create_instant_instances.__name__)
    time_delta = datetime.timedelta(seconds=instant_delta.delta_seconds)
    timezone_utc = django.utils.timezone.utc
    datetime_from_utc = timezone_utc.localize(datetime_from)
    datetime_to_utc = timezone_utc.localize(datetime_to)
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

        consumer_unit_profile.save()
        logger.info(
            data_warehouse_extended.globals.SystemInfo.
                CONSUMER_UNIT_PROFILE_SAVED +\
            " " + str(consumer_unit_profile))


################################################################################
#
# Data Processing Scripts
#
################################################################################

def get_curve_fit_function_interpolation(
        independent_data_list,
        dependent_data_list
):

    pass


def get_curve_fit_function_regression(
        independent_data_list,
        dependent_data_list
):

    curve_fit_coefficients =\
        pylab.polyfit(independent_data_list, dependent_data_list, 2)

    a_coefficient = curve_fit_coefficients[0]
    b_coefficient = curve_fit_coefficients[1]
    c_coefficient = curve_fit_coefficients[2]

    curve_fit_function =\
        lambda x, a=a_coefficient, b=b_coefficient, c=c_coefficient: (a*x**2)+(b*x)+c

    return curve_fit_function


def get_instants_groups(
        instants_list,
        group_size
):
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


def process_consumer_unit_electrical_parameter(
        consumer_unit,
        datetime_from,
        datetime_to,
        electrical_parameter,
        instant_delta
):

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

    timezone_current = django.utils.timezone.get_current_timezone()
    datetime_from_local = timezone_current.localize(datetime_from)
    datetime_from_utc =\
        datetime_from_local.astimezone(django.utils.timezone.utc)

    datetime_to_local = timezone_current.localize(datetime_to)
    datetime_to_utc = datetime_to_local.astimezone(django.utils.timezone.utc)

    instants =\
        data_warehouse_extended.models.Instant.objects.filter(
            instant_delta=instant_delta,
            instant_datetime__gte=datetime_from_utc,
            instant_datetime__lte=datetime_to_utc
        ).order_by(
            'instant_datetime'
        )

    instants_groups =\
        get_instants_groups(
            instants,
            data_warehouse_extended.globals.Constant.INSTANT_GROUP_SIZE)

    for instants_group in instants_groups:
        process_consumer_unit_electrical_parameter_instant_group(
            consumer_unit,
            electrical_parameter,
            instants_group)



def process_consumer_unit_electrical_parameter_instant_group(
        consumer_unit,
        electrical_parameter,
        instants_group
):

    if len(instants_group) < 1:
        logger.error(
            data_warehouse_extended.globals.SystemError.INSTANTS_GROUP_EMPTY)

        return

    instant_delta = instants_group[0].instant_delta
    timedelta = datetime.timedelta(seconds=instant_delta.delta_seconds)
    datetime_from = instants_group[0].instant_datetime - timedelta
    datetime_to = instants_group[-1].instant_datetime + timedelta
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

    independent_data_list = []
    dependent_data_list = []
    for electric_data_raw_dictionary in electric_data_raw_dictionaries_list:
        timedelta_current =\
            electric_data_raw_dictionary['medition_date'] - datetime_from

        timedelta_current_seconds =\
            timedelta_current.seconds + (timedelta_current.days * 24 * 3600)

        independent_data_list.append(timedelta_current_seconds)
        dependent_data_list.append(
            electric_data_raw_dictionary[
                electrical_parameter.name_transactional])

    if electrical_parameter.type ==\
           data_warehouse_extended.models.ElectricalParameter.INSTANT:

        curve_fit_function =\
            get_curve_fit_function_regression(
                independent_data_list,
                dependent_data_list)

    elif electrical_parameter.type ==\
             data_warehouse_extended.models.ElectricalParameter.CUMULATIVE:

        curve_fit_function =\
            get_curve_fit_function_interpolation(
                independent_data_list,
                dependent_data_list)

    else:
        logger.error(
            data_warehouse_extended.globals.SystemError.
            ELECTRICAL_PARAMETER_TYPE_NOT_SUPPORTED)

        return


################################################################################
#
# External Communication Scripts
#
################################################################################

def test_process_consumer_unit_electrical_parameter():
    pass
