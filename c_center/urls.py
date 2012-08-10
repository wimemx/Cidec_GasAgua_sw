from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^cfe/', 'c_center.views.cfe_bill'),
    url(r'^potencia_activa/', 'c_center.views.potencia_activa'),
    url(r'^potencia_reactiva/', 'c_center.views.potencia_reactiva'),
    url(r'^factor_potencia/', 'c_center.views.factor_potencia'),
    url(r'^perfil_carga/', 'c_center.views.perfil_carga'),
    url(r'^set_default_building/(?P<id_building>\d+)/', 'c_center.views.set_default_building'),
)
