import c_center.models
from django.contrib import admin

class SectoralTypeAdmin(admin.ModelAdmin):
    actions = ["Activar","Desactivar","Eliminar(ocultar)"]

    def make_published(self, request, queryset):
        rows_updated=queryset.update(published=True)
        if rows_updated == 1:
            message_bit = "1 entrada fue marcada"
        else:
            message_bit = "%s entradas fueron marcadas" % rows_updated
        self.message_user(request, "%s como publicadas." % message_bit)
    make_published.short_description = "Marcar entradas como publicadas"

    def make_unpublished(self, request, queryset):
        rows_updated=queryset.update(published=False)
        if rows_updated == 1:
            message_bit = "1 entrada fue"
        else:
            message_bit = "%s entradas fueron" % rows_updated
        self.message_user(request, "%s marcadas como no publicadas." % message_bit)
    make_unpublished.short_description = "Marcar entradas como no publicadas"

admin.site.register(c_center.models.SectoralType)
admin.site.register(c_center.models.Cluster)
admin.site.register(c_center.models.Company)
class ClusterCompanyAdmin(admin.ModelAdmin):
    list_display=['title', 'autor', 'published_date', 'published']
    list_filter=['published_date','title','published']
    actions = ["make_published","make_unpublished"]

    def make_published(self, request, queryset):
        rows_updated=queryset.update(published=True)
        if rows_updated == 1:
            message_bit = "1 entrada fue marcada"
        else:
            message_bit = "%s entradas fueron marcadas" % rows_updated
        self.message_user(request, "%s como publicadas." % message_bit)
    make_published.short_description = "Marcar entradas como publicadas"

    def make_unpublished(self, request, queryset):
        rows_updated=queryset.update(published=False)
        if rows_updated == 1:
            message_bit = "1 entrada fue"
        else:
            message_bit = "%s entradas fueron" % rows_updated
        self.message_user(request, "%s marcadas como no publicadas." % message_bit)
    make_unpublished.short_description = "Marcar entradas como no publicadas"
admin.site.register(c_center.models.ClusterCompany)
admin.site.register(c_center.models.ConfigurationTemplateCompany)
admin.site.register(c_center.models.BuildingAttributesType)
admin.site.register(c_center.models.BuildingAttributes)
admin.site.register(c_center.models.Building)
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