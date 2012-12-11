# -*- coding: utf-8 -*-

#
# Django imports
#
from django.db import models

###############################################################################
#
# Data Warehouse Dimension Tables
#
###############################################################################

class FiveMinuteInstant(models.Model):
    instant_datetime = models.DateTimeField(primary_key=True,
                                            verbose_name=u"Instante de Tiempo")

    def __unicode__(self):
        return u"Instante: " + self.instant_datetime.strftime(u"%Y/%m/%d %H:%M")


class FiveMinuteInterval(models.Model):
    start_datetime = models.DateTimeField(verbose_name=u"Inicio del Intervalo")
    end_datetime = models.DateTimeField(verbose_name=u"Fin del Intervlo")

    class Meta:
        unique_together = ("start_datetime", "end_datetime")


    def __unicode__(self):
        return u"Intervalo: " + self.start_datetime.strftime(
            u"%Y/%m/%d %H:%M") + u" - " +\
               self.end_datetime.strftime(u"%Y/%m/%d %H:%M")


class HourInstant(models.Model):
    instant_datetime = models.DateTimeField(primary_key=True,
                                            verbose_name=u"Instante de Tiempo")

    def __unicode__(self):
        return u"Instante: " + self.instant_datetime.strftime(u"%Y/%m/%d %H:%M")


class HourInterval(models.Model):
    start_datetime = models.DateTimeField(verbose_name=u"Inicio del Intervalo")
    end_datetime = models.DateTimeField(verbose_name=u"Fin del Intervlo")

    class Meta:
        unique_together = ("start_datetime", "end_datetime")


    def __unicode__(self):
        return u"Intervalo: " + self.start_datetime.strftime(
            u"%Y/%m/%d %H:%M") + u" - " +\
               self.end_datetime.strftime(u"%Y/%m/%d %H:%M")


class DayInstant(models.Model):
    instant_datetime = models.DateTimeField(primary_key=True,
                                            verbose_name=u"Instante de Tiempo")

    def __unicode__(self):
        return u"Instante: " + self.instant_datetime.strftime(u"%Y/%m/%d %H:%M")


class DayInterval(models.Model):
    start_datetime = models.DateTimeField(verbose_name=u"Inicio del Intervalo")
    end_datetime = models.DateTimeField(verbose_name=u"Fin del Intervlo")

    class Meta:
        unique_together = ("start_datetime", "end_datetime")

    def __unicode__(self):
        return u"Intervalo: " + self.start_datetime.strftime(
            u"%Y/%m/%d %H:%M") + u" - " +\
               self.end_datetime.strftime(u"%Y/%m/%d %H:%M")


class WeekInstant(models.Model):
    instant_datetime = models.DateTimeField(primary_key=True,
                                            verbose_name=u"Instante de Tiempo")

    def __unicode__(self):
        return u"Instante: " + self.instant_datetime.strftime(u"%Y/%m/%d %H:%M")


class WeekInterval(models.Model):
    start_datetime = models.DateTimeField(verbose_name=u"Inicio del Intervalo")
    end_datetime = models.DateTimeField(verbose_name=u"Fin del Intervlo")

    class Meta:
        unique_together = ("start_datetime", "end_datetime")


    def __unicode__(self):
        return u"Intervalo: " + self.start_datetime.strftime(
            u"%Y/%m/%d %H:%M") + u" - " +\
               self.end_datetime.strftime(u"%Y/%m/%d %H:%M")


class ConsumerUnit(models.Model):
    transactional_id = models.IntegerField(primary_key=True)
    building_name = models.CharField(max_length=128,
                                     verbose_name=u"Nombre de Edificio")
    part_of_building_name = models.CharField(max_length=128,
                                             null=True,
                                             blank=True,
                                             default=u"",
                                             verbose_name=u"Nombre de Parte "
                                                          u"del Edificio")

    electric_device_type_name = models.CharField(
        max_length=128,
        verbose_name=u"Nombre del Tipo de Dispositivo Electrico")

    def __unicode__(self):
        return self.building_name + u" - " +\
               (
               self.part_of_building_name if self.part_of_building_name is
               not None else u"") +\
               u" - " + self.electric_device_type_name


###############################################################################
#
# Data Warehouse Facts Tables
#
###############################################################################

