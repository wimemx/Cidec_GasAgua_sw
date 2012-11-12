#
# Python Imports
#
from datetime import timedelta, datetime
import logging
import math
from scipy import interpolate
import time

#
# Django imports
#
from django.utils.timezone import utc
from django.core.exceptions import ValidationError

#
# Application Specific Imports
#
import decimal
from data_warehouse.models import *
from c_center.models import Building, ConsumerUnit as ConsumerUnitTransactional,\
    ElectricDataTemp, ElectricDeviceType,PartOfBuilding, ProfilePowermeter

#
# Constants
#
CUMULATIVE_ELECTRIC_DATA = {
    "TotalkWhIMPORT":"kWh",
    "TotalkvarhIMPORT":"kvarh",
    "kvahTOTAL":"kvah"
}

FACTS_INSTANT_CLASSES = {
    "five-minute":ConsumerUnitFiveMinuteElectricData,
    "hour":ConsumerUnitHourElectricData,
    "day":ConsumerUnitDayElectricData,
    "week":ConsumerUnitWeekElectricData
}

FACTS_INTERVAL_CLASSES = {
    "five-minute":ConsumerUnitFiveMIntElectricData,
    "hour":ConsumerUnitHourIntElectricData,
    "day":ConsumerUnitDayIntElectricData,
    "week":ConsumerUnitWeekIntElectricData
}

TIME_INSTANTS_CLASSES = {
    "five-minute":FiveMinuteInstant,
    "hour":HourInstant,
    "day":DayInstant,
    "week":WeekInstant
}

TIME_INTERVALS_CLASSES = {
    "five-minute":FiveMinuteInterval,
    "hour":HourInterval,
    "day":DayInterval,
    "week":WeekInterval
}

TIME_INSTANTS_TIME_DELTA = {
    "five-minute":timedelta(minutes=5),
    "hour":timedelta(hours=1),
    "day":timedelta(days=1),
    "week":timedelta(weeks=1)
}

#
# Globals
#
logger = logging.getLogger("data_warehouse")

##########################################################################################
#
# Constant Classes
#
##########################################################################################

class Error:

    BUILDING_DOES_NOT_EXIST = "building_does_not_exist"
    BUILDING_NAME = "building_name_error"
    CONSUMER_UNIT_DOES_NOT_EXIST = "consumer_unit_does_not_exist"
    DATA_SET_EMPTY = "data_set_empty"
    DOES_NOT_HAVE_ATTRIBUTE = "does_not_have_attribute"
    ELECTRIC_DEVICE_TYPE_DOES_NOT_EXIST = "electric_device_type_does_not_exist"
    ELECTRIC_DEVICE_TYPE_NAME = "electric_device_type_name"
    FACT_DOES_NOT_EXIST = "fact_does_not_exist"
    INSTANT_ALREADY_EXISTS = "instant_already_exist"
    INSTANT_DOES_NOT_EXIST = "instant_does_not_exist"
    INTERPOLATION_FUNCTION_EXECUTION = "interpolation_function_execution_error"
    INVALID_INTERPOLATION = "invalid_interpolation"
    KEY_ERROR = "key_error"
    PART_OF_BUILDING_DOES_NOT_EXIST = "part_of_building_does_not_exist"
    PROFILE_POWERMETER_DOES_NOT_EXIST = "profile_powermeter_does_not_exist"
    VALIDATION_ERROR = "validation_error"


##########################################################################################
#
# Exceptions
#
##########################################################################################

class DataWarehouseException(Exception):

    def __init__(
            self,
            function,
            reason
    ):

        self.function = function
        self.reason = reason

    def __str__(self):

        return "\n\tFunction: " + self.function + "\n\tReason: " + self.reason


class DataWarehouseInformationRetrieveException(DataWarehouseException):

    def __init__(
            self,
            function,
            reason
    ):
        super(DataWarehouseInformationRetrieveException, self).__init__(function, reason)

    def __str__(self):

        return "\nDataWarehouseInformationRetrieveException " +\
               super(DataWarehouseInformationRetrieveException, self).__str__()


##########################################################################################
#
# Dimension Tables Fill Scripts
#
##########################################################################################

