from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^medition_rate/', 'c_center.calculations.tag_reading'),
    url(r'^cfe/', 'c_center.views.cfe_bill'),
    #url(r'^potencia_activa/', 'c_center.views.potencia_activa'),
    url(r'^potencia_activa/', 'c_center.views.potencia_activa'),
    url(r'^potencia_activa_data/', 'c_center.views.get_kw_data'),
    url(r'^potencia_activa_data_b/', 'c_center.views.get_kw_data_boris'),

    url(r'^potencia_reactiva/', 'c_center.views.potencia_reactiva'),
    url(r'^potencia_reactiva_data_b/', 'c_center.views.get_kvar_data_boris'),

    url(r'^potencia_reactiva_data/', 'c_center.views.get_kvar_data'),
    url(r'^factor_potencia/', 'c_center.views.factor_potencia'),

    url(r'^factor_potencia_data/', 'c_center.views.get_pf_data'),
    url(r'^factor_potencia_data_b/', 'c_center.views.get_pf_data_boris'),

    url(r'^perfil_carga/', 'c_center.views.perfil_carga'),
    url(r'^perfil_carga_data/', 'c_center.views.get_pp_data'),
    url(r'^set_default_building/(?P<id_building>\d+)/', 'c_center.views.set_default_building'),
)
