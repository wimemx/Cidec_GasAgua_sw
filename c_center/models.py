# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User
import datetime
import hashlib
import variety
from location.models import Pais, Estado, Municipio, Colonia, Calle, Region
from electric_rates.models import ElectricRates, ElectricRatesPeriods

STATUS = (
    (1, 'Activo'),
    (0, 'Inactivo'),
    (2, 'Eliminado')
)


class SectoralType(models.Model):
    """ Sector Type Catalog

    Es un catalogo en el que se almacenaran los diferentes tipos de sectores
    (ramos) que pueden pertenecer los diferentes clustets.
    Por ejemplo: industrial, comercial y de infraestructura y construccion.

    """
    sectorial_type_name = models.CharField("Nombre de Sector", max_length="80")
    sectoral_type_description = models.TextField(u"Descripción", max_length=256,
                                                 null=True, blank=True)
    sectoral_type_status = models.IntegerField("Estatus", choices=STATUS,
                                               default=1)
    sectoral_type_sequence = models.IntegerField("Secuencia", null=True,
                                                 blank=True)

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
    cluster_description = models.TextField(blank=True, null=True)
    cluster_image = models.CharField(max_length=200, null=True, blank=True)

    def __unicode__(self):
        return self.cluster_name + " - " + self.sectoral_type \
            .sectorial_type_name

    @staticmethod
    def autocomplete_search_fields():
        return "id__iexact", "cluster_name_name__icontains"


class Company(models.Model):
    """ Almacena la informacion de perfil de una empresa"""
    sectoral_type = models.ForeignKey(SectoralType, on_delete=models.PROTECT)
    company_registered = models.DateTimeField(default=datetime.datetime.now())
    company_status = models.IntegerField(choices=STATUS, default=1)
    company_name = models.CharField(max_length=128)
    company_description = models.TextField(max_length=256, null=True,
                                           blank=True)
    company_logo = models.ImageField(max_length=500, blank=True, null=True,
                                     upload_to="logotipos/")

    def __unicode__(self):
        return self.company_name + " - " + self.sectoral_type \
            .sectorial_type_name


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
    header_background_color = models.CharField(max_length=6, null=True,
                                               blank=True)
    header_text = models.CharField(max_length=200, null=True, blank=True)
    mainbody_text_color = models.CharField(max_length=6, null=True, blank=True)
    mainbody_background_color = models.CharField(max_length=6, null=True,
                                                 blank=True)
    footer_text_color = models.CharField(max_length=6, null=True, blank=True)
    footer_background_color = models.CharField(max_length=6, null=True,
                                               blank=True)
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
    building_attributes_type_description = models.TextField(max_length=256,
                                                            null=True,
                                                            blank=True)
    building_attributes_type_sequence = models.IntegerField(null=True,
                                                            blank=True)
    building_attributes_type_status = models.IntegerField("Estatus",
                                                          choices=STATUS,
                                                          default=1)

    def __unicode__(self):
        return self.building_attributes_type_name

    class Meta:
        ordering = ['building_attributes_type_sequence',
                    'building_attributes_type_name']


