"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase
from gas_agua.models import WaterGasData
from c_center.models import IndustrialEquipment
import random
import datetime
from datetime import timedelta
class SimpleTest(TestCase):
    def test_basic_addition(self):
        """
        Tests that 1 + 1 always equals 2.
        """
        self.assertEqual(1 + 1, 2)


def Insert_water_gas():

    block = [];
    medition_date = datetime.datetime(2013,6,1,00,00,00)
    serials = ['11453', '18464', '73784', '187463']
    ie = IndustrialEquipment.objects.get(pk=5)
    gas_total = 0
    for i in range(0,26010):
        dec = random.randint(0,6)
        if dec == 2 or dec == 5:
            gas_entered = random.randint(200,400)
            gas_consumed = random.randint(0,30)
            gas_total = gas_total + gas_consumed
            serial_gas = random.randint(0,3)
            b = WaterGasData(industrial_equipment=ie,gas_entered=gas_entered,gas_entered_serial=serials[serial_gas],gas_consumed=gas_total,gas_consumed_serial=serials[serial_gas],
                         water_entered=gas_entered,water_entered_serial=serials[serial_gas],water_consumed=gas_total,water_consumed_serial=serials[serial_gas],medition_date=medition_date)
            b.save()
            medition_date = medition_date + timedelta(minutes=5)
        else:
            gas_entered = random.randint(200,400)
            gas_consumed = random.randint(0,30)
            gas_total = gas_total + gas_consumed
            serial_gas = random.randint(0,3)
            b = WaterGasData(industrial_equipment=ie,gas_entered=gas_entered,gas_entered_serial=serials[serial_gas],gas_consumed=gas_total,gas_consumed_serial=serials[serial_gas],
                         water_entered=gas_entered,water_entered_serial=serials[serial_gas],water_consumed=gas_total,water_consumed_serial=serials[serial_gas],medition_date=medition_date)
            b.save()
            medition_date = medition_date + timedelta(minutes=5)
