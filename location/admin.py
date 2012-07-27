import location.models
from django.contrib import admin

admin.site.register(location.models.Pais)
admin.site.register(location.models.Estado)
admin.site.register(location.models.Municipio)
admin.site.register(location.models.Colonia)
admin.site.register(location.models.Calle)
admin.site.register(location.models.Region)
admin.site.register(location.models.PaisEstado)
admin.site.register(location.models.EstadoMunicipio)
admin.site.register(location.models.MunicipioColonia)
admin.site.register(location.models.ColoniaCalle)
admin.site.register(location.models.RegionEstado)