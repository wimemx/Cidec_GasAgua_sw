from django.conf.urls import patterns, include, url
from c_center import urls as c_center_urls
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

    # Uncomment the admin/doc line below to enable admin documentation:
    #url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
    (r'^grappelli/', include('grappelli.urls')),
)
