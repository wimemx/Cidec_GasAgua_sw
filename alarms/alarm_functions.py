__author__ = 'wime'
import json

from alarms.models import Alarms
from c_center.models import IndustrialEquipment, Building


def set_alarm_json(building, user):
    """ Generate and save a JSON containing the whole alarm configuration for
    a buildinf
    :param building: Object.- Building instance
    :param user: Object.- django.contrib.auth.models.User instance
    """
    b_alarms = Alarms.objects.filter(consumer_unit__building=building)
    alarm_arr = []
    for ba in b_alarms:
        status = "true" if ba.status else "false"
        min_value = 0 if not ba.min_value else float(str(ba.min_value))
        max_value = 0 if not ba.max_value else float(str(ba.max_value))
        alarm_arr.append(
            dict(alarm_identifier=ba.alarm_identifier,
                 electric_parameter_id=ba.electric_parameter.pk,
                 min_value=min_value,
                 max_value=max_value,
                 status=status
            ))
    i_eq = IndustrialEquipment.objects.get(building=building)
    i_eq.has_new_alarm_config = True
    i_eq.new_alarm_config = json.dumps(alarm_arr)
    i_eq.modified_by = user
    i_eq.save()