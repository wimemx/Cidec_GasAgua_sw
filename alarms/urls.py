from django.conf.urls import patterns, url

urlpatterns = patterns('',
                       url(r'^send_mail/', 'alarms.views.send_notif_mail'),

                       url(r'^alta_alarma/',
                           'alarms.views.add_alarm'),
                       url(r'^editar_alarma/(?P<id_alarm>\d+)/',
                           'alarms.views.edit_alarm'),
                       url(r'^suscripcion_alarma/(?P<id_alarm>\d+)/',
                           'alarms.views.suscribe_alarm'),
                       url(r'^desuscribir_alarma/(?P<id_alarm>\d+)/',
                           'alarms.views.unsuscribe_alarm'),

                       url(r'^status_batch_alarm/$',
                           'alarms.views.status_batch_alarm'),
                       url(r'^status_alarm/(?P<id_alarm>\d+)',
                           'alarms.views.status_alarm'),
                       url(r'^alarmas/', 'alarms.views.alarm_list'),
                       url(r'^suscripcion_alarma/',
                           'alarms.views.alarm_suscription_list'),
                       url(r'^alta_suscripcion_alarma/',
                           'alarms.views.add_alarm_suscription'),
                       url(r'^alarma/(?P<id_alarm>\d+)/',
                           'alarms.views.see_alarm'),
                       url(r'^buscar_alarma/',
                           'alarms.views.search_alarm'),
                       )