def fill_instants(
        instants_type
):

    from_datetime = datetime(year=2010, month=1, day=1, tzinfo=utc)
    to_datetime = datetime(year=2010, month=1, day=2, tzinfo=utc)
    fill_instants_table(from_datetime, to_datetime, instants_type)


def fill_intervals(
        intervals_type
):

    from_datetime = datetime(year=2012, month=1, day=1, tzinfo=utc)
    to_datetime = datetime(year=2012, month=12, day=31, tzinfo=utc)
    fill_intervals_table(from_datetime, to_datetime, intervals_type)


def fill_instants_table(
        from_datetime,
        to_datetime,
        instants_type
):

    time_delta = TIME_INSTANTS_TIME_DELTA[instants_type]
    time_class = TIME_INSTANTS_CLASSES[instants_type]
    current_datetime = from_datetime
    while current_datetime <= to_datetime:
        current_period = time_class(instant_datetime = current_datetime)
        try:
            current_period.full_clean()

        except ValidationError:
            logger.error(Error.INSTANT_ALREADY_EXISTS)
            current_datetime += time_delta
            continue

        current_period.save()
        logger.info(str(current_period))
        current_datetime += time_delta


def fill_intervals_table(
        from_datetime,
        to_datetime,
        intervals_type
):

    time_delta = TIME_INSTANTS_TIME_DELTA[intervals_type]
    interval_class = TIME_INTERVALS_CLASSES[intervals_type]
    current_datetime = from_datetime
    while current_datetime <= to_datetime:
        current_period = interval_class(start_datetime=current_datetime,
            end_datetime=current_datetime+time_delta)
        try:
            current_period.full_clean()

        except ValidationError:
            logger.error(Error.INSTANT_ALREADY_EXISTS)
            current_datetime += time_delta
            continue

        current_period.save()
        logger.info(str(current_period))
        current_datetime += time_delta


def get_consumer_unit_by_id(
        consumer_unit_id
):
    try:
        consumer_unit = ConsumerUnit.objects.get(pk=consumer_unit_id)

    except ConsumerUnit.DoesNotExist as consumer_unit_does_not_exist:
        logger.error(str(consumer_unit_does_not_exist))
        raise DataWarehouseInformationRetrieveException(
            function="get_consumer_unit_by_id",
            reason="consumer_unit_does_not_exist")

    return consumer_unit


def get_consumer_unit_building_name(
        consumer_unit
):

    try:
        building = Building.objects.get(pk=consumer_unit.building.id)

    except Building.DoesNotExist as building_does_not_exist:
        logger.error(Error.BUILDING_DOES_NOT_EXIST + "\n\t" + str(building_does_not_exist))
        return Error.BUILDING_NAME

    return building.building_name


def get_consumer_unit_part_of_building_name(
        consumer_unit
):

    if consumer_unit.part_of_building is None:
        return None

    try:
        part_of_building = PartOfBuilding.objects.get(
            pk=consumer_unit.part_of_building.id)

    except PartOfBuilding.DoesNotExist as part_of_building_does_not_exist:
        logger.error(Error.PART_OF_BUILDING_DOES_NOT_EXIST + "\n\t" +
                     str(part_of_building_does_not_exist))

        return None

    return part_of_building.part_of_building_name


def get_consumer_unit_electric_device_type_name(
        consumer_unit
):

    try:
        electric_device_type = ElectricDeviceType.objects.get(pk=consumer_unit.electric_device_type.id)

    except ElectricDeviceType.DoesNotExist as electric_device_type_does_not_exist:
        logger.error(Error.ELECTRIC_DEVICE_TYPE_DOES_NOT_EXIST + "\n\t" +
                     str(electric_device_type_does_not_exist))

        return Error.ELECTRIC_DEVICE_TYPE_NAME

    return electric_device_type.electric_device_type_name


