#coding:utf-8

# Python imports
import datetime
import logging

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
    datetime_current = datetime_from
    while datetime_current <= datetime_to:
        instant_current = data_warehouse_extended.models.Instant(
                              instant_delta=instant_delta,
                              instant_datetime=datetime_current)

        try:
            instant_current.full_clean()

        except django.core.exceptions.ValidationError:
            logger.error(
                data_warehouse_extended.globals.SystemError.
                INSTANT_ALREADY_EXISTS)

            datetime_current += time_delta
            continue

        instant_current.save()
        logger.info(data_warehouse_extended.globals.SystemInfo.INSTANT_SAVED +\
                    " " + str(instant_current))

        datetime_current += time_delta


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

def process_consumer_unit_electrical_parameter(
        consumer_unit_id,
        datetime_from,
        datetime_to,
        electrical_parameter_name
):

    try:
        electrical_parameter =\
            data_warehouse_extended.models.ElectricalParameter.objects.get(
                name=electrical_parameter_name)

    except data_warehouse_extended.models.ElectricalParameter.DoesNotExist:
        logger.error(
            data_warehouse_extended.globals.SystemError.
                ELECTRICAL_PARAMETER_DOES_NOT_EXIST +\
            " " + electrical_parameter_name)

        return

    try:
        consumer_unit =\
            c_center.models.ConsumerUnit.objects.get(pk=consumer_unit_id)

    except c_center.models.ConsumerUnit.DoesNotExist:
        logger.error(
            data_warehouse_extended.globals.SystemError.
                CONSUMER_UNIT_DOES_NOT_EXIST +\
            " " + str(consumer_unit_id))

        return

    try:
        consumer_unit_profile =\
            data_warehouse_extended.models.ConsumerUnitProfile.objects.get(
                pk=consumer_unit_id)

    except data_warehouse_extended.models.ConsumerUnitProfile.DoesNotExist:
        logger.error(
            data_warehouse_extended.globals.SystemError.
                CONSUMER_UNIT_PROFILE_DOES_NOT_EXIST +\
            " " + str(consumer_unit_id))

        return
