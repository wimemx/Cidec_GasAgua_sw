from django.conf.urls import patterns, url

urlpatterns = patterns('',
        url(r'^tiempos/', 'alarms.views.see_times'),
        url(r'^tiempos/inds_eq/', 'alarms.views.change_ie_time_config'),
        url(r'^send_mail/','alarms.views.send_notif_mail'),

        url(r'^alta_alarma/','alarms.views.add_alarm'),
        url(r'^ver_alarmas/','alarms.views.alarm_list'),
        url(r'^suscripcion_alarma/','alarms.views.suscribe_alarm'),
        url(r'^editar_alarma/','alarms.views.edit_alarm'),
)