def update_consumer_units():

    consumer_units = ConsumerUnitTransactional.objects.all()
    for consumer_unit in consumer_units:
        try:
            consumer_unit_data_warehouse = ConsumerUnit.objects.get(pk=consumer_unit.pk)
        except ConsumerUnit.DoesNotExist:
            consumer_unit_data_warehouse_new = ConsumerUnit(
                transactional_id=consumer_unit.id,
                building_name = get_consumer_unit_building_name(consumer_unit),
                part_of_building_name = get_consumer_unit_part_of_building_name(
                    consumer_unit),
                electric_device_type_name = get_consumer_unit_electric_device_type_name(
                    consumer_unit)
            )
            try:
                consumer_unit_data_warehouse_new.full_clean()

            except ValidationError as consumer_unit_data_warehouse_new_validation_error:
                logger.error(Error.VALIDATION_ERROR + "\n\t" +
                             str(consumer_unit_data_warehouse_new_validation_error))

                continue

            consumer_unit_data_warehouse_new.save()
            continue

        consumer_unit_data_warehouse.building_name =\
        get_consumer_unit_building_name(consumer_unit)

        consumer_unit_data_warehouse.part_of_building_name =\
        get_consumer_unit_part_of_building_name(consumer_unit)

        consumer_unit_data_warehouse.electric_device_type_name =\
        get_consumer_unit_electric_device_type_name(consumer_unit)

        try:
            consumer_unit_data_warehouse.full_clean()

        except ValidationError as consumer_unit_data_warehouse_validation_error:
            logger.error(Error.VALIDATION_ERROR + "\n\t" +
                         str(consumer_unit_data_warehouse_validation_error))

            continue

        consumer_unit_data_warehouse.save()


##########################################################################################
#
# Facts Table Scripts
#
##########################################################################################


def get_facts_instant_tuple_by_interval(
        consumer_unit,
        interval,
        granularity
):
    instant_start, instant_end = get_instants_tuple_by_interval(interval, granularity)

    try:
        FactsInstantClass = FACTS_INSTANT_CLASSES[granularity]

    except KeyError as facts_interval_class_key_error:
        logger.error(Error.KEY_ERROR + "\n\t" + str(facts_interval_class_key_error))
        raise DataWarehouseInformationRetrieveException(
            function="get_facts_tuple_by_interval",
            reason="facts_interval_class_key_error")

    try:
        facts_instant_start = FactsInstantClass.objects.get(consumer_unit=consumer_unit,
            instant=instant_start)

    except FactsInstantClass.DoesNotExist as facts_start_does_not_exist:
        logger.error(str(facts_start_does_not_exist))
        raise DataWarehouseInformationRetrieveException(
            function="get_facts_tuple_by_interval",
            reason="facts_instant_start_does_not_exist")

    try:
        facts_instant_end = FactsInstantClass.objects.get(consumer_unit=consumer_unit,
            instant=instant_end)

    except FactsInstantClass.DoesNotExist as facts_start_does_not_exist:
        logger.error(str(facts_start_does_not_exist))
        raise DataWarehouseInformationRetrieveException(
            function="get_facts_tuple_by_interval",
            reason="facts_instant_end_does_not_exist")

    return facts_instant_start, facts_instant_end


def get_instants_tuple_by_interval(
        interval,
        granularity
):
    try:
        InstantClass = TIME_INSTANTS_CLASSES[granularity]

    except KeyError as instant_class_key_error:
        logger.error(Error.KEY_ERROR + "\n\t" + str(instant_class_key_error))
        raise DataWarehouseInformationRetrieveException(
            function="get_instants_tuple_by_interval",
            reason="instant_class_key_error")

    try:
        instant_start = InstantClass.objects.get(instant_datetime=interval.start_datetime)

    except InstantClass.DoesNotExist as instant_start_does_not_exist:
        logger.error(str(instant_start_does_not_exist))
        raise DataWarehouseInformationRetrieveException(
            function="get_instants_tuple_by_interval",
            reason="instant_start_does_not_exist")

    try:
        instant_end = InstantClass.objects.get(instant_datetime=interval.end_datetime)

    except InstantClass.DoesNotExist as instant_end_does_not_exist:
        logger.error(str(instant_end_does_not_exist))
        raise DataWarehouseInformationRetrieveException(
            function="get_instants_tuple_by_interval",
            reason="instant_end_does_not_exist")

    return instant_start, instant_end


def is_cumulative_electric_data_valid(
        consumer_unit_instant_electric_data
):
    for instant_fact in CUMULATIVE_ELECTRIC_DATA.keys():
        if not hasattr(consumer_unit_instant_electric_data, instant_fact):
            raise DataWarehouseInformationRetrieveException(
                function="is_cumulative_electric_data_valid",
                reason="consumer_unit_instant_electric_data_key_error")

        if getattr(consumer_unit_instant_electric_data, instant_fact) is None:
            return False

    return True