class BuildingAttributes(models.Model):
    """ Atributos de Edificios

    Es un catalogo en el que se almacenaran los diferentes atributos
    que pueden ser clasificadas en el catalogo building_attributes_type y
    que pueden ser atributos extendidos de un edificio o parte de un edificio.
    Ejemplo: numero de operaciones diarias, numero de personas que operan
    en el edificio, entre otros.

    """
    building_attributes_type = models.ForeignKey(BuildingAttributesType,
                                                 on_delete=models.PROTECT)
    building_attributes_name = models.CharField(max_length=128)
    building_attributes_description = models.TextField(max_length=256,
                                                       null=True, blank=True)
    building_attributes_value_boolean = models.BooleanField(default=False)
    building_attributes_units_of_measurement = models.CharField(max_length=80,
                                                                blank=True,
                                                                null=True,
                                                                default="")
    building_attributes_sequence = models.IntegerField(null=True, blank=True)
    building_attributes_status = models.BooleanField(default=True)

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
    building_registered = models.DateTimeField("Registrado:",
                                               default=datetime.datetime.now())
    building_status = models.IntegerField("Estatus:", choices=STATUS, default=1)
    building_name = models.CharField("Nombre:", max_length=128)
    building_description = models.TextField("Descripcion", max_length=256,
                                            null=True, blank=True)
    building_formatted_address = models.TextField("Direccion:", max_length=256)
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT)
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT)
    colonia = models.ForeignKey(Colonia, on_delete=models.PROTECT)
    calle = models.ForeignKey(Calle, on_delete=models.PROTECT)
    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    building_external_number = models.CharField("No. Exterior", max_length=10)
    building_internal_number = models.CharField("No. Interior", max_length=10,
                                                null=True, blank=True)
    building_code_zone = models.CharField("C.P.:", max_length=5)
    building_long_address = models.DecimalField("Longitud", max_digits=10,
                                                decimal_places=6)
    building_lat_address = models.DecimalField("Latitud", max_digits=10,
                                               decimal_places=6)
    electric_rate = models.ForeignKey(ElectricRates, on_delete=models.PROTECT,
                                      verbose_name=u"Tarifa Eléctrica")
    mts2_built = models.DecimalField(max_digits=6, decimal_places=2, null=True,
                                     blank=True)
    cutoff_day = models.IntegerField("Dia de Corte:", default=31)

    def __unicode__(self):
        return self.building_name + " - " + self.building_formatted_address


class BuildingAttributesForBuilding(models.Model):
    """Asocia el conjunto de atributos extendidos de un edificio."""
    building = models.ForeignKey(Building, on_delete=models.PROTECT)
    building_attributes = models.ForeignKey(BuildingAttributes,
                                            on_delete=models.PROTECT)
    building_attributes_value = models.DecimalField(max_digits=11,
                                                    decimal_places=2)

    def __unicode__(self):
        return self.building.building_name + " - " + str(
            self.building_attributes_value) \
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
    status = models.BooleanField(default=True)

    def __unicode__(self):
        return self.powermeter_brand + " " + self.powermeter_model


class Powermeter(models.Model):
    """ Medidores

    Almacena todos los medidores que se encuentran registrados e instalados
    en el sistema.

    """
    powermeter_model = models.ForeignKey(PowermeterModel,
                                         on_delete=models.PROTECT)
    powermeter_anotation = models.CharField(max_length=256)
    powermeter_installation_date = models.DateField(
        default=datetime.datetime.now())
    powermeter_serial = models.CharField(max_length=128)
    status = models.IntegerField("Estatus", choices=STATUS, default=1)

    def __unicode__(self):
        return self.powermeter_anotation


class ProfilePowermeter(models.Model):
    """ Medidores para mediciones

    Asocia los medidores instalados con un perfil para su manejo interno en
    el sistema

    """
    powermeter = models.OneToOneField(Powermeter, on_delete=models.PROTECT)
    profile_powermeter_status = models.IntegerField(choices=STATUS, default=1)
    read_time_rate = models.IntegerField(default=300)
    send_time_rate = models.IntegerField(default=300)
    initial_send_time = models.TimeField(auto_now_add=True)
    send_time_duration = models.IntegerField(default=300)
    realtime = models.BooleanField(default=False)
    identifier = models.TextField(max_length=50,
                                  default=hashlib.md5(
                                      variety.random_string_generator(30)
                                  ).hexdigest())

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
    electric_device_type_description = models.TextField(max_length=256,
                                                        null=True, blank=True)
    electric_device_type_status = models.IntegerField(choices=STATUS, default=1)
    electric_device_type_sequence = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return self.electric_device_type_name

    class Meta:
        ordering = ['electric_device_type_sequence',
                    'electric_device_type_name']


class PartOfBuildingType(models.Model):
    """ Espacios en edificios

    Es un catalogo en el que se almacenaran los diferentes tipos
    de partes de espacios fisicos que conforman un building.
    Estos tipos pueden ser: Niveles, Zonas, Site, Cuarto, Bodega, ente otros.

    """
    part_of_building_type_name = models.TextField(max_length=64)
    part_of_building_type_description = models.TextField(max_length=256,
                                                         null=True, blank=True)
    part_of_building_type_status = models.IntegerField(choices=STATUS,
                                                       default=1)
    part_of_building_type_sequence = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return self.part_of_building_type_name

    class Meta:
        ordering = ['part_of_building_type_sequence',
                    'part_of_building_type_name']


