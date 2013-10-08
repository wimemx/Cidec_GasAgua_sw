#coding:utf-8
__author__ = 'velocidad'
from django import forms


class CUGenerator(forms.Form):
    number_of_sas = forms.IntegerField(
        label="Número de Sistemas de Adquisición")
    number_of_pms = forms.IntegerField(
        label="Número de medidores por SA"
    )