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