class BuildingType(models.Model):
    """ Tipos de Edificios

    Es un catalogo en el que se almacenaran los diferentes tipos de
    edificios/centros/unidad de negocio/sede/oficina/entre otros espacios
    fisicos que pueden ser un building.
    Por ejemplo: centro de capacitacion, oficina de ventas,

    """
    building_type_name = models.TextField(max_length=64)
    building_type_description = models.TextField(max_length=256, null=True,
                                                 blank=True)
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
    building_type_for_building_description = models.TextField(max_length=256,
                                                              null=True,
                                                              blank=True)

    def __unicode__(self):
        return self.building.building_name + " - " + self.building_type \
            .building_type_name


class PartOfBuilding(models.Model):
    """ Una seccion de un edificio

    Almacena la informacion del perfil basico de una parte de un edificio.
    Es decir, un edificio puede estar compuesto de partes.
    Estas pueden ser: niveles, zonas, entre otra demarcacion fisica que
    compone un edificio.

    """
    building = models.ForeignKey(Building, on_delete=models.PROTECT)
    part_of_building_type = models.ForeignKey(PartOfBuildingType,
                                              on_delete=models.PROTECT,
                                              null=True, blank=True)
    part_of_building_name = models.CharField(max_length=128)
    part_of_building_description = models.TextField(max_length=256, null=True,
                                                    blank=True)
    mts2_built = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    part_of_building_status = models.BooleanField(default=True)

    def __unicode__(self):
        return self.building.building_name + " - " + self.part_of_building_name


class CompanyBuilding(models.Model):
    """ Agrupa el conjunto de edificios que pertenecen a una empresa """
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    building = models.ForeignKey(Building, on_delete=models.PROTECT)

    def __unicode__(self):
        return self.company.company_name + " - " + self.building.building_name

    class Meta:
        unique_together = ('company', 'building')


class BuilAttrsForPartOfBuil(models.Model):
    """Asocia el conjunto de atributos extendidos de una parte de un edificio
    ."""
    part_of_building = models.ForeignKey(PartOfBuilding,
                                         on_delete=models.PROTECT)
    building_attributes = models.ForeignKey(BuildingAttributes,
                                            on_delete=models.PROTECT)
    building_attributes_value = models.DecimalField(max_digits=12,
                                                    decimal_places=6)

    def __unicode__(self):
        return self.part_of_building.part_of_building_name + " - " + \
               self.building_attributes.building_attributes_name


class ConsumerUnit(models.Model):
    """ Unidades de consumo

    Una unidad de consumo integra la identificacion del medidor que obtiene
    parametros electricos;
    el dispositivo electrico al que esta conectado un medidor y
    el edificio y/o parte del edificio en el que se encuentra.

    """
    building = models.ForeignKey(Building, on_delete=models.PROTECT)
    part_of_building = models.ForeignKey(PartOfBuilding,
                                         on_delete=models.PROTECT, null=True,
                                         blank=True)
    electric_device_type = models.ForeignKey(ElectricDeviceType,
                                             on_delete=models.PROTECT)
    profile_powermeter = models.ForeignKey(ProfilePowermeter,
                                           on_delete=models.PROTECT)

    def __unicode__(self):
        return self.building.building_name + " - " + \
               self.electric_device_type.electric_device_type_name + " - " + \
               self.profile_powermeter.powermeter.powermeter_anotation


