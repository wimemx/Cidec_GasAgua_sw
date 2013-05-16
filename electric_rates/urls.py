from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^alta_tarifa3/', 'electric_rates.views.add_tarifa3'),
    url(r'^editar_tarifa3/(?P<id_t3>\d+)/', 'electric_rates.views.edit_tarifa3'),
    url(r'^tarifa3/', 'electric_rates.views.view_tarifa_3'),

    url(r'^alta_tarifaHM/', 'electric_rates.views.add_tarifaHM'),
    url(r'^editar_tarifaHM/(?P<id_hm>\d+)/', 'electric_rates.views.edit_tarifaHM'),
    url(r'^tarifas/(?P<tarifa_n>\w+)/', 'electric_rates.views.tarifaHM_header'),
    url(r'^tabla_tarifaHM/','electric_rates.views.getRatesTable'),

    url(r'^alta_tarifaDac/', 'electric_rates.views.add_tarifaDac'),
    url(r'^editar_tarifaDac/(?P<id_dac>\d+)/', 'electric_rates.views.edit_tarifaDac'),
    url(r'^tarifaDac/', 'electric_rates.views.view_tarifa_DAC'),
)