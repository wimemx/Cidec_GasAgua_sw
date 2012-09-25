# -*- coding: utf-8 -*-

from django.db import models

##########################################################################################
#
# Data warehouse Time-Dimension tables
#
##########################################################################################

class FiveMinuteInstant(models.Model):

    instant_datetime = models.DateTimeField(primary_key=True,
                                            verbose_name=u"Instante de Tiempo")

    def __unicode__(self):

        return u"Intervalo de 5 minutos - Instante: " + str(self.instant_datatime)


class HourInstant(models.Model):

    instant_datetime = models.DateTimeField(primary_key=True,
                                            verbose_name=u"Instante de Tiempo")

    def __unicode__(self):

        return u"Intervalo de una hora - Instante: " + str(self.instant_datatime)


class DayInstant(models.Model):

    instant_datetime = models.DateTimeField(primary_key=True,
                                            verbose_name=u"Instante de Tiempo")

    def __unicode__(self):

        return u"Intervalo de una hora - Instante: " + str(self.instant_datatime)


class WeekInstant(models.Model):

    instant_datetime = models.DateTimeField(primary_key=True,
                                            verbose_name=u"Instante de Tiempo")

    def __unicode__(self):

        return u"Intervalo de una semana - Instante: " + str(self.instant_datatime)


class ConsumerUnit(models.Model):

    transactional_id = models.IntegerField(primary_key=True)
    building_name = models.CharField(max_length=128, verbose_name=u"Nombre de Edificio")
    part_of_building_name = models.CharField(max_length=128,
                                             null=True,
                                             blank=True,
                                             default=u"",
                                             verbose_name=u"Nombre de Parte del Edificio")

    electric_device_type_name = models.CharField(
                                    max_length=128,
                                    verbose_name=u"Nombre del Tipo de Dispositivo Electrico")

    def __unicode__(self):
        return self.building_name + u" - " + self.part_of_building_name + u" - " +\
               self.electric_device_type_name


##########################################################################################
#
# Data warehouse Facts tables
#
##########################################################################################

class ConsumerUnitFiveMinuteElectricData(models.Model):

    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    instant = models.ForeignKey(FiveMinuteInstant, on_delete=models.PROTECT)
    kW = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvar = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    PF = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kWhIMPORT = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvarhIMPORT = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)

    class Meta:

        unique_together = ("consumer_unit", "instant")

    def __unicode__(self):

        return self.building.building_name +\
               u" - " +\
               str(self.instant) +\
               u"\nkW = " +\
               str(kW) +\
               u"\nkvar = " +\
               str(kvar) +\
               u"\nPF = " +\
               str(PF)

class ConsumerUnitHourElectricData(models.Model):

    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    instant = models.ForeignKey(HourInstant, on_delete=models.PROTECT)
    kW = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvar = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    PF = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kWhIMPORT = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvarhIMPORT = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)

    class Meta:

        unique_together = ("consumer_unit", "instant")

    def __unicode__(self):

        return self.building.building_name +\
               u" - " +\
               str(self.instant) +\
               u"\nkW = " +\
               str(kW) +\
               u"\nkvar = " +\
               str(kvar) +\
               u"\nPF = " +\
               str(PF)


class ConsumerUnitDayElectricData(models.Model):

    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    instant = models.ForeignKey(DayInstant, on_delete=models.PROTECT)
    kW = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvar = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    PF = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kWhIMPORT = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvarhIMPORT = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)

    class Meta:

        unique_together = ("consumer_unit", "instant")

    def __unicode__(self):

        return self.building.building_name +\
               u" - " +\
               str(self.instant) +\
               u"\nkW = " +\
               str(kW) +\
               u"\nkvar = " +\
               str(kvar) +\
               u"\nPF = " +\
               str(PF)


class ConsumerUnitWeekElectricData(models.Model):

    consumer_unit = models.ForeignKey(ConsumerUnit, on_delete=models.PROTECT)
    instant = models.ForeignKey(WeekInstant, on_delete=models.PROTECT)
    kW = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvar = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    PF = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kWhIMPORT = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvarhIMPORT = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)

    class Meta:

        unique_together = ("consumer_unit", "instant")

    def __unicode__(self):

        return self.building.building_name +\
               u" - " +\
               str(self.instant) +\
               u"\nkW = " +\
               str(kW) +\
               u"\nkvar = " +\
               str(kvar) +\
               u"\nPF = " +\
               str(PF)