from django.db import models
from c_center.models import ConsumerUnit
import django.contrib.auth.models


class ElectricParameters(models.Model):
    name = models.CharField(max_length=64)
    position = models.IntegerField()


class Alarms(models.Model):
    alarm_identifier = models.CharField(max_length=256)
    electric_parameter = models.ForeignKey(ElectricParameters,
                                           on_delete=models.PROTECT)
    max_value = models.DecimalField(blank=True, null=True, max_digits=20,
                                    decimal_places=6)
    min_value = models.DecimalField(blank=True, null=True, max_digits=20,
                                    decimal_places=6)
    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    last_changed = models.DateTimeField(auto_now=True)
    status = models.BooleanField(default=True)

    def __unicode__(self):
        return self.alarm_identifier + "-" +\
               self.consumer_unit.profile_powermeter.powermeter\
               .powermeter_anotation


class AlarmEvents(models.Model):
    alarm = models.ForeignKey(Alarms, on_delete=models.PROTECT)
    triggered_time = models.DateTimeField(auto_now=True)
    value = models.DecimalField(max_digits=20, decimal_places=6)

    def __unicode__(self):
        return  self.alarm.alarm_identifier + " - " + str(self.value) +\
                self.alarm.electric_parameter.name + " - " + str(
            self.triggered_time)


class UserNotificationSettings(models.Model):
    notification_types = (
        (1, "push"),
        (2, "sms"),
        (3, "email"),
        (4, "ninguno")
        )
    alarm = models.ForeignKey(Alarms, on_delete=models.PROTECT)
    user = models.ForeignKey(django.contrib.auth.models.User,
                             on_delete=models.PROTECT)
    notification_type = models.IntegerField(choices=notification_types)
    status = models.BooleanField(default=True)

    def __unicode__(self):
        return self.user.username + " - " + self.alarm.alarm_identifier + ": " \
                                                                          "" +\
               self.notification_types[self.notification_type][1]


class UserNotifications(models.Model):
    alarm_event = models.ForeignKey(AlarmEvents, on_delete=models.PROTECT)
    user = models.ForeignKey(django.contrib.auth.models.User,
                             on_delete=models.PROTECT)
    read = models.BooleanField(default=False)

    def __unicode__(self):
        return self.user.username + " - " + self.alarm_event.alarm.alarm_identifier