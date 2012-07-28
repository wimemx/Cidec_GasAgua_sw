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
    list_filter = ['building_status','pais','estado','municipio']
    actions = ["make_active","make_inactive","mark_deleted"]

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

admin.site.register(c_center.models.BuildingAttributesForBuilding)
admin.site.register(c_center.models.Powermeter)
admin.site.register(c_center.models.ElectricDeviceType)
admin.site.register(c_center.models.PartOfBuildingType)
admin.site.register(c_center.models.BuildingType)
admin.site.register(c_center.models.BuildingTypeForBuilding)
admin.site.register(c_center.models.PartOfBuilding)
admin.site.register(c_center.models.HierarchyOfPart)
admin.site.register(c_center.models.CompanyBuilding)
admin.site.register(c_center.models.BuilAttrsForPartOfBuil)
admin.site.register(c_center.models.ConsumerUnit)