def is_valid_index(
        current_index,
        maximum_index, data_set_length
):

    if maximum_index < 0:
        return (current_index >= 0) and (current_index < data_set_length)

    return (current_index < maximum_index) and (current_index < data_set_length)


def is_valid_points_count(points_count):

    try:
        return points_count['previous'] > 0 and\
               points_count['next'] > 0 and\
               points_count['next'] - points_count['previous'] > 0

    except KeyError as points_count_key_error:
        logger.error(Error.KEY_ERROR + "\n\t" + str(points_count_key_error))
        return False


def update_data_dictionaries(
        independent_data,
        dependent_data,
        data_set,
        instant_datetime,
        maximum_index
):

    #
    # ASSUMPTIONS:
    #
    #   It is assumed that both independent data and dependent data dictionaries have the
    #   same keys
    #
    data_set_length = len(data_set)

    if data_set_length <= 0:
        logger.error(Error.DATA_SET_EMPTY)
        return False

    if not hasattr(data_set[0], 'medition_date'):
        logger.error(Error.DOES_NOT_HAVE_ATTRIBUTE + " - medition_date")
        return False

    current_index = len(data_set) + maximum_index if maximum_index < 0 else 0
    while is_valid_index(current_index, maximum_index, data_set_length):
        data = data_set[current_index]
        time_delta = data.medition_date - instant_datetime
        seconds_delta =\
        (time_delta.microseconds +\
         (time_delta.seconds + time_delta.days * 24 * 3600) * 10**6) / 10**6

        for electric_data in independent_data.keys():
            try:
                if hasattr(data, electric_data) and\
                   getattr(data, electric_data) is not None:

                    independent_data[electric_data].append(seconds_delta)
                    dependent_data[electric_data].append(getattr(data, electric_data))

            except KeyError as independent_or_dependent_data_key_error:
                logger.error(Error.KEY_ERROR + "\n\t" +
                             str(independent_or_dependent_data_key_error))

                return False

        current_index += 1

    return True


def update_points_count_dictionary(
        independent_data_dictionary,
        points_count_dictionary,
        points_count_type
):

    #
    # It is assumed that independent_data_dictionary and points_count_dictionary have the
    # same keys.
    #
    for key in independent_data_dictionary.keys():
        try:
            points_count_dictionary[key][points_count_type] +=\
            len(independent_data_dictionary[key])

        except KeyError as points_count_dictionary_key_error:
            logger.error(Error.KEY_ERROR + "\n\t" + str(points_count_dictionary_key_error))
            return False

    return True


def interpolation_functions_dictionary(independent_data, dependent_data, points_count_dictionary):

    interpolation_functions = {}

    for key in dependent_data.keys():
        try:
            if is_valid_points_count(points_count_dictionary[key]):
                interpolation_functions[key] = interpolate.interp1d(independent_data[key],
                    dependent_data[key],
                    'cubic')

        except KeyError as interpolation_functions_key_error:
            logger.error(Error.KEY_ERROR + "\n\t" + str(interpolation_functions_key_error))
            return None

    return interpolation_functions