class ConsumerUnitFiveMinuteElectricData(models.Model):
    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    instant = models.ForeignKey(FiveMinuteInstant, on_delete=models.PROTECT)
    V1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    V2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    V3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    I1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    I2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    I3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    kWL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kWL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kWL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kvarL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kvarL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kvarL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kVAL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kVAL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kVAL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    PFL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    PFL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    PFL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kW = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    kvar = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    TotalkVA = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                   blank=True, default=None)
    PF = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    FREQ = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    TotalkWhIMPORT = models.DecimalField(max_digits=20, decimal_places=6,
                                         null=True, blank=True, default=None)
    TotalkvarhIMPORT = models.DecimalField(max_digits=20, decimal_places=6,
                                           null=True, blank=True, default=None)
    kWhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kWhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kwhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kvarhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=None)
    kvarhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=None)
    kvarhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=None)
    kVAhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kVAhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kVAhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kW_import_sliding_window_demand = models.DecimalField(max_digits=20,
                                                          decimal_places=6,
                                                          null=True, blank=True,
                                                          default=None)
    kvar_import_sliding_window_demand = models.DecimalField(max_digits=20,
                                                            decimal_places=6,
                                                            null=True,
                                                            blank=True,
                                                            default=None)
    kVA_sliding_window_demand = models.DecimalField(max_digits=20,
                                                    decimal_places=6, null=True,
                                                    blank=True, default=None)
    kvahTOTAL = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                    blank=True, default=None)

    class Meta:
        unique_together = ("consumer_unit", "instant")

    def __unicode__(self):
        return self.consumer_unit.__unicode__() +\
               u" -- " +\
               self.instant.__unicode__()


class ConsumerUnitFiveMIntElectricData(models.Model):
    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    interval = models.ForeignKey(FiveMinuteInterval, on_delete=models.PROTECT)
    kWh = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                              blank=True, default=None)
    kvarh = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kvah = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)

    class Meta:
        unique_together = ("consumer_unit", "interval")

    def __unicode__(self):
        return self.consumer_unit.__unicode__() +\
               u" -- " +\
               self.interval.__unicode__()


class ConsumerUnitHourElectricData(models.Model):
    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    instant = models.ForeignKey(HourInstant, on_delete=models.PROTECT)
    V1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    V2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    V3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    I1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    I2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    I3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    kWL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kWL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kWL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kvarL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kvarL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kvarL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kVAL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kVAL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kVAL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    PFL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    PFL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    PFL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kW = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    kvar = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    TotalkVA = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                   blank=True, default=None)
    PF = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    FREQ = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    TotalkWhIMPORT = models.DecimalField(max_digits=20, decimal_places=6,
                                         null=True, blank=True, default=None)
    TotalkvarhIMPORT = models.DecimalField(max_digits=20, decimal_places=6,
                                           null=True, blank=True, default=None)
    kWhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kWhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kwhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kvarhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=None)
    kvarhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=None)
    kvarhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=None)
    kVAhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kVAhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kVAhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kW_import_sliding_window_demand = models.DecimalField(max_digits=20,
                                                          decimal_places=6,
                                                          null=True, blank=True,
                                                          default=None)
    kvar_import_sliding_window_demand = models.DecimalField(max_digits=20,
                                                            decimal_places=6,
                                                            null=True,
                                                            blank=True,
                                                            default=None)
    kVA_sliding_window_demand = models.DecimalField(max_digits=20,
                                                    decimal_places=6, null=True,
                                                    blank=True, default=None)
    kvahTOTAL = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                    blank=True, default=None)

    class Meta:
        unique_together = ("consumer_unit", "instant")

    def __unicode__(self):
        return self.consumer_unit.__unicode__() +\
               u" -- " +\
               self.instant.__unicode__()


class ConsumerUnitHourIntElectricData(models.Model):
    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    interval = models.ForeignKey(HourInterval, on_delete=models.PROTECT)
    kWh = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                              blank=True, default=None)
    kvarh = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kvah = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)

    class Meta:
        unique_together = ("consumer_unit", "interval")

    def __unicode__(self):
        return self.consumer_unit.__unicode__() +\
               u" -- " +\
               self.interval.__unicode__()