class HierarchyOfPart(models.Model):
    """ Gerarquia de parte

    Almacena la informacion del perfil basico de un edificio/centro/unidad
    de negocio/sede/oficina/entre otros espacios fisicos.
    Una empresa puede estar operando en diferentes espacios fisicos.

    """
    part_of_building_composite = models.ForeignKey(
        PartOfBuilding,
        on_delete=models.PROTECT,
        related_name="hyerarchy_of_part_composite",
        null=True,
        blank=True,
        default=None)
    part_of_building_leaf = models.ForeignKey(
        PartOfBuilding,
        on_delete=models.PROTECT,
        related_name="hyerarchy_of_part_leaf",
        null=True,
        blank=True,
        default=None)
    consumer_unit_composite = models.ForeignKey(
        ConsumerUnit,
        on_delete=models.PROTECT,
        related_name="consumer_unit_composite",
        null=True,
        blank=True,
        default=None)
    consumer_unit_leaf = models.ForeignKey(ConsumerUnit,
                                           on_delete=models.PROTECT,
                                           related_name="consumer_unit_leaf",
                                           null=True, blank=True,
                                           default=None)
    ExistsPowermeter = models.BooleanField()

    def __unicode__(self):
        if self.part_of_building_composite:
            s = self.part_of_building_composite.part_of_building_name
        else:
            s = self.consumer_unit_composite.electric_device_type.electric_device_type_name
        if self.part_of_building_leaf:
            t = self.part_of_building_leaf.part_of_building_name
        else:
            t = self.consumer_unit_leaf.electric_device_type.electric_device_type_name
        return s + " > " + t

    class Meta:
        unique_together = (
            'part_of_building_composite', 'part_of_building_leaf')


class ElectricData(models.Model):
    """ Historico de datos electricos

    Almacena los datos historicos de las mediciones electricas de un medidor
    segun su id interno

    """
    profile_powermeter = models.ForeignKey(ProfilePowermeter,
                                           on_delete=models.PROTECT, null=True,
                                           blank=True)
    powermeter_serial = models.CharField(max_length=128)
    medition_date = models.DateTimeField(default=datetime.datetime.now())
    V1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    V2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    V3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    I1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    I2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    I3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    kWL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    kWL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    kWL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    kvarL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True)
    kvarL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True)
    kvarL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True)
    kVAL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True)
    kVAL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True)
    kVAL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True)
    PFL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    PFL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    PFL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    kW = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    kvar = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    kVA = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                              blank=True)
    PF = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    FREQ = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    kWhIMPORT = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                    blank=True)
    kvahTOTAL = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                    blank=True)
    kvarhIMPORT = models.DecimalField(max_digits=20, decimal_places=6,
                                      null=True, blank=True)
    V1THD = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True)
    V2THD = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True)
    V3THD = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True)
    I1THD = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True)
    I2THD = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True)
    I3THD = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True)
    kWhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=0)
    kWhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=0)
    kwhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=0)
    kvarhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=0)
    kvarhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=0)
    kvarhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=0)
    kVAhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=0)
    kVAhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=0)
    kVAhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=0)
    kW_import_sliding_window_demand = models.DecimalField(max_digits=20,
                                                          decimal_places=6,
                                                          null=True, blank=True,
                                                          default=0)
    kvar_import_sliding_window_demand = models.DecimalField(max_digits=20,
                                                            decimal_places=6,
                                                            null=True,
                                                            blank=True,
                                                            default=0)
    kVA_sliding_window_demand = models.DecimalField(max_digits=20,
                                                    decimal_places=6, null=True,
                                                    blank=True, default=0)

    def __unicode__(self):
        return self.profile_powermeter.powermeter.powermeter_anotation + \
               " " + str(self.medition_date)


class ElectricDataTemp(models.Model):
    profile_powermeter = models.ForeignKey(ProfilePowermeter,
                                           on_delete=models.PROTECT, null=True,
                                           blank=True)

    medition_date = models.DateTimeField(default=datetime.datetime.now())
    V1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    V2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    V3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    I1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    I2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    I3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    kWL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    kWL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    kWL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    kvarL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True)
    kvarL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True)
    kvarL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True)
    kVAL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True)
    kVAL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True)
    kVAL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True)
    PFL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    PFL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    PFL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    kW = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    kvar = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    TotalkVA = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                   blank=True)
    PF = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                             blank=True)
    FREQ = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                               blank=True)
    TotalkWhIMPORT = models.DecimalField(max_digits=20, decimal_places=6,
                                         null=True,
                                         blank=True)
    powermeter_serial = models.CharField(max_length=128)
    TotalkvarhIMPORT = models.DecimalField(max_digits=20, decimal_places=6,
                                           null=True,
                                           blank=True)
    kWhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=0)
    kWhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=0)
    kwhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                blank=True, default=0)
    kvarhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=0)
    kvarhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=0)
    kvarhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                  blank=True, default=0)
    kVAhL1 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=0)
    kVAhL2 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=0)
    kVAhL3 = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                 blank=True, default=0)
    kW_import_sliding_window_demand = models.DecimalField(max_digits=20,
                                                          decimal_places=6,
                                                          null=True, blank=True,
                                                          default=0)
    kvar_import_sliding_window_demand = models.DecimalField(max_digits=20,
                                                            decimal_places=6,
                                                            null=True,
                                                            blank=True,
                                                            default=0)
    kVA_sliding_window_demand = models.DecimalField(max_digits=20,
                                                    decimal_places=6, null=True,
                                                    blank=True, default=0)
    kvahTOTAL = models.DecimalField(max_digits=20, decimal_places=6, null=True,
                                    blank=True)

    def __unicode__(self):
        return "\n" + self.profile_powermeter.powermeter.powermeter_anotation + \
               " " + str(self.medition_date) + "\nkWL1 = " + str(self.kWL1) + \
               "\nkWL2 = " + str(self.kWL2) + \
               "\nkWL3 = " + str(self.kWL3)

    class Meta:
        verbose_name = "Electric Data"


