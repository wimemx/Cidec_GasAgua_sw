from django.conf.urls import patterns, url

urlpatterns = patterns('',
                       url(r'^celery/', 'c_center.views.call_celery_delay'),
                       url(r'^graficas/', 'c_center.graphics.render_graphics'),
                       url(r'^graficas_extendidas/',
                           'c_center.graphics.render_graphics_extended'),
                       url(r'^grafica_datos_csv/',
                           'c_center.views.grafica_datoscsv'),
                       url(r'^grafica_tendencia_consumo_mensual/',
                           'c_center.graphics'
                           '.render_graphics_month_consumption_trend'),
                       url(r'^verificar_graficas_intervalos/',
                           'c_center.graphics'
                           '.render_graphics_interval_verification'),

                       url(r'^medition_rate/',
                           'c_center.calculations.tag_reading'),
                       url(r'^profile_for_serial/',
                           'c_center.c_center_functions.get_profile'),

                       url(r'^cfe/', 'c_center.views.cfe_bill'),
                       #url(r'^perfil_carga/', 'c_center.views.perfil_carga'),
                       #url(r'^perfil_carga_data/',
                       # 'c_center.views.get_pp_data'),
                       url(r'^set_default_building/(?P<id_building>\d+)/',
                           'c_center.views.set_default_building'),
                       url(r'^set_consumer_unit/',
                         'c_center.views.set_consumer_unit'),

                       url(r'^set_c_u/(?P<id_c_u>\d+)/',
                           'c_center.views.set_default_consumer_unit'),

                       #url(r'^weekly_summary_kwh/',
                       # 'c_center.views.get_weekly_summary_comparison_kwh'),
                       url(r'^week_comparison/',
                           'c_center.views'
                           '.render_cumulative_comparison_in_week'),
                       url(r'^cfe_calculos/',
                           'c_center.views.cfe_calculations'),

                       url(r'^get_cluster_companies/(?P<id_cluster>\d+)/',
                           'c_center.c_center_functions.get_cluster_companies'),
                       url(r'^get_company_buildings/(?P<id_company>\d+)/',
                           'c_center.c_center_functions.get_company_buildings'),
                       url(r'^get_parts_of_building/(?P<id_building>\d+)/',
                           'c_center.c_center_functions.get_parts_of_building'),

                       url(r'^agregar_atributo/',
                           'c_center.views.add_building_attr'),
                       url(r'^atributos/', 'c_center.views.b_attr_list'),
                       url(r'^eliminar_b_attr/(?P<id_b_attr>\d+)/',
                           'c_center.views.delete_b_attr'),
                       url(r'^editar_b_attr/(?P<id_b_attr>\d+)/',
                           'c_center.views.editar_b_attr'),
                       url(r'^ver_b_attr/(?P<id_b_attr>\d+)/',
                           'c_center.views.ver_b_attr'),
                       url(r'^status_batch_building_attr/',
                           'c_center.views.status_batch_building_attr'),

                       url(r'^clusters/', 'c_center.views.view_cluster'),
                       url(r'^nuevo_cluster/', 'c_center.views.add_cluster'),
                       url(r'^editar_cluster/(?P<id_cluster>\d+)/',
                           'c_center.views.edit_cluster'),
                       url(r'^status_cluster/(?P<id_cluster>\d+)',
                           'c_center.views.status_cluster'),
                       url(r'^status_batch_cluster/$',
                           'c_center.views.status_batch_cluster'),
                       url(r'^ver_cluster/(?P<id_cluster>\d+)',
                           'c_center.views.see_cluster'),

                       url(r'^alta_modelo_medidor/',
                           'c_center.views.add_powermetermodel'),
                       url(
                           r'^editar_modelo_medidor/'
                           r'(?P<id_powermetermodel>\d+)/',
                           'c_center.views.edit_powermetermodel'),
                       url(r'^modelos_medidor/',
                           'c_center.views.view_powermetermodels'),
                       url(r'^status_batch_powermetermodel/$',
                           'c_center.views.status_batch_powermetermodel'),
                       url(r'^status_modelomedidor/(?P<id_powermetermodel>\d+)',
                           'c_center.views.status_powermetermodel'),

                       url(r'^alta_medidor/', 'c_center.views.add_powermeter'),
                       url(r'^editar_medidor/(?P<id_powermeter>\d+)/',
                           'c_center.views.edit_powermeter'),
                       url(r'^medidores/', 'c_center.views.view_powermeter'),
                       url(r'^status_batch_powermeter/$',
                           'c_center.views.status_batch_powermeter'),
                       url(r'^status_medidor/(?P<id_powermeter>\d+)',
                           'c_center.views.status_powermeter'),
                       url(r'^ver_medidor/(?P<id_powermeter>\d+)',
                           'c_center.views.see_powermeter'),

                       url(r'^alta_tipo_equipo_electrico/',
                           'c_center.views.add_electric_device_type'),
                       url(r'^editar_tipo_equipo_electrico/(?P<id_edt>\d+)/',
                           'c_center.views.edit_electric_device_type'),
                       url(r'^tipos_equipo_electrico/',
                           'c_center.views.view_electric_device_type'),
                       url(r'^status_batch_electrictypedevice/$',
                           'c_center.views.status_batch_electric_device_type'),
                       url(r'^status_tipo_equipo_electrico/(?P<id_edt>\d+)',
                           'c_center.views.status_electric_device_type'),

                       url(r'^alta_empresa/', 'c_center.views.add_company'),
                       url(r'^editar_empresa/(?P<id_cpy>\d+)/',
                           'c_center.views.edit_company'),
                       url(r'^empresas/', 'c_center.views.view_companies'),
                       url(r'^status_batch_companies/$',
                           'c_center.views.status_batch_companies'),
                       url(r'^status_empresa/(?P<id_cpy>\d+)',
                           'c_center.views.status_company'),
                       url(r'^ver_empresa/(?P<id_cpy>\d+)',
                           'c_center.views.see_company'),

                       url(r'^estructura/$',
                           'c_center.views.c_center_structures'),

                       url(r'^alta_tipo_edificio/',
                           'c_center.views.add_buildingtype'),
                       url(r'^editar_tipo_edificio/(?P<id_btype>\d+)/',
                           'c_center.views.edit_buildingtype'),
                       url(r'^tipos_edificios/',
                           'c_center.views.view_buildingtypes'),
                       url(r'^status_batch_buildingtypes/$',
                           'c_center.views.status_batch_buildingtypes'),
                       url(r'^status_tipo_edificio/(?P<id_btype>\d+)',
                           'c_center.views.status_buildingtype'),

                       url(r'^alta_tipo_sector/',
                           'c_center.views.add_sectoraltype'),
                       url(r'^editar_tipo_sector/(?P<id_stype>\d+)/',
                           'c_center.views.edit_sectoraltype'),
                       url(r'^tipos_sectores/',
                           'c_center.views.view_sectoraltypes'),
                       url(r'^status_batch_sectoraltypes/$',
                           'c_center.views.status_batch_sectoraltypes'),
                       url(r'^status_tipo_sector/(?P<id_stype>\d+)',
                           'c_center.views.status_sectoraltype'),

                       url(r'^alta_tipo_atributo_edificio/',
                           'c_center.views.add_b_attributes_type'),
                       url(
                           r'^editar_tipo_atributo_edificio/('
                           r'?P<id_batype>\d+)/',
                           'c_center.views.edit_b_attributes_type'),
                       url(r'^tipos_atributos_edificios/',
                           'c_center.views.view_b_attributes_type'),
                       url(r'^status_batch_b_attributes_type/$',
                           'c_center.views.status_batch_b_attributes_type'),
                       url(r'^status_tipo_atributo_edificio/(?P<id_batype>\d+)',
                           'c_center.views.status_b_attributes_type'),

                       url(r'^alta_tipo_parte_edificio/',
                           'c_center.views.add_partbuildingtype'),
                       url(r'^editar_tipo_parte_edificio/(?P<id_pbtype>\d+)/',
                           'c_center.views.edit_partbuildingtype'),
                       url(r'^tipos_partes_edificio/',
                           'c_center.views.view_partbuildingtype'),
                       url(r'^status_batch_partbuildingtype/$',
                           'c_center.views.status_batch_partbuildingtype'),
                       url(r'^status_tipo_parte_edificio/(?P<id_pbtype>\d+)',
                           'c_center.views.status_partbuildingtype'),

                       url(r'^alta_parte_edificio/',
                           'c_center.views.add_partbuilding'),
                       url(r'^editar_parte_edificio/(?P<id_bpart>\d+)/',
                           'c_center.views.edit_partbuilding'),
                       url(r'^partes_edificio/',
                           'c_center.views.view_partbuilding'),
                       url(r'^status_batch_partbuilding/$',
                           'c_center.views.status_batch_partofbuilding'),
                       url(r'^status_parte_edificio/(?P<id_bpart>\d+)',
                           'c_center.views.status_partofbuilding'),

                       url(r'^search_buildings/',
                           'c_center.views.search_buildings'),
                       url(r'^get_attributes/(?P<id_attribute_type>\d+)',
                           'c_center.views.get_select_attributes'),

                       url(r'^alta_edificio/', 'c_center.views.add_building'),
                       url(r'^editar_edificio/(?P<id_bld>\d+)/',
                           'c_center.views.edit_building'),
                       url(r'^edificios/', 'c_center.views.view_building'),
                       url(r'^status_batch_building/$',
                           'c_center.views.status_batch_building'),
                       url(r'^status_edificio/(?P<id_bld>\d+)',
                           'c_center.views.status_building'),

                       url(r'^search_bld_country/',
                           'location.views.search_country'),
                       url(r'^search_bld_state/',
                           'location.views.search_state'),
                       url(r'^search_bld_municipality/',
                           'location.views.search_municipality'),
                       url(r'^search_bld_neighborhood/',
                           'location.views.search_neighboorhood'),
                       url(r'^search_bld_street/',
                           'location.views.search_street'),

                       url(r'^alta_ie/', 'c_center.views.add_ie'),
                       url(r'^editar_ie/(?P<id_ie>\d+)/',
                           'c_center.views.edit_ie'),
                       url(r'^asign_pm/(?P<id_ie>\d+)/',
                           'c_center.views.asign_pm'),
                       url(r'^detach_pm/(?P<id_ie>\d+)/',
                           'c_center.views.detach_pm'),

                       url(r'^industrial_equipments/',
                           'c_center.views.view_ie'),
                       url(r'^status_batch_ie/$',
                           'c_center.views.status_batch_ie'),
                       url(r'^status_ie/(?P<id_ie>\d+)',
                           'c_center.views.status_ie'),
                       url(r'^ver_ie/(?P<id_ie>\d+)',
                           'c_center.views.see_ie'),
                       url(r'^buscar_pm/',
                           'c_center.views.search_pm'),

                       url(r'^configurar_equipo_industrial/(?P<id_ie>\d+)/',
                           'c_center.views.configure_ie'),

                       url(r'^crear_jerarquia/(?P<id_building>\d+)/',
                           'c_center.views.create_hierarchy'),

                       url(r'^add_partbuilding_pop/(?P<id_building>\d+)/',
                           'c_center.views.add_partbuilding_pop'),
                       url(r'^save_add_part_popup/',
                           'c_center.views.save_add_part_popup'),

                       url(r'^add_powermeter_popup/',
                           'c_center.views.add_powermeter_popup'),
                       url(r'^save_add_powermeter_popup/',
                           'c_center.views.save_add_powermeter_popup'),

                       url(r'^add_electric_device_popup/',
                           'c_center.views.add_electric_device_popup'),
                       url(r'^save_add_electric_device_popup/',
                           'c_center.views.save_add_electric_device_popup'),

                       url(r'^add_cu/',
                           'c_center.views.add_cu'),
                       url(r'^del_cu/(?P<id_cu>\d+)/',
                           'c_center.views.del_cu'),

                       url(r'^editar_parte_edificio_popup/(?P<cu_id>\d+)/',
                           'c_center.views.popup_edit_partbuilding'),
                       url(r'^save_edit_part_popup/(?P<cu_id>\d+)/',
                           'c_center.views.save_edit_part_popup'),

                       url(r'^edit_cu/(?P<cu_id>\d+)/',
                           'c_center.views.edit_cu'),
                       url(r'^get_json_pw/$',
                           'c_center.c_center_functions.get_pw_profiles'),
                       url(r'^add_hierarchy_node/$',
                           'c_center.views.add_hierarchy_node'),
                       url(r'^reset_hierarchy/$',
                           'c_center.views.reset_hierarchy'),

                       url(r'^mediciones_pw/(?P<id_pw>\d+)/',
                           'c_center.views.pw_meditions'),

                       url(r'^fechas_corte/', 'c_center.views.view_cutdates'),
                       url(r'^establecer_fecha/(?P<id_cutdate>\d+)/',
                           'c_center.views.set_cutdate'),

                       url(r'^desglose/', 'c_center.views.cfe_desglose'),
                       url(r'^desglose_calculos/',
                           'c_center.views.cfe_desglose_calcs'),

                       url(r'^corte_recibo/(?P<id_cutdate>\d+)/',
                           'c_center.views.set_cutdate_bill_show'),
                       url(r'^set_cutdate_ajax/',
                           'c_center.views.set_cutdate_bill'),

                       url(r'^analisis_mensual/',
                           'c_center.views.montly_analitics'),
                       url(r'^analisis_facturacion/',
                           'c_center.views.billing_analisis_header'),
                       url(r'^analisis_fac_ajax/',
                           'c_center.views.billing_analisis'),
                       url(r'^analisis_costo_facturacion/',
                           'c_center.views.billing_c_analisis_header'),
                       url(r'^analisis_costo_fac_frame/',
                           'c_center.views.billing_cost_analisis'),
                       url(r'^desempenio_energetico/',
                           'c_center.views.power_performance_header'),
                       url(r'^desempenio_energetico_frame/',
                           'c_center.views.power_performance'),

                       url(r'^node/',
                           'django.views.generic.simple.direct_to_template',
                           {'template': 'test.html'}),

                       url(r'^month_analitics/(?P<id_building>\d+)/'
                           r'(?P<year>\d+)/(?P<month>\d+)/',
                           'c_center.views.montly_data_for_building'),
                       url(r'^month_analitics_h/(?P<id_building>\d+)/'
                           r'(?P<year>\d+)/(?P<month>\d+)/',
                           'c_center.views.montly_data_hfor_building'),
                       url(r'^month_analitics_week/(?P<id_building>\d+)/'
                           r'(?P<year>\d+)/(?P<month>\d+)/',
                           'c_center.views.montly_data_w_for_building'),
                       url(r'^month_analitics_day/(?P<id_building>\d+)/',
                           'c_center.views.month_analitics_day'),

)