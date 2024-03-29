# -*- coding: utf-8 -*-
from django.db import models


class Timezones(models.Model):
    name = models.CharField(max_length=140)
    raw_offset = models.SmallIntegerField(max_length=2, default=-6)
    dst_offset = models.IntegerField(max_length=2, default=-5)
    longitude = models.DecimalField("Longitud", max_digits=10,
                                    decimal_places=6, default=0)
    latitude = models.DecimalField("Latitud", max_digits=10,
                                   decimal_places=6, default=0)

    zone_id = models.CharField(null=True, blank=True, max_length=32)

    def __unicode__(self):
        return self.name


class Pais(models.Model):
    pais_name = models.CharField(max_length=128)

    def __unicode__(self):
        return self.pais_name

    @staticmethod
    def autocomplete_search_fields():
        return "id__iexact", "pais_name__icontains"

    class Meta:
        verbose_name_plural = "Paises"


class Estado(models.Model):
    estado_name = models.CharField(max_length=128)

    def __unicode__(self):
        return self.estado_name

    @staticmethod
    def autocomplete_search_fields():
        return "id__iexact", "estado_name__icontains"


class Municipio(models.Model):
    municipio_name = models.CharField(max_length=128)
    border = models.BooleanField(default=False)

    def __unicode__(self):
        return self.municipio_name

    @staticmethod
    def autocomplete_search_fields():
        return "id__iexact", "municipio_name__icontains"


class Colonia(models.Model):
    colonia_name = models.CharField(max_length=128)

    def __unicode__(self):
        return self.colonia_name

    @staticmethod
    def autocomplete_search_fields():
        return "id__iexact", "colonia_name__icontains"


class Calle(models.Model):
    calle_name = models.CharField(max_length=128)

    def __unicode__(self):
        return self.calle_name

    @staticmethod
    def autocomplete_search_fields():
        return "id__iexact", "calle_name__icontains"


class Region(models.Model):
    region_name = models.CharField(max_length=128)
    region_description = models.TextField(blank=True, null=True)

    def __unicode__(self):
        return self.region_name

    @staticmethod
    def autocomplete_search_fields():
        return "id__iexact", "region_name__icontains"


class PaisEstado(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT, unique=True)

    def __unicode__(self):
        return self.pais.pais_name + " - " + self.estado.estado_name

    class Meta:
        unique_together = ('pais', 'estado')


class EstadoMunicipio(models.Model):
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT)
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT,
                                  unique=True)

    def __unicode__(self):
        return self.estado.estado_name + " - " + self.municipio.municipio_name

    class Meta:
        unique_together = ('estado', 'municipio')


class MunicipioColonia(models.Model):
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT)
    colonia = models.ForeignKey(Colonia, on_delete=models.PROTECT, unique=True)

    def __unicode__(self):
        return self.municipio.municipio_name + " - " + self.colonia.colonia_name

    class Meta:
        unique_together = ('municipio', 'colonia')


class ColoniaCalle(models.Model):
    colonia = models.ForeignKey(Colonia, on_delete=models.PROTECT)
    calle = models.ForeignKey(Calle, on_delete=models.PROTECT, unique=True)

    def __unicode__(self):
        return self.colonia.colonia_name + " - " + self.calle.calle_name

    class Meta:
        unique_together = ('colonia', 'calle')


class RegionEstado(models.Model):
    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT)
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT,
                                  blank=True, null=True)

    def __unicode__(self):
        return self.region.region_name + " - " + self.estado.estado_name

    class Meta:
        unique_together = ('region', 'estado', 'municipio')