class ElectricRateForElectricData(models.Model):
    electric_rates_periods = models.ForeignKey(ElectricRatesPeriods,
                                               on_delete=models.PROTECT)
    electric_data = models.ForeignKey(ElectricDataTemp,
                                      on_delete=models.PROTECT)
    identifier = models.CharField(max_length=128)

    def __unicode__(self):
        return "Electric Data: " + str(self.electric_data.pk) + " " + \
               self.identifier + " - " + \
               self.electric_rates_periods.electric_rate.electric_rate_name

    class META:
        unique_together = ('electric_rates_periods', 'electric_data')


class ElectricDataTags(models.Model):
    electric_rates_periods = models.ForeignKey(ElectricRatesPeriods,
                                               on_delete=models.PROTECT)
    electric_data = models.ForeignKey(ElectricDataTemp,
                                      on_delete=models.PROTECT)
    identifier = models.IntegerField(default=1)

    def __unicode__(self):
        return "Electric Data: " + str(self.electric_data.pk) + " " +\
               str(self.identifier) + " - " +\
               self.electric_rates_periods.electric_rate.electric_rate_name

    class META:
        unique_together = ('electric_rates_periods', 'electric_data')


class IndustrialEquipment(models.Model):
    """

    Almacena los equipos industriales (computadoras a las que se conectan
    los medidores electricos)

    """
    alias = models.CharField(max_length=128)
    description = models.TextField(max_length=256, null=True, blank=True)
    monitor_time_rate = models.IntegerField(default=120)
    check_config_time_rate = models.IntegerField(default=120)
    has_new_config = models.BooleanField(default=False)
    new_config = models.TextField(blank=True, null=True)
    has_new_alarm_config = models.BooleanField(default=False)
    new_alarm_config = models.TextField(blank=True, null=True)
    server = models.CharField(max_length=256, blank=True, null=True)
    last_changed = models.DateTimeField(auto_now=True)
    realtime = models.BooleanField(default=False)
    status = models.BooleanField(default=True)
    building = models.OneToOneField(Building, on_delete=models.PROTECT)
    modified_by = models.ForeignKey(User, on_delete=models.PROTECT, default=1)

    def __unicode__(self):
        return self.alias


class PowermeterForIndustrialEquipment(models.Model):
    """

    Asocia los medidores instalados con un perfil para su manejo
    interno en el sistema

    """
    powermeter = models.ForeignKey(Powermeter, on_delete=models.PROTECT)
    industrial_equipment = models.ForeignKey(IndustrialEquipment,
                                             on_delete=models.PROTECT)

    def __unicode__(self):
        return self.powermeter.powermeter_anotation + " - " + \
               self.industrial_equipment.indistrial_equipment_identifier

    class Meta:
        unique_together = ('powermeter', 'industrial_equipment')


class MonthlyCutDates(models.Model):
    building = models.ForeignKey(Building, on_delete=models.PROTECT)
    billing_month = models.DateField("Fecha de Inicio")
    date_init = models.DateTimeField("Fecha de Inicio")
    date_end = models.DateTimeField("Fecha de Fin", null=True, blank=True)

    def __unicode__(self):
        return "Edificio: " + self.building.building_name + " - Mes:" + str(
            self.billing_month) + ": Del " + \
               str(self.date_init) + " al " + str(self.date_end)

    class Meta:
        verbose_name_plural = "Fechas Mensuales de Corte"


