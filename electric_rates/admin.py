import electric_rates.models
from django.contrib import admin

admin.site.register(electric_rates.models.DateIntervals)
admin.site.register(electric_rates.models.Groupdays)
admin.site.register(electric_rates.models.Holydays)
admin.site.register(electric_rates.models.ElectricRates)
admin.site.register(electric_rates.models.ElectricRatesDetail)
admin.site.register(electric_rates.models.ElectricRatesPeriods)