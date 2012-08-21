# -*- coding: utf-8 -*-
from django.db import models
import datetime
from location.models import Pais, Estado, Municipio, Colonia, Calle, Region
from electric_rates.models import ElectricRates, ElectricRatesPeriods

STATUS = (
    (1,'Activo'),
    (0,'Inactivo'),
    (2,'Eliminado')
    )

class SectoralType(models.Model):
    """ Sector Type Catalog

    Es un catalogo en el que se almacenaran los diferentes tipos de sectores
    (ramos) que pueden pertenecer los diferentes clustets.
    Por ejemplo: industrial, comercial y de infraestructura y construccion.

    """
    sectorial_type_name = models.CharField("Nombre de Sector", max_length="80")
    sectoral_type_description = models.TextField(u"Descripción", max_length=256, null=True, blank=True)
    sectoral_type_status = models.IntegerField("Estatus", choices=STATUS, default=1)
    sectoral_type_sequence = models.IntegerField("Secuencia", null=True, blank=True)

    def __unicode__(self):
        return self.sectorial_type_name
    @staticmethod
    def autocomplete_search_fields():
        return "id__iexact", "sectorial_type_name__icontains"
    class Meta:
        ordering = ['sectoral_type_sequence', 'sectorial_type_name']

class Cluster(models.Model):
    """ Catalogo de Clusters

    Es un catalogo en el que se almacenaran los diferentes clusters en los que
    pueden estar agrupadas las empresas. Por ejemplo:
    - Grupo Condumex
    - Grupo Sanborns

    """
    sectoral_type = models.ForeignKey(SectoralType, on_delete=models.PROTECT)
    cluster_registered = models.DateTimeField(default=datetime.datetime.now())
    cluster_status = models.IntegerField(choices=STATUS, default=1)
    cluster_name = models.CharField(max_length=128)
    cluster_image = models.CharField(max_length=200, null=True, blank=True)

    def __unicode__(self):
        return self.cluster_name + " - " + self.sectoral_type.sectorial_type_name
    @staticmethod
    def autocomplete_search_fields():
        return "id__iexact", "cluster_name_name__icontains"

class Company(models.Model):
    """ Almacena la informacion de perfil de una empresa"""
    sectoral_type = models.ForeignKey(SectoralType, on_delete=models.PROTECT)
    company_registered = models.DateTimeField(default=datetime.datetime.now())
    company_status = models.IntegerField(choices=STATUS, default=1)
    company_name = models.CharField(max_length=128)
    company_description = models.TextField(max_length=256, null=True, blank=True)

    def __unicode__(self):
        return self.company_name + " - " + self.sectoral_type.sectorial_type_name

class ClusterCompany(models.Model):
    """Agrupa el conjunto de empresas que agrupa el cluster"""
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)

    def __unicode__(self):
        return self.cluster.cluster_name + " - " + self.company.company_name
    class Meta:
        unique_together = ('cluster', 'company')

class ConfigurationTemplateCompany(models.Model):
    """ Configuracion del template del perfil de la empresa

    Almacena la configuracion de templares que permitan personalizar el look
    and feel del sistema dependiendo de la empresa.

    """
    company = models.OneToOneField(Company, on_delete=models.PROTECT)
    logo = models.CharField(max_length=200, null=True, blank=True)
    header_text_color = models.CharField(max_length=6, null=True, blank=True)
    header_background_color = models.CharField(max_length=6, null=True, blank=True)
    header_text = models.CharField(max_length=200, null=True, blank=True)
    mainbody_text_color = models.CharField(max_length=6, null=True, blank=True)
    mainbody_background_color = models.CharField(max_length=6, null=True, blank=True)
    footer_text_color = models.CharField(max_length=6, null=True, blank=True)
    footer_background_color = models.CharField(max_length=6, null=True, blank=True)
    footer_text = models.CharField(max_length=200, null=True, blank=True)

    def __unicode__(self):
        return "Template of" + " " + self.company.company_name

class BuildingAttributesType(models.Model):
    """ Tipos de atributos para edificios

    Es un catalogo en el que se almacenaran los diferente tipos de
    atributos extendidos.
    Es decir, es un clasificador de atributos extensibles de un edificio
    o parte de un edificio.
    Por ejemplo, Atributos de Productividad, Atributos de Habitabilidad,
    Atributos de Equipamiento, entre otros.

    """
    building_attributes_type_name = models.CharField(max_length=128)
    building_attributes_type_description = models.TextField(max_length=256, null=True, blank=True)
    building_attributes_type_sequence = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return self.building_attributes_type_name
    class Meta:
        ordering = ['building_attributes_type_sequence', 'building_attributes_type_name']