class HMHistoricData(models.Model):
    monthly_cut_dates = models.ForeignKey(MonthlyCutDates,
                                          on_delete=models.PROTECT)
    KWH_total = models.IntegerField(null=True, blank=True)
    KWH_base = models.IntegerField(null=True, blank=True)
    KWH_intermedio = models.IntegerField(null=True, blank=True)
    KWH_punta = models.IntegerField(null=True, blank=True)
    KW_base = models.IntegerField(null=True, blank=True)
    KW_punta = models.IntegerField(null=True, blank=True)
    KW_intermedio = models.IntegerField(null=True, blank=True)
    KVARH = models.IntegerField(null=True, blank=True)
    power_factor = models.DecimalField(max_digits=20, decimal_places=2,
                                       null=True, blank=True, default=0)
    charge_factor = models.DecimalField(max_digits=20, decimal_places=2,
                                        null=True, blank=True, default=0)
    billable_demand = models.IntegerField(null=True, blank=True)
    KWH_base_rate = models.DecimalField(max_digits=20, decimal_places=2,
                                        null=True, blank=True, default=0)
    KWH_intermedio_rate = models.DecimalField(max_digits=20, decimal_places=2,
                                              null=True, blank=True, default=0)
    KWH_punta_rate = models.DecimalField(max_digits=20, decimal_places=2,
                                         null=True, blank=True, default=0)
    billable_demand_rate = models.DecimalField(max_digits=20, decimal_places=2,
                                               null=True, blank=True, default=0)
    average_rate = models.DecimalField(max_digits=20, decimal_places=2,
                                       null=True, blank=True, default=0)
    energy_cost = models.DecimalField(max_digits=20, decimal_places=2,
                                      null=True, blank=True, default=0)
    billable_demand_cost = models.DecimalField(max_digits=20, decimal_places=2,
                                               null=True, blank=True, default=0)
    power_factor_bonification = models.DecimalField(max_digits=20,
                                                    decimal_places=2, null=True,
                                                    blank=True, default=0)
    subtotal = models.DecimalField(max_digits=20, decimal_places=2, null=True,
                                   blank=True, default=0)
    iva = models.DecimalField(max_digits=20, decimal_places=2, null=True,
                              blank=True, default=0)
    total = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    def __unicode__(self):
        return "Building: " + self.monthly_cut_dates.building.building_name + \
               " - Mes:" + str(self.monthly_cut_dates.billing_month)

    class Meta:
        verbose_name_plural = "Información Historica de Tarifa HM"


class DacHistoricData(models.Model):
    monthly_cut_dates = models.ForeignKey(MonthlyCutDates,
                                          on_delete=models.PROTECT)
    KWH_total = models.IntegerField(null=True, blank=True)
    KWH_rate = models.DecimalField(max_digits=20, decimal_places=2, null=True,
                                   blank=True, default=0)
    monthly_rate = models.DecimalField(max_digits=20, decimal_places=2,
                                       null=True, blank=True, default=0)
    average_rate = models.DecimalField(max_digits=20, decimal_places=2,
                                       null=True, blank=True, default=0)
    energy_cost = models.DecimalField(max_digits=20, decimal_places=2,
                                      null=True, blank=True, default=0)
    subtotal = models.DecimalField(max_digits=20, decimal_places=2, null=True,
                                   blank=True, default=0)
    iva = models.DecimalField(max_digits=20, decimal_places=2, null=True,
                              blank=True, default=0)
    total = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    def __unicode__(self):
        return "CU: " + self.consumer_unit + " - Mes:" + str(self.billing_month)

    class Meta:
        verbose_name_plural = "Información Historica de Tarifa DAC"