def save_electric_data(
        consumer_unit,
        instant_datetime,
        interpolation_functions,
        independent_data,
        granularity
):

    interpolation_values = {}
    for key in independent_data.keys():
        if interpolation_functions.has_key(key):
            function_current = interpolation_functions[key]
            try:
                data = decimal.Decimal(str(function_current([0])[0]))

            except:
                logger.error(Error.INTERPOLATION_FUNCTION_EXECUTION)
                data = None

            if math.isnan(data):
                data = None

            interpolation_values[key] = data

        else:
            interpolation_values[key] = None

    time_instant_class = TIME_INSTANTS_CLASSES[granularity]
    try:
        hour_instant = time_instant_class.objects.get(instant_datetime=instant_datetime)

    except time_instant_class.DoesNotExist as instant_does_not_exist:
        logger.error(Error.INSTANT_DOES_NOT_EXIST + "\n\t" + str(instant_does_not_exist))
        return False

    FactsClass = FACTS_INSTANT_CLASSES[granularity]

    electric_data_new = FactsClass(
        consumer_unit=consumer_unit,
        instant=hour_instant
    )

    for electric_data_name, interpolation_value  in interpolation_values.iteritems():
        if hasattr(electric_data_new, electric_data_name):
            setattr(electric_data_new, electric_data_name, interpolation_value)

        else:
            logger.error(Error.DOES_NOT_HAVE_ATTRIBUTE)

    try:
        electric_data_new.validate_unique()

    except ValidationError:
        try:
            electric_data_update = FactsClass.objects.get(consumer_unit=consumer_unit.pk,
                instant=hour_instant.pk)

        except FactsClass.DoesNotExist as fact_does_not_exist:
            logger.error(Error.FACT_DOES_NOT_EXIST + "\n\t" + str(fact_does_not_exist))
            return False

        for electric_data_name, interpolation_value  in interpolation_values.iteritems():
            if hasattr(electric_data_update, electric_data_name):
                setattr(electric_data_update, electric_data_name, interpolation_value)

            else:
                logger.error(Error.DOES_NOT_HAVE_ATTRIBUTE + " - " + electric_data_name)

        try:
            electric_data_update.full_clean()

        except ValidationError as electric_data_update_validation_error:
            logger.error(Error.VALIDATION_ERROR + "\n\t" +
                         str(electric_data_update_validation_error))

        electric_data_update.save()
        logger.info("electric_data_update - " + str(electric_data_update.pk))
        return True

    try:
        electric_data_new.full_clean()

    except ValidationError as electric_data_new_validation_error:
        logger.error(Error.VALIDATION_ERROR + "\n\t" + str(electric_data_new_validation_error))

    electric_data_new.save()
    logger.info("electric_data_new - " + str(electric_data_new.pk))
    return True


def interpolate_consumer_unit_electric_data_instant(
        consumer_unit,
        profile_powermeter,
        instant_datetime,
        granularity
):

    #
    # Dictionaries that will store independent and dependent data from the transactional
    # database in order to obtain dependent data for a specific independent value using
    # interpolation. The obtained data will be stored in the data warehouse
    #
    FactsClass = FACTS_INSTANT_CLASSES[granularity]
    electric_data_independent =\
    dict((attribute.name, []) for attribute in FactsClass._meta.fields if attribute.null)

    electric_data_dependent =\
    dict((attribute.name, []) for attribute in FactsClass._meta.fields if attribute.null)

    electric_data_points_count =\
    dict((attribute.name, {'previous': 0, 'next': 0})
        for attribute in FactsClass._meta.fields if attribute.null)

    #
    # Update and validate independent and dependent data dictionaries with points (at most
    # 5) that have a medition_date before instant_datetime
    #
    previous_electric_data_set = ElectricDataTemp.objects.filter(
        profile_powermeter=profile_powermeter.id,
        medition_date__lt=instant_datetime\
    ).order_by('medition_date')

    is_update_data_successful = update_data_dictionaries(electric_data_independent,
        electric_data_dependent,
        previous_electric_data_set,
        instant_datetime,
        -5)

    if not is_update_data_successful:
        return False

    is_update_points_count_successful = update_points_count_dictionary(
        electric_data_dependent,
        electric_data_points_count,
        "previous")

    if not is_update_points_count_successful:
        return False

    #
    # Update and validate independent and dependent data dictionaries with points (at most
    # 5) that have a medition_date after instant_datetime
    #
    next_electric_data_set = ElectricDataTemp.objects.filter(
        profile_powermeter=profile_powermeter.id,
        medition_date__gte=instant_datetime\
    ).order_by('medition_date')

    is_update_data_successful = update_data_dictionaries(electric_data_independent,
        electric_data_dependent,
        next_electric_data_set,
        instant_datetime,
        5)

    if not is_update_data_successful:
        return False

    is_update_points_count_successful = update_points_count_dictionary(
        electric_data_dependent,
        electric_data_points_count,
        "next")

    if not is_update_points_count_successful:
        return False

    interpolation_functions = interpolation_functions_dictionary(electric_data_independent,
        electric_data_dependent,
        electric_data_points_count)

    is_save_electric_data_successful = save_electric_data(consumer_unit,
        instant_datetime,
        interpolation_functions,
        electric_data_independent,
        granularity)

    if not is_save_electric_data_successful:
        return False

    return True


