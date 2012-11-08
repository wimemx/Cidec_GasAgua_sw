from data_warehouse.models import *
from django.contrib import admin

admin.site.register(FiveMinuteInstant)
admin.site.register(FiveMinuteInterval)
admin.site.register(HourInstant)
admin.site.register(HourInterval)
admin.site.register(DayInstant)
admin.site.register(DayInterval)
admin.site.register(WeekInstant)
admin.site.register(WeekInterval)
admin.site.register(ConsumerUnit)
admin.site.register(ConsumerUnitFiveMinuteElectricData)
admin.site.register(ConsumerUnitFiveMIntElectricData)
admin.site.register(ConsumerUnitHourElectricData)
admin.site.register(ConsumerUnitHourIntElectricData)
admin.site.register(ConsumerUnitDayElectricData)
admin.site.register(ConsumerUnitDayIntElectricData)
admin.site.register(ConsumerUnitWeekElectricData)
admin.site.register(ConsumerUnitWeekIntElectricData)
