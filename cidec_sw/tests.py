# -*- coding: utf-8 -*-
import random
import variety
import json
import thread
import time
import httplib
import urllib
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.template.context import RequestContext
from django.shortcuts import render_to_response
from django.core.mail import EmailMultiAlternatives
from django.db import connection, transaction
from django.db.models import Q

from socketIO_client import SocketIO
from celery import task

from c_center.models import *
from location.models import *
from alarms.models import *
from rbac.models import *
from data_warehouse_extended.models import *
from tareas.tasks import *
from c_center.c_center_functions import *
from rbac.rbac_functions import *
from alarms.alarm_functions import *

from cidec_sw.forms import CUGenerator


VIRTUAL_PROFILE = ProfilePowermeter.objects.get(
    powermeter__powermeter_anotation="Medidor Virtual")

@login_required(login_url="/")
def consumer_unit_generator_2000(request):
    form = CUGenerator(request.POST or None)
    msg = None
    if form.is_valid():
        msg = "Generando unidades, por favor espere."
        sa_number = form.cleaned_data['number_of_sas']
        pwrm_number = form.cleaned_data['number_of_pms']

        generate_cus.delay(sa_number, pwrm_number, request.user)

    variables_template = RequestContext(request, {"form": form,
                                                  "message": msg})
    return render_to_response("cu_generator.html", variables_template)


def create_fake_powermeter(building, iterator):
    """ Creates a complete structure for a fake powermeter

    :param building: Building object
    :param iterator: a number, user for identification
    :return: ProfilePowermeter object
    """
    pw_model = PowermeterModel.objects.all().order_by("?")[0]
    pw_serial = variety.random_string_generator(4, "1234567890")
    pw_alias = "alias del medidor " + str(iterator) + "_" + pw_serial

    pw_modbus = random.randint(0, 20)
    newPowerMeter = Powermeter(
        powermeter_model=pw_model,
        powermeter_anotation=pw_alias,
        powermeter_serial=pw_serial,
        modbus_address=pw_modbus
    )
    newPowerMeter.save()
    profile = ProfilePowermeter(powermeter=newPowerMeter)
    profile.save()
    electric_device_type = ElectricDeviceType.objects.all().exclude(
        electric_device_type_name="Total Edificio").order_by("?")[0]
    consumer_unit = ConsumerUnit(
        building=building,
        electric_device_type=electric_device_type,
        profile_powermeter=profile
    )
    consumer_unit.save()
    populate_data_warehouse_extended(
        populate_instants=None,
        populate_consumer_unit_profiles=True,
        populate_data=None)
    ind_eq = IndustrialEquipment.objects.get(
        building=building)
    p_i = PowermeterForIndustrialEquipment(
        powermeter=newPowerMeter,
        industrial_equipment=ind_eq)
    p_i.save()
    param = ElectricParameters.objects.all()[0]
    Alarms.objects.get_or_create(
        alarm_identifier="Interrupción de Datos",
        electric_parameter=param,
        consumer_unit=consumer_unit)
    return profile


