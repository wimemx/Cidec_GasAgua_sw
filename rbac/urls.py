from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^add_permissions/', 'rbac.views.add_data_context_permissions'),
    url(r'^new_role/', 'rbac.views.add_role'),
)
