# -*- coding: utf-8 -*-
__author__ = 'velocidad'
from django import forms
from c_center.models import Building, CompanyBuilding, \
    BuildingTypeForBuilding, TimezonesBuildings


class BuildingForm(forms.ModelForm):
    class Meta:
        model = Building
        widgets = {
            'building_name': forms.TextInput(
                attrs={'id': 'b_name', 'class': 'g8'}),
            'building_description': forms.Textarea(
                attrs={'id': 'b_description', 'class': 'g8'}),
            'mts2_built': forms.TextInput(
                attrs={'id': 'b_mt2', 'class': 'g8'}),
            'electric_rate': forms.Select(
                attrs={'id': 'b_electric_rate', 'class': 'g8'}),
            'pais': forms.HiddenInput(attrs={"id": "b_country_id"}),
            'estado': forms.HiddenInput(attrs={"id": "b_state_id"}),
            'municipio': forms.HiddenInput(attrs={"id": "b_municipality_id"}),
            'colonia': forms.HiddenInput(attrs={"id": "b_neighborhood_id"}),
            'calle': forms.HiddenInput(attrs={"id": "b_street_id"}),
            'building_external_number': forms.TextInput(attrs={"id": "b_ext",
                                                               "class": "g8"}),
            'building_internal_number': forms.TextInput(attrs={"id": "b_int",
                                                               "class": "g8"}),
            'building_code_zone': forms.TextInput(attrs={"id": "b_zip",
                                                         "class": "g8"}),
            'region': forms.Select(attrs={"id": "b_region",
                                          "class": "g8"}),
            'building_long_address': forms.HiddenInput(
                attrs={"id": "b_longitude", 'class': 'g8'}),
            'building_lat_address': forms.HiddenInput(
                attrs={"id": "b_latitude", 'class': 'g8'}),
        }

    def __init__(self, *args, **kwargs):
        super(BuildingForm, self).__init__(*args, **kwargs)
        self.fields['electric_rate'].empty_label = \
            "Selecciona una tarifa eléctrica"
        self.fields['region'].empty_label = \
            "Selecciona una región"


class TimezonesBuildingsForm(forms.ModelForm):
    class Meta:
        model = TimezonesBuildings
        widgets = {
            'time_zone': forms.Select(
                attrs={'id': 'b_time_zone', 'class': 'g8'}),
        }

    def __init__(self, *args, **kwargs):
        super(TimezonesBuildingsForm, self).__init__(*args, **kwargs)
        self.fields['time_zone'].empty_label = "Selecciona una zona horaria"


class CompanyBuildingForm(forms.ModelForm):
    class Meta:
        model = CompanyBuilding
        widgets = {
            'company': forms.Select(
                attrs={'id': 'b_company', 'class': 'g8'}),
        }

    def __init__(self, *args, **kwargs):
        super(CompanyBuildingForm, self).__init__(*args, **kwargs)
        self.fields['company'].empty_label = "Selecciona una empresa"


class BuildingTypeForBuildingForm(forms.ModelForm):
    class Meta:
        model = BuildingTypeForBuilding
        exclude = ("building",
                   "building_type_for_building_description")
        widgets = {
            'building_type': forms.SelectMultiple(
                attrs={'id': 'b_type', 'size': '10', 'class': 'g8'}),
        }

    def __init__(self, *args, **kwargs):
        super(BuildingTypeForBuildingForm, self).__init__(*args, **kwargs)
        self.fields['building_type'].empty_label = None