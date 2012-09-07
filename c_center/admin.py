import c_center.models
from django.contrib import admin

class SectoralTypeAdmin(admin.ModelAdmin):
    list_display = ['sectorial_type_name', 'sectoral_type_status', 'sectoral_type_sequence']
    list_filter = ['sectoral_type_status','sectoral_type_sequence']
    actions = ["make_active","make_inactive","mark_deleted"]

    def make_active(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=1)
        if rows_updated == 1:
            message_bit = "El sector fue marcado como activo"
        else:
            message_bit = "Los sectores fueron marcados como activos"
        self.message_user(request, message_bit)
    make_active.short_description = "Marcar sectores como activos"

    def make_inactive(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=0)
        if rows_updated == 1:
            message_bit = "El sector ha sido desactivado"
        else:
            message_bit = "Los %s sectores fueron marcados como desactivados" % rows_updated
        self.message_user(request, message_bit)
    make_inactive.short_description = "Marcar sectores como inactivos"

    def mark_deleted(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=2)
        if rows_updated == 1:
            message_bit = "El sector ha sido marcado como eliminado(oculto)"
        else:
            message_bit = "Los %s sectores fueron marcados como eliminados(ocultos)" % rows_updated
        self.message_user(request, message_bit)
    mark_deleted.short_description = "Marcar sectores como eliminados(ocultos)"
admin.site.register(c_center.models.SectoralType, SectoralTypeAdmin)

class ClusterAdmin(admin.ModelAdmin):
    list_display = ['cluster_name', 'sectoral_type', 'cluster_status']
    list_filter = ['sectoral_type','cluster_status']
    actions = ["make_active","make_inactive","mark_deleted"]

    def make_active(self, request, queryset):
        rows_updated=queryset.update(cluster_status=1)
        if rows_updated == 1:
            message_bit = "El cluster fue marcado como activo"
        else:
            message_bit = "Los clusters fueron marcados como activos"
        self.message_user(request, message_bit)
    make_active.short_description = "Marcar clusters como activos"

    def make_inactive(self, request, queryset):
        rows_updated=queryset.update(cluster_status=0)
        if rows_updated == 1:
            message_bit = "El cluster ha sido desactivado"
        else:
            message_bit = "Los %s clusters fueron marcados como desactivados" % rows_updated
        self.message_user(request, message_bit)
    make_inactive.short_description = "Marcar clusters como inactivos"

    def mark_deleted(self, request, queryset):
        rows_updated=queryset.update(cluster_status=2)
        if rows_updated == 1:
            message_bit = "El cluster ha sido marcado como eliminado(oculto)"
        else:
            message_bit = "Los %s clusters fueron marcados como eliminados(ocultos)" % rows_updated
        self.message_user(request, message_bit)
    mark_deleted.short_description = "Marcar clusters como eliminados(ocultos)"
admin.site.register(c_center.models.Cluster, ClusterAdmin)

class CompanyAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'sectoral_type', 'company_status']
    list_filter = ['sectoral_type','company_status']
    actions = ["make_active","make_inactive","mark_deleted"]

    def make_active(self, request, queryset):
        rows_updated=queryset.update(company_status=1)
        if rows_updated == 1:
            message_bit = "La empresa fue marcada como activa"
        else:
            message_bit = "Las empresas fueron marcadas como activas"
        self.message_user(request, message_bit)
    make_active.short_description = "Marcar empresas como activas"

    def make_inactive(self, request, queryset):
        rows_updated=queryset.update(company_status=0)
        if rows_updated == 1:
            message_bit = "La empresa ha sido desactivada"
        else:
            message_bit = "Las %s empresas fueron marcados como desactivadas" % rows_updated
        self.message_user(request, message_bit)
    make_inactive.short_description = "Marcar empresas como inactivas"

    def mark_deleted(self, request, queryset):
        rows_updated=queryset.update(company_status=2)
        if rows_updated == 1:
            message_bit = "La empresa ha sido marcada como eliminada(oculta)"
        else:
            message_bit = "Las %s empresas fueron marcadas como eliminadas(ocultas)" % rows_updated
        self.message_user(request, message_bit)
    mark_deleted.short_description = "Marcar empresas como eliminadas(ocultas)"
admin.site.register(c_center.models.Company, CompanyAdmin)

class ClusterCompanyAdmin(admin.ModelAdmin):
    list_display = ['cluster', 'company']
    list_filter = ['cluster']
admin.site.register(c_center.models.ClusterCompany, ClusterCompanyAdmin)

admin.site.register(c_center.models.ConfigurationTemplateCompany)

admin.site.register(c_center.models.BuildingAttributesType)

admin.site.register(c_center.models.BuildingAttributes)

