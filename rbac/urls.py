from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^asignacion_permisos/', 'rbac.views.add_data_context_permissions'),
)