def populate_consumer_unit_electric_data(
        consumer_unit,
        from_datetime,
        to_datetime,
        granularity
):

    try:
        profile_powermeter = ProfilePowermeter.objects.get(pk=consumer_unit.profile_powermeter.pk)

    except ProfilePowermeter.DoesNotExist as profile_powermeter_does_not_exist:
        logger.error(Error.PROFILE_POWERMETER_DOES_NOT_EXIST + "\n\t" +
                     str(profile_powermeter_does_not_exist))

        return False

    try:
        consumer_unit_data_warehouse = ConsumerUnit.objects.get(transactional_id=consumer_unit.pk)

    except ConsumerUnit.DoesNotExist as consumer_unit_does_not_exist:
        logger.error(Error.CONSUMER_UNIT_DOES_NOT_EXIST + "\n\t" +
                     str(consumer_unit_does_not_exist))

        return False

    try:
        FactsClass = FACTS_INSTANT_CLASSES[granularity]
        TimeInstantClass = TIME_INSTANTS_CLASSES[granularity]

    except KeyError as facts_or_time_instant_classes_key_error:
        logger.error(Error.KEY_ERROR + "\n\t" + str(facts_or_time_instant_classes_key_error))
        return False

    instants = TimeInstantClass.objects.filter(instant_datetime__gte=from_datetime,
        instant_datetime__lte=to_datetime)

    for instant in instants:
        is_valid = interpolate_consumer_unit_electric_data_instant(
            consumer_unit_data_warehouse,
            profile_powermeter,
            instant.instant_datetime,
            granularity)

        if not is_valid:
            logger.error(Error.INVALID_INTERPOLATION)
            try:
                electric_data = FactsClass.objects.get(
                    consumer_unit=consumer_unit_data_warehouse,
                    instant=instant)

            except FactsClass.DoesNotExist:
                electric_data = FactsClass(consumer_unit=consumer_unit_data_warehouse,
                    instant=instant)

            for attribute in FactsClass._meta.fields:
                if attribute.null:
                    setattr(electric_data, attribute.name, None)

            try:
                electric_data.full_clean()

            except ValidationError as electric_data_validation_error:
                logger.error(str(electric_data_validation_error))
                return False

            electric_data.save()
            logger.info("electric_data_invalid - " + str(electric_data.pk))

    return True


def populate_consumer_unit_electric_data_interval(
        consumer_unit,
        from_datetime,
        to_datetime,
        granularity
):
    try:
        consumer_unit_data_warehouse = ConsumerUnit.objects.get(transactional_id=consumer_unit.pk)

    except ConsumerUnit.DoesNotExist as consumer_unit_does_not_exist:
        logger.error(Error.CONSUMER_UNIT_DOES_NOT_EXIST + "\n\t" +
                     str(consumer_unit_does_not_exist))

        return False

    try:
        FactsIntervalClass = FACTS_INTERVAL_CLASSES[granularity]
        TimeIntervalClass = TIME_INTERVALS_CLASSES[granularity]

    except KeyError as facts_or_time_instant_classes_key_error:
        logger.error(Error.KEY_ERROR + "\n\t" + str(facts_or_time_instant_classes_key_error))
        return False

    intervals = TimeIntervalClass.objects.filter(start_datetime__gte=from_datetime,
        end_datetime__lte=to_datetime)

    for interval in intervals:
        are_facts_valid = True
        try:
            facts_instant_start, facts_instant_end = get_facts_instant_tuple_by_interval(
                consumer_unit_data_warehouse,
                interval,
                granularity)

        except DataWarehouseInformationRetrieveException as\
        interval_instants_information_retrieve_exception:

            logger.error(str(interval_instants_information_retrieve_exception))
            are_facts_valid = False


        interpolate_facts_instant = True
        if are_facts_valid:
            if is_cumulative_electric_data_valid(facts_instant_start) and\
               is_cumulative_electric_data_valid(facts_instant_end):

                interpolate_facts_instant = False

        if interpolate_facts_instant:
            populate_consumer_unit_electric_data(consumer_unit,
                interval.start_datetime,
                interval.end_datetime,
                granularity)

        try:
            facts_instant_start, facts_instant_end = get_facts_instant_tuple_by_interval(
                consumer_unit_data_warehouse,
                interval,
                granularity)

        except DataWarehouseInformationRetrieveException as\
        interval_instants_information_retrieve_exception:

            logger.error(str(interval_instants_information_retrieve_exception))
            continue

        try:
            facts_interval = FactsIntervalClass.objects.get(
                consumer_unit=consumer_unit_data_warehouse,
                interval=interval)

        except FactsIntervalClass.DoesNotExist:
            facts_interval = FactsIntervalClass(consumer_unit=consumer_unit_data_warehouse,
                interval=interval)

        for fact_instant_name, fact_interval_name in CUMULATIVE_ELECTRIC_DATA.iteritems():
            if hasattr(facts_instant_start, fact_instant_name) and\
               hasattr(facts_instant_end, fact_instant_name) and\
               hasattr(facts_interval, fact_interval_name):

                fact_instant_start_value = getattr(facts_instant_start, fact_instant_name)
                fact_instant_end_value = getattr(facts_instant_end, fact_instant_name)

                if fact_instant_start_value is not None and\
                   fact_instant_end_value is not None:

                    fact_interval_value =\
                    fact_instant_end_value - fact_instant_start_value

                    setattr(facts_interval, fact_interval_name, fact_interval_value)

        try:
            facts_interval.full_clean()

        except ValidationError as facts_interval_validation_error:
            logger.error(str(facts_interval_validation_error))
            continue

        facts_interval.save()
        logger.info("electric_data_interval - " + str(facts_interval.pk))

    return True


