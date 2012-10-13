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

    url(r'^clusters/', 'c_center.views.view_cluster'),
    url(r'^nuevo_cluster/', 'c_center.views.add_cluster'),
    url(r'^editar_cluster/(?P<id_cluster>\d+)/', 'c_center.views.edit_cluster'),
    url(r'^eliminar_cluster/(?P<id_cluster>\d+)', 'c_center.views.delete_cluster'),
    url(r'^delete_batch_cluster/$', 'c_center.views.delete_batch_cluster'),
    url(r'^ver_cluster/(?P<id_cluster>\d+)', 'c_center.views.see_cluster'),

    url(r'^alta_modelo_medidor/', 'c_center.views.add_powermetermodel'),
    url(r'^editar_modelo_medidor/(?P<id_powermetermodel>\d+)/', 'c_center.views.edit_powermetermodel'),
    url(r'^modelos_medidor/', 'c_center.views.view_powermetermodels'),

    url(r'^alta_medidor/', 'c_center.views.add_powermeter'),
    url(r'^editar_medidor/(?P<id_powermeter>\d+)/', 'c_center.views.edit_powermeter'),
    url(r'^medidores/', 'c_center.views.view_powermeter'),
    url(r'^eliminar_medidor/(?P<id_powermeter>\d+)', 'c_center.views.delete_powermeter'),
    url(r'^delete_batch_powermeter/$', 'c_center.views.delete_batch_powermeter'),
    url(r'^status_medidor/(?P<id_powermeter>\d+)', 'c_center.views.status_powermeter'),
    url(r'^ver_medidor/(?P<id_powermeter>\d+)', 'c_center.views.see_powermeter'),

    url(r'^alta_tipo_equipo_electrico/', 'c_center.views.add_electric_device_type'),
    url(r'^editar_tipo_equipo_electrico/(?P<id_edt>\d+)/', 'c_center.views.edit_electric_device_type'),
    url(r'^tipos_equipo_electrico/', 'c_center.views.view_electric_device_type'),
    url(r'^eliminar_tipo_equipo_electrico/(?P<id_edt>\d+)', 'c_center.views.delete_electric_device_type'),
    url(r'^delete_batch_electrictypedevice/$', 'c_center.views.delete_batch_electric_device_type'),
    url(r'^status_tipo_equipo_electrico/(?P<id_edt>\d+)', 'c_center.views.status_electric_device_type'),

    url(r'^alta_empresa/', 'c_center.views.add_company'),
    url(r'^editar_empresa/(?P<id_cpy>\d+)/', 'c_center.views.edit_company'),
    url(r'^empresas/', 'c_center.views.view_companies'),
    url(r'^eliminar_empresa/(?P<id_cpy>\d+)', 'c_center.views.delete_company'),
    url(r'^delete_batch_companies/$', 'c_center.views.delete_batch_companies'),
    url(r'^status_empresa/(?P<id_cpy>\d+)', 'c_center.views.status_company'),
    url(r'^ver_empresa/(?P<id_cpy>\d+)', 'c_center.views.see_company'),


)