def create_fake_building(iterator, user):
    """ Creates the whole structure for a building

    :param iterator: a number, used for identification
    :param user: django.contrib.models.Auth object
    :return: Building object, the newly created building
    """
    b_name = "edificio generado " + str(iterator)
    b_description = "Descripción de " + b_name
    formatted_address = "Dirección de " + b_name
    countryObj = Pais.objects.all().order_by("?")[0]
    stateObj = Estado.objects.all().order_by("?")[0]
    municipalityObj = Municipio.objects.all().order_by("?")[0]
    neighborhoodObj = Colonia.objects.all().order_by("?")[0]
    streetObj = Calle.objects.all().order_by("?")[0]
    regionObj = Region.objects.all().order_by("?")[0]
    b_ext = random.randint(1, 10)
    b_zip = variety.random_string_generator(5, "1234567890")
    tarifaObj = ElectricRates.objects.all().order_by("?")[0]

    newBuilding = Building(
        building_name=b_name,
        building_description=b_description,
        building_formatted_address=formatted_address,
        pais=countryObj,
        estado=stateObj,
        municipio=municipalityObj,
        colonia=neighborhoodObj,
        calle=streetObj,
        region=regionObj,
        building_external_number=b_ext,
        building_code_zone=b_zip,
        building_long_address=0,
        building_lat_address=0,
        electric_rate=tarifaObj)
    newBuilding.save()

    #Se da de alta la zona horaria del edificio
    timeZone = Timezones.objects.all().order_by("?")[0]
    newTimeZone = TimezonesBuildings(
        building=newBuilding,
        time_zone=timeZone)
    newTimeZone.save()

    today = datetime.datetime.now()
    today = today.replace(tzinfo=None)
    border = municipalityObj.border

    dsd = DaySavingDates.objects.filter(border=bool(border))
    for ds in dsd:
        winter = ds.winter_date
        winter = winter.replace(tzinfo=None)
        summer = ds.summer_date
        summer = summer.replace(tzinfo=None)
        if summer < today < winter:
            newTimeZone.day_saving_date = ds
            break
    else:
        dsd2 = DaySavingDates.objects.filter(
            border=bool(border), winter_date__lte=today)[0]
        newTimeZone.day_saving_date = dsd2

    newTimeZone.save()

    days_s = newTimeZone.day_saving_date.pk
    raw = newTimeZone.time_zone.raw_offset
    dst = newTimeZone.time_zone.dst_offset

    json_dic = {"raw_offset": raw,
                "dst_offset": dst,
                "daysaving_id": days_s}
    dts = json.dumps(json_dic)

    ie = IndustrialEquipment(
        alias="SA de "+b_name,
        building=newBuilding,
        timezone_dst=dts)
    ie.save()
    #Se da de alta la fecha de corte

    date_init = datetime.datetime.today().utcnow().replace(
        tzinfo=pytz.utc)
    billing_month = datetime.date(year=date_init.year,
                                  month=date_init.month, day=1)

    new_cut = MonthlyCutDates(
        building=newBuilding,
        billing_month=billing_month,
        date_init=date_init,
    )
    new_cut.save()

    #Se relaciona la compania con el edificio
    companyObj = Company.objects.all().order_by("?")[0]
    newBldComp = CompanyBuilding(
        company=companyObj,
        building=newBuilding,
    )
    newBldComp.save()

    #Se obtiene el objeto del tipo de edificio
    typeObj = BuildingType.objects.all().order_by("?")[0]
    bt_n = newBuilding.building_name + " - " + \
        typeObj.building_type_name
    newBuildingTypeBuilding = BuildingTypeForBuilding(
        building=newBuilding,
        building_type=typeObj,
        building_type_for_building_name=bt_n
    )
    newBuildingTypeBuilding.save()

    electric_device_type = ElectricDeviceType.objects.get(
        electric_device_type_name="Total Edificio")
    cu = ConsumerUnit(
        building=newBuilding,
        electric_device_type=electric_device_type,
        profile_powermeter=VIRTUAL_PROFILE
    )
    cu.save()
    #Add the consumer_unit instance for the DW
    populate_data_warehouse_extended(
        populate_instants=None,
        populate_consumer_unit_profiles=True,
        populate_data=None)
    regenerate_ie_config(ie.pk, user)
    return newBuilding


