#
# Standard Library Imports
#
from datetime import timedelta, datetime
import time

#
# Application Specific Imports
#
import decimal
from data_warehouse.models import *
from c_center.models import Building, ConsumerUnit as ConsumerUnitTransactional,\
    ElectricDataTemp, ElectricDeviceType,PartOfBuilding, ProfilePowermeter

#
# Django imports
#
from django.utils.timezone import utc
from django.core.exceptions import ValidationError

#
# Third party imports
#
import math
from scipy import interpolate

FACTS_CLASSES = {
    "five-minute":ConsumerUnitFiveMinuteElectricData,
    "hour":ConsumerUnitHourElectricData,
    "day":ConsumerUnitDayElectricData,
    "week":ConsumerUnitWeekElectricData
}

TIME_INSTANTS_CLASSES = {
    "five-minute":FiveMinuteInstant,
    "hour":HourInstant,
    "day":DayInstant,
    "week":WeekInstant
}

TIME_INSTANTS_TIME_DELTA = {
    "five-minute":timedelta(minutes=5),
    "hour":timedelta(hours=1),
    "day":timedelta(days=1),
    "week":timedelta(weeks=1)
}

#########################################################################################
#
# Dimension Tables Fill Scripts
#
#########################################################################################

def fill_instants_table(from_datetime, to_datetime, instants_type):

    time_delta = TIME_INSTANTS_TIME_DELTA[instants_type]
    time_class = TIME_INSTANTS_CLASSES[instants_type]
    current_datetime = from_datetime
    while current_datetime <= to_datetime:
        current_period = time_class(instant_datetime = current_datetime)
        current_period.save()
        current_datetime += time_delta


def fill_instants(instants_type):

    from_datetime = datetime(year=1970, month=1, day=5, tzinfo=utc)
    to_datetime = datetime(year=2014, month=12, day=29, tzinfo=utc)
    fill_instants_table(from_datetime, to_datetime, instants_type)


def get_consumer_unit_building_name(consumer_unit):

    try:
        building = Building.objects.get(pk=consumer_unit.building.id)

    except Building.DoesNotExist:
        print "ERROR in 'get_consumer_unit_building_name' - Building Does Not Exist"
        return "Building Name - Does Not Exist Error"

    except:
        print "ERROR in 'get_consumer_unit_building_name' - Unexpected Error"
        return "Building Name - Unexpected Error"

    return building.building_name


def get_consumer_unit_part_of_building_name(consumer_unit):

    if consumer_unit.part_of_building is None:
        return None

    try:
        part_of_building = PartOfBuilding.objects.get(pk=consumer_unit.part_of_building.id)

    except PartOfBuilding.DoesNotExist:
        print "ERROR in 'get_consumer_unit_part_of_building' - PartOfBuilding Does Not Exist"
        return None

    except:
        print "ERROR in 'get_consumer_unit_part_of_building' - Unexpected Error"
        return None

    return part_of_building.part_of_building_name


def get_consumer_unit_electric_device_type_name(consumer_unit):

    try:
        electric_device_type = ElectricDeviceType.objects.get(pk=consumer_unit.electric_device_type.id)

    except ElectricDeviceType.DoesNotExist:
        print "ERROR in 'get_consumer_unit_electric_device_type_name' - Electric Device Type Does Not Exist"
        return "Electric Device Type Name - Does Not Exist Error"

    except:
        print "ERROR in 'get_consumer_unit_electric_device_type_name' - Unexpected Error"
        return "Electric Device Type Name - Unexpected Error"

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
                part_of_building_name = get_consumer_unit_part_of_building_name(consumer_unit),
                electric_device_type_name = get_consumer_unit_electric_device_type_name(consumer_unit)
            )
            consumer_unit_data_warehouse_new.save()
            continue

        consumer_unit_data_warehouse.building_name = \
            get_consumer_unit_building_name(consumer_unit)

        consumer_unit_data_warehouse.part_of_building_name =\
            get_consumer_unit_part_of_building_name(consumer_unit)

        consumer_unit_data_warehouse.electric_device_type_name =\
            get_consumer_unit_electric_device_type_name(consumer_unit)

        consumer_unit_data_warehouse.save()

#########################################################################################
#
# Facts Table Scripts
#
#########################################################################################

def is_valid_index(current_index, maximum_index, data_set_length):

        if maximum_index < 0:
            return (current_index >= 0) and (current_index < data_set_length)

        return (current_index < maximum_index) and (current_index < data_set_length)


