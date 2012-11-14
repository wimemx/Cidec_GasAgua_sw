from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^$', 'rbac.views.control_panel'),
    url(r'^add_permissions/', 'rbac.views.add_data_context_permissions'),
    url(r'^nuevo_rol/', 'rbac.views.add_role'),
    url(r'^editar_rol/(?P<id_role>\d+)/', 'rbac.views.edit_role'),
    url(r'^delete_perms/(?P<id_role>\d+)', 'rbac.views.edit_role'),
    url(r'^ver_rol/(?P<id_role>\d+)', 'rbac.views.see_role'),
    url(r'^eliminar_rol/(?P<id_role>\d+)', 'rbac.views.delete_role'),
    url(r'^delete_batch/$', 'rbac.views.delete_batch'),
    url(r'^add_user/$', 'rbac.views.add_user'),
    url(r'^eliminar_usuario/(?P<id_user>\d+)', 'rbac.views.delete_user'),
    url(r'^delete_batch_user/$', 'rbac.views.delete_batch_user'),
    url(r'^editar_usuario/(?P<id_user>\d+)/', 'rbac.views.edit_user'),
    url(r'^ver_usuario/(?P<id_user>\d+)', 'rbac.views.see_user'),
    url(r'^roles/', 'rbac.views.view_roles'),
    url(r'^usuarios/', 'rbac.views.view_users'),
    url(r'^asignar_roles/', 'rbac.views.add_data_context_permissions'),
    url(r'^roles_asignados/', 'rbac.views.added_data_context_permissions'),
    url(r'^eliminar_asignacion_rol/(?P<id_data_context>\d+)/', 'rbac.views.delete_data_context'),
    url(r'^delete_batch_datacontext/$', 'rbac.views.delete_batch_data_context'),


    url(r'^search_users/', 'rbac.views.search_users'),
    url(r'^get_group/(?P<id_operation>\d+)', 'rbac.views.get_select_group'),
    url(r'^get_object/(?P<id_group>\d+)', 'rbac.views.get_select_object'),
)