class BuildingAdmin(admin.ModelAdmin):
    list_display = ['building_name', 'building_formatted_address', 'building_status', 'pais', 'estado', 'municipio']
    list_filter = ['pais', 'estado', 'municipio', 'building_status']
    actions = ["make_active","make_inactive","mark_deleted"]
    # define the raw_id_fields
    raw_id_fields = ('pais', 'estado', 'municipio', 'colonia', 'calle', 'region')
    # define the related_lookup_fields
    autocomplete_lookup_fields = {
        'fk': ['pais', 'estado', 'municipio', 'colonia', 'calle', 'region'],
    }

    def make_active(self, request, queryset):
        rows_updated=queryset.update(building_status=1)
        if rows_updated == 1:
            message_bit = "El edificio fue marcado como activo"
        else:
            message_bit = "Los edificios fueron marcados como activos"
        self.message_user(request, message_bit)
    make_active.short_description = "Marcar edificios como activos"

    def make_inactive(self, request, queryset):
        rows_updated=queryset.update(building_status=0)
        if rows_updated == 1:
            message_bit = "El edificio ha sido desactivado"
        else:
            message_bit = "Los %s edificios fueron marcados como desactivados" % rows_updated
        self.message_user(request, message_bit)
    make_inactive.short_description = "Marcar edificios como inactivos"

    def mark_deleted(self, request, queryset):
        rows_updated=queryset.update(building_status=2)
        if rows_updated == 1:
            message_bit = "El edificio ha sido marcado como eliminado(oculto)"
        else:
            message_bit = "Los %s edificios fueron marcados como eliminados(ocultos)" % rows_updated
        self.message_user(request, message_bit)
    mark_deleted.short_description = "Marcar edificios como eliminados(ocultos)"
admin.site.register(c_center.models.Building, BuildingAdmin)

class BuildingAttributesForBuildingAdmin(admin.ModelAdmin):
    list_filter = ['building_attributes', 'building']
admin.site.register(c_center.models.BuildingAttributesForBuilding, BuildingAttributesForBuildingAdmin)
admin.site.register(c_center.models.PowermeterModel)

class PowermeterAdmin(admin.ModelAdmin):
    list_filter = ['powermeter_model']
admin.site.register(c_center.models.Powermeter, PowermeterAdmin)

class ProfilePowermeterAdmin(admin.ModelAdmin):
    list_filter = ['profile_powermeter_status']
    actions = ["make_active", "make_inactive", "mark_deleted"]

    def make_active(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=1)
        if rows_updated == 1:
            message_bit = "El perfil fue marcado como activo"
        else:
            message_bit = "Los perfiles fueron marcados como activos"
        self.message_user(request, message_bit)
    make_active.short_description = "Marcar perfiles como activos"

    def make_inactive(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=0)
        if rows_updated == 1:
            message_bit = "El perfil ha sido desactivado"
        else:
            message_bit = "Los %s perfiles fueron marcados como desactivados" % rows_updated
        self.message_user(request, message_bit)
    make_inactive.short_description = "Marcar perfiles como inactivos"

    def mark_deleted(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=2)
        if rows_updated == 1:
            message_bit = "El perfil ha sido marcado como eliminado(oculto)"
        else:
            message_bit = "Los %s perfiles fueron marcados como eliminados(ocultos)" % rows_updated
        self.message_user(request, message_bit)
    mark_deleted.short_description = "Marcar perfiles como eliminados(ocultos)"

admin.site.register(c_center.models.ProfilePowermeter, ProfilePowermeterAdmin)

class ElectricDeviceTypeAdmin(admin.ModelAdmin):
    list_filter = ['electric_device_type_status']
    actions = ["make_active", "make_inactive", "mark_deleted"]

    def make_active(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=1)
        if rows_updated == 1:
            message_bit = "El dispositivo o sistema fue marcado como activo"
        else:
            message_bit = "Los dispositivos o sistemas fueron marcados como activos"
        self.message_user(request, message_bit)
    make_active.short_description = "Marcar dispositivos o sistemas como activos"

    def make_inactive(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=0)
        if rows_updated == 1:
            message_bit = "El dispositivo o sistema ha sido desactivado"
        else:
            message_bit = "Los %s dispositivos o sistemas fueron marcados como desactivados" % rows_updated
        self.message_user(request, message_bit)
    make_inactive.short_description = "Marcar dispositivos o sistemas como inactivos"

    def mark_deleted(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=2)
        if rows_updated == 1:
            message_bit = "El dispositivo o sistema ha sido marcado como eliminado(oculto)"
        else:
            message_bit = "Los %s dispositivos o sistemas fueron marcados como eliminados(ocultos)" % rows_updated
        self.message_user(request, message_bit)
    mark_deleted.short_description = "Marcar dispositivos o sistemas como eliminados(ocultos)"

