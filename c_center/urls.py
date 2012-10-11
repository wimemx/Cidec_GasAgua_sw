from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^graficas/', 'c_center.views.graficas'),
    url(r'^grafica_datos/', 'c_center.views.grafica_datos'),

    url(r'^medition_rate/', 'c_center.calculations.tag_reading'),
    url(r'^cfe/', 'c_center.views.cfe_bill'),
    url(r'^perfil_carga/', 'c_center.views.perfil_carga'),
    url(r'^perfil_carga_data/', 'c_center.views.get_pp_data'),
    url(r'^set_default_building/(?P<id_building>\d+)/', 'c_center.views.set_default_building'),
    url(r'^set_consumer_unit/', 'c_center.views.set_consumer_unit'),

    url(r'^set_c_u/(?P<id_c_u>\d+)/', 'c_center.views.set_default_consumer_unit'),

    url(r'^weekly_summary_kwh/', 'c_center.views.get_weekly_summary_comparison_kwh'),
    url(r'^cfe_calculos/', 'c_center.views.cfe_calculations'),

    url(r'^get_cluster_companies/(?P<id_cluster>\d+)/', 'c_center.views.get_cluster_companies'),
    url(r'^get_company_buildings/(?P<id_company>\d+)/', 'c_center.views.get_company_buildings'),
    url(r'^get_parts_of_building/(?P<id_building>\d+)/', 'c_center.views.get_parts_of_building'),

    url(r'^agregar_atributo/', 'c_center.views.add_building_attr'),
    url(r'^atributos/', 'c_center.views.b_attr_list'),
    url(r'^eliminar_b_attr/(?P<id_b_attr>\d+)/', 'c_center.views.delete_b_attr'),
    url(r'^editar_b_attr/(?P<id_b_attr>\d+)/', 'c_center.views.editar_b_attr'),
    url(r'^ver_b_attr/(?P<id_b_attr>\d+)/', 'c_center.views.ver_b_attr'),




)
