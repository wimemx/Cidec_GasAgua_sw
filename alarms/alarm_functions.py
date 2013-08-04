# -*- coding: utf-8 -*-
__author__ = 'wime'
import json
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404

from c_center.c_center_functions import get_c_unitsforbuilding_for_operation

from alarms.models import Alarms, ElectricParameters
from c_center.models import IndustrialEquipment, Building, ConsumerUnit, \
    ProfilePowermeter, Powermeter, PowermeterForIndustrialEquipment
from rbac.models import Operation


VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")


def set_alarm_json(building, user):
    """ Generate and save a JSON containing the whole alarm configuration for
    a buildinf
    :param building: Object.- Building instance
    :param user: Object.- django.contrib.auth.models.User instance
    """
    cunits = get_c_unitsforbuilding_for_operation("Modificar alarmas",
                                                  UPDATE, user, building)[0]
    eAlarmsPerEDevices = []
    for cu in cunits:
        p_serial = cu.profile_powermeter.powermeter.powermeter_serial
        eDeviceAlarms = []
        cu_alarms = Alarms.objects.filter(consumer_unit=cu).exclude(
            status=False).exclude(alarm_identifier="Interrupción de Datos")
        for cua in cu_alarms:
            status = 1 if cua.status else 0
            min_value = 0 if not cua.min_value else float(str(cua.min_value))
            max_value = 0 if not cua.max_value else float(str(cua.max_value))
            eDeviceAlarms.append(
                dict(alarm_identifier=cua.alarm_identifier,
                     electric_parameter_id=cua.electric_parameter.pk,
                     min_value=min_value,
                     max_value=max_value,
                     status=status
                ))
        eAlarmsPerEDevices.append(dict(powermeter_serial=p_serial,
                                       EDeviceAlarms=eDeviceAlarms))

    i_eq = IndustrialEquipment.objects.get(building=building)
    i_eq.has_new_alarm_config = True
    i_eq.new_alarm_config = json.dumps(
        dict(eAlarmsPerEDevices=eAlarmsPerEDevices))
    i_eq.modified_by = user
    i_eq.save()
    print i_eq.new_alarm_config


def update_alarm_config(new_alarm_config, ie_pk):
    ie = get_object_or_404(IndustrialEquipment, pk=ie_pk)
    config = json.loads(new_alarm_config)
    for device in config['eAlarmsPerEDevices']:
        try:
            cu = ConsumerUnit.objects.get(
                profile_powermeter__powermeter__powermeter_serial=
                device['powermeter_serial'])
        except ObjectDoesNotExist:
            return False
        else:
            Alarms.objects.filter(consumer_unit=cu).update(status=False)
            for alarm in device['EDeviceAlarms']:
                print "alarm: ", alarm
                param = ElectricParameters.objects.get(
                    pk=alarm['electric_parameter_id'])
                try:
                    al = Alarms.objects.get(
                        alarm_identifier=alarm['alarm_identifier'])
                except ObjectDoesNotExist:
                    al = Alarms(alarm_identifier=alarm['alarm_identifier'],
                                electric_parameter=param,
                                max_value=str(alarm['max_value']),
                                min_value=str(alarm['min_value']),
                                consumer_unit=cu)
                    al.save()
                else:
                    al.electric_parameter = param
                    al.consumer_unit = cu
                    al.status = True
                    al.max_value = str(alarm['max_value'])
                    al.min_value = str(alarm['min_value'])
                al.save()
    ie.has_new_alarm_config = False
    ie.save()
    return True


def update_ie_config(new_config, ie_pk):
    ie = get_object_or_404(IndustrialEquipment, pk=ie_pk)
    config = json.loads(new_config)
    p_i = PowermeterForIndustrialEquipment.objects.filter(
        industrial_equipment=ie).exclude(
            powermeter__powermeter_anotation="Medidor Virtual").exclude(
                powermeter__powermeter_anotation="No Registrado")
    #set status to false of all the powermeters
    for pw in p_i:
        pw.powermeter.status = False
        pw.powermeter.save()

    for device in config['eDevicesConfigList']:
        try:
            profile = ProfilePowermeter.objects.get(
                powermeter__powermeter_serial=str(device['IdMedidorESN']))
        except ObjectDoesNotExist:
            return False
        profile.read_time_rate = int(device['ReadTimeRate'])
        profile.send_time_rate = int(device['SendTimeRate'])
        profile.save()
        profile.powermeter.modbus_address = int(device['ModbusAddress'])
        profile.powermeter.powermeter_anotation = device['PowermeterAnnotation']
        profile.powermeter.status = True
        profile.powermeter.save()
    ie.has_new_config = False
    ie.save()
    return True


def get_alarm_from_building(id_bld):
    """ Return the alarm for the request building
    :param building: Object.- Building instance
    """

    alarma = Alarms.objects.filter(
        consumer_unit__building__pk=id_bld,
        status=True).values(
            "pk",
            "consumer_unit__building__building_name",
            "electric_parameter__name",
            "consumer_unit__electric_device_type__electric_device_type_name",
            "consumer_unit__profile_powermeter__powermeter__powermeter_anotation")
    serie = []
    for res in alarma:
        serie.append(dict(
            param=res['electric_parameter__name'],
            id=res['pk'],
            device=res['consumer_unit__electric_device_type__electric_device_type_name'],
            pm=res['consumer_unit__profile_powermeter__powermeter__powermeter_anotation'],
            edificio=res['consumer_unit__building__building_name']))
    return serie