def is_valid_points_count(points_count):

    try:
        return points_count['previous'] > 0 and\
               points_count['next'] > 0 and\
               points_count['next'] - points_count['previous'] > 0

    except KeyError:
        print "ERROR in 'is_valid_points_count' - KeyError"
        print KeyError.message
        return False

    except:
        print "ERROR in 'is_valid_points_count' - Unexpected Error"
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
    #   - It is assumed that both independent data and dependent data dictionaries have the
    #   same keys ('kW', 'kvar', 'PF', 'kWhIMPORT' and 'kvarhIMPORT')
    #
    data_set_length = len(data_set)

    if data_set_length <= 0:
        print "ERROR in 'update_data_dictionaries' - data_set empty"
        return False

    if not hasattr(data_set[0], 'medition_date'):
        print "ERROR in 'update_data_dictionaries' - data does not have attribute 'medition_date'"
        return False

    current_index = len(data_set) + maximum_index if maximum_index < 0 else 0
    while is_valid_index(current_index, maximum_index, data_set_length):
        data = data_set[current_index]
        time_delta = data.medition_date - instant_datetime
        seconds_delta = (time_delta.microseconds +\
                        (time_delta.seconds + time_delta.days * 24 * 3600) * 10**6) / 10**6

        try:
            if hasattr(data, 'kW') and data.kW is not None:
                independent_data['kW'].append(seconds_delta)
                dependent_data['kW'].append(data.kW)

            if hasattr(data, 'kvar') and data.kvar is not None:
                independent_data['kvar'].append(seconds_delta)
                dependent_data['kvar'].append(data.kvar)

            if hasattr(data, 'PF') and data.PF is not None:
                independent_data['PF'].append(seconds_delta)
                dependent_data['PF'].append(data.PF)

            if hasattr(data, 'kWhIMPORT') and data.kWhIMPORT is not None:
                independent_data['kWhIMPORT'].append(seconds_delta)
                dependent_data['kWhIMPORT'].append(data.kWhIMPORT)

            if hasattr(data, 'kvarhIMPORT') and data.kvarhIMPORT is not None:
                independent_data['kvarhIMPORT'].append(seconds_delta)
                dependent_data['kvarhIMPORT'].append(data.kvarhIMPORT)

        except KeyError:
            print "ERROR in update_data_dictionaries - KeyError"
            print KeyError.message
            return False

        except:
            print "ERROR in update_data_dictionaries - Unexpected Error"
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
            points_count_dictionary[key][points_count_type] += len(independent_data_dictionary[key])

        except KeyError:
            print "ERROR in 'update_points_count_dictionary' - KeyError"
            print KeyError.message()
            return False

        except:
            print "ERROR in 'update_points_count_dictionary' - Unexpected Error"
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

        except KeyError:
            print "ERROR in 'interpolation_functions_dictionary' - KeyError"
            print KeyError.message
            return None
        except:
            print "ERROR in 'interpolation_functions_dictionary' - Unexpected Error"
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
                data = None

            if math.isnan(data):
                data = None

            interpolation_values[key] = data

        else:
            interpolation_values[key] = None

    time_instant_class = TIME_INSTANTS_CLASSES[granularity]
    try:
        hour_instant = time_instant_class.objects.get(instant_datetime=instant_datetime)

    except time_instant_class.DoesNotExist:
        print "ERROR in 'save_electric_data' - Instant Does Not Exist"
        return False

    FactsClass = FACTS_CLASSES[granularity]

    electric_data_new = FactsClass(
        consumer_unit=consumer_unit,
        instant=hour_instant,
        kW = interpolation_values['kW'],
        kvar = interpolation_values['kvar'],
        PF = interpolation_values['PF'],
        kWhIMPORT = interpolation_values['kWhIMPORT'],
        kvarhIMPORT = interpolation_values['kvarhIMPORT']
    )

    try:
        electric_data_new.validate_unique()

    except ValidationError:
        try:
            electric_data_update = FactsClass.objects.get(consumer_unit=consumer_unit.pk,
                                                          instant=hour_instant.pk)

        except FactsClass.DoesNotExist:
            print "ERROR in 'save_electric_data' - Fact Record Does Not Exist"
            return False

        except:
            print "ERROR in 'save_electric_data' - Unexpected Error"
            return False

        electric_data_update.kW = interpolation_values['kW']
        electric_data_update.kvar = interpolation_values['kvar']
        electric_data_update.PF = interpolation_values['PF']
        electric_data_update.kWhIMPORT = interpolation_values['kWhIMPORT']
        electric_data_update.kvarhIMPORT = interpolation_values['kvarhIMPORT']
        electric_data_update.save()
        return True

    electric_data_new.save()

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
    electric_data_independent = {'kW':[], 'kvar':[], 'PF':[], 'kWhIMPORT':[], 'kvarhIMPORT':[]}
    electric_data_dependent = {'kW':[], 'kvar':[], 'PF':[], 'kWhIMPORT':[], 'kvarhIMPORT':[]}
    electric_data_points_count = {'kW':{'previous': 0, 'next': 0},
                                  'kvar':{'previous': 0, 'next': 0},
                                  'PF':{'previous': 0, 'next': 0},
                                  'kWhIMPORT': {'previous': 0, 'next': 0},
                                  'kvarhIMPORT':{'previous': 0, 'next': 0}}

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