@task(ignore_result=True)
def generate_cus(sa_number, pwrm_number, user):
    """Asynchronous task that creates a whole structure of n acquisition systems

    :param sa_number:
    :param pwrm_number:
    :param user:
    :return:None
    """
    generated_data = []
    for i in range(0, sa_number):
        #create building, IE and other data
        building = create_fake_building(i, user)
        buil_pms = dict(building=building.building_name, pms=[])
        for j in range(0, pwrm_number):
            #create powermeters
            pm = create_fake_powermeter(building, j)
            buil_pms["pms"].append(dict(profile=pm.pk,
                                        serial=pm.powermeter.powermeter_serial))
            set_alarm_json(building, user)
            ie = IndustrialEquipment.objects.get(building=building)
            regenerate_ie_config(ie.pk, user)
        generated_data.append(buil_pms)
    from_email = "noreply@auditem.mx"
    subject = "Unidades de consumo creadas"
    message = "Se crearon los siguientes edificios y medidores \n"
    message += json.dumps(generated_data)
    msg = EmailMultiAlternatives(subject=subject,
                                 body=message,
                                 from_email=from_email,
                                 bcc=["hector@wime.com.mx"])
    msg.attach_alternative(message, "text/html")
    try:
        msg.send()
    except:
        pass

    print message
    for building in generated_data:
        delay = random.randint(30, 60)
        try:
            thread.start_new_thread(simulate_sas, (building, delay, 0))
        except:
            print "Error: unable to start thread"
    return None


def simulate_sas(powermeters, delay, control):
    """Simulates a medition for an array of powermeters

    :param powermeters: dict containing an array of powermeters
    :param delay: number of seconds to the next "reading"
    :return: True on completition
    """
    time.sleep(delay)
    pwermeters_copy = []
    control += 1
    for pwermeter in powermeters["pms"]:
        kvahTOTAL = pwermeter.get("kvahTOTAL", 0)
        totalkvarhIMPORT = pwermeter.get("totalkvarhIMPORT", 0)
        totalkWhIMPORT = pwermeter.get("totalkWhIMPORT", 0)

        _id, kvah, kvarh, kwh = simulate_medition(pwermeter["profile"],
                                                  pwermeter["serial"],
                                                  kvahTOTAL,
                                                  totalkvarhIMPORT,
                                                  totalkWhIMPORT)
        params = urllib.urlencode({'id_reading': _id})
        print "params", params
        conn = httplib.HTTPConnection("auditem.mx")
        conn.request("POST", "/buildings/medition_rate/", params)
        response = conn.getresponse()
        print response.status, response.reason
        conn.close()
        pwermeters_copy.append(dict(profile=pwermeter["profile"],
                                    serial=pwermeter["serial"],
                                    kvahTOTAL=kvah,
                                    totalkvarhIMPORT=kvarh,
                                    totalkWhIMPORT=kwh))
    if control < 288:
        return simulate_sas(dict(pms=pwermeters_copy), 300, control)
    else:
        print "Ending simulation for the following powermeters:", powermeters
        return True


def simulate_medition(profile, powermeter, kvahTOTAL=0, totalkvarhIMPORT=0,
                      totalkWhIMPORT=0):
    """Simulate a reading for a powermeter

    :param profile: number, id of ProfilePowermeter
    :param powermeter: string, serial number of the powermeter
    :param kvahTOTAL: number, the last kvahTOTAL value
    :param totalkvarhIMPORT: number, the last totalkvarhIMPORT value
    :param totalkWhIMPORT: number, the last totalkWhIMPORT value
    :return:
    """
    print "threaded for powermeter", powermeter
    data = get_randomized_data(kvahTOTAL, totalkvarhIMPORT, totalkWhIMPORT)

    cursor = connection.cursor()
    sql = "insert into c_center_electricdatatemp (profile_powermeter_id, " \
          "medition_date, V1, V2, V3, I1, I2, I3, kWL1, kWL2, kWL3, kvarL1, " \
          "kvarL2, kvarL3, kVAL1, kVAL2, kVAL3, PFL1, PFL2,PFL3, kW, kvar, " \
          "TotalkVA, PF, FREQ, TotalkWhIMPORT, powermeter_serial," \
          "TotalkvarhIMPORT, kWhL1, kWhL2, kwhL3, kvarhL1, kvarhL2, kvarhL3, " \
          "kVAhL1, kVAhL2, kVAhL3, kW_import_sliding_window_demand, " \
          "kvar_import_sliding_window_demand, kVA_sliding_window_demand, " \
          "kvahTOTAL) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s," \
          "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, " \
          "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    medition_date = str(datetime.datetime.utcnow())
    cursor.execute(sql, [profile,
                         medition_date,
                         data["V1"],
                         data["V2"],
                         data["V3"],
                         data["I1"],
                         data["I2"],
                         data["I3"],
                         data["kWL1"],
                         data["kWL2"],
                         data["kWL3"],
                         data["kvarL1"],
                         data["kvarL2"],
                         data["kvarL3"],
                         data["kVAL1"],
                         data["kVAL2"],
                         data["kVAL3"],
                         data["PFL1"],
                         data["PFL2"],
                         data["PFL3"],
                         data["kW"],
                         data["kvar"],
                         data["TotalkVA"],
                         data["PF"],
                         data["FREQ"],
                         data["TotalkWhIMPORT"],
                         powermeter,
                         data["TotalkvarhIMPORT"],
                         data["kWhL1"],
                         data["kWhL2"],
                         data["kwhL3"],
                         data["kvarhL1"],
                         data["kvarhL2"],
                         data["kvarhL3"],
                         data["kVAhL1"],
                         data["kVAhL2"],
                         data["kVAhL3"],
                         data["kW_import_sliding_window_demand"],
                         data["kvar_import_sliding_window_demand"],
                         data["kVA_sliding_window_demand"],
                         data["kvahTOTAL"]
                         ])
    transaction.commit_unless_managed()
    cursor.execute("SELECT id FROM c_center_electricdatatemp WHERE "
                   "medition_date = %s AND powermeter_serial = %s",
                   [medition_date, powermeter])
    row = cursor.fetchone()
    print row
    return row[0], kvahTOTAL, totalkvarhIMPORT, totalkWhIMPORT


