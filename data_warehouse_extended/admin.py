#coding:utf-8

# Django imports
import django.contrib.admin

# Data Warehouse Extended imports
import data_warehouse_extended.models

django.contrib.admin.site.register(
    data_warehouse_extended.models.ConsumerUnitInstantElectricalData)

django.contrib.admin.site.register(
    data_warehouse_extended.models.ConsumerUnitProfile)

django.contrib.admin.site.register(
    data_warehouse_extended.models.ElectricalParameter)

django.contrib.admin.site.register(data_warehouse_extended.models.Instant)
django.contrib.admin.site.register(data_warehouse_extended.models.InstantDelta)