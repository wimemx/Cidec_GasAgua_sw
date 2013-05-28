import rbac.models
from django.contrib import admin

admin.site.register(rbac.models.ExtendedUser)
admin.site.register(rbac.models.UserProfile)
admin.site.register(rbac.models.Operation)
admin.site.register(rbac.models.Object)
admin.site.register(rbac.models.Role)
admin.site.register(rbac.models.PermissionAsigment)
admin.site.register(rbac.models.UserRole)

class DataContextPermissionAdmin(admin.ModelAdmin):
    list_display = ['user_role', 'cluster', 'company', 'building',
                    'part_of_building']
    list_filter = ['user_role']

admin.site.register(rbac.models.DataContextPermission,
                    DataContextPermissionAdmin)
admin.site.register(rbac.models.Group)


class GroupObjectAdmin(admin.ModelAdmin):
    list_display = ['group', 'object']
    list_filter = ['group', ]

admin.site.register(rbac.models.GroupObject, GroupObjectAdmin)
admin.site.register(rbac.models.OperationForGroup)


class OperationGroupObjectAdmin(admin.ModelAdmin):
    list_display = ['operation', 'group_object']
    list_filter = ['operation', 'group_object']

admin.site.register(rbac.models.OperationForGroupObjects,
                    OperationGroupObjectAdmin)
admin.site.register(rbac.models.MenuCategs)


class MenuHierarchyAdmin(admin.ModelAdmin):
    list_display = ['parent_cat', 'child_cat']
    list_filter = ['parent_cat', 'parent_cat']

admin.site.register(rbac.models.MenuHierarchy,
                    MenuHierarchyAdmin)

admin.site.register(rbac.models.ControlPanel)


class CPanelHierarchyAdmin(admin.ModelAdmin):
    list_display = ['parent_cat', 'child_cat']
    list_filter = ['parent_cat', 'parent_cat']


admin.site.register(rbac.models.CPanelHierarchy,
                    CPanelHierarchyAdmin)