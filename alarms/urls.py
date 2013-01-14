from django.conf.urls import patterns, url

urlpatterns = patterns('',
                       url(r'^tiempos/', 'alarms.views.see_times'),
                       url(r'^tiempos/inds_eq/',
                           'alarms.views.change_ie_time_config'),
                       url(r'^send_mail/','alarms.views.send_notif_mail')
                       )