class BuildingAttributes(models.Model):
    """ Atributos de Edificios

    Es un catalogo en el que se almacenaran los diferentes atributos
    que pueden ser clasificadas en el catalogo building_attributes_type y
    que pueden ser atributos extendidos de un edificio o parte de un edificio.
    Ejemplo: numero de operaciones diarias, numero de personas que operan
    en el edificio, entre otros.

    """
    building_attributes_type = models.ForeignKey(BuildingAttributesType, on_delete=models.PROTECT)
    building_attributes_name = models.CharField(max_length=128)
    building_attributes_description = models.TextField(max_length=256, null=True, blank=True)
    building_attributes_value_boolean = models.BooleanField(default=False)
    building_attributes_units_of_measurement = models.CharField(max_length=10)
    building_attributes_sequence = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return self.building_attributes_name
    class Meta:
        ordering = ['building_attributes_sequence', 'building_attributes_name']


class Building(models.Model):
    """ Edificios

    Almacena la informacion del perfil basico de un edificio, es decir,
    un espacios fisicos en el que se encuentra la empresa.
    Una empresa puede estar operando en diferentes espacios fisicos.

    """
    building_registered = models.DateTimeField("Registrado:", default=datetime.datetime.now())
    building_status = models.IntegerField("Estatus:", choices=STATUS, default=1)
    building_name = models.CharField("Nombre:", max_length=128)
    building_description = models.TextField("Descripcion", max_length=256, null=True, blank=True)
    building_formatted_address = models.TextField("Direccion:", max_length=256)
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT)
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT)
    colonia = models.ForeignKey(Colonia, on_delete=models.PROTECT)
    calle = models.ForeignKey(Calle, on_delete=models.PROTECT)
    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    building_external_number = models.CharField("No. Exterior", max_length=10)
    building_internal_number = models.CharField("No. Interior", max_length=10, null=True, blank=True)
    building_code_zone = models.CharField("C.P.:", max_length=5)
    building_long_address = models.DecimalField("Longitud", max_digits=10, decimal_places=6)
    building_lat_address = models.DecimalField("Latitud", max_digits=10, decimal_places=6)
    electric_rate = models.ForeignKey(ElectricRates, on_delete=models.PROTECT, verbose_name=u"Tarifa Eléctrica")
    mts2_built = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    def __unicode__(self):
        return self.building_name + " - " + self.building_formatted_address

class BuildingAttributesForBuilding(models.Model):
    """Asocia el conjunto de atributos extendidos de un edificio."""
    building = models.ForeignKey(Building, on_delete=models.PROTECT)
    building_attributes = models.ForeignKey(BuildingAttributes, on_delete=models.PROTECT)
    building_attributes_value = models.DecimalField(max_digits=11, decimal_places=2)

    def __unicode__(self):
        return self.building.building_name + " - " + str(self.building_attributes_value)\
        + self.building_attributes.building_attributes_name
    class Meta:
        unique_together = ('building', 'building_attributes')

class PowermeterModel(models.Model):
    """ Modelos de medidores

    Almacena todas las marcas y modelos posibles para los medidores
    que seran usados en la medicion.

    """
    powermeter_brand = models.CharField(max_length=128)
    powermeter_model = models.CharField(max_length=128)

    def __unicode__(self):
        return self.powermeter_brand + " " + self.powermeter_model

class Powermeter(models.Model):
    """ Medidores

    Almacena todos los medidores que se encuentran registrados e instalados en el sistema.

    """
    powermeter_model = models.ForeignKey(PowermeterModel, on_delete=models.PROTECT)
    powermeter_anotation = models.CharField(max_length=256)
    powermeter_installation_date = models.DateField(default=datetime.datetime.now())
    powermeter_serial = models.CharField(max_length=128)
    status = models.IntegerField("Estatus", choices=STATUS, default=1)

    def __unicode__(self):
        return self.powermeter_anotation

class ProfilePowermeter(models.Model):
    """ Medidores para mediciones

    Asocia los medidores instalados con un perfil para su manejo interno en el sistema

    """
    powermeter = models.OneToOneField(Powermeter, on_delete=models.PROTECT)
    profile_powermeter_status = models.IntegerField(choices=STATUS, default=1)

    def __unicode__(self):
        return self.powermeter.powermeter_anotation


