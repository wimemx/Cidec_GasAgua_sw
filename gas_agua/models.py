from django.db import models
from c_center.models import IndustrialEquipment
import datetime
from django.contrib import admin
from django.core.exceptions import FieldError
from django.contrib import messages


class WaterGasData(models.Model):
    industrial_equipment = models.ForeignKey(IndustrialEquipment,
                                             on_delete=models.PROTECT)
    gas_entered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gas_entered_serial = models.CharField(max_length=10, default=0)
    gas_consumed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gas_consumed_serial = models.CharField(max_length=10, default=0)
    water_entered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    water_entered_serial = models.CharField(max_length=10, default=0)
    water_consumed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    water_consumed_serial = models.CharField(max_length=10, default=0)
    medition_date = models.DateTimeField(default=datetime.datetime.now())
    tank_gasoccupied = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    tank_wateroccupied = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    def __unicode__(self):
        return self.industrial_equipment.building.building_name

class WaterGasAdmin(admin.ModelAdmin):
    pass

admin.site.register(WaterGasData, WaterGasAdmin)

class WaterGasLoad(models.Model):
    industrial_equipment = models.ForeignKey(IndustrialEquipment,
                                             on_delete=models.PROTECT,
                                             unique=True)
    load_percent_gas = models.DecimalField(max_digits=5, decimal_places=2)
    load_percent_water = models.DecimalField(max_digits=5, decimal_places=2)
    medition_day = models.DateField()

    def __unicode__(self):
        return self.industrial_equipment.building.building_name + " - " + \
            str(self.medition_day)


class TankInfo(models.Model):
    industrial_equipment = models.ForeignKey(IndustrialEquipment,
                                             on_delete=models.PROTECT,
                                             unique=True)
    tank_capacity_gas = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    tank_initial_gas = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    tank_capacity_water = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    tank_initial_water = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    def save(self, *args, **kwargs):
        water_occupied = self.tank_initial_water
        gas_occupied = self.tank_initial_gas
        if self.tank_initial_gas:
            if self.tank_initial_gas > self.tank_capacity_gas:
                return False
        if self.tank_capacity_gas == 0:
            gas_occupied = None
        if self.tank_initial_water:
            if self.tank_initial_water > self.tank_capacity_water:
                return False
        if self.tank_capacity_water == 0:
            water_occupied = None
        check = WaterGasData.objects.filter(industrial_equipment=self.industrial_equipment)
        if not check:
            w = WaterGasData(industrial_equipment=self.industrial_equipment,
                             medition_date=datetime.datetime.now(),
                             tank_gasoccupied=gas_occupied,
                             tank_wateroccupied=water_occupied)
            w.save()
        super(TankInfo, self).save(*args, **kwargs)


class TankAdmin(admin.ModelAdmin):
    pass

admin.site.register(TankInfo, TankAdmin)