from django.conf.urls import patterns, include, url
from c_center import urls as c_center_urls
from rbac import urls as rbac_urls
from location import urls as location_urls
from alarms import urls as alarms_urls
# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    url(r'^$', 'cidec_sw.views._login', name='home'),
    url(r'^logout/$', 'cidec_sw.views.logout_page'),
    url(r'^main/', 'cidec_sw.views.index'),
    url(r'^parse/', 'cidec_sw.views.parse_csv'),
    url(r'^reportes/', include(c_center_urls)),
    url(r'^buildings/', include(c_center_urls)),
    url(r'^panel_de_control/', include(rbac_urls)),
    url(r'^rbac/', include(rbac_urls)),
    url(r'^profile/', include(rbac_urls)),
    url(r'^location/', include(location_urls)),
    url(r'^configuracion/', include(alarms_urls)),
    #url(r'^prueba_cfe/', 'c_center.calculations.recibocfe'),
    url(r'^set_timezone/', 'cidec_sw.views.set_timezone', name="set_timezone"),

    # Url used for prototypes
    url(r'^prototype/', 'data_warehouse.prototype.render_prototype'),

    # Uncomment the admin/doc line below to enable admin documentation:
    #url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
    (r'^grappelli/', include('grappelli.urls')),
)