class ElectricDeviceType(models.Model):
    """Dispositivos electricos

    Es un catalogo en el que se almacenaran los diferentes tipos de dispositivos
    o sistemas electricos a los que se conecta un powermeter para obtener
    parametros electricos que consume.
    Estos pueden ser: Sistema de Iluminacion, Aire Acondicionado,
    Sistema de Calefaccion, entre otros

    """
    electric_device_type_name = models.TextField(max_length=64)
    electric_device_type_description = models.TextField(max_length=256, null=True, blank=True)
    electric_device_type_status = models.IntegerField(choices=STATUS, default=1)
    electric_device_type_sequence = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return self.electric_device_type_name
    class Meta:
        ordering = ['electric_device_type_sequence', 'electric_device_type_name']

class PartOfBuildingType(models.Model):
    """ Espacios en edificios

    Es un catalogo en el que se almacenaran los diferentes tipos
    de partes de espacios fisicos que conforman un building.
    Estos tipos pueden ser: Niveles, Zonas, Site, Cuarto, Bodega, ente otros.

    """
    part_of_building_type_name = models.TextField(max_length=64)
    part_of_building_type_description = models.TextField(max_length=256, null=True, blank=True)
    part_of_building_type_status = models.IntegerField(choices=STATUS, default=1)
    part_of_building_type_sequence = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return self.part_of_building_type_name
    class Meta:
        ordering = ['part_of_building_type_sequence', 'part_of_building_type_name']

class BuildingType(models.Model):
    """ Tipos de Edificios

    Es un catalogo en el que se almacenaran los diferentes tipos de
    edificios/centros/unidad de negocio/sede/oficina/entre otros espacios
    fisicos que pueden ser un building.
    Por ejemplo: centro de capacitacion, oficina de ventas,

    """
    building_type_name = models.TextField(max_length=64)
    building_type_description = models.TextField(max_length=256, null=True, blank=True)
    building_type_status = models.IntegerField(choices=STATUS, default=1)
    building_type_sequence = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return self.building_type_name
    class Meta:
        ordering = ['building_type_sequence', 'building_type_name']

class BuildingTypeForBuilding(models.Model):
    """ Asociacion entre buildings y sus tipos

    Asocio el conjunto de tipos de edificio/centro/unidad de
    negocio/centro de entrenamiento/entre otros tipos que tiene
    asociado un edificio.
    Es posible que UN edificio pueda tener mas de un tipo.
    Ejemplo: Condumex en 5 de Febrero tiene un centro de capacitacion,
    oficina de ventas, centro de desarrollo, entre otros tipos de uso.

    """
    building = models.ForeignKey(Building, on_delete=models.PROTECT)
    building_type = models.ForeignKey(BuildingType, on_delete=models.PROTECT)
    building_type_for_building_name = models.CharField(max_length=128)
    building_type_for_building_description = models.TextField(max_length=256, null=True, blank=True)

    def __unicode__(self):
        return self.building.building_name + " - " + self.building_type.building_type_name

class PartOfBuilding(models.Model):
    """ Una seccion de un edificio

    Almacena la informacion del perfil basico de una parte de un edificio.
    Es decir, un edificio puede estar compuesto de partes.
    Estas pueden ser: niveles, zonas, entre otra demarcacion fisica que compone un edificio.

    """
    building = models.ForeignKey(Building, on_delete=models.PROTECT)
    part_of_building_type = models.ForeignKey(PartOfBuildingType, on_delete=models.PROTECT, null=True, blank=True)
    part_of_building_name = models.CharField(max_length=128)
    part_of_building_description = models.TextField(max_length=256, null=True, blank=True)
    mts2_built = models.DecimalField(max_digits=6, decimal_places=2)

    def __unicode__(self):
        return self.building.building_name + " - " + self.part_of_building_name

class HierarchyOfPart(models.Model):
    """ Gerarquia de parte

    Almacena la informacion del perfil basico de un edificio/centro/unidad
    de negocio/sede/oficina/entre otros espacios fisicos.
    Una empresa puede estar operando en diferentes espacios fisicos.

    """
    part_of_building_composite = models.ForeignKey(PartOfBuilding,
        on_delete=models.PROTECT, related_name="hyerarchy_of_part_composite")
    part_of_building_leaf = models.ForeignKey(PartOfBuilding,
        on_delete=models.PROTECT, related_name="hyerarchy_of_part_leaf")

    def __unicode__(self):
        return self.part_of_building_composite.building.building_name +\
               " > " +self.part_of_building_leaf.building.building_name

