from django.db import models
from c_center.models import IndustrialEquipment


class WaterGasData(models.Model):
    industrial_equipment = models.ForeignKey(IndustrialEquipment,
                                             on_delete=models.PROTECT,
                                             unique=True)
    gas_entered = models.DecimalField(max_digits=12, decimal_places=2)
    gas_entered_serial = models.CharField(max_length=10)
    gas_consumed = models.DecimalField(max_digits=12, decimal_places=2)
    gas_consumed_serial = models.CharField(max_length=10)
    water_entered = models.DecimalField(max_digits=12, decimal_places=2)
    water_entered_serial = models.CharField(max_length=10)
    water_consumed = models.DecimalField(max_digits=12, decimal_places=2)
    water_consumed_serial = models.CharField(max_length=10)
    medition_date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.industrial_equipment.building.building_name


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