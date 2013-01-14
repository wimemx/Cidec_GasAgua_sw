import alarms.models
from django.contrib import admin

class AlarmEventsAdmin(admin.ModelAdmin):
    list_filter = ['alarm']
    list_display = ['alarm', 'triggered_time', 'value']
admin.site.register(alarms.models.AlarmEvents, AlarmEventsAdmin)

class AlarmsAdmin(admin.ModelAdmin):
    list_filter = ['alarm_identifier', 'electric_parameter',
                   'consumer_unit', 'status']
    list_display = ['alarm_identifier', 'consumer_unit',
                    'electric_parameter', 'max_value', 'min_value', 'status']
admin.site.register(alarms.models.Alarms, AlarmsAdmin)

admin.site.register(alarms.models.ElectricParameters)

class UserNotificationSettingsClass(admin.ModelAdmin):
    list_filter = ['user', 'notification_type', 'status']
    list_display = ['alarm', 'user', 'notification_type', 'status']
admin.site.register(alarms.models.UserNotificationSettings,
                    UserNotificationSettingsClass)

class UserNotificationSettingsClass(admin.ModelAdmin):
    list_filter = ['user', 'read']
    list_display = ['alarm_event', 'user', 'read']
admin.site.register(alarms.models.UserNotifications, UserNotificationSettingsClass)