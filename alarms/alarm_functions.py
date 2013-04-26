__author__ = 'wime'
import json

from c_center.c_center_functions import get_c_unitsforbuilding_for_operation

from alarms.models import Alarms
from c_center.models import IndustrialEquipment, Building, ConsumerUnit
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
        cu_alarms = Alarms.objects.filter(consumer_unit=cu)

        for cua in cu_alarms:
            status = "true" if cua.status else "false"
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


def get_alarm_from_building(building):
    """ Return the alarm for the request building
    :param building: Object.- Building instance
    """

    alarma = Alarms.objects.filter(consumer_unit__building=building)










