# -*- coding: utf-8 -*-
#standard library imports
import datetime
import pytz

#related third party imports
from socketIO_client import SocketIO
from celery import task
from celery.task.schedules import crontab
from celery.decorators import periodic_task

import django.utils.timezone
from django.core.mail import send_mail, EmailMultiAlternatives

#local application/library specific imports
import data_warehouse_extended.globals
import data_warehouse_extended.models
import alarms.models
import c_center.models
import data_warehouse_extended.views

from data_warehouse.views import populate_data_warehouse, \
    data_warehouse_update
from c_center.c_center_functions import save_historic, dailyReportAll, \
    asign_electric_data_to_pw, calculateMonthlyReport_all, all_dailyreportAll,\
    getRatesCurrentMonth
from c_center.calculations import daytag_period_allProfilePowermeters
from tareas.models import *


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
        return
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


def populate_data_warehouse_specific_int(
        consumer_unit,
        instant_delta,
        date_from,
        date_to
):
    """
        Description:
            This function populates basic data for the Data Warehouse Extended
            to start working.

        Arguments:
            consumer_unit - the consumer unit to generate.

            instant_delta - the desired granularity.

            date_from - Datetime (the begining for the process)

            date_to - Datetime (the end for the process)

        Return:
            None.
    """

    electrical_parameters = \
        data_warehouse_extended.models.ElectricalParameter.objects.all()

    #
    # Generate data for Instant Delta.
    # Generate data for each Electrical Parameter.
    #
    for electrical_parameter in electrical_parameters:
        process_dw_consumerunit_electrical_parameter.delay(
            consumer_unit,
            date_from,
            date_to,
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
def tag_batch(start_day=datetime.datetime(2012, 8, 1),
              end_day=datetime.datetime(2013, 5, 29)):
    daytag_period_allProfilePowermeters(start_day, end_day)


@task(ignore_result=True)
def calculate_dw(granularity):
    data_warehouse_update(granularity)


@task(ignore_resulset=True)
def daily_report():
    dailyReportAll()


@task(ignore_resulset=True)
def all_daily_report_all(from_date):
    all_dailyreportAll(from_date)

@task(ignore_resulset=True)
def save_historic_delay(cd_b, building):
    save_historic(cd_b, building)


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

#############################
#                           #
#       Periodic Tasks      #
#                           #
#############################


@periodic_task(run_every=crontab(minute=1, hour=0))
def reporte_diario_para_reporte_mensual():
    daily_report.delay()
    print "firing periodic task - Raily Report"


@periodic_task(run_every=crontab(day_of_month='1'))
def calculateMonthlyReport():
    past_month_dt = datetime.date.today() - datetime.timedelta(days=2)
    calculateMonthlyReport_all(past_month_dt.month, past_month_dt.year)
    print "Task done: calculateMonthlyReport_all"
    getRatesCurrentMonth()
    print "Task done: getCFERates"


@periodic_task(run_every=crontab(minute='*/50'))
def data_warehouse_five_minute():
    end = datetime.datetime.now()
    start = datetime.datetime.now() - datetime.timedelta(minutes=50)
    delta_name = "Five Minute Delta"
    update_data_dw_delta.delay(end, start, delta_name)
    print "firing periodic task - DW 50 min, :)"


@periodic_task(run_every=crontab(hour='*/10'))
def data_warehouse_hour():
    end = datetime.datetime.now()
    start = datetime.datetime.now() - datetime.timedelta(hours=10)
    delta_name = "Hour Delta"
    update_data_dw_delta.delay(end, start, delta_name)
    print "firing periodic task - DW 150 min, :)"


@periodic_task(run_every=crontab(hour='*/12'))
def data_warehouse_six_hour():
    end = datetime.datetime.now()
    last, created = test_tasks.objects.get_or_create(
        task="6hr", value="",
        defaults={'executed_time': datetime.datetime.now()})
    delta1 = datetime.datetime.now(tz=pytz.utc) - last.executed_time
    if delta1 > datetime.timedelta(hours=60):
        start = datetime.datetime.now() - datetime.timedelta(hours=60)
        delta_name = "Six Hours Delta"
        last.executed_time = datetime.datetime.now(tz=pytz.utc)
        last.save()
        update_data_dw_delta.delay(end, start, delta_name)
        print "firing periodic task - DW 60 hours, :)"
    else:
        print "not firing:", str(delta1), "to fire"


@periodic_task(run_every=crontab(minute=0, hour=0))
def data_warehouse_day():
    end = datetime.datetime.now()
    last, created = test_tasks.objects.get_or_create(
        task="1day", value="",
        defaults={'executed_time': datetime.datetime.now()})
    delta1 = datetime.datetime.now(tz=pytz.utc) - last.executed_time
    if delta1 > datetime.timedelta(days=10):
        start = datetime.datetime.now() - datetime.timedelta(days=10)
        delta_name = "Day Delta"
        last.executed_time = datetime.datetime.now(tz=pytz.utc)
        last.save()
        update_data_dw_delta.delay(end, start, delta_name)
        print "firing periodic task - DW 10 days :)"
    else:
        print "not firing:", str(delta1), "to fire"


@periodic_task(run_every=crontab(minute='*/30'))
def last_data_received():
    delta_t = datetime.timedelta(minutes=30)
    cus = c_center.models.ConsumerUnit.objects.exclude(
        profile_powermeter__powermeter__powermeter_anotation="Medidor Virtual")

    subject = "Interrupción en la adquisición de datos"
    from_email = "noreply@auditem.mx"
    to_mail = []

    for cu in cus:
        profile = cu.profile_powermeter
        last_data = c_center.models.ElectricDataTemp.objects.filter(
            profile_powermeter=profile).order_by("-medition_date")[0]
        date_last = last_data.medition_date
        now_dt = datetime.datetime.now(tz=pytz.utc)
        try:
            alarm_cu = alarms.models.Alarms.objects.get(
                alarm_identifier="Interrupción de Datos",
                consumer_unit=cu)
        except alarms.models.Alarms.DoesNotExist:
            continue

        if (now_dt - date_last) > delta_t:
            ae = alarms.models.AlarmEvents(alarm=alarm_cu, value=0)
            ae.save()
            #send push notification
            socketIO = SocketIO('localhost', 9999)
            socketIO.emit('stopped_sa', {'alarm_event': ae.pk})

            users_to_notify = \
                alarms.models.UserNotificationSettings.objects.filter(
                    alarm=alarm_cu, status=1
                )
            for user in users_to_notify:
                if user.notification_type == 3:
                    to_mail.append(user.user.email)
                us_not = alarms.models.UserNotifications(user=user.user,
                                                         alarm_event=ae)
                us_not.save()
            if to_mail:
                str_data = (cu.building.building_name,
                            cu.electric_device_type.electric_device_type_name,
                            django.utils.timezone.localtime(date_last))
                text_content = """Saludos.\nEl presente es un correo
                autogenerado por Auditem con el fin de notificarle que:\n
                No se han obtenido datos eléctricos para la configuración de
                %s en %s,
                la última lectura fue tomada a las %s\n
                Por favor revise el estado del sistema
                de adquisición""".decode("utf-8") % str_data

                html_content = """<h2>Saludos.</h2><p>
                El presente es un correo autogenerado por
                Auditem con el fin de notificarle que:</p>
                <p>No se han obtenido datos eléctricos para la configuración de
                <span style="font-weight:700">%s</span> en
                <span style="font-weight:700">%s
                </span>,la última lectura fue tomada a las %s</p>
                <p>Por favor revise el estado del sistema de
                adquisición</p>""".decode("utf-8") % str_data
                msg = EmailMultiAlternatives(subject,
                                             text_content,
                                             from_email,
                                             to_mail)
                msg.attach_alternative(html_content, "text/html")
                msg.send()
