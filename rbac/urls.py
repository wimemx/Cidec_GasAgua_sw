from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^add_permissions/', 'rbac.views.add_data_context_permissions'),
    url(r'^nuevo_rol/', 'rbac.views.add_role'),
    url(r'^roles/', 'rbac.views.view_roles'),
    url(r'^get_group/(?P<id_operation>\d+)', 'rbac.views.get_select_group'),
    url(r'^get_object/(?P<id_group>\d+)', 'rbac.views.get_select_object'),
)