def interpolate_electric_data():

    consumer_unit = ConsumerUnitTransactional.objects.get(pk=31)
    from_datetime = datetime(year=2012, month=9, day=1, hour=0, tzinfo=utc)
    to_datetime = datetime(year=2012, month=10, day=25, hour=0, tzinfo=utc)
    granularity="day"
    populate_consumer_unit_electric_data(consumer_unit,
        from_datetime,
        to_datetime,
        granularity)


def interpolate_electric_data_interval():

    consumer_unit = ConsumerUnitTransactional.objects.get(pk=7)
    from_datetime = datetime(year=2012, month=9, day=1, hour=0, tzinfo=utc)
    to_datetime = datetime(year=2012, month=10, day=25, hour=0, tzinfo=utc)
    granularity="day"
    populate_consumer_unit_electric_data_interval(consumer_unit,
        from_datetime,
        to_datetime,
        granularity)


##########################################################################################
#
# Facts Table Scripts
#
##########################################################################################

def get_consumer_unit_and_time_interval_information(
        consumer_unit_id,
        start_datetime,
        end_datetime
):

    try:
        consumer_unit = ConsumerUnit.objects.get(pk=consumer_unit_id)

    except ConsumerUnit.DoesNotExist as consumer_unit_does_not_exist:
        logger.error(str(consumer_unit_does_not_exist))
        return None

    start_datetime_string = start_datetime.strftime("%Y/%m/%d")
    end_datetime_string = end_datetime.strftime("%Y/%m/%d")
    return dict(consumer_unit_string=consumer_unit.__unicode__(),
        start_datetime_string=start_datetime_string,
        end_datetime_string=end_datetime_string)


def get_consumer_unit_electric_data(
        electric_data,
        granularity,
        consumer_unit_id,
        from_datetime,
        to_datetime
):

    try:
        consumer_unit = ConsumerUnit.objects.get(pk=consumer_unit_id)

    except ConsumerUnit.DoesNotExist:
        return []

    electric_data_values = []
    electric_data_class = FACTS_INSTANT_CLASSES[granularity]
    time_instant_class = TIME_INSTANTS_CLASSES[granularity]
    time_instants = time_instant_class.objects.filter(
        instant_datetime__gte=from_datetime,
        instant_datetime__lte=to_datetime)

    for time_instant in time_instants:
        electric_data_values_dictionary = electric_data_class.objects.filter(
            consumer_unit=consumer_unit,
            instant=time_instant
        ).values(electric_data)

        if len(electric_data_values_dictionary) == 1 and\
           electric_data_values_dictionary[0][electric_data] is not None:

            electric_data_value = float(electric_data_values_dictionary[0][electric_data])

        else:
            electric_data_value = None


        electric_data_values.append(dict(datetime=int(time.mktime(time_instant.instant_datetime.timetuple())),
            electric_data=electric_data_value))


    return electric_data_values


