from data_warehouse.models import *
from django.contrib import admin

admin.site.register(FiveMinuteInstant)
admin.site.register(HourInstant)
admin.site.register(DayInstant)
admin.site.register(WeekInstant)
admin.site.register(ConsumerUnit)
admin.site.register(ConsumerUnitHourElectricData)
admin.site.register(ConsumerUnitDayElectricData)
admin.site.register(ConsumerUnitWeekElectricData)