admin.site.register(c_center.models.ElectricDeviceType, ElectricDeviceTypeAdmin)

class PartOfBuildingTypeAdmin(admin.ModelAdmin):
    list_filter = ['part_of_building_type_status']
    actions = ["make_active", "make_inactive", "mark_deleted"]

    def make_active(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=1)
        if rows_updated == 1:
            message_bit = "la parte fue marcada como activa"
        else:
            message_bit = "Las partes fueron marcados como activas"
        self.message_user(request, message_bit)
    make_active.short_description = "Marcar partes como activas"

    def make_inactive(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=0)
        if rows_updated == 1:
            message_bit = "La parte ha sido desactivado"
        else:
            message_bit = "Las %s partes fueron marcadas como desactivadas" % rows_updated
        self.message_user(request, message_bit)
    make_inactive.short_description = "Marcar partes como inactivas"

    def mark_deleted(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=2)
        if rows_updated == 1:
            message_bit = "La parte ha sido marcada como eliminada(oculta)"
        else:
            message_bit = "Las %s partes fueron marcadas como eliminadas(ocultas)" % rows_updated
        self.message_user(request, message_bit)
    mark_deleted.short_description = "Marcar partes como eliminadas(ocultas)"
admin.site.register(c_center.models.PartOfBuildingType, PartOfBuildingTypeAdmin)

class BuildingTypeAdmin(admin.ModelAdmin):
    list_filter = ['building_type_status']
    actions = ["make_active", "make_inactive", "mark_deleted"]

    def make_active(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=1)
        if rows_updated == 1:
            message_bit = "El tipo fue marcado como activo"
        else:
            message_bit = "Los tipos fueron marcados como activos"
        self.message_user(request, message_bit)
    make_active.short_description = "Marcar tipos como activos"

    def make_inactive(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=0)
        if rows_updated == 1:
            message_bit = "El tipo ha sido desactivado"
        else:
            message_bit = "Los %s tipos fueron marcados como desactivados" % rows_updated
        self.message_user(request, message_bit)
    make_inactive.short_description = "Marcar tipos como inactivos"

    def mark_deleted(self, request, queryset):
        rows_updated=queryset.update(sectoral_type_status=2)
        if rows_updated == 1:
            message_bit = "El tipo ha sido marcado como eliminado(oculto)"
        else:
            message_bit = "Los %s tipos fueron marcados como eliminados(ocultos)" % rows_updated
        self.message_user(request, message_bit)
    mark_deleted.short_description = "Marcar tipos como eliminados(ocultos)"
admin.site.register(c_center.models.BuildingType, BuildingTypeAdmin)

class BuildingTypeForBuildingAdmin(admin.ModelAdmin):
    list_filter = ['building_type', 'building']
admin.site.register(c_center.models.BuildingTypeForBuilding, BuildingTypeForBuildingAdmin)

class PartOfBuildingAdmin(admin.ModelAdmin):
    list_filter = ['part_of_building_type', 'building']
admin.site.register(c_center.models.PartOfBuilding, PartOfBuildingAdmin)

class HierarchyOfPartAdmin(admin.ModelAdmin):
    list_filter = ['part_of_building_composite', 'part_of_building_leaf']
admin.site.register(c_center.models.HierarchyOfPart, HierarchyOfPartAdmin)

class CompanyBuildingAdmin(admin.ModelAdmin):
    list_filter = ['company']
admin.site.register(c_center.models.CompanyBuilding, CompanyBuildingAdmin)

class BuilAttrsForPartOfBuilAdmin(admin.ModelAdmin):
    list_filter = ['part_of_building', 'part_of_building']
admin.site.register(c_center.models.BuilAttrsForPartOfBuil, BuilAttrsForPartOfBuilAdmin)

class ConsumerUnitAdmin(admin.ModelAdmin):
    list_filter = ['building', 'part_of_building']
    search_fields = ['profile_powermeter__powermeter__powermeter_serial',
                     'profile_powermeter__powermeter__powermeter_anotation',
                     'building__building_name']
admin.site.register(c_center.models.ConsumerUnit, ConsumerUnitAdmin)

class ElectricDataAdmin(admin.ModelAdmin):
    list_filter = ['profile_powermeter']
admin.site.register(c_center.models.ElectricData, ElectricDataAdmin)
admin.site.register(c_center.models.IndustrialEquipment)
admin.site.register(c_center.models.PowermeterForIndustrialEquipment)
class ElectricRateForElectricDataAdmin(admin.ModelAdmin):
    list_filter = ['electric_data__profile_powermeter']
    search_fields = ['electric_data__profile_powermeter__powermeter__powermeter_serial',
                     'electric_data__profile_powermeter__powermeter__powermeter_anotation']
admin.site.register(c_center.models.ElectricRateForElectricData, ElectricRateForElectricDataAdmin)
