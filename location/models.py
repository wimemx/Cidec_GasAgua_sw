from django.db import models

class Pais(models.Model):

    pais_name = models.CharField(max_length=128)
    def __unicode__(self):
        return self.pais_name
    class Meta:
        verbose_name_plural = "Paises"
class Estado(models.Model):

    estado_name = models.CharField(max_length=128)
    def __unicode__(self):
        return self.estado_name

class Municipio(models.Model):

    municipio_name = models.CharField(max_length=128)
    def __unicode__(self):
        return self.municipio_name

class Colonia(models.Model):

    colonia_name = models.CharField(max_length=128)
    def __unicode__(self):
        return self.colonia_name

class Calle(models.Model):

    calle_name = models.CharField(max_length=128)
    def __unicode__(self):
        return self.calle_name

class Region(models.Model):

    region_name = models.CharField(max_length=128)
    region_description = models.CharField(max_length=256)
    date = models.DateField()
    def __unicode__(self):
        return self.region_name

class PaisEstado(models.Model):

    pais = models.ForeignKey(Pais, on_delete=models.PROTECT)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT)
    def __unicode__(self):
        return self.pais.pais_name + " - " + self.estado.estado_name

    class Meta:
        unique_together = ('pais', 'estado')

class EstadoMunicipio(models.Model):
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT)
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT)
    def __unicode__(self):
        return self.estado.estado_name + " - " + self.municipio.municipio_name

    class Meta:
        unique_together = ('estado', 'municipio')

class MunicipioColonia(models.Model):
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT)
    colonia = models.ForeignKey(Colonia, on_delete=models.PROTECT)
    def __unicode__(self):
        return self.municipio.municipio_name + " - " + self.colonia.colonia_name

    class Meta:
        unique_together = ('municipio', 'colonia')

class ColoniaCalle(models.Model):
    colonia = models.ForeignKey(Colonia, on_delete=models.PROTECT)
    calle = models.ForeignKey(Calle, on_delete=models.PROTECT)
    def __unicode__(self):
        return self.colonia.colonia_name + " - " + self.calle.calle_name

    class Meta:
        unique_together = ('colonia', 'calle')

class RegionEstado(models.Model):
    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT)
    def __unicode__(self):
        return self.region.region_name + " - " + self.estado.estado_name

    class Meta:
        unique_together = ('region', 'estado')