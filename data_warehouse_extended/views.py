#coding:utf-8

# Python imports
import datetime
import logging

# Django imports
import django.core.exceptions

# Data Warehouse Extended imports
import data_warehouse_extended.globals
import data_warehouse_extended.models

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

    # Research if a function name can be accesed by itself
    logger.info("create_instant_instances")
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
