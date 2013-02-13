# coding: utf-8
import django_tables2 as tables
from .models import ElectricDataTemp


class ElectricDataTempTable(tables.Table):
    profile_powermeter = tables.Column()
    medition_date = tables.Column()
    V1 = tables.Column(verbose_name="voltage 1")
    V2 = tables.Column()
    V3 = tables.Column()
    I1 = tables.Column()
    I2 = tables.Column()
    I3 = tables.Column()
    kWL1 = tables.Column()
    kWL2 = tables.Column()
    kWL3 = tables.Column()
    kvarL1 = tables.Column()
    kvarL2 = tables.Column()
    kvarL3 = tables.Column()
    kVAL1 = tables.Column()
    kVAL2 = tables.Column()
    kVAL3 = tables.Column()
    PFL1 = tables.Column()
    PFL2 = tables.Column()
    PFL3 = tables.Column()
    kW = tables.Column()
    kvar = tables.Column()
    TotalkVA = tables.Column()
    PF = tables.Column()
    FREQ = tables.Column()
    TotalkWhIMPORT = tables.Column()
    powermeter_serial = tables.Column()
    TotalkvarhIMPORT = tables.Column()
    kWhL1 = tables.Column()
    kWhL2 = tables.Column()
    kwhL3 = tables.Column()
    kvarhL1 = tables.Column()
    kvarhL2 = tables.Column()
    kvarhL3 = tables.Column()
    kVAhL1 = tables.Column()
    kVAhL2 = tables.Column()
    kVAhL3 = tables.Column()
    kW_import_sliding_window_demand = tables.Column()
    kvar_import_sliding_window_demand = tables.Column()
    kVA_sliding_window_demand = tables.Column()
    kvahTOTAL = tables.Column()

    class Meta:
        model = ElectricDataTemp

class ThemedElectricDataTempTable(ElectricDataTempTable):
    class Meta:
        attrs = {'class': 'paleblue'}