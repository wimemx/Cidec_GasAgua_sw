from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^add_permissions/', 'rbac.views.add_data_context_permissions'),
    url(r'^nuevo_rol/', 'rbac.views.add_role'),
    url(r'^editar_rol/(?P<id_role>\d+)/', 'rbac.views.edit_role'),
    url(r'^delete_perms/(?P<id_role>\d+)', 'rbac.views.edit_role'),
    url(r'^ver_rol/(?P<id_role>\d+)', 'rbac.views.see_role'),
    url(r'^eliminar_rol/(?P<id_role>\d+)', 'rbac.views.delete_role'),
    url(r'^delete_batch/$', 'rbac.views.delete_batch'),
    url(r'^add_user/$', 'rbac.views.add_user'),

    url(r'^roles/', 'rbac.views.view_roles'),
    url(r'^get_group/(?P<id_operation>\d+)', 'rbac.views.get_select_group'),
    url(r'^get_object/(?P<id_group>\d+)', 'rbac.views.get_select_object'),
)