class CompanyBuilding(models.Model):
    """ Agrupa el conjunto de edificios que pertenecen a una empresa """
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    building = models.ForeignKey(Building, on_delete=models.PROTECT)

    def __unicode__(self):
        return self.company.company_name + " - " + self.building.building_name
    class Meta:
        unique_together = ('company', 'building')

class BuilAttrsForPartOfBuil(models.Model):
    """Asocia el conjunto de atributos extendidos de una parte de un edificio."""
    part_of_building = models.ForeignKey(PartOfBuilding, on_delete=models.PROTECT)
    building_attributes = models.ForeignKey(BuildingAttributes, on_delete=models.PROTECT)
    building_attributes_value = models.DecimalField(max_digits=12, decimal_places=6)

    def __unicode__(self):
        return self.part_of_building.part_of_building_name + " - " +\
               self.building_attributes.building_attributes_name


class ConsumerUnit(models.Model):
    """ Unidades de consumo

    Una unidad de consumo integra la identificacion del medidor que obtiene
    parametros electricos;
    el dispositivo electrico al que esta conectado un medidor y
    el edificio y/o parte del edificio en el que se encuentra.

    """
    building = models.ForeignKey(Building, on_delete=models.PROTECT)
    part_of_building = models.ForeignKey(PartOfBuilding, on_delete=models.PROTECT, null=True, blank=True)
    electric_device_type = models.ForeignKey(ElectricDeviceType, on_delete=models.PROTECT)
    profile_powermeter = models.OneToOneField(ProfilePowermeter, on_delete=models.PROTECT)

    def __unicode__(self):
        return self.building.building_name + " - " +\
               self.electric_device_type.electric_device_type_name + " - " +\
               self.profile_powermeter.powermeter.powermeter_anotation
    class Meta:
        unique_together = ('building', 'profile_powermeter')

class ElectricData(models.Model):
    """ Historico de datos electricos

    Almacena los datos historicos de las mediciones electricas de un medidor segun su id interno

    """
    profile_powermeter = models.ForeignKey(ProfilePowermeter, on_delete=models.PROTECT, null=True, blank=True)
    powermeter_serial = models.CharField(max_length=128)
    medition_date = models.DateTimeField(default=datetime.datetime.now())
    V1 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    V2 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    V3 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    I1 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    I2 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    I3 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kWL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kWL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kWL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvarL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvarL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvarL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kVAL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kVAL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kVAL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    PFL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    PFL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    PFL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kW = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvar = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kVA = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    PF = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    In = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    FREQ = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kWIMPSDMAX = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kWIMPACCDMD = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kVASDMAX = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kVAACCDMD = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    I1DMDMAX = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    I2DMDMAX = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    I3DMDMAX = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kWhIMPORT = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kWhEXPORT = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvarhNET = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    kvarhIMPORT = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    V1THD = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    V2THD = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    V3THD = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    I1THD = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    I2THD = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    I3THD = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    def __unicode__(self):
        return self.profile_powermeter.powermeter.powermeter_anotation + \
               " " + str(self.medition_date)

class ElectricRateForElectricData(models.Model):
    electric_rates_periods = models.ForeignKey(ElectricRatesPeriods, on_delete=models.PROTECT)
    electric_data = models.ForeignKey(ElectricData, on_delete=models.PROTECT)
    identifier = models.CharField(max_length=128)

    class META:
        unique_together=('electric_rates_periods','electric_data')

class IndustrialEquipment(models.Model):
    """

    Almacena los equipos industriales (computadoras a las que se conectan los medidores electricos)

    """
    indistrial_equipment_identifier = models.CharField(max_length=128)
    description = models.TextField(max_length=256, null=True, blank=True)

class PowermeterForIndustrialEquipment(models.Model):
    """

    Asocia los medidores instalados con un perfil para su manejo interno en el sistema

    """
    powermeter = models.ForeignKey(Powermeter, on_delete=models.PROTECT)
    industrial_equipment = models.ForeignKey(IndustrialEquipment, on_delete=models.PROTECT)
    def __unicode__(self):
        return self.powermeter.powermeter_anotation + " - " + \
               self.industrial_equipment.indistrial_equipment_identifier
    class Meta:
        unique_together = ('powermeter', 'industrial_equipment')