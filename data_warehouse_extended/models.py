#coding:utf-8

# Django imports
import django.db.models

# Data Warehouse Extended imports
import data_warehouse_extended.globals


class InstantDelta(django.db.models.Model):

    name =\
        django.db.models.CharField(
            unique=True,
            max_length=data_warehouse_extended.globals.Constant.NAME_LENGTH,
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                             INSTANT_DELTA__NAME)

    delta_seconds =\
        django.db.models.IntegerField(
            unique=True,
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                             INSTANT_DELTA__DELTA_SECONDS)

    def __unicode__(self):
        return self.name + u" - " + str(self.delta_seconds)


class Instant(django.db.models.Model):

    instant_delta =\
        django.db.models.ForeignKey(
            InstantDelta,
            related_name=data_warehouse_extended.globals.ModelFieldRelatedName.
                             INSTANT,
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                             INSTANT__INSTANT_DELTA)

    instant_datetime =\
        django.db.models.DateTimeField(
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                             INSTANT__INSTANT_DATETIME)

    class Meta:
        unique_together = ("instant_delta", "instant_datetime")


    def __unicode__(self):
        return self.instant_delta.name + u" - " +\
               self.instant_datetime.strftime(u"%Y/%m/%d %H:%M")


class ConsumerUnitProfile(django.db.models.Model):

    transactional_id =\
        django.db.models.IntegerField(
            primary_key=True,
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                             CONSUMER_UNIT_PROFILE__TRANSACTIONAL_ID)

    building_name =\
        django.db.models.CharField(
            max_length=data_warehouse_extended.globals.Constant.
                           NAME_TRANSACTIONAL_LENGTH,
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                             CONSUMER_UNIT_PROFILE__BUILDING_NAME)

    part_of_building_name =\
        django.db.models.CharField(
            max_length=data_warehouse_extended.globals.Constant.
                           NAME_TRANSACTIONAL_LENGTH,
            null=True,
            blank=True,
            default=u"",
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                         CONSUMER_UNIT_PROFILE__PART_OF_BUILDING_NAME)

    electric_device_type_name =\
        django.db.models.CharField(
            max_length=data_warehouse_extended.globals.Constant.
                           NAME_TRANSACTIONAL_LENGTH,
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                             CONSUMER_UNIT_PROFILE__ELECTRIC_DEVICE_TYPE_NAME)

    def __unicode__(self):
        return str(self.transactional_id) + u" - " + self.building_name


class ElectricalParameter(django.db.models.Model):

    INSTANT = 1
    CUMULATIVE = 2
    TYPES =\
        (
            (INSTANT, data_warehouse_extended.globals.ModelFieldName.
                            ELECTRICAL_PARAMETER__TYPE__INSTANT),
            (CUMULATIVE, data_warehouse_extended.globals.ModelFieldName.
                             ELECTRICAL_PARAMETER__TYPE__CUMULATIVE),
        )

    name =\
        django.db.models.CharField(
            unique=True,
            max_length=data_warehouse_extended.globals.Constant.NAME_LENGTH,
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                             ELECTRICAL_PARAMETER__NAME)

    name_transactional =\
        django.db.models.CharField(
            unique=True,
            max_length=data_warehouse_extended.globals.Constant.NAME_LENGTH,
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                             ELECTRICAL_PARAMETER__NAME_TRANSACTIONAL)

    type =\
        django.db.models.IntegerField(
            choices=TYPES,
            default=INSTANT,
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                             ELECTRICAL_PARAMETER__TYPE)

    def __unicode__(self):
        return self.name + self.name_transactional + self.TYPES[self.type][1]


class ConsumerUnitInstantElectricalData(django.db.models.Model):

    id =\
        django.db.models.BigIntegerField(
            primary_key=True,
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                             CONSUMER_UNIT_INSTANT_ELECTRIC_DATA__ID)

    consumer_unit_profile =\
        django.db.models.ForeignKey(
            ConsumerUnitProfile,
            related_name=data_warehouse_extended.globals.ModelFieldRelatedName.
                             CONSUMER_UNIT_INSTANT_ELECTRIC_DATA,
            verbose_name=\
                data_warehouse_extended.globals.ModelFieldName.
                    CONSUMER_UNIT_INSTANT_ELECTRIC_DATA__CONSUMER_UNIT_PROFILE)

    instant =\
        django.db.models.ForeignKey(
            Instant,
            related_name=data_warehouse_extended.globals.ModelFieldRelatedName.
                             CONSUMER_UNIT_INSTANT_ELECTRIC_DATA,
            verbose_name=\
                data_warehouse_extended.globals.ModelFieldName.
                    CONSUMER_UNIT_INSTANT_ELECTRIC_DATA__INSTANT)

    electrical_parameter =\
        django.db.models.ForeignKey(
            ElectricalParameter,
            related_name=data_warehouse_extended.globals.ModelFieldRelatedName.
                             CONSUMER_UNIT_INSTANT_ELECTRIC_DATA,
            verbose_name=\
                data_warehouse_extended.globals.ModelFieldName.
                    CONSUMER_UNIT_INSTANT_ELECTRIC_DATA__ELECTRICAL_PARAMETER)

    value =\
        django.db.models.DecimalField(
            max_digits=data_warehouse_extended.globals.Constant.
                           DECIMAL_FIELD_MAX_DIGITS,
            decimal_places=data_warehouse_extended.globals.Constant.
                               DECIMAL_FIELD_DECIMAL_PLACES,
            null=True,
            blank=True,
            default=None,
            verbose_name=data_warehouse_extended.globals.ModelFieldName.
                             CONSUMER_UNIT_INSTANT_ELECTRIC_DATA__VALUE)

    class Meta:
        unique_together =\
            ("consumer_unit_profile", "instant", "electrical_parameter")

    def __unicode__(self):
        return self.consumer_unit_profile.building_name + u" - " +\
               self.instant.__unicode__() + self.electrical_parameter.name +\
               str(self.value)
