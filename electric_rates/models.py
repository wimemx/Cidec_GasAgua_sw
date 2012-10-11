# -*- coding: utf-8 -*-
from django.db import models
from location.models import Region
# Create your models here.

class ElectricRates(models.Model):
    """Catalogo de tarifas electricas"""
    electric_rate_name = models.CharField(max_length=128)
    description = models.CharField(max_length=256)

    def __unicode__(self):
        return self.electric_rate_name
    class Meta:
        verbose_name_plural = "Electric Rates"

class DateIntervals(models.Model):
    """ Intelvalo de Fechas de cobro

    Es un catalogo de fechas de inicio y finalizacion de periodos de cobro segun la CFE

    """
    interval_identifier = models.CharField("Identificador", max_length=128)
    date_init = models.DateField()
    date_end = models.DateField()
    electric_rate = models.ForeignKey(ElectricRates, on_delete=models.PROTECT, default=1)

    def __unicode__(self):
        return self.interval_identifier + "(" + str(self.date_init) + \
               "-" + str(self.date_end) + ")"
    class Meta:
        verbose_name_plural = "Date Intervals"

class Groupdays(models.Model):
    """ Agrupa los dias de la semana con fines tarifarios de la CFE """
    groupdays_identifier = models.CharField("Identificador", max_length=128)
    monday = models.BooleanField()
    tuesday = models.BooleanField()
    wednesday = models.BooleanField()
    thursday = models.BooleanField()
    friday = models.BooleanField()
    saturday = models.BooleanField()
    sunday = models.BooleanField()
    holydays = models.BooleanField()

    def  __unicode__(self):
        return self.groupdays_identifier
    class Meta:
        verbose_name_plural = "Group Days"

class Holydays(models.Model):
    """Almacena un listado de los dias festivos oficiales"""
    day = models.CharField("dia", max_length=64)
    month = models.IntegerField("mes")
    description = models.CharField(u"Descripción", max_length=128, blank=True, null=True)

    def __unicode__(self):
        return str(day) + "/" + str(month)
    class Meta:
        verbose_name_plural = "Holydays"


class ElectricRatesDetail(models.Model):
    """Cuotas aplicables a las tarifa por periodo"""
    electric_rate = models.ForeignKey(ElectricRates, on_delete=models.PROTECT)
    KDF = models.DecimalField("Cargo por kilowatt de demanda facturable", max_digits=12, decimal_places=6)
    KWHP = models.DecimalField(u"Cargo por kilowatt - hora de energía de punta", max_digits=12, decimal_places=6)
    KWHI = models.DecimalField(u"Cargo por kilowatt - hora de energía intermedia", max_digits=12, decimal_places=6)
    KWHB = models.DecimalField(u"Cargo por kilowatt - hora de energía de base", max_digits=12, decimal_places=6)
    FRI = models.DecimalField(max_digits=12, decimal_places=6)
    FRB = models.DecimalField(max_digits=12, decimal_places=6)
    KWDMM = models.DecimalField(u"Cargo por kilowatt de demanda máxima medida", max_digits=12, decimal_places=6)
    KWHEC = models.DecimalField(u"Cargo por kilowatt - hora de energía consumida", max_digits=12, decimal_places=6)
    date_init = models.DateField("Fecha de Inicio")
    date_end = models.DateField("Fecha de Fin")
    region = models.ForeignKey(Region, on_delete=models.PROTECT)

    def __unicode__(self):
        return "Cuota aplicable a la tarifa " + self.electric_rate.electric_rate_name + \
               " del " + str(self.date_init) + " al " + str(self.date_end)
    class Meta:
        verbose_name_plural = "Electric Rates Detail"

class ElectricRatesPeriods(models.Model):
    """ Agrupa las tarifas electricas segun su hora, fecha y region"""
    PERIODS = (
        ('base','Base'),
        ('intermedio','Intermedio'),
        ('punta','Punta')
        )

    electric_rate = models.ForeignKey(ElectricRates, on_delete=models.PROTECT, verbose_name=u"Tarifa Eléctrica")
    region = models.ForeignKey(Region, on_delete=models.PROTECT, null=True, blank=True)
    date_interval = models.ForeignKey(DateIntervals, on_delete=models.PROTECT, verbose_name="Periodo")
    groupdays = models.ForeignKey(Groupdays, on_delete=models.PROTECT, null=True, blank=True)
    time_init = models.TimeField("Hora de inicio", null=True, blank=True)
    time_end = models.TimeField("Hora Fin", null=True, blank=True)
    period_type = models.CharField("Tipo de periodo", max_length=10, choices=PERIODS, null=True, blank=True)

    def __unicode__(self):
        return self.electric_rate.electric_rate_name + " - " + \
               str(self.date_interval)
    class Meta:
        verbose_name_plural = "Electric Rates Periods"

class DACElectricRateDetail(models.Model):
    region = models.ForeignKey(Region, on_delete=models.PROTECT, null=True, blank=True)
    date_interval = models.ForeignKey(DateIntervals, on_delete=models.PROTECT, verbose_name="Periodo", null=True, blank=True)
    month_rate = models.DecimalField(u"Cargo mensual", max_digits=12, decimal_places=6)
    kwh_rate = models.DecimalField(u"Cargo por kilowatt - hora", max_digits=12, decimal_places=6)
    date_init = models.DateField("Fecha de Inicio")
    date_end = models.DateField("Fecha de Fin")

    def __unicode__(self):
        return "Cuota Aplicable para la region " + self.region.region_name +\
               " del " + str(self.date_init) + " al " + str(self.date_end)

    class Meta:
        verbose_name_plural = "Dac Electric Rate Detail"