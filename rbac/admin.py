import rbac.models
from django.contrib import admin

admin.site.register(rbac.models.ExtendedUser)
admin.site.register(rbac.models.UserProfile)
admin.site.register(rbac.models.Operation)
admin.site.register(rbac.models.Object)
admin.site.register(rbac.models.Role)
admin.site.register(rbac.models.PermissionAsigment)
admin.site.register(rbac.models.UserRole)
admin.site.register(rbac.models.DataContextPermission)
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