class T3HistoricData(models.Model):
    monthly_cut_dates = models.ForeignKey(MonthlyCutDates,
                                          on_delete=models.PROTECT)
    KWH_total = models.IntegerField(null=True, blank=True)
    KVARH = models.IntegerField(null=True, blank=True)
    power_factor = models.DecimalField(max_digits=20, decimal_places=2,
                                       null=True, blank=True, default=0)
    charge_factor = models.DecimalField(max_digits=20, decimal_places=2,
                                        null=True, blank=True, default=0)
    max_demand = models.IntegerField(null=True, blank=True)
    KWH_rate = models.DecimalField(max_digits=20, decimal_places=2, null=True,
                                   blank=True, default=0)
    demand_rate = models.DecimalField(max_digits=20, decimal_places=2,
                                      null=True, blank=True, default=0)
    average_rate = models.DecimalField(max_digits=20, decimal_places=2,
                                       null=True, blank=True, default=0)
    energy_cost = models.DecimalField(max_digits=20, decimal_places=2,
                                      null=True, blank=True, default=0)
    demand_cost = models.DecimalField(max_digits=20, decimal_places=2,
                                      null=True, blank=True, default=0)
    power_factor_bonification = models.DecimalField(max_digits=20,
                                                    decimal_places=2, null=True,
                                                    blank=True, default=0)
    subtotal = models.DecimalField(max_digits=20, decimal_places=2, null=True,
                                   blank=True, default=0)
    iva = models.DecimalField(max_digits=20, decimal_places=2, null=True,
                              blank=True, default=0)
    total = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    def __unicode__(self):
        return "CU: " + self.consumer_unit + " - Mes:" + str(self.billing_month)

    class Meta:
        verbose_name_plural = "Información Historica de Tarifa 3"


class DailyData(models.Model):
    consumer_unit = models.ForeignKey(ConsumerUnit,
                                      on_delete=models.PROTECT, null=True,
                                      blank=True)
    data_day = models.DateField("Fecha del dia")
    KWH_total = models.IntegerField(null=True, blank=True)
    KWH_base = models.IntegerField(null=True, blank=True)
    KWH_intermedio = models.IntegerField(null=True, blank=True)
    KWH_punta = models.IntegerField(null=True, blank=True)
    max_demand = models.IntegerField(null=True, blank=True)
    max_demand_time = models.TimeField("Hora de la demanda maxima")
    min_demand = models.IntegerField(null=True, blank=True, default=0)
    min_demand_time = models.TimeField("Hora de la demanda minima",
                                       default=datetime.time(0,0,0))
    KWH_cost = models.DecimalField(max_digits=20, decimal_places=2, null=True,
                                   blank=True, default=0)
    power_factor = models.DecimalField(max_digits=20, decimal_places=2,
                                       null=True, blank=True, default=0)
    KVARH = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        if self.consumer_unit:
            return "Consumer Unit: " + \
                   self.consumer_unit.building.building_name + " - Dia:" + \
                   str(self.data_day)
        else:
            return "Dia:" + str(self.data_day)

    class Meta:
        verbose_name_plural = "Información Diaria"


class MonthlyData(models.Model):
    consumer_unit = models.ForeignKey(ConsumerUnit,
                                      on_delete=models.PROTECT, null=True,
                                      blank=True)
    month = models.IntegerField()
    year = models.IntegerField()
    KWH_total = models.IntegerField(null=True, blank=True)
    max_demand = models.IntegerField(null=True, blank=True)
    max_cons = models.IntegerField(null=True, blank=True)
    carbon_emitions = models.IntegerField(null=True, blank=True)
    power_factor = models.DecimalField(max_digits=20, decimal_places=2,
                                       null=True, blank=True, default=0)
    min_demand = models.IntegerField(null=True, blank=True, default=0)
    min_cons = models.IntegerField(null=True, blank=True)
    average_demand = models.DecimalField(max_digits=20, decimal_places=2,
                                         null=True, blank=True, default=0)
    average_cons = models.DecimalField(max_digits=20, decimal_places=2,
                                       null=True, blank=True, default=0)
    median_cons = models.DecimalField(max_digits=20, decimal_places=2,
                                      null=True, blank=True, default=0)
    deviation_cons = models.DecimalField(max_digits=20, decimal_places=2,
                                         null=True, blank=True, default=0)

    def __unicode__(self):
        if self.consumer_unit:
            return "Consumer Unit: " + \
                   self.consumer_unit.building.building_name + " - Mes: " + \
                   str(self.month) + " - " + str(self.year)
        else:
            return "Mes: " + str(self.month) + " - " + str(self.year)