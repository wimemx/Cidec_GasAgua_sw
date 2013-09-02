# -*- coding: utf-8 -*-
__author__ = 'velocidad'
import re

from django import forms
from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.validators import RegexValidator

from c_center.models import BuildingType, Company
from electric_rates.models import ElectricRates
from location.models import Region, Timezones


class DecimalHumanizedInput(forms.TextInput):
    def __init__(self, initial=None, *args, **kwargs):
        super(DecimalHumanizedInput, self).__init__(*args, **kwargs)

    def render(self, name, value, attrs=None):
        value = intcomma(value)
        return super(DecimalHumanizedInput, self).render(name, value, attrs)


class CommaSeparatedDecimalField(forms.DecimalField):
    """
    Use this as a drop-in replacement for forms.DecimalField()
    """
    widget = DecimalHumanizedInput

    def clean(self, value):
        if value:
            value = value.replace(',', '')
            super(CommaSeparatedDecimalField, self).clean(value)
        return value


class BuildingForm(forms.Form):
    ##############
    # VALIDATORS #
    ##############
    arePat = re.compile(r'[^\w\s\-\'\."]', re.UNICODE)
    alpha = RegexValidator(arePat,
                           'Solo se permiten caracteres alfabéticos, '
                           'guiones y puntos')
    numeric = RegexValidator(r'[^0-9]',
                             'Solo se permiten caracteres numéricos')
    #####################
    # DROP DOWN OPTIONS #
    #####################
    company_tuple = Company.objects.all().exclude(company_status=0).values(
        "pk", "company_name")
    company_tuple = [(cm["pk"], cm["company_name"]) for cm in company_tuple]
    company_tuple.insert(0, ("0", "Seleccione una empresa"))

    rate_tuple = ElectricRates.objects.all().values(
        "pk", "electric_rate_name")
    rate_tuple = [(rt["pk"], rt["electric_rate_name"]) for rt in rate_tuple]
    rate_tuple.insert(0, ("0", "Seleccione una tarifa eléctrica"))

    btype_tuple = BuildingType.objects.all().values(
        "pk", "building_type_name")
    btype_tuple = [(rt["pk"], rt["building_type_name"]) for rt in btype_tuple]

    region_tuple = Region.objects.all().values("pk", "region_name")
    region_tuple = [(rg["pk"], rg["region_name"]) for rg in region_tuple]
    region_tuple.insert(0, ("0", "Seleccione una región"))

    tz_tuple = Timezones.objects.all().values("pk", "name")
    tz_tuple = [(tz["pk"], tz["name"]) for tz in tz_tuple]
    tz_tuple.insert(0, ("0", "Seleccione una zona horaria"))

    ###############
    # FORM FIELDS #
    ###############
    building_name = forms.CharField(max_length=128, widget=forms.TextInput(
                                    attrs={'id': 'b_name', 'class': 'g8'}),
                                    validators=[alpha])
    building_description = forms.CharField(
        widget=forms.Textarea(
            attrs={"rows": "5", "class": "g8", "id": "b_description"}),
        required=False)
    company = forms.ChoiceField(choices=company_tuple,
                                label="Selecciona una empresa",
                                widget=forms.Select(attrs={"id": "b_company",
                                                           "class": "g8"}))
    mts2_built = CommaSeparatedDecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "g8", "id": "b_mt2"}
        ))

    electric_rate = forms.ChoiceField(
        choices=rate_tuple,
        widget=forms.Select(attrs={"class": "g8", "id": "b_electric_rate"}))

    building_type = forms.ChoiceField(
        choices=btype_tuple,
        widget=forms.SelectMultiple(attrs={'id': 'b_type',
                                           'size': '10',
                                           'class': 'g8'}))

    pais = forms.IntegerField(widget=forms.HiddenInput(
        attrs={"id": "b_country_id"}), required=False)
    estado = forms.IntegerField(widget=forms.HiddenInput(
        attrs={"id": "b_state_id"}), required=False)
    municipio = forms.IntegerField(widget=forms.HiddenInput(
        attrs={"id": "b_municipality_id"}), required=False)
    colonia = forms.IntegerField(widget=forms.HiddenInput(
        attrs={"id": "b_neighborhood_id"}), required=False)
    calle = forms.IntegerField(widget=forms.HiddenInput(
        attrs={"id": "b_street_id"}), required=False)

    pais_input = forms.CharField(widget=forms.TextInput(
        attrs={"id": "b_country", "class": "g8", "autocomplete": "off"}))
    estado_input = forms.CharField(widget=forms.TextInput(
        attrs={"id": "b_state", "class": "g8", "autocomplete": "off"}))
    municipio_input = forms.CharField(widget=forms.TextInput(
        attrs={"id": "b_municipality", "class": "g8", "autocomplete": "off"}))
    colonia_input = forms.CharField(widget=forms.TextInput(
        attrs={"id": "b_neighborhood", "class": "g8", "autocomplete": "off"}))
    calle_input = forms.CharField(widget=forms.TextInput(
        attrs={"id": "b_street", "class": "g8", "autocomplete": "off"}))

    external_number = forms.CharField(
        widget=forms.TextInput(attrs={'id': 'b_ext', 'class': 'g8'}),
        validators=[alpha])
    internal_number = forms.CharField(
        widget=forms.TextInput(attrs={'id': 'b_int', 'class': 'g8'}),
        validators=[alpha], required=False)

    code_zone = forms.CharField(widget=forms.TextInput(
        attrs={"id": "b_zip"}), validators=[numeric])

    region = forms.ChoiceField(
        choices=region_tuple,
        widget=forms.Select(attrs={'id': 'b_region',
                                   'class': 'g8'}))

    time_zone = forms.ChoiceField(
        choices=tz_tuple,
        widget=forms.Select(attrs={'id': 'b_time_zone',
                                   'class': 'g8'}))
    lat_addr = forms.DecimalField(
        max_digits=10, decimal_places=6,
        widget=forms.HiddenInput(attrs={"id": "b_latitude"}))
    long_addr = forms.DecimalField(
        max_digits=10, decimal_places=6,
        widget=forms.HiddenInput(attrs={"id": "b_longitude"}))

    def __init__(self, *args, **kwargs):
        companies = kwargs.pop("empresas", None)
        super(BuildingForm, self).__init__(*args, **kwargs)
        if companies:
            self.fields["company"].choices = companies

