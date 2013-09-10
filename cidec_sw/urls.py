from django.conf.urls import patterns, include, url
from c_center import urls as c_center_urls
from rbac import urls as rbac_urls
from location import urls as location_urls
from alarms import urls as alarms_urls
from electric_rates import urls as electric_rates_urls
# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()
from django.conf import settings

urlpatterns = patterns('',
    # Examples:
    url(r'^$', 'cidec_sw.views._login', name='home'),
    url(r'^logout/$', 'cidec_sw.views.logout_page'),
    url(r'^forgot_password/','rbac.views.forgot_password'),
    url(r'^main/', 'cidec_sw.views.index'),
    url(r'^medition_type_menu/', 'cidec_sw.views.medition_type_menu'),
    url(r'^restaurar_datos/', 'c_center.views.parse_csv'),
    url(r'^plupload/', 'plupload.views.upload_file'),
    url(r'^del_file/(\d{4})/(\d{2})/(\d+)/$',
        'plupload.views.del_file'),
    #retrieves a list of all files in a dir, change as convenient
    url(r'^get_all_files/(\d{4})/(\d{2})/(\d+)/$',
        'plupload.views.get_all_files'),

    url(r'^reportes/', include(c_center_urls)),
    #url(r'^reportes-extendidos/', include(reports_urls)),
    url(r'^buildings/', include(c_center_urls)),
    url(r'^panel_de_control/', include(rbac_urls)),
    url(r'^rbac/', include(rbac_urls)),
    url(r'^profile/', include(rbac_urls)),
    url(r'^location/', include(location_urls)),
    url(r'^configuracion/', include(alarms_urls)),
    url(r'^electric_rates/', include(electric_rates_urls)),
    url(r'^set_timezone/', 'cidec_sw.views.set_timezone', name="set_timezone"),
    url(r'^gas_medition/', 'gas_agua.views.gas_medition'),
    url(r'^water_medition/', 'gas_agua.views.water_medition'),
    url(r'^reportes_extendidos/', 'reports.views.render_instant_measurements'),
    url(r'^consumido_por_mes/',
        'reports.views.render_report_consumed_by_month'),
    url(r'^data/',
        'cidec_sw.views.serve_data'),
    url(r'^csv/',
        'reports.views.csv_report'),


    # Uncomment the admin/doc line below to enable admin documentation:
    #url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
    (r'^grappelli/', include('grappelli.urls')),
    (r'^static/(?P<path>.*)$', 'django.views.static.serve',
         {'document_root': settings.STATIC_ROOT}),
)