def populate_consumer_unit_electric_data(consumer_unit, from_datetime, to_datetime, granularity):

    try:
        profile_powermeter = ProfilePowermeter.objects.get(pk=consumer_unit.profile_powermeter.pk)

    except ProfilePowermeter.DoesNotExist:
        print "ERROR in 'populate_consumer_unit_electric_data' - ProfilePowermeter Does Not Exist"
        return False

    except:
        print "ERROR in 'populate_consumer_unit_electric_data' - Unexpected Error"
        return False

    try:
        consumer_unit_data_warehouse = ConsumerUnit.objects.get(transactional_id=consumer_unit.pk)

    except ConsumerUnit.DoesNotExist:
        print "ERROR in 'populate_consumer_unit_electric_data' - ConsumerUnit Does Not Exist"
        return False

    except:
        print "ERROR in 'populate_consumer_unit_electric_data' - Unexpected Error"
        return False

    try:
        FactsClass = FACTS_CLASSES[granularity]
        TimeInstantClass = TIME_INSTANTS_CLASSES[granularity]

    except KeyError:
        print "ERROR in 'populate_consumer_unit_electric_data' - KeyError"
        return False

    except:
        print "ERROR in 'populate_consumer_unit_electric_data' - Unexpected Error"
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
            electric_data = FactsClass(consumer_unit=consumer_unit_data_warehouse,
                                       instant=instant,
                                       kW=None,
                                       kvar=None,
                                       PF=None,
                                       kWhIMPORT=None,
                                       kvarhIMPORT=None)

            try:
                electric_data.save()

            except:
                print "ERROR in 'populate_consumer_unit_electric_data' - Unexpected Error"
                return False

    return True


def interpolate_electric_data():

    consumer_unit = ConsumerUnitTransactional.objects.get(pk=7)
    from_datetime = datetime(year=2012, month=9, day=3, hour=16, tzinfo=utc)
    to_datetime = datetime(year=2012, month=9, day=18, hour=12, tzinfo=utc)

    #print populate_consumer_unit_electric_data(consumer_unit, from_datetime, to_datetime, "five-minute")
    #print populate_consumer_unit_electric_data(consumer_unit, from_datetime, to_datetime, "hour")
    print populate_consumer_unit_electric_data(consumer_unit, from_datetime, to_datetime, "day")
    print populate_consumer_unit_electric_data(consumer_unit, from_datetime, to_datetime, "week")


##########################################################################################
#
# Facts Table Scripts
#
##########################################################################################

def get_consumer_unit_and_time_interval_information(consumer_unit_id, start_datetime, end_datetime):

    try:
        consumer_unit = ConsumerUnit.objects.get(pk=consumer_unit_id)

    except ConsumerUnit.DoesNotExist:
        return None

    start_datetime_string = start_datetime.strftime("%Y/%m/%d")
    end_datetime_string = end_datetime.strftime("%Y/%m/%d")
    return dict(consumer_unit_string=consumer_unit.__unicode__(),
                start_datetime_string=start_datetime_string,
                end_datetime_string=end_datetime_string)


def get_consumer_unit_electric_data(electric_data, granularity, consumer_unit_id, from_datetime, to_datetime):

    try:
        consumer_unit = ConsumerUnit.objects.get(pk=consumer_unit_id)

    except ConsumerUnit.DoesNotExist:
        return []

    electric_data_values = []
    electric_data_class = FACTS_CLASSES[granularity]
    time_instant_class = TIME_INSTANTS_CLASSES[granularity]

    time_instants = time_instant_class.objects.filter(
                        instant_datetime__gte=from_datetime,
                        instant_datetime__lte=to_datetime)

    #print len(time_instants)
    for time_instant in time_instants:
        electric_data_values_dictionary = electric_data_class.objects.filter(
                                              consumer_unit=consumer_unit,
                                              instant=time_instant
                                          ).values(electric_data)

        #print "Electric Data Values Dictionary"
        #print electric_data_values_dictionary
        #print "\n"
        if len(electric_data_values_dictionary) == 1 and\
           electric_data_values_dictionary[0][electric_data] is not None:
            electric_data_value = float(electric_data_values_dictionary[0][electric_data])

        else:
            electric_data_value = None


        electric_data_values.append(dict(datetime=int(time.mktime(time_instant.instant_datetime.timetuple())),
                                         electric_data=electric_data_value))


    #print electric_data_values
    return electric_data_values
