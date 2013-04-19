#coding:utf-8

# Django imports
import django.contrib.admin
from django.contrib import admin

# Data Warehouse Extended imports
import data_warehouse_extended.models


class C_U_Instant_ED_Admin(admin.ModelAdmin):
    list_filter = ['consumer_unit_profile__building_name',
                   'consumer_unit_profile__electric_device_type_name',
                   'electrical_parameter']

django.contrib.admin.site.register(
    data_warehouse_extended.models.ConsumerUnitInstantElectricalData,
    C_U_Instant_ED_Admin)

django.contrib.admin.site.register(
    data_warehouse_extended.models.ConsumerUnitProfile)

django.contrib.admin.site.register(
    data_warehouse_extended.models.ElectricalParameter)

django.contrib.admin.site.register(data_warehouse_extended.models.Instant)
django.contrib.admin.site.register(data_warehouse_extended.models.InstantDelta)