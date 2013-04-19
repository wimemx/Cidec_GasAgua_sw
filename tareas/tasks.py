import datetime

from celery import task
from celery.task.schedules import crontab
from celery.decorators import periodic_task

from data_warehouse.views import populate_data_warehouse, \
    data_warehouse_update
from c_center.c_center_functions import save_historic, dailyReportAll, \
    asign_electric_data_to_pw
from c_center.calculations import reTagHolidays

import data_warehouse_extended.globals
import data_warehouse_extended.models
import data_warehouse_extended.views

import c_center.models


from datetime import date

@task(ignore_result=True)
def change_profile_electric_data(serials):
    asign_electric_data_to_pw(serials)


def populate_data_warehouse_extended(
        populate_instants=None,
        populate_consumer_unit_profiles=None,
        populate_data=None
):
    """
        Description:
            This function populates basic data for the Data Warehouse Extended
            to start working.

        Arguments:
            populate_instants - If True the function creates Instants in the
                interval embedded in the code.

            populate_consumer_unit_profiles - If True the function updates the
                information about the Consumer Unit Profiles using the
                transactional database.

        Return:
            None.
    """

    if populate_instants:

        #
        # Create instants for each instant delta
        #
        datetime_from = \
            data_warehouse_extended.globals.Constant.INSTANT_DATETIME_FIRST

        datetime_to = \
            data_warehouse_extended.globals.Constant.INSTANT_DATETIME_LAST

        instant_deltas = \
            data_warehouse_extended.models.InstantDelta.objects.all()

        for instant_delta in instant_deltas:
            data_warehouse_extended.views.create_instant_instances(
                datetime_from, datetime_to, instant_delta)

    if populate_consumer_unit_profiles:
        #
        # Create and update Consumer Unit Profiles based on the existent
        # Consumer Units in the transactional database.
        #
        data_warehouse_extended.views.update_consumer_units()

    if populate_data:
        consumer_unit_profiles = \
            data_warehouse_extended.models.ConsumerUnitProfile.objects.all()

        electrical_parameters = \
            data_warehouse_extended.models.ElectricalParameter.objects.all()

        instant_deltas = \
            data_warehouse_extended.models.InstantDelta.objects.all()

        #
        # Generate data for each Consumer Unit Profile
        #
        for consumer_unit_profile in consumer_unit_profiles:
            try:
                consumer_unit = \
                    c_center.models.ConsumerUnit.objects.get(
                        pk=consumer_unit_profile.pk)

            except c_center.models.ConsumerUnit.DoesNotExist:
                print "Unidad de consumo no encontrada", consumer_unit_profile

                continue

            #
            # Generate data for each Instant Delta.
            #
            for instant_delta in instant_deltas:
                #
                # Generate data for each Electrical Parameter.
                #
                for electrical_parameter in electrical_parameters:
                    process_dw_consumerunit_electrical_parameter.delay(
                        consumer_unit,
                        data_warehouse_extended.globals.Constant.
                        DATA_DATETIME_FIRST,
                        data_warehouse_extended.globals.Constant.
                        DATA_DATETIME_LAST,
                        electrical_parameter,
                        instant_delta)

    return


def populate_data_warehouse_specific(
        consumer_unit,
        instant_delta,
        date_from
):
    """
        Description:
            This function populates basic data for the Data Warehouse Extended
            to start working.

        Arguments:
            consumer_unit - the consumer unit to generate.

            instant_delta - the desired granularity.

            date_from - Datetime (the begining for the process)

        Return:
            None.
    """

    electrical_parameters = \
        data_warehouse_extended.models.ElectricalParameter.objects.all()

    #
    # Generate data for each Consumer Unit Profile
    #
    try:
        consumer_unit = \
            c_center.models.ConsumerUnit.objects.get(
                pk=consumer_unit.transactional_id)

    except c_center.models.ConsumerUnit.DoesNotExist:
        print "Unidad de consumo no encontrada", consumer_unit

    #
    # Generate data for Instant Delta.
    # Generate data for each Electrical Parameter.
    #
    for electrical_parameter in electrical_parameters:
        process_dw_consumerunit_electrical_parameter.delay(
            consumer_unit,
            date_from,
            data_warehouse_extended.globals.Constant.
            DATA_DATETIME_LAST,
            electrical_parameter,
            instant_delta)

    return


@task(ignore_result=True)
def process_dw_consumerunit_electrical_parameter(
        consumer_unit, first, last, electrical_parameter, instant_delta):
    data_warehouse_extended.views.process_consumer_unit_electrical_parameter(
        consumer_unit, first, last, electrical_parameter, instant_delta
    )

@task(ignore_result=True)
def tag_batch(initial, last):
    recursive_tag(initial, last)

@task(ignore_result=True)
def calculate_dw(granularity):
    data_warehouse_update(granularity)

@task(ignore_resulset=True)
def daily_report():
    dailyReportAll()

@task(ignore_resulset=True)
def save_historic_delay(cd_b, building):
    save_historic(cd_b, building)

# this will run every minute, see http://celeryproject.org/docs/reference/celery.task.schedules.html#celery.task.schedules.crontab
@periodic_task(run_every=crontab(minute='*/60'))
def data_warehouse_one_hour():
    #calculate_dw.delay("hour")
    data_warehouse_update("hour")
    print "firing periodic task - DW Hour, :)"

