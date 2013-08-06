# -*- coding: utf-8 -*-
import location.models
from django.contrib import admin

admin.site.register(location.models.Pais)
admin.site.register(location.models.Estado)
admin.site.register(location.models.Municipio)
admin.site.register(location.models.Colonia)
admin.site.register(location.models.Calle)
admin.site.register(location.models.Region)


class PaisEstadoAdmin(admin.ModelAdmin):
    # define the raw_id_fields
    raw_id_fields = ('pais', 'estado')
    # define the related_lookup_fields
    autocomplete_lookup_fields = {
        'fk': ['pais', 'estado'],
    }

admin.site.register(location.models.PaisEstado, PaisEstadoAdmin)


class EstadoMunicipioAdmin(admin.ModelAdmin):
    # define the raw_id_fields
    raw_id_fields = ('estado', 'municipio')
    # define the related_lookup_fields
    autocomplete_lookup_fields = {
        'fk': ['estado', 'municipio'],
    }

admin.site.register(location.models.EstadoMunicipio, EstadoMunicipioAdmin)


class MunicipioColoniaAdmin(admin.ModelAdmin):
    # define the raw_id_fields
    raw_id_fields = ('municipio', 'colonia')
    # define the related_lookup_fields
    autocomplete_lookup_fields = {
        'fk': ['municipio', 'colonia'],
    }

admin.site.register(location.models.MunicipioColonia, MunicipioColoniaAdmin)


class ColoniaCalleAdmin(admin.ModelAdmin):
    # define the raw_id_fields
    raw_id_fields = ('colonia', 'calle')
    # define the related_lookup_fields
    autocomplete_lookup_fields = {
        'fk': ['colonia', 'calle'],
    }

admin.site.register(location.models.ColoniaCalle, ColoniaCalleAdmin)

class RegionEstadoAdmin(admin.ModelAdmin):
    # define the raw_id_fields
    raw_id_fields = ('estado', 'region')
    # define the related_lookup_fields
    autocomplete_lookup_fields = {
        'fk': ['estado', 'region'],
    }

admin.site.register(location.models.RegionEstado, RegionEstadoAdmin)

admin.site.register(location.models.Timezones)