def get_consumer_unit_electric_data_csv(
        electric_data,
        granularity,
        consumer_unit,
        from_datetime,
        to_datetime
):
    electric_data_rows = []
    electric_data_class = FACTS_INSTANT_CLASSES[granularity]
    time_instant_class = TIME_INSTANTS_CLASSES[granularity]
    time_instants = time_instant_class.objects.filter(
        instant_datetime__gte=from_datetime,
        instant_datetime__lte=to_datetime)

    for time_instant in time_instants:
        electric_data_values_dictionary = electric_data_class.objects.filter(
            consumer_unit=consumer_unit,
            instant=time_instant
        ).values(electric_data)

        if len(electric_data_values_dictionary) == 1 and\
           electric_data_values_dictionary[0][electric_data] is not None:

            electric_data_value_string =\
            "%.6f" % electric_data_values_dictionary[0][electric_data]

            instant_string = time_instant.instant_datetime.strftime("%Y/%m/%d %H:%M")
            electric_data_row = [consumer_unit.building_name,
                                 consumer_unit.electric_device_type_name,
                                 electric_data,
                                 electric_data_value_string,
                                 instant_string]

            electric_data_rows.append(electric_data_row)

    return electric_data_rows


def get_consumer_unit_electric_data_interval(
        electric_data,
        granularity,
        consumer_unit_id,
        from_datetime,
        to_datetime
):

    #
    # TODO - Check if passing consumer_unit as object instead of as id increases performance
    #
    try:
        consumer_unit = ConsumerUnit.objects.get(pk=consumer_unit_id)

    except ConsumerUnit.DoesNotExist:
        return []

    electric_data_values = []
    electric_data_class = FACTS_INTERVAL_CLASSES[granularity]
    time_instant_class = TIME_INTERVALS_CLASSES[granularity]
    time_intervals = time_instant_class.objects.filter(
        start_datetime__gte=from_datetime,
        start_datetime__lte=to_datetime)

    for time_interval in time_intervals:
        electric_data_values_dictionary = electric_data_class.objects.filter(
            consumer_unit=consumer_unit,
            interval=time_interval
        ).values(electric_data)

        if len(electric_data_values_dictionary) == 1 and\
           electric_data_values_dictionary[0][electric_data] is not None:

            electric_data_value = float(electric_data_values_dictionary[0][electric_data])

        else:
            electric_data_value = None


        electric_data_values.append(dict(datetime=int(time.mktime(time_interval.start_datetime.timetuple())),
            electric_data=electric_data_value))


    return electric_data_values


def get_consumer_unit_electric_data_interval_csv(
        electric_data,
        granularity,
        consumer_unit,
        from_datetime,
        to_datetime
):
    electric_data_rows = []
    electric_data_class = FACTS_INTERVAL_CLASSES[granularity]
    time_instant_class = TIME_INTERVALS_CLASSES[granularity]
    time_intervals = time_instant_class.objects.filter(
        start_datetime__gte=from_datetime,
        start_datetime__lte=to_datetime)

    for time_interval in time_intervals:
        electric_data_values_dictionary = electric_data_class.objects.filter(
            consumer_unit=consumer_unit,
            interval=time_interval
        ).values(electric_data)

        if len(electric_data_values_dictionary) == 1 and\
           electric_data_values_dictionary[0][electric_data] is not None:

            electric_data_value_string =\
            "%.6f" % electric_data_values_dictionary[0][electric_data]

            start_datetime_string = time_interval.start_datetime.strftime(
                "%Y/%m/%d %H:%M")

            end_datetime_string = time_interval.end_datetime.strftime("%Y/%m/%d %H:%M")
            electric_data_row = [consumer_unit.building_name,
                                 consumer_unit.electric_device_type_name,
                                 electric_data,
                                 electric_data_value_string,
                                 start_datetime_string,
                                 end_datetime_string]

            electric_data_rows.append(electric_data_row)

    return electric_data_rows