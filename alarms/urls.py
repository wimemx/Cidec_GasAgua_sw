from django.conf.urls import patterns, url

urlpatterns = patterns('',
                       url(r'^send_mail/', 'alarms.views.send_notif_mail'),

                       url(r'^alta_alarma/',
                           'alarms.views.add_alarm'),
                       url(r'^editar_alarma/(?P<id_alarm>\d+)/',
                           'alarms.views.edit_alarm'),

                       url(r'^status_batch_alarm/$',
                           'alarms.views.status_batch_alarm'),
                       url(r'^status_suscription_batch_alarm/$',
                           'alarms.views.status_suscription_batch_alarm'),
                       url(r'^status_alarm/(?P<id_alarm>\d+)',
                           'alarms.views.status_alarm'),
                       url(r'^status_suscription_alarm/(?P<id_alarm>\d+)',
                           'alarms.views.status_suscription_alarm'),
                       url(r'^alarmas/', 'alarms.views.alarm_list'),
                       url(r'^suscripcion_alarma/',
                           'alarms.views.alarm_suscription_list'),
                       url(r'^alta_suscripcion_alarma/',
                           'alarms.views.add_alarm_suscription'),
                       url(r'^editar_suscripcion_alarma/(?P<id_alarm>\d+)',
                           'alarms.views.edit_alarm_suscription'),
                       url(r'^alarma/(?P<id_alarm>\d+)/',
                           'alarms.views.mostrar_alarma'),
                       url(r'^alarma_suscripcion/(?P<id_alarm>\d+)/',
                           'alarms.views.mostrar_suscripcion_alarma'),

                       url(r'^get_unread_notifs_count/',
                           'alarms.views.get_unread_notifs_count'),
                       url(r'^user_notifications/',
                           'alarms.views.user_notifications'),
                       url(r'^get_latest_notifs/',
                           'alarms.views.get_latest_notifs'),

                       url(r'^refresh_ie_config/',
                           'alarms.views.refresh_ie_config'),

                       )