class ConsumerUnitDayElectricData(models.Model):
    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    instant = models.ForeignKey(DayInstant, on_delete=models.PROTECT)
    V1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    V2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    V3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    I1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    I2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    I3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    kWL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kWL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kWL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kvarL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kvarL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kvarL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kVAL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kVAL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kVAL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    PFL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    PFL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    PFL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kW = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    kvar = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    TotalkVA = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                   blank=True, default=None)
    PF = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    FREQ = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    TotalkWhIMPORT = models.DecimalField(max_digits=20, decimal_places=6,
                                         null=True, blank=True, default=None)
    TotalkvarhIMPORT = models.DecimalField(max_digits=20, decimal_places=6,
                                           null=True, blank=True, default=None)
    kWhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kWhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kwhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kvarhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=None)
    kvarhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=None)
    kvarhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=None)
    kVAhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kVAhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kVAhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kW_import_sliding_window_demand = models.DecimalField(max_digits=20,
                                                          decimal_places=6,
                                                          null=True, blank=True,
                                                          default=None)
    kvar_import_sliding_window_demand = models.DecimalField(max_digits=20,
                                                            decimal_places=6,
                                                            null=True,
                                                            blank=True,
                                                            default=None)
    kVA_sliding_window_demand = models.DecimalField(max_digits=20,
                                                    decimal_places=6, null=True,
                                                    blank=True, default=None)
    kvahTOTAL = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                    blank=True, default=None)

    class Meta:
        unique_together = ("consumer_unit", "instant")

    def __unicode__(self):
        return self.consumer_unit.__unicode__() +\
               u" -- " +\
               self.instant.__unicode__()


class ConsumerUnitDayIntElectricData(models.Model):
    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    interval = models.ForeignKey(DayInterval, on_delete=models.PROTECT)
    kWh = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                              blank=True, default=None)
    kvarh = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kvah = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)

    class Meta:
        unique_together = ("consumer_unit", "interval")

    def __unicode__(self):
        return self.consumer_unit.__unicode__() +\
               u" -- " +\
               self.interval.__unicode__()


class ConsumerUnitWeekElectricData(models.Model):
    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    instant = models.ForeignKey(WeekInstant, on_delete=models.PROTECT)
    V1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    V2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    V3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    I1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    I2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    I3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    kWL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kWL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kWL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kvarL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kvarL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kvarL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kVAL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kVAL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kVAL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    PFL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    PFL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    PFL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    kW = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    kvar = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    TotalkVA = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                   blank=True, default=None)
    PF = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True, default=None)
    FREQ = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)
    TotalkWhIMPORT = models.DecimalField(max_digits=20, decimal_places=6,
                                         null=True, blank=True, default=None)
    TotalkvarhIMPORT = models.DecimalField(max_digits=20, decimal_places=6,
                                           null=True, blank=True, default=None)
    kWhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kWhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kwhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kvarhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=None)
    kvarhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=None)
    kvarhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=None)
    kVAhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kVAhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kVAhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=None)
    kW_import_sliding_window_demand = models.DecimalField(max_digits=20,
                                                          decimal_places=6,
                                                          null=True, blank=True,
                                                          default=None)
    kvar_import_sliding_window_demand = models.DecimalField(max_digits=20,
                                                            decimal_places=6,
                                                            null=True,
                                                            blank=True,
                                                            default=None)
    kVA_sliding_window_demand = models.DecimalField(max_digits=20,
                                                    decimal_places=6, null=True,
                                                    blank=True, default=None)
    kvahTOTAL = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                    blank=True, default=None)

    class Meta:
        unique_together = ("consumer_unit", "instant")

    def __unicode__(self):
        return self.consumer_unit.__unicode__() +\
               u" -- " +\
               self.instant.__unicode__()


class ConsumerUnitWeekIntElectricData(models.Model):
    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    interval = models.ForeignKey(WeekInterval, on_delete=models.PROTECT)
    kWh = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                              blank=True, default=None)
    kvarh = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=None)
    kvah = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True, default=None)

    class Meta:
        unique_together = ("consumer_unit", "interval")

    def __unicode__(self):
        return self.consumer_unit.__unicode__() +\
               u" -- " +\
               self.interval.__unicode__()