@periodic_task(run_every=crontab(minute=0, hour=0))
def data_warehouse_one_day():
    calculate_dw.delay("day")
    print "firing periodic task - DW Day"

@periodic_task(run_every=crontab(minute=1, hour=0))
def reporte_diario_para_reporte_mensual():
    daily_report.delay()
    print "firing periodic task - Raily Report"

@periodic_task(run_every=crontab(minute=0, hour=0, day_of_week='sun'))
def data_warehouse_one_week():
    calculate_dw.delay("week")
    print "firing periodic task - DW week"

# this will run every minute, see http://celeryproject.org/docs/reference/celery.task.schedules.html#celery.task.schedules.crontab
#@periodic_task(run_every=crontab(hour="*", minute="*/2", day_of_week="*"))
#def test_two_minute():
#    print "firing another test"

@periodic_task(run_every=crontab(minute='*/50'))
def data_warehouse_five_minute():
    end = datetime.datetime.now()
    start = datetime.datetime.now() - datetime.timedelta(minutes=50)
    delta_name = "Five Minute Delta"
    update_data_dw_delta.delay(end, start, delta_name)
    print "firing periodic task - DW 50 min, :)"

@periodic_task(run_every=crontab(minute='*/100'))
def data_warehouse_ten_minutes():
    end = datetime.datetime.now()
    start = datetime.datetime.now() - datetime.timedelta(minutes=100)
    delta_name = "Ten Minute Delta"
    update_data_dw_delta.delay(end, start, delta_name)
    print "firing periodic task - DW 100 min, :)"


@periodic_task(run_every=crontab(minute='*/150'))
def data_warehouse_fifteen_minutes():
    end = datetime.datetime.now()
    start = datetime.datetime.now() - datetime.timedelta(minutes=150)
    delta_name = "15 min Delta"
    update_data_dw_delta.delay(end, start, delta_name)
    print "firing periodic task - DW 150 min, :)"

@periodic_task(run_every=crontab(hour='*/5'))
def data_warehouse_half_hour():
    end = datetime.datetime.now()
    start = datetime.datetime.now() - datetime.timedelta(minutes=300)
    delta_name = "Half Hour Delta"
    update_data_dw_delta.delay(end, start, delta_name)
    print "firing periodic task - DW 300 min, :)"

@periodic_task(run_every=crontab(hour='*/10'))
def data_warehouse_hour():
    end = datetime.datetime.now()
    start = datetime.datetime.now() - datetime.timedelta(hours=10)
    delta_name = "Hour Delta"
    update_data_dw_delta.delay(end, start, delta_name)
    print "firing periodic task - DW 150 min, :)"


@periodic_task(run_every=crontab(hour='*/30'))
def data_warehouse_three_hour():
    end = datetime.datetime.now()
    start = datetime.datetime.now() - datetime.timedelta(hours=30)
    delta_name = "Three Hours Delta"
    update_data_dw_delta.delay(end, start, delta_name)
    print "firing periodic task - DW 150 min, :)"


@periodic_task(run_every=crontab(hour='*/60'))
def data_warehouse_six_hour():
    end = datetime.datetime.now()
    start = datetime.datetime.now() - datetime.timedelta(hours=60)
    delta_name = "Six Hours Delta"
    update_data_dw_delta.delay(end, start, delta_name)
    print "firing periodic task - DW 60 hours, :)"


@periodic_task(run_every=crontab(hour='*/120'))
def data_warehouse_twelve_hour():
    end = datetime.datetime.now()
    start = datetime.datetime.now() - datetime.timedelta(days=5)
    delta_name = "Half Day Delta"
    update_data_dw_delta.delay(end, start, delta_name)
    print "firing periodic task - DW 5 days :)"


@periodic_task(run_every=crontab(hour='*/240'))
def data_warehouse_day():
    end = datetime.datetime.now()
    start = datetime.datetime.now() - datetime.timedelta(days=10)
    delta_name = "Day Delta"
    update_data_dw_delta.delay(end, start, delta_name)
    print "firing periodic task - DW 10 days :)"


@task(ignore_result=True)
def update_data_dw_delta(end, start, delta_name):
    consumer_unit_profiles = \
        data_warehouse_extended.models.ConsumerUnitProfile.objects.all()

    electrical_parameters = \
        data_warehouse_extended.models.ElectricalParameter.objects.all()

    instant_delta = \
        data_warehouse_extended.models.InstantDelta.objects.get(
            name=delta_name)

    #
    # Generate data for each Consumer Unit Profile
    #
    for consumer_unit_profile in consumer_unit_profiles:
        try:
            consumer_unit = \
                c_center.models.ConsumerUnit.objects.get(
                    pk=consumer_unit_profile.pk)

        except c_center.models.ConsumerUnit.DoesNotExist:
            print "unidad de consumo no encontrada", consumer_unit_profile
            continue

        #
        # Generate data for each Instant Delta.
        #

        #
        # Generate data for each Electrical Parameter.
        #
        for electrical_parameter in electrical_parameters:
            process_dw_consumerunit_electrical_parameter.delay(
                consumer_unit, start, end,
                electrical_parameter,
                instant_delta)