def get_randomized_data(kvahTOTAL, totalkvarhIMPORT, totalkWhIMPORT):
    """ Generates a whole set of fictional data for a medition

    :param kvahTOTAL: number, the last kvahTOTAL value to increment
    :param totalkvarhIMPORT: number, the last totalkvarhIMPORT value to increment
    :param totalkWhIMPORT: number, the last totalkWhIMPORT value to increment
    :return: dict of simulated data
    """
    kvahTOTAL += Decimal(str(round(random.uniform(4, 11), 6)))
    totalkvarhIMPORT += Decimal(str(round(random.uniform(4, 11), 6)))
    totalkWhIMPORT += Decimal(str(round(random.uniform(4, 11), 6)))
    data = dict(
        V1=Decimal(str(round(random.uniform(120, 128), 6))),
        V2=Decimal(str(round(random.uniform(120, 128), 6))),
        V3=Decimal(str(round(random.uniform(120, 128), 6))),
        I1=Decimal(str(round(random.uniform(4, 11), 6))),
        I2=Decimal(str(round(random.uniform(4, 11), 6))),
        I3=Decimal(str(round(random.uniform(4, 11), 6))),
        kWL1=Decimal(str(round(random.uniform(0, 6), 6))),
        kWL2=Decimal(str(round(random.uniform(0, 6), 6))),
        kWL3=Decimal(str(round(random.uniform(0, 6), 6))),
        kvarL1=Decimal(str(round(random.uniform(0, 1), 6))),
        kvarL2=Decimal(str(round(random.uniform(0, 1), 6))),
        kvarL3=Decimal(str(round(random.uniform(0, 1), 6))),
        kVAL1=Decimal(str(round(random.uniform(0, 2), 6))),
        kVAL2=Decimal(str(round(random.uniform(0, 2), 6))),
        kVAL3=Decimal(str(round(random.uniform(0, 2), 6))),
        PFL1=Decimal(str(round(random.uniform(.8, 1), 6))),
        PFL2=Decimal(str(round(random.uniform(.8, 1), 6))),
        PFL3=Decimal(str(round(random.uniform(.8, 1), 6))),
        kW=Decimal(str(round(random.uniform(0, 6), 6))),
        kvar=Decimal(str(round(random.uniform(0, 1), 6))),
        TotalkVA=Decimal(str(round(random.uniform(0, 1), 6))),
        PF=Decimal(str(round(random.uniform(.8, 1), 6))),
        FREQ=Decimal(str(round(random.uniform(50, 61), 6))),
        TotalkWhIMPORT=totalkWhIMPORT,
        TotalkvarhIMPORT=totalkvarhIMPORT,
        kWhL1=totalkWhIMPORT,
        kWhL2=totalkWhIMPORT,
        kwhL3=totalkWhIMPORT,
        kvarhL1=totalkvarhIMPORT,
        kvarhL2=totalkvarhIMPORT,
        kvarhL3=totalkvarhIMPORT,
        kVAhL1=kvahTOTAL,
        kVAhL2=kvahTOTAL,
        kVAhL3=kvahTOTAL,
        kW_import_sliding_window_demand=Decimal(str(
            round(random.uniform(0, 6), 6))),
        kvar_import_sliding_window_demand=Decimal(str(
            round(random.uniform(0, 1), 6))),
        kVA_sliding_window_demand=Decimal(str(round(random.uniform(0, 1), 6))),
        kvahTOTAL=kvahTOTAL
    )
    return data

@login_required(login_url="/")
def delete_building(request):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']
    template_vars["buildings"] = Building.objects.all()

    variables_template = RequestContext(request, template_vars)
    return render_to_response("delete_building.html", variables_template)


@login_required(login_url="/")
def delete_data_building(request, id_building):
    """ Deletes ALL the data for a building

    :param request: django request object
    :param id_building: number, the id of building
    :return: status 200 on success
    """
    if request.user.is_superuser:
        id_building = int(id_building)
        #eliminamos datos por edificio

        MonthlyCutDates.objects.filter(building__pk=id_building).delete()
        try:
            CompanyBuilding.objects.get(building__pk=id_building).delete()
        except ObjectDoesNotExist:
            print "ObjectDoesNotExist CompanyBuilding"
            pass
        print "DELETED: MonthlyCutDates, CompanyBuilding"

        PowermeterForIndustrialEquipment.objects.filter(
            industrial_equipment__building__pk=id_building).delete()
        try:
            IndustrialEquipment.objects.get(building__pk=id_building).delete()
        except ObjectDoesNotExist:
            print "ObjectDoesNotExist IndustrialEquipment"
            pass
        try:
            TimezonesBuildings.objects.get(building__pk=id_building).delete()
        except ObjectDoesNotExist:
            print "ObjectDoesNotExist TimezonesBuildings"
            pass
        print "DELETED: IndustrialEquipment, TimezonesBuildings"

        BuildingAttributesForBuilding.objects.filter(building__pk=id_building)
        try:
            BuildingTypeForBuilding.objects.get(
                building__pk=id_building).delete()
        except ObjectDoesNotExist:
            print "ObjectDoesNotExist BuildingTypeForBuilding"
            pass
        print "DELETED BuildingAttributesForBuilding, BuildingTypeForBuilding"
        HierarchyOfPart.objects.filter(
            Q(part_of_building_composite__building__pk=id_building) |
            Q(part_of_building_leaf__building__pk=id_building) |
            Q(consumer_unit_composite__building__pk=id_building) |
            Q(consumer_unit_leaf__building__pk=id_building)
        ).delete()

        cus = ConsumerUnit.objects.filter(building__pk=id_building)
        cus_pks = [cu.pk for cu in cus]
        serials = []
        for cu in cus:
            if cu.profile_powermeter.powermeter.powermeter_anotation != \
                    "Medidor Virtual":
                serial = cu.profile_powermeter.powermeter.powermeter_serial
                print "Medidor:", serial
                serials.append(serial)
        profiles = ProfilePowermeter.objects.filter(
            powermeter__powermeter_serial__in=serials)
        powermeters = Powermeter.objects.filter(powermeter_serial__in=serials)

        #Datos eléctricos
        edata = ElectricDataTemp.objects.filter(powermeter_serial__in=serials)
        ed_pks = [e.pk for e in edata]
        ElectricDataTags.objects.filter(electric_data__pk__in=ed_pks).delete()
        edata.delete()
        print "DELETED HierarchyOfPart, ElectricDataTemp, ElectricDataTags"
        DailyData.objects.filter(
            consumer_unit__building__pk=id_building).delete()
        MonthlyData.objects.filter(
            consumer_unit__building__pk=id_building).delete()
        print "DELETED DailyData, MonthlyData"
        #data_warehouse
        dw_cus = ConsumerUnitProfile.objects.filter(
            transactional_id__in=cus_pks)
        dw_cus_pks = [c.pk for c in dw_cus]
        ConsumerUnitInstantElectricalData.objects.filter(
            consumer_unit_profile__pk__in=dw_cus_pks).delete()
        dw_cus.delete()
        print "DELETED Data Warehouse"
        #Alarmas
        UserNotifications.objects.filter(
            alarm_event__alarm__consumer_unit__building__id=id_building
        ).delete()
        UserNotificationSettings.objects.filter(
            alarm__consumer_unit__building__id=id_building).delete()
        AlarmEvents.objects.filter(
            alarm__consumer_unit__building__id=id_building).delete()
        Alarms.objects.filter(consumer_unit__pk__in=cus_pks).delete()
        print "DELETED Alarms"
        cus.delete()
        profiles.delete()
        powermeters.delete()
        print "DELETED: Consumerunits, Profiles and Powermeters"

        PartOfBuilding.objects.filter(building__pk=id_building).delete()
        DataContextPermission.objects.filter(building__pk=id_building).delete()
        print "DELETED: PartOfBuilding, DataContextPermission"
        try:
            Building.objects.get(pk=id_building).delete()
        except ObjectDoesNotExist:
            print "ObjectDoesNotExist Building"
            pass
        print "All Deleted"
        return HttpResponse(status=200)
    else:
        raise Http404


def alarm_raiser_4000(ind_eq):
    """ Rimulates repeating alarm events for the industrial equipment array

    :param ind_eq: array containing ids of industrial equipments
    :return: True on completition
    """

    for ie in ind_eq:
        ind_eq = IndustrialEquipment.objects.get(pk=ie)
        alarm = Alarms.objects.filter(
            consumer_unit__building=ind_eq.building
        ).exclude(
            alarm_identifier='Interrupción de Datos'
        ).order_by("?")[0]
        delay = random.randint(1, 30)
        thread.start_new_thread(simulate_sa_alarm, (alarm, delay, 0))


def simulate_sa_alarm(alarm, delay, cont):
    cont += 1
    time.sleep(delay)
    cursor = connection.cursor()
    sql = "insert into alarms_alarmevents (alarm_id, triggered_time, value) " \
          "values (%s, %s, %s)"
    triggered_time = str(datetime.datetime.utcnow())
    cursor.execute(sql, [alarm.pk, str(triggered_time), 300])
    transaction.commit_unless_managed()
    cursor.execute("SELECT id FROM alarms_alarmevents WHERE "
                   "triggered_time = %s AND alarm_id = %s",
                   [triggered_time, alarm.pk])
    row = cursor.fetchone()
    alarm_event = row[0]

    socket = SocketIO('auditem.mx', 9999)
    socket.emit('alarm_trigger', {'alarm_event': alarm_event})

    print "alarm ", alarm.pk, "triggered at", triggered_time

    sql = "insert into alarms_alarmevents (alarm_id, triggered_time, value) " \
          "values (%s, %s, %s)"
    triggered_time = str(datetime.datetime.utcnow())
    cursor.execute(sql, [alarm.pk, str(triggered_time), 300])
    transaction.commit_unless_managed()
    cursor.execute("SELECT id FROM alarms_alarmevents WHERE "
                   "triggered_time = %s AND alarm_id = %s",
                   [triggered_time, alarm.pk])
    row = cursor.fetchone()
    alarm_event = row[0]

    socket.emit('alarm_trigger', {'alarm_event': alarm_event})

    SocketIO.disconnect(socket)

    print "alarm ", alarm.pk, "triggered at", triggered_time

    if cont < 60:
        simulate_sa_alarm(alarm, 30, cont)
    else:
        print "Simulation complete"
        return