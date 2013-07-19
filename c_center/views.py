# -*- coding: utf-8 -*-
#standard library imports
import datetime
from dateutil.relativedelta import relativedelta
from math import *
import Image
import cStringIO
import os
from django.core.files import File
import hashlib
import csv
import re
import time
import pytz
import locale
#related third party imports
import variety

#from PIL import *

#local application/library specific imports
from django.shortcuts import render_to_response, get_object_or_404, render
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.context import RequestContext
from django.utils import timezone
from django.db.models.aggregates import *
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.contrib.auth.decorators import login_required

from django_tables2 import RequestConfig

from cidec_sw import settings
from c_center.calculations import *
from alarms.models import Alarms, AlarmEvents, ElectricParameters
from c_center.models import *
from location.models import *
from data_warehouse_extended.models import InstantDelta, ConsumerUnitProfile
from electric_rates.models import ElectricRatesDetail, DACElectricRateDetail, \
    ThreeElectricRateDetail
from rbac.models import Operation, DataContextPermission, UserRole, Object, \
    PermissionAsigment, GroupObject
from rbac.rbac_functions import has_permission, get_buildings_context, \
    default_consumerUnit
from c_center_functions import *

from c_center.graphics import *
from data_warehouse.views import get_consumer_unit_electric_data_csv, \
    get_consumer_unit_electric_data_interval_csv, \
    DataWarehouseInformationRetrieveException, \
    get_consumer_unit_by_id as get_data_warehouse_consumer_unit_by_id, \
    get_consumer_unit_electric_data_interval_tuple_list

from alarms.alarm_functions import set_alarm_json

import data_warehouse_extended.models

from .tables import ElectricDataTempTable, ThemedElectricDataTempTable

import json as simplejson
import sys
from tareas.tasks import save_historic_delay, \
    change_profile_electric_data, populate_data_warehouse_extended, \
    populate_data_warehouse_specific, restore_data, tag_batch_cu, \
    daily_report_period, tag_n_daily_report, calculateMonthlyReportCU

VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")

GRAPHS_ENERGY = GroupObject.objects.filter(
    group__group_name="Energía").values_list("object__pk", flat=True)
GRAPHS_I = GroupObject.objects.filter(
    group__group_name="Corriente").values_list("object__pk", flat=True)
GRAPHS_V = GroupObject.objects.filter(
    group__group_name="Voltaje").values_list("object__pk", flat=True)
GRAPHS_PF = GroupObject.objects.filter(
    group__group_name="Perfil de carga").values_list("object__pk", flat=True)
GRAPHS_F1 = GroupObject.objects.filter(
    group__group_name="Fase 1").values_list("object__pk", flat=True)
GRAPHS_F2 = GroupObject.objects.filter(
    group__group_name="Fase 2").values_list("object__pk", flat=True)
GRAPHS_F3 = GroupObject.objects.filter(
    group__group_name="Fase 3").values_list("object__pk", flat=True)
GRAPHS_CACUM = GroupObject.objects.filter(
    group__group_name="Consumo Acumulado").values_list("object__pk", flat=True)
GRAPHS_CONS = GroupObject.objects.filter(
    group__group_name="Consumo").values_list("object__pk", flat=True)
GRAPHS = dict(energia=GRAPHS_ENERGY, corriente=GRAPHS_I, voltaje=GRAPHS_V,
              perfil_carga=GRAPHS_PF, perfil_carga_mes=GRAPHS_PF,
              fase1=GRAPHS_F1, fase2=GRAPHS_F2,
              fase3=GRAPHS_F3, consumo_acumulado=GRAPHS_CACUM,
              consumo=GRAPHS_CONS)

VIRTUAL_PROFILE = ProfilePowermeter.objects.get(
    powermeter__powermeter_anotation="Medidor Virtual")

MSG_PERMIT_ERROR = "<h2 style='font-family: helvetica; color: #878787; " \
                   "font-size:14px;' text-align: center;>" \
                   "No hay unidades de consumo asignadas, " \
                   "por favor ponte en contacto con el administrador para " \
                   "remediar esta situaci&oacute;n</h2>"

FILE_FOLDER = "templates/static/media/csv_files/"

@login_required(login_url='/')
def call_celery_delay(request):
    if request.user.is_superuser:
        if request.method == "POST":
            text = '<h3>Se calcular&aacute;n: </h3>'
            almenosuno = False
            if "instantes" in request.POST:
                fill_instants = True
                text += "instantes<br/>"
                almenosuno = True
            else:
                fill_instants = None
            if "intervalos" in request.POST:
                fill_intervals = True
                text += "intervalos<br/>"
                almenosuno = True
            else:
                fill_intervals = None
            if "consumer_units" in request.POST:
                _update_consumer_units = True
                text += "consumer_units<br/>"
                almenosuno = True
            else:
                _update_consumer_units = None
            if "instant_facts" in request.POST:
                populate_instant_facts = True
                text += "instant_facts<br/>"
                almenosuno = True
            else:
                populate_instant_facts = None
            if "interval_facts" in request.POST:
                populate_interval_facts = True
                text += "interval_facts<br/>"
                almenosuno = True
            else:
                populate_interval_facts = None
            if almenosuno:
                populate_data_warehouse_extended(
                    fill_instants,
                    _update_consumer_units,
                    populate_instant_facts
                )
            else:
                text = "No se realizar&aacute; ninguna acci&oacute;n"
        else:
            text = ''
        template_vars = dict(text=text)
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("tasks/datawarehouse_populate.html",
                                  template_vars_template)
    else:
        raise Http404

@login_required(login_url='/')
def dw_specific(request):
    datacontext, b_list = get_buildings_context(request.user)
    if datacontext:
        template_vars = {"datacontext": datacontext}
    else:
        template_vars = dict()
    if request.user.is_superuser:
        granul = data_warehouse_extended.models.InstantDelta.objects.all()
        consumer_units = data_warehouse_extended.models.ConsumerUnitProfile\
            .objects.all()
        template_vars['deltas'] = granul
        template_vars['consumer_units'] = consumer_units

        if request.method == "POST":
            fecha = datetime.datetime.strptime(
                request.POST['date_from'], "%Y-%m-%d")
            cu = data_warehouse_extended.models.ConsumerUnitProfile.objects.get(
                transactional_id=int(request.POST['consumer_unit'])
            )
            delta = data_warehouse_extended.models.InstantDelta.objects.get(
                pk=int(request.POST['intervalos'])
            )
            populate_data_warehouse_specific(cu, delta, fecha)
            template_vars['text'] = "Tarea enviada, para " + cu.building_name \
                                    + " - " + cu.electric_device_type_name + \
                                    " con granularidad " + delta.name \
                                    + ". Espera resultados"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("tasks/data_warehouse_specific.html",
                                  template_vars_template)
    else:
        raise Http404


@login_required(login_url='/')
def set_default_building(request, id_building):
    """Sets the default building for reports"""
    request.session['main_building'] = Building.objects.get(pk=id_building)
    request.session['timezone']= get_google_timezone(
        request.session['main_building'])
    tz = pytz.timezone(request.session.get('timezone'))
    if tz:
        timezone.activate(tz)
    c_b = CompanyBuilding.objects.get(building=request.session['main_building'])
    request.session['company'] = c_b.company
    request.session['consumer_unit'] = \
        default_consumerUnit(request.session['main_building'])

    if request.session['consumer_unit']:
        dicc = dict(edificio=request.session['main_building'].building_name,
                    electric_device_type=request.session['consumer_unit']
                    .electric_device_type.electric_device_type_name)
        data = simplejson.dumps(dicc)
        if 'referer' in request.GET:
            if request.GET['referer'] == "cfe":
                return HttpResponseRedirect("/reportes/cfe/")
    else:
        data = ""
    return HttpResponse(content=data, content_type="application/json")


@login_required(login_url='/')
def set_consumer_unit(request):
    building = request.session['main_building']

    hierarchy_list = get_hierarchy_list(building, request.user)
    template_vars = dict(hierarchy=hierarchy_list)
    template_vars_template = RequestContext(request, template_vars)

    return render_to_response("consumption_centers/choose_hierarchy.html",
                              template_vars_template)


@login_required(login_url='/')
def set_default_consumer_unit(request, id_c_u):
    """Sets the consumer_unit for all the reports"""
    c_unit = ConsumerUnit.objects.get(pk=id_c_u)
    request.session['consumer_unit'] = c_unit
    return HttpResponse(status=200)


def week_report_kwh(request):
    """ Index page?
    shows a report of the consumed kwh in the current week
    """
    datacontext, buildings = get_buildings_context(request.user)
    if not datacontext:
        request.session['consumer_unit'] = None
    set_default_session_vars(request, buildings)

    if request.session['consumer_unit'] and request.session['main_building']:
        graphs = graphs_permission(request.user,
                                   request.session['consumer_unit'],
                                   GRAPHS['energia'])
        if graphs:
            consumer_unit = request.session['consumer_unit']
            datetime_current = datetime.datetime.now()
            year_current = datetime_current.year
            month_current = datetime_current.month
            week_current = variety.get_week_of_month_from_datetime(
                datetime_current)
            week_report_cumulative, week_report_cumulative_total = \
                get_consumer_unit_week_report_cumulative(consumer_unit,
                                                         year_current,
                                                         month_current,
                                                         week_current,
                                                         "kWh")

            week_start_datetime, week_end_datetime = \
                variety.get_week_start_datetime_end_datetime_tuple(
                    year_current, month_current, week_current)

            template_vars = dict(
                datacontext=datacontext, fi=week_start_datetime.date(),
                ff=(week_end_datetime - datetime.timedelta(days=1)).date(),
                empresa=request.session['main_building'],
                company=request.session['company'],
                consumer_unit=request.session['consumer_unit'],
                sidebar=request.session['sidebar'],
                electric_data_name="kWh",
                week_report_cumulative=week_report_cumulative,
                week_report_cumulative_total=week_report_cumulative_total)

            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/main.html",
                                      template_vars_template)
        else:
            template_vars = dict(
                datacontext=datacontext,
                empresa=request.session['main_building'],
                company=request.session['company'],
                consumer_unit=request.session['consumer_unit'],
                sidebar=request.session['sidebar'])
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("generic_error.html",
                                      template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("empty.html", template_vars_template)


def main_page(request):
    """Main Page
    in the mean time the main view is the graphics view
    sets the session variables needed to show graphs
    """
    datacontext, b_list = get_buildings_context(request.user)
    if not datacontext:
        request.session['consumer_unit'] = None
        print "set consumer unit to none"
    set_default_session_vars(request, b_list)

    if request.session['consumer_unit'] and request.session['main_building']:
        if "g_type" not in request.GET:
            graphs_type = GRAPHS['energia']
        else:
            try:
                graphs_type = GRAPHS[request.GET['g_type']]
            except KeyError:
                graphs_type = GRAPHS['energia']

        graphs = graphs_permission(request.user,
                                   request.session['consumer_unit'],
                                   graphs_type)
        if graphs:
            template_vars = {"graph_type": graphs[0],
                             "datacontext": datacontext,
                             'empresa': request.session['main_building'],
                             'company': request.session['company'],
                             'consumer_unit': request.session['consumer_unit'],
                             'sidebar': request.session['sidebar']}
            template_vars_template = RequestContext(request, template_vars)
            if request.GET['g_type'] == "consumo_acumulado":
                template_vars['years'] = request.session['years']
                template = "consumption_centers/graphs/main_consumed.html"
            elif request.GET['g_type'] == "perfil_carga_mes":
                template_vars['years'] = request.session['years']
                template = "consumption_centers/graphs/main_pprofile_month.html"
            else:
                template = "consumption_centers/graphs/main.html"
            return render_to_response(template,
                                      template_vars_template)
        else:
            template_vars = {'datacontext': datacontext,
                             'empresa': request.session['main_building'],
                             'company': request.session['company'],
                             'consumer_unit': request.session['consumer_unit'],
                             'sidebar': request.session['sidebar']}

            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("generic_error.html",
                                      template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("empty.html", template_vars_template)


# noinspection PyArgumentList
@login_required(login_url='/')
def cfe_bill(request):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW,
                      "Consultar recibo CFE") or request.user.is_superuser:
        set_default_session_vars(request, datacontext)

        today = datetime.datetime.today().replace(
            hour=0, minute=0, second=0, tzinfo=timezone.get_current_timezone())
        month = int(today.month)
        year = int(today.year)
        dict(one=1, two=2)
        month_list = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
                      5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
                      9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre',
                      12: 'Diciembre'}
        year_list = {2010: 2010, 2011: 2011, 2012: 2012, 2013: 2013}

        template_vars = {"type": "cfe", "datacontext": datacontext,
                         'empresa': request.session['main_building'],
                         'company': request.session['company'],
                         'month': month, 'year': year, 'month_list': month_list,
                         'year_list': year_list,
                         'sidebar': request.session['sidebar']}

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/cfe.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html",
                                  RequestContext(request,
                                                 {"datacontext": datacontext}))


# noinspection PyArgumentList
@login_required(login_url='/')
def cfe_calculations(request):
    """Renders the cfe bill and the historic data chart"""
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW,
                      "Consultar recibo CFE") or request.user.is_superuser:
        if not request.session['consumer_unit']:
            return HttpResponse(
                content=MSG_PERMIT_ERROR)

        set_default_session_vars(request, datacontext)
        print "Offset", request.session['timezone']

        template_vars = dict(type="cfe", datacontext=datacontext,
                             empresa=request.session['main_building'])

        #print "Edifico", request.session['main_building']

        if request.GET:
            month = int(request.GET['month'])
            year = int(request.GET['year'])
        else:
        #Obtener la fecha actual
            today = datetime.datetime.today().replace(
                hour=0, minute=0,  second=0,
                tzinfo=timezone.get_current_timezone())
            month = int(today.month)
            year = int(today.year)

        #Se buscan los datos en el historico
        # noinspection PyArgumentList
        billing_month = datetime.date(year=year, month=month, day=1)

        #Se obtiene el tipo de tarifa del edificio (HM o DAC)
        tipo_tarifa = request.session['main_building'].electric_rate

        if tipo_tarifa.pk == 1:
        #Tarifa HM
            #print "Historico HM"
            cfe_historico = HMHistoricData.objects.filter(
                monthly_cut_dates__building=request.session['main_building']
            ).filter(
                monthly_cut_dates__billing_month=billing_month)
        elif tipo_tarifa.pk == 2:
        #Tarifa DAC
            #print "Historico DAC"
            cfe_historico = DacHistoricData.objects.filter(
                monthly_cut_dates__building=request.session['main_building']
            ).filter(
                monthly_cut_dates__billing_month=billing_month)
        else:
            #print "Historico T3"
            #if tipo_tarifa.pk == 3: #Tarifa 3
            cfe_historico = T3HistoricData.objects.filter(
                monthly_cut_dates__building=request.session['main_building']
            ).filter(
                monthly_cut_dates__billing_month=billing_month)

        #Si hay información en la tabla del historico, toma los datos
        resultado_mensual = {}
        if cfe_historico:
            #Tarifa HM
            if tipo_tarifa.pk == 1:
                resultado_mensual["kw_base"] = \
                    cfe_historico[0].KW_base
                resultado_mensual["kw_intermedio"] =\
                    cfe_historico[0].KW_intermedio
                resultado_mensual["kw_punta"] = \
                    cfe_historico[0].KW_punta

                resultado_mensual["kwh_base"] = \
                    cfe_historico[0].KWH_base
                resultado_mensual["kwh_intermedio"] =\
                    cfe_historico[0].KWH_intermedio
                resultado_mensual["kwh_punta"] = \
                    cfe_historico[0].KWH_punta
                resultado_mensual["kwh_totales"] = \
                    cfe_historico[0].KWH_total

                fecha_ini = cfe_historico[0].monthly_cut_dates.date_init.\
                    astimezone(timezone.get_current_timezone()).\
                    strftime('%d/%m/%Y %I:%M %p')
                fecha_fin = cfe_historico[0].monthly_cut_dates.date_end.\
                    astimezone(timezone.get_current_timezone()).\
                    strftime('%d/%m/%Y %I:%M %p')

                periodo = fecha_ini + " - " + fecha_fin

                resultado_mensual['periodo'] = periodo
                resultado_mensual['corte'] = cfe_historico[0].monthly_cut_dates
                resultado_mensual['demanda_facturable'] =\
                    cfe_historico[0].billable_demand
                resultado_mensual['factor_potencia'] = \
                    cfe_historico[0].power_factor
                resultado_mensual['factor_carga'] = \
                    cfe_historico[0].charge_factor
                resultado_mensual['kvarh_totales'] = \
                    cfe_historico[0].KVARH
                resultado_mensual['tarifa_kwhb'] = \
                    cfe_historico[0].KWH_base_rate
                resultado_mensual['tarifa_kwhi'] = \
                    cfe_historico[0].KWH_intermedio_rate
                resultado_mensual['tarifa_kwhp'] = \
                    cfe_historico[0].KWH_punta_rate
                resultado_mensual['tarifa_df'] = \
                    cfe_historico[0].billable_demand_rate
                resultado_mensual['costo_energia'] =\
                    cfe_historico[0].energy_cost
                resultado_mensual['costo_dfacturable'] =\
                    cfe_historico[0].billable_demand_cost
                resultado_mensual['costo_fpotencia'] =\
                    cfe_historico[0].power_factor_bonification
                resultado_mensual['subtotal'] = \
                    cfe_historico[0].subtotal
                resultado_mensual['iva'] = \
                    cfe_historico[0].iva
                resultado_mensual['total'] = \
                    cfe_historico[0].total
                resultado_mensual['status'] = 'OK'

            #Tarifa Dac
            if tipo_tarifa.pk == 2:

                periodo = cfe_historico[0].monthly_cut_dates.date_init. \
                              astimezone(timezone.get_current_timezone()). \
                              strftime('%d/%m/%Y %I:%M %p') + " - " + \
                          cfe_historico[0].monthly_cut_dates.date_end. \
                              astimezone(timezone.get_current_timezone()). \
                              strftime('%d/%m/%Y %I:%M %p')

                resultado_mensual['periodo'] = periodo
                resultado_mensual['corte'] = cfe_historico[0].monthly_cut_dates
                resultado_mensual['kwh_totales'] = cfe_historico[0].KWH_total
                resultado_mensual['tarifa_kwh'] = cfe_historico[0].KWH_rate
                resultado_mensual['tarifa_mes'] = cfe_historico[0].monthly_rate
                resultado_mensual['importe'] = cfe_historico[0].energy_cost
                resultado_mensual['costo_energia'] = cfe_historico[0].subtotal
                resultado_mensual['iva'] = cfe_historico[0].iva
                resultado_mensual['total'] = cfe_historico[0].total
                resultado_mensual['status'] = 'OK'

            #Tarifa 3
            if tipo_tarifa.pk == 3:

                periodo = cfe_historico[0].monthly_cut_dates.date_init.\
                              astimezone(timezone.get_current_timezone()).\
                              strftime('%d/%m/%Y %I:%M %p') + " - " + \
                          cfe_historico[0].monthly_cut_dates.date_end.\
                              astimezone(timezone.get_current_timezone()).\
                              strftime('%d/%m/%Y %I:%M %p')

                resultado_mensual['periodo'] = periodo
                resultado_mensual['corte'] = cfe_historico[0].monthly_cut_dates
                resultado_mensual['kwh_totales'] = cfe_historico[0].KWH_total
                resultado_mensual['tarifa_kwh'] = cfe_historico[0].KWH_rate
                resultado_mensual['kw_totales'] = cfe_historico[0].max_demand
                resultado_mensual['tarifa_kw'] = cfe_historico[0].demand_rate
                resultado_mensual['factor_potencia'] = \
                    cfe_historico[0].power_factor
                resultado_mensual['costo_energia'] = \
                    cfe_historico[0].energy_cost
                resultado_mensual['costo_demanda'] = \
                    cfe_historico[0].demand_cost
                resultado_mensual['costo_fpotencia'] = \
                    cfe_historico[0].power_factor_bonification
                resultado_mensual['subtotal'] = cfe_historico[0].subtotal
                resultado_mensual['iva'] = cfe_historico[0].iva
                resultado_mensual['total'] = cfe_historico[0].total
                resultado_mensual['status'] = 'OK'

            template_vars['control'] = cfe_historico[0].monthly_cut_dates.pk

        else:
        #si no, hace el calculo al momento. NOTA: Se hace el calculo,
        # pero no se guarda
            #Se obtiene la fecha inicial y la fecha final
            #print "Se calcula el recibe"
            building = request.session['main_building']
            #print "Edificio", building
            hasDates = inMonthlyCutdates(building, month, year)
            if hasDates:
                s_date, e_date = getStartEndDateUTC(building, month, year)
                resultado_mensual['corte'] = getMonthlyCutDate(building, month,
                                                               year)
                template_vars['control'] = resultado_mensual['corte'].pk
            else:
                template_vars['control'] = "NO tiene fechas"
                s_date, e_date = getStartEndDateUTC(building, month, year)
                #La siguiente sección sirve para poner al corriente las
                #fechas de corte.

                #Se obtiene el número de días entre la fecha final y la
                #fecha inicial
                num_dias = (e_date - s_date).days

                #Si son más de 30 dias es necesario poner al corriente las
                #fechas de corte
                if num_dias > 35:

                    meses_restantes = num_dias / 30
                    c_meses = 0
                    while c_meses < meses_restantes:
                        #Se obtiene la última fecha de corte
                        last_cutdates = MonthlyCutDates.objects.filter(
                            building=building).order_by("-billing_month")
                        last_cutdate = last_cutdates[0]

                        #A la fecha inicial se le suman 30 dias, para obtener
                        #la fecha final y se guarda
                        last_cutdate.date_end = last_cutdate.date_init + \
                                                relativedelta(days=+30)
                        last_cutdate.save()

                        #Se genera el recibo de la CFE y se guarda
                        save_historic_delay.delay(last_cutdate, building)

                        #Se guarda el siguiente mes de facturación.
                        #Fecha inicial = fecha final del mes anterior.
                        #Fecha final = vacía
                        billing_month = last_cutdate.billing_month + \
                                        relativedelta(months=+1)
                        new_cut = MonthlyCutDates(
                            building=building,
                            billing_month=billing_month,
                            date_init=last_cutdate.date_end
                        )
                        new_cut.save()

                        c_meses += 1
                elif num_dias < 30:
                    cut_date_lb = s_date + relativedelta(days=+30)
                    template_vars['message'] = \
                        'El corte para este mes se realizará ' \
                        'automáticamente el día ' + \
                        cut_date_lb.strftime("%d/%m/%Y")
                    template_vars['type'] = "n_notif"
                elif 30 <= num_dias <= 35:
                    template_vars['message'] = 'La facturación para este ' \
                                               'mes ya rebasa los 30 días. ' \
                                               'Selecciona la fecha de corte ' \
                                               '<a href="#">aquí</a>'
                    template_vars['type'] = "n_error"
                    template_vars['morethan30'] = True


                #Se obtienen nuevamente las fechas
                s_date, e_date = getStartEndDateUTC(building, month, year)

            #Se general el recibo.
            if tipo_tarifa.pk == 1: #Tarifa HM
                #print "Calculo Tarifa HM"
                resultado_mensual = tarifaHM_2(request.session['main_building'],
                                               s_date, e_date, month, year)

            elif tipo_tarifa.pk == 2: #Tarifa DAC
                #print "Calculo Tarifa DAC"
                resultado_mensual = tarifaDAC_2(
                    request.session['main_building'], s_date, e_date, month,
                    year)

            elif tipo_tarifa.pk == 3: #Tarifa 3
                #print "Calculo Tarifa 3"
                resultado_mensual = tarifa_3(
                    request.session['main_building'], s_date, e_date, month,
                    year)


            resultado_mensual['corte'] = getMonthlyCutDate(building, month,
                                                           year)
            template_vars['control'] = resultado_mensual['corte'].pk

        if resultado_mensual['status'] == 'OK':
            template_vars['resultados'] = resultado_mensual
            template_vars['tipo_tarifa'] = tipo_tarifa

            template_vars['historico'] = obtenerHistorico_r(resultado_mensual)
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response(
                "consumption_centers/graphs/cfe_bill.html",
                template_vars_template)
        if resultado_mensual['status'] == 'ERROR':
            template_vars['mensaje'] = resultado_mensual['mensaje']
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response(
                "consumption_centers/graphs/cfe_bill_error.html",
                template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


# noinspection PyArgumentList
def getStartEndDateUTC(building, month, year):
    billing_month = datetime.date(year=year, month=month, day=1)

    #Se obtienen las fechas de inicio y de fin para ese mes
    try:
        month_cut_dates = MonthlyCutDates.objects.get(
            building=building, billing_month=billing_month
        )
    except MonthlyCutDates.DoesNotExist:
        month_all_cut_dates = MonthlyCutDates.objects.filter(
            building=building).order_by("-billing_month")
        month_cut_dates = month_all_cut_dates[0]

    #Se obtiene la fecha de inicio
    s_date = month_cut_dates.date_init

    #Se obtiene la fecha final
    if month_cut_dates.date_end:
        e_date = month_cut_dates.date_end
    else:
        #Si no tiene fecha final, se toma el día de hoy
        # (debe estar en formato, UTC)
        e_date = datetime.datetime.today().utcnow().replace(tzinfo=pytz.utc)

    return s_date, e_date


# noinspection PyArgumentList
def getMonthlyCutDate(building, month, year):
    billing_month = datetime.date(year=year, month=month, day=1)

    #Se obtienen las fechas de inicio y de fin para ese mes
    try:
        month_cut_dates = MonthlyCutDates.objects.get(
            building=building, billing_month=billing_month
        )
    except MonthlyCutDates.DoesNotExist:
        month_all_cut_dates = MonthlyCutDates.objects.filter(
            building=building).order_by("-billing_month")
        month_cut_dates = month_all_cut_dates[0]

    return month_cut_dates


# noinspection PyArgumentList
def inMonthlyCutdates(building, month, year):
    billing_month = datetime.date(year=year, month=month, day=1)

    #Se obtienen las fechas de inicio y de fin para ese mes
    try:
        month_cut_dates = MonthlyCutDates.objects.get(
            building=building, billing_month=billing_month
        )
    except MonthlyCutDates.DoesNotExist:
        return False

    #Se obtiene la fecha final
    if not month_cut_dates.date_end:
        return False

    return True

# noinspection PyArgumentList
def getStartEndDate(building, month, year):
    billing_month = datetime.date(year=year, month=month, day=1)

    try:
        month_cut_dates = MonthlyCutDates.objects.get(
            building=building, billing_month=billing_month)
    except MonthlyCutDates.DoesNotExist:
        month_all_cut_dates = MonthlyCutDates.objects.filter(
            building=building).order_by("-billing_month")
        month_cut_dates = month_all_cut_dates[0]

        #Se obtiene la fecha de inicio
    s_date = datetime.datetime(year=month_cut_dates.date_init.year,
                               month=month_cut_dates.date_init.month,
                               day=month_cut_dates.date_init.day,
                               tzinfo=timezone.get_current_timezone()
    )

    #Si la fecha de fin no es nula
    if month_cut_dates.date_end:
        e_date = datetime.datetime(year=month_cut_dates.date_end.year,
                                   month=month_cut_dates.date_end.month,
                                   day=month_cut_dates.date_end.day,
                                   tzinfo=timezone.get_current_timezone()
        )
    else: #Si la fecha de fin es nula, se toma el dia de hoy
        e_date = datetime.datetime.today().replace(
            tzinfo=timezone
            .get_current_timezone())

    return s_date, e_date


def grafica_datoscsv(request):
    if request.method == "GET":
        #electric_data = ""
        #granularity = "day"
        try:
            #electric_data = request.GET['graph']
            granularity = request.GET['granularity']

        except KeyError:
            raise Http404

        #suffix_consumed = "_consumido"
        is_interval = False
        #suffix_index = string.find(electric_data, suffix_consumed)
        #if suffix_index >= 0:
        #    electric_data = electric_data[:suffix_index]
        #    is_interval = True

        data = []
        consumer_unit_counter = 1
        consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
        date_start_get_key = "date-from%02d" % consumer_unit_counter
        date_end_get_key = "date-to%02d" % consumer_unit_counter
        electric_param_key = "electrical-parameter-name%02d" % consumer_unit_counter
        report_name = ""
        while request.GET.has_key(consumer_unit_get_key):
            consumer_unit_id = request.GET[consumer_unit_get_key]
            electric_data = request.GET[electric_param_key]
            report_name += electric_data + "_"
            print "date_start_get_key", date_start_get_key
            if request.GET.has_key(date_start_get_key) and \
                    request.GET.has_key(date_end_get_key):
                datetime_start = datetime.datetime.strptime(
                    request.GET[date_start_get_key],
                    "%Y-%m-%d")
                datetime_end = \
                    datetime.datetime.strptime(request.GET[date_end_get_key],
                                               "%Y-%m-%d") + \
                    datetime.timedelta(days=1)

            else:
                datetime_start = get_default_datetime_start()
                datetime_end = get_default_datetime_end() + datetime.timedelta(
                    days=1)
            #print "consumer_unit_counter" + str(consumer_unit_counter)
            #print "datetime_start", datetime_start
            #print "datetime_end", datetime_end
            try:
                consumer_unit = get_data_warehouse_consumer_unit_by_id(
                    consumer_unit_id)

            except DataWarehouseInformationRetrieveException as \
                consumer_unit_information_exception:
                print str(consumer_unit_information_exception)
                continue

            if is_interval:
                electric_data_csv_rows = \
                    get_consumer_unit_electric_data_interval_csv(
                        electric_data,
                        granularity,
                        consumer_unit,
                        datetime_start,
                        datetime_end)
            else:
                electric_data_csv_rows = get_consumer_unit_electric_data_csv(
                    electric_data,
                    granularity,
                    consumer_unit,
                    datetime_start,
                    datetime_end)

            data.extend(electric_data_csv_rows)
            consumer_unit_counter += 1
            consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
            date_start_get_key = "date-from%02d" % consumer_unit_counter
            date_end_get_key = "date-to%02d" % consumer_unit_counter
            electric_param_key = "electrical-parameter-name%02d" % consumer_unit_counter

        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename="datos_' + \
                                          report_name + '.csv"'
        writer = csv.writer(response)
        for data_item in data:
            writer.writerow(data_item)

        return response

    else:
        return Http404


def render_cumulative_comparison_in_week(request):
    if request.GET:
        try:
            electric_data = request.GET['electric-data']
            if electric_data == 'TotalkWhIMPORT':
                electric_data = "kWh"
        except KeyError:
            return HttpResponse("")
        else:
            consumer_unit_counter = 1
            consumer_units_data_tuple_list = []
            consumer_unit_get_key = "consumer-unit%02d" % consumer_unit_counter
            year_get_key = "year%02d" % consumer_unit_counter
            month_get_key = "month%02d" % consumer_unit_counter
            week_get_key = "week%02d" % consumer_unit_counter
            while request.GET.has_key(consumer_unit_get_key):
                consumer_unit_id_current = request.GET[consumer_unit_get_key]
                if request.GET.has_key(year_get_key) and \
                        request.GET.has_key(month_get_key) and \
                        request.GET.has_key(week_get_key):
                    year_current = int(request.GET[year_get_key])
                    month_current = int(request.GET[month_get_key])
                    week_current = int(request.GET[week_get_key])
                    start_datetime, end_datetime = variety. \
                        get_week_start_datetime_end_datetime_tuple(
                        year_current,
                        month_current,
                        week_current)

                    try:
                        consumer_unit_current = \
                            ConsumerUnit.objects.get(
                                pk=consumer_unit_id_current)

                    except ConsumerUnit.DoesNotExist:
                        return HttpResponse("")

                    (electric_data_days_tuple_list,
                     consumer_unit_electric_data_tuple_list_current) = \
                        get_consumer_unit_week_report_cumulative(
                            consumer_unit_current,
                            year_current,
                            month_current,
                            week_current,
                            electric_data)

                    week_day_date = start_datetime.date()
                    for index in range(0, 7):
                        week_day_name, electric_data_value = \
                            consumer_unit_electric_data_tuple_list_current[index]

                        consumer_unit_electric_data_tuple_list_current[index] \
                            = \
                            (week_day_date, electric_data_value)

                        week_day_date += datetime.timedelta(days=1)

                    consumer_units_data_tuple_list.append(
                        (consumer_unit_current,
                         consumer_unit_electric_data_tuple_list_current))

                    consumer_unit_counter += 1
                    consumer_unit_get_key = "consumer-unit%02d" % \
                                            consumer_unit_counter
                    year_get_key = "year%02d" % consumer_unit_counter
                    month_get_key = "month%02d" % consumer_unit_counter
                    week_get_key = "week%02d" % consumer_unit_counter

            week_days_data_tuple_list = [("Lunes", []),
                                         ("Martes", []),
                                         ("Miercoles", []),
                                         ("Jueves", []),
                                         ("Viernes", []),
                                         ("Sabado", []),
                                         ("Domingo", [])]

            consumer_unit_electric_data_total_tuple_list = []
            all_meditions = True
            for consumer_unit, electric_data_tuple_list in \
                consumer_units_data_tuple_list:

                consumer_unit_total = \
                    reduce(lambda x, y: x + y,
                           [electric_data_value for
                            week_day_date, electric_data_value in
                            electric_data_tuple_list])

                consumer_unit_electric_data_total_tuple_list.append(
                    (consumer_unit, consumer_unit_total))

                week_day_index = 0
                for week_day_date, \
                        electric_data_value in electric_data_tuple_list:
                    electric_data_percentage = \
                        0 if consumer_unit_total == 0 else \
                            electric_data_value / \
                            consumer_unit_total \
                            * 100

                    week_days_data_tuple_list[week_day_index][1].append(
                        (consumer_unit,
                         week_day_date,
                         electric_data_value,
                         electric_data_percentage))
                    if not electric_data_percentage:
                        all_meditions = False
                    week_day_index += 1

            template_variables = dict()
            template_variables["week_days_data_tuple_list"] = \
                week_days_data_tuple_list

            template_variables['all_meditions'] = all_meditions
            template_variables["consumer_unit_electric_data_total_tuple_list"] \
                = consumer_unit_electric_data_total_tuple_list

            template_context = RequestContext(request, template_variables)
            return render_to_response(
                'consumption_centers/graphs/week_comparison.html',
                template_context)
    else:
        return Http404


@login_required(login_url='/')
def add_building_attr(request):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, CREATE, "Alta de atributos de edificios") \
        or request.user.is_superuser:
        empresa = request.session['main_building']
        company = request.session['company']
        _type = ""
        message = ""
        attributes = BuildingAttributesType.objects.all().order_by(
            "building_attributes_type_sequence")
        template_vars = dict(datacontext=datacontext,
                             company=company,
                             type=_type,
                             message=message,
                             attributes=attributes,
                             sidebar=request.session['sidebar'])
        if request.method == "POST":
            template_vars['post'] = variety.get_post_data(request.POST)

            valid = True
            attr_name = template_vars['post']['attr_name']
            attr = get_object_or_404(BuildingAttributesType,
                                     pk=template_vars['post']['attr_type'])
            desc = template_vars['post']['description']
            if not variety.validate_string(attr_name):
                valid = False
                template_vars['message'] = \
                    "Por favor solo ingrese caracteres v&aacute;lidos"
            if desc != '':
                if not variety.validate_string(desc):
                    valid = False
                    template_vars['message'] = \
                        "Por favor solo ingrese caracteres v&aacute;lidos"

            if int(template_vars['post']['value_boolean']) == 1:
                _bool = True
                unidades = template_vars['post']['unidades']
                if not unidades:
                    valid = False
                else:
                    if not variety.validate_string(unidades):
                        valid = False
                        template_vars['message'] = "Por favor solo ingrese" \
                                                   " caracteres v&aacute;lidos"
            else:
                _bool = False
                unidades = ""
            if attr_name and valid:
                b_attr = BuildingAttributes(
                    building_attributes_type=attr,
                    building_attributes_name=attr_name,
                    building_attributes_description=desc,
                    building_attributes_value_boolean=_bool,
                    building_attributes_units_of_measurement=unidades
                )
                b_attr.save()
                template_vars['message'] = "El atributo fue dado de alta" \
                                           " correctamente"
                template_vars['type'] = "n_success"
                if not (not has_permission(request.user,
                                           VIEW,
                                           "Ver atributos de edificios") and
                            not request.user.is_superuser):
                    return HttpResponseRedirect("/buildings/atributos?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            else:
                template_vars['type'] = "n_error"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_building_attr.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def b_attr_list(request):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW, "Ver atributos de edificios") or \
            request.user.is_superuser:
        empresa = request.session['main_building']
        company = request.session['company']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''
        order_attrname = 'asc'
        order_type = 'asc'
        order_units = 'asc'
        order_sequence = 'asc'
        order_status = 'asc'
        order = "building_attributes_name" #default order
        if "order_attrname" in request.GET:
            if request.GET["order_attrname"] == "desc":
                order = "-building_attributes_name"
                order_attrname = "asc"
            else:
                order_attrname = "desc"
        elif "order_type" in request.GET:
            if request.GET["order_type"] == "asc":
                order = \
                    "building_attributes_type__building_attributes_type_name"
                order_type = "desc"
            else:
                order = \
                    "-building_attributes_type__building_attributes_type_name"
                order_type = "asc"
        elif "order_units" in request.GET:
            if request.GET["order_units"] == "asc":
                order = "building_attributes_units_of_measurement"
                order_units = "desc"
            else:
                order = "-building_attributes_units_of_measurement"
                order_units = "asc"
        elif "order_sequence" in request.GET:
            if request.GET["order_sequence"] == "asc":
                order = "building_attributes_sequence"
                order_sequence = "desc"
            else:
                order = "-building_attributes_sequence"
                order_sequence = "asc"
        elif "order_status" in request.GET:
            if request.GET["order_status"] == "asc":
                order = "building_attributes_status"
                order_status = "desc"
            else:
                order = "-building_attributes_status"
                order_status = "asc"

        if search:
            lista = BuildingAttributes.objects.filter(
                Q(building_attributes_name__icontains=
                request.GET['search']) |
                Q(building_attributes_description__icontains=
                request.GET['search'])).order_by(order)
        else:
            lista = BuildingAttributes.objects.all().order_by(order)
        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(roles=paginator, order_attrname=order_attrname,
                             order_type=order_type, order_units=order_units,
                             order_sequence=order_sequence,
                             order_status=order_status, company=company,
                             datacontext=datacontext,
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_role = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_role = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_role

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/building_attr_list.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def delete_b_attr(request, id_b_attr):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, DELETE, "Eliminar atributos de edificios") or\
        has_permission(request.user, UPDATE, "Modificar atributos de edificios")\
        or request.user.is_superuser:
        b_attr = get_object_or_404(BuildingAttributes, pk=id_b_attr)

        if b_attr.building_attributes_status:
            b_attr.building_attributes_status = False
        else:
            b_attr.building_attributes_status = True

        b_attr.save()

        mensaje = "El atributo ha cambiado de status correctamente"
        _type = "n_success"
        return HttpResponseRedirect("/buildings/atributos/?msj=" + mensaje +
                                    "&ntype=" + _type)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def editar_b_attr(request, id_b_attr):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW, "Ver atributos de edificios") or \
            request.user.is_superuser:
        b_attr = get_object_or_404(BuildingAttributes, pk=id_b_attr)
        empresa = request.session['main_building']
        company = request.session['company']
        if b_attr.building_attributes_value_boolean:
            _bool = "1"
        else:
            _bool = "0"
        post = {'attr_name': b_attr.building_attributes_name,
                'description': b_attr.building_attributes_description,
                'attr_type': b_attr.building_attributes_type.pk,
                'value_boolean': _bool,
                'unidades': b_attr.building_attributes_units_of_measurement}
        message = ''
        _type = ''
        attributes = BuildingAttributesType.objects.all().order_by(
            "building_attributes_type_sequence")
        template_vars = dict(datacontext=datacontext,
                             message=message, post=post, type=_type,
                             operation="edit", company=company,
                             attributes=attributes,
                             sidebar=request.session['sidebar'])
        if request.method == "POST":
            template_vars['post'] = variety.get_post_data(request.POST)

            valid = True
            attr_name = template_vars['post']['attr_name']
            attr = get_object_or_404(BuildingAttributesType,
                                     pk=template_vars['post']['attr_type'])
            desc = template_vars['post']['description']
            if not variety.validate_string(desc) or not \
                variety.validate_string(attr_name):
                valid = False
                template_vars['message'] = "Por favor solo ingrese " \
                                           "caracteres v&aacute;lidos"

            if template_vars['post']['value_boolean'] == 1:
                _bool = True
                unidades = template_vars['post']['unidades']
                if not unidades:
                    valid = False
                else:
                    if not variety.validate_string(unidades):
                        valid = False
                        template_vars['message'] = "Por favor solo ingrese" \
                                                   " caracteres v&aacute;lidos"
            else:
                _bool = False
                unidades = ""
            if attr_name and valid:
                b_attr.building_attributes_type = attr
                b_attr.building_attributes_name = attr_name
                b_attr.building_attributes_description = desc
                b_attr.building_attributes_value_boolean = _bool
                b_attr.building_attributes_units_of_measurement = unidades
                b_attr.save()
                template_vars['message'] = "El atributo fue editado" \
                                           " correctamente"
                template_vars['type'] = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver atributos de edificios") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/atributos?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            else:
                template_vars['type'] = "n_error"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_building_attr.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def ver_b_attr(request, id_b_attr):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW, "Ver atributos de edificios") or \
            request.user.is_superuser:
        b_attr = get_object_or_404(BuildingAttributes, pk=id_b_attr)
        empresa = request.session['main_building']
        company = request.session['company']
        if b_attr.building_attributes_value_boolean:
            _bool = "1"
        else:
            _bool = "0"
        post = {'attr_name': b_attr.building_attributes_name,
                'description': b_attr.building_attributes_description,
                'attr_type': b_attr.building_attributes_type.
                building_attributes_type_name,
                'value_boolean': _bool,
                'unidades': b_attr.building_attributes_units_of_measurement}
        message = ''
        _type = ''
        attributes = BuildingAttributesType.objects.all().order_by(
            "building_attributes_type_sequence")
        template_vars = dict(datacontext=datacontext,
                             message=message, company=company, post=post,
                             type=_type, operation="edit",
                             attributes=attributes,
                             sidebar=request.session['sidebar'])

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/see_building_attr.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_building_attr(request):
    if has_permission(request.user,
                      UPDATE,
                      "Modificar atributos de edificios") or \
            request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] != '0':
            for key in request.POST:
                if re.search('^attr_\w+', key):
                    r_id = int(key.replace("attr_", ""))
                    atributo = get_object_or_404(BuildingAttributes, pk=r_id)

                    if request.POST['actions'] == "activate":
                        atributo.building_attributes_status = True
                    else:
                        atributo.building_attributes_status = False
                    atributo.save()

            mensaje = "Los atributos seleccionados han cambiado su estatus" \
                      " correctamente"
            return HttpResponseRedirect("/buildings/atributos/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/atributos/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

#====
@login_required(login_url='/')
def add_cluster(request):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, CREATE, "Alta de grupos de empresas") or \
            request.user.is_superuser:
        empresa = request.session['main_building']
        message = ''
        _type = ''
        #Se obtienen los sectores
        sectores = SectoralType.objects.filter(sectoral_type_status=1)
        template_vars = dict(datacontext=datacontext,
                             sectores=sectores,
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            clustername = request.POST.get('clustername').strip()
            clusterdescription = request.POST.get('clusterdescription').strip()
            clustersector = request.POST.get('clustersector')

            continuar = True
            if clustername == '':
                message = "El nombre del Cluster no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(clustername):
                message = "El nombre del Cluster contiene caracteres inválidos"
                _type = "n_notif"
                clustername = ""
                continuar = False

            if clustersector == '':
                message = "El Cluster debe pertenecer a un tipo de sector"
                _type = "n_notif"
                continuar = False

            #Valida por si le da muchos clics al boton
            clusterValidate = Cluster.objects.filter(
                cluster_name=clustername).count()
            if clusterValidate:
                message = "Ya existe un cluster con ese nombre"
                _type = "n_notif"
                continuar = False

            post = {'clustername': clustername,
                    'clusterdescription': clusterdescription,
                    'clustersector': int(clustersector)}
            template_vars['post'] = post

            if continuar:
                sector_type = SectoralType.objects.get(pk=clustersector)

                newCluster = Cluster(
                    sectoral_type=sector_type,
                    cluster_description=clusterdescription,
                    cluster_name=clustername,
                )
                newCluster.save()

                template_vars["message"] = "Cluster de Empresas creado " \
                                           "exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW, "Ver grupos de empresas") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/clusters?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")

            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_cluster.html",
            template_vars_template)

    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def view_cluster(request):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW, "Ver grupos de empresas") or \
            request.user.is_superuser:
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_sector = 'asc'
        order_status = 'asc'
        order = "cluster_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-cluster_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_sector" in request.GET:
                if request.GET["order_sector"] == "asc":
                    order = "sectoral_type__sectorial_type_name"
                    order_sector = "desc"
                else:
                    order = "-sectoral_type__sectorial_type_name"
                    order_sector = "asc"
            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "cluster_status"
                    order_status = "desc"
                else:
                    order = "-cluster_status"
                    order_status = "asc"

        if search:
            lista = Cluster.objects.filter(
                Q(cluster_name__icontains=request.GET['search']) |
                Q(sectoral_type__sectorial_type_name__icontains=
                request.GET['search'])).exclude(
                cluster_status=2).order_by(order)

        else:
            lista = Cluster.objects.all().exclude(cluster_status=2). \
                order_by(order)
        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_sector=order_sector,
                             order_status=order_status,
                             datacontext=datacontext,
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/clusters.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_cluster(request, id_cluster):
    if has_permission(request.user, UPDATE, "Modificar cluster de empresas") \
        or request.user.is_superuser:
        cluster = get_object_or_404(Cluster, pk=id_cluster)
        if cluster.cluster_status == 1:
            cluster.cluster_status = 0
            action = "inactivo"
        else: #if cluster.cluster_status == 0:
            cluster.cluster_status = 1
            action = "activo"
        cluster.save()
        mensaje = "El estatus del cluster " + cluster.cluster_name + \
                  " ha cambiado a " + action
        _type = "n_success"

        return HttpResponseRedirect("/buildings/clusters/?msj=" + mensaje +
                                    "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_cluster(request):
    if has_permission(
            request.user,
            UPDATE,
            "Modificar cluster de empresas") or request.user.is_superuser:

        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^cluster_\w+', key):
                    r_id = int(key.replace("cluster_", ""))
                    cluster = get_object_or_404(Cluster, pk=r_id)
                    if cluster.cluster_status == 1:
                        cluster.cluster_status = 0
                    elif cluster.cluster_status == 0:
                        cluster.cluster_status = 1
                    cluster.save()

            mensaje = "Los clusters seleccionados han cambiado su status " \
                      "correctamente"
            return HttpResponseRedirect("/buildings/clusters/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/clusters/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def edit_cluster(request, id_cluster):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(
            request.user,
            UPDATE,
            "Modificar cluster de empresas") or request.user.is_superuser:
        cluster = get_object_or_404(Cluster, pk=id_cluster)

        #Se obtienen los sectores
        sectores = SectoralType.objects.filter(sectoral_type_status=1)

        post = {'clustername': cluster.cluster_name,
                'clusterdescription': cluster.cluster_description,
                'clustersector': cluster.sectoral_type.pk}

        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        message = ''
        _type = ''

        if request.method == "POST":
            clustername = request.POST.get('clustername')
            clusterdescription = request.POST.get('clusterdescription')
            clustersector = request.POST.get('clustersector')
            continuar = True
            if clustername == '':
                message = "El nombre del cluster no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(clustername):
                message = "El nombre del Cluster contiene caracteres inválidos"
                _type = "n_notif"
                clustername = ""
                continuar = False

            if clustersector == '':
                message = "El sector del cluster no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if cluster.cluster_name != clustername:
                #Valida por si le da muchos clics al boton
                clusterValidate = Cluster.objects.filter(
                    cluster_name=clustername).count()
                if clusterValidate:
                    message = "Ya existe un cluster con ese nombre"
                    _type = "n_notif"
                    continuar = False

            post = {'clustername': cluster.cluster_name,
                    'clusterdescription': clusterdescription,
                    'clustersector': int(clustersector)}

            if continuar:
                sector_type = SectoralType.objects.get(pk=clustersector)

                cluster.cluster_name = clustername
                cluster.cluster_description = clusterdescription
                cluster.sectoral_type = sector_type
                cluster.save()

                message = "Cluster editado exitosamente"
                _type = "n_success"
                if has_permission(request.user,
                                  VIEW,
                                  "Ver grupos de empresas") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/clusters?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             sectores=sectores,
                             post=post,
                             operation="edit",
                             message=message,
                             type=_type,
                             sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_cluster.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def see_cluster(request, id_cluster):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW, "Ver grupos de empresas") or \
            request.user.is_superuser:
        empresa = request.session['main_building']

        cluster = Cluster.objects.get(pk=id_cluster)
        cluster_companies = ClusterCompany.objects.filter(cluster__pk=id_cluster)

        template_vars = dict(
            datacontext=datacontext,
            cluster=cluster,
            cluster_companies=cluster_companies,
            sidebar=request.session['sidebar']
        )

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/see_cluster.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

###################
#POWERMETER MODELS#
###################

@login_required(login_url='/')
def add_powermetermodel(request):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user,
                      CREATE,
                      "Alta de modelos de medidores eléctricos") \
        or request.user.is_superuser:
        empresa = request.session['main_building']

        template_vars = dict(datacontext=datacontext,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            pw_brand = request.POST.get('pw_brand').strip()
            pw_model = request.POST.get('pw_model').strip()
            message = ''
            _type = ''

            continuar = True

            if pw_brand == '':
                message = "El nombre de la Marca no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(pw_brand):
                message = "El nombre de la Marca contiene caracteres inválidos"
                _type = "n_notif"
                pw_brand = ""
                continuar = False

            if pw_model == '':
                message = "El nombre del Modelo no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(pw_model):
                message = "El nombre del Modelo contiene caracteres inválidos"
                _type = "n_notif"
                pw_model = ""
                continuar = False

            #Valida no puede haber empresas con el mismo nombre
            p_modelValidate = PowermeterModel.objects.filter(
                powermeter_brand=pw_brand
            ).filter(powermeter_model=pw_model)
            if p_modelValidate:
                message = "Ya existe una Marca y un Modelo con esos datos"
                _type = "n_notif"
                continuar = False

            post = {'pw_brand': pw_brand, 'pw_model': pw_model}

            if continuar:
                newPowerMeterModel = PowermeterModel(
                    powermeter_brand=pw_brand,
                    powermeter_model=pw_model
                )
                newPowerMeterModel.save()

                template_vars["message"] = "Modelo de Medidor creado " \
                                           "exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user,
                                  VIEW,
                                  "Ver modelos de medidores eléctricos") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/modelos_medidor?msj=" +
                        template_vars["message"] + "&ntype=n_success")

            template_vars['post'] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_powermetermodel.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def edit_powermetermodel(request, id_powermetermodel):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user,
                      UPDATE,
                      "Modificar modelos de medidores eléctricos") \
        or request.user.is_superuser:
        powermetermodel = get_object_or_404(PowermeterModel,
                                            pk=id_powermetermodel)

        post = {'pw_brand': powermetermodel.powermeter_brand,
                'pw_model': powermetermodel.powermeter_model}

        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        message = ''
        _type = ''

        if request.method == "POST":
            pw_brand = request.POST.get('pw_brand')
            pw_model = request.POST.get('pw_model')

            continuar = True
            if pw_brand == '':
                message = "El nombre de la Marca no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(pw_brand):
                message = "El nombre de la Marca contiene caracteres inválidos"
                _type = "n_notif"
                pw_brand = ""
                continuar = False

            if pw_model == '':
                message = "El nombre del Modelo no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(pw_model):
                message = "El nombre del Modelo contiene caracteres inválidos"
                _type = "n_notif"
                pw_model = ""
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if powermetermodel.powermeter_brand != pw_brand or \
                            powermetermodel.powermeter_model != pw_model:
                p_modelValidate = PowermeterModel.objects.filter(
                    powermeter_brand=pw_brand).filter(
                    powermeter_model=pw_model)
                if p_modelValidate:
                    message = "Ya existe una Marca y un Modelo con esos datos"
                    _type = "n_notif"
                    continuar = False

            post = {'pw_brand': pw_brand, 'pw_model': pw_model}

            if continuar:
                powermetermodel.powermeter_brand = pw_brand
                powermetermodel.powermeter_model = pw_model
                powermetermodel.save()

                message = "Modelo de Medidor editado exitosamente"
                _type = "n_success"
                if has_permission(request.user,
                                  VIEW,
                                  "Ver modelos de medidores eléctricos") \
                    or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/modelos_medidor?msj=" + message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             post=post,
                             operation="edit",
                             message=message,
                             type=_type,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_powermetermodel.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def view_powermetermodels(request):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW,
                      "Ver modelos de medidores eléctricos") or \
            request.user.is_superuser:
        empresa = request.session['main_building']
        company = request.session['company']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_brand = 'asc'
        order_model = 'asc'
        order_status = 'asc'
        order = "powermeter_brand" #default order
        if "order_brand" in request.GET:
            if request.GET["order_brand"] == "desc":
                order = "-powermeter_brand"
                order_brand = "asc"
            else:
                order_brand = "desc"
        else:
            if "order_model" in request.GET:
                if request.GET["order_model"] == "asc":
                    order = "powermeter_model"
                    order_model = "desc"
                else:
                    order = "-powermeter_model"
                    order_model = "asc"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "status"
                    order_status = "desc"
                else:
                    order = "-status"
                    order_status = "asc"

        if search:
            lista = PowermeterModel.objects.filter(Q(
                powermeter_brand__icontains=request.GET['search']) | Q(
                powermeter_model__icontains=request.GET['search'])). \
                order_by(order)

        else:
            lista = PowermeterModel.objects.all().order_by(order)
        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_brand=order_brand,
                             order_model=order_model,
                             order_status=order_status,
                             datacontext=datacontext,
                             company=company,
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/powermetermodels.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_powermetermodel(request):
    if has_permission(request.user,
                      UPDATE,
                      "Modificar modelos de medidores eléctricos") or \
            request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^model_\w+', key):
                    r_id = int(key.replace("model_", ""))
                    powermetermodel = get_object_or_404(PowermeterModel,
                                                        pk=r_id)
                    if powermetermodel.status == 0:
                        powermetermodel.status = 1
                    elif powermetermodel.status == 1:
                        powermetermodel.status = 0
                    powermetermodel.save()

            mensaje = "Los modelos seleccionados han cambiado su estatus" \
                      " correctamente"
            return HttpResponseRedirect("/buildings/modelos_medidor/?msj=" +
                                        mensaje + "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/modelos_medidor/?msj=" +
                                        mensaje + "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_powermetermodel(request, id_powermetermodel):
    if has_permission(request.user,
                      UPDATE,
                      "Modificar modelos de medidores eléctricos") or \
            request.user.is_superuser:
        powermetermodel = get_object_or_404(PowermeterModel,
                                            pk=id_powermetermodel)
        if powermetermodel.status == 0:
            powermetermodel.status = 1
            str_status = "Activo"
        else: #if powermetermodel.status == 1:
            powermetermodel.status = 0
            str_status = "Inactivo"
        powermetermodel.save()

        mensaje = "El estatus del modelo ha cambiado a " + str_status
        _type = "n_success"

        return HttpResponseRedirect("/buildings/modelos_medidor/?msj=" +
                                    mensaje + "&ntype=" + _type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

#############
#POWERMETERS#
#############
@login_required(login_url='/')
def add_powermeter(request):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, CREATE,
                      "Alta de medidor electrico") or request.user.is_superuser:
        empresa = request.session['main_building']
        post = ''
        pw_models_list = PowermeterModel.objects.all().exclude(
            status=0).order_by("powermeter_brand")
        template_vars = dict(datacontext=datacontext,
                             modelos=pw_models_list,
                             post=post,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            pw_alias = request.POST.get('pw_alias').strip()
            pw_model = request.POST.get('pw_model')
            pw_serial = request.POST.get('pw_serial').strip()
            pw_modbus = 0
            message = ''
            _type = ''

            continuar = True
            if pw_alias == '':
                message = "El Alias del medidor no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(pw_alias):
                message = "El Alias del medidor contiene caracteres inválidos"
                _type = "n_notif"
                pw_alias = ""
                continuar = False

            if pw_model == '':
                message = "El modelo del medidor no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if pw_serial == '':
                message = "El número serial del medidor no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            #Valida por si le da muchos clics al boton
            pwValidate = Powermeter.objects.filter(
                powermeter_model__pk=pw_model).filter(
                powermeter_serial=pw_serial)
            if pwValidate:
                message = "Ya existe un Medidor con ese Modelo y ese " \
                          "Número de Serie"
                _type = "n_notif"
                continuar = False

            post = {'pw_alias': pw_alias, 'pw_model': int(pw_model),
                    'pw_serial': pw_serial}

            if continuar:
                pw_model = PowermeterModel.objects.get(pk=pw_model)

                newPowerMeter = Powermeter(
                    powermeter_model=pw_model,
                    powermeter_anotation=pw_alias,
                    powermeter_serial=pw_serial,
                    modbus_address=pw_modbus
                )
                newPowerMeter.save()
                ProfilePowermeter(powermeter=newPowerMeter).save()
                change_profile_electric_data.delay([pw_serial])

                template_vars["message"] = "Medidor creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver medidores eléctricos") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/medidores?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_powermeter.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def edit_powermeter(request, id_powermeter):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, UPDATE,
                      "Modificar medidores eléctricos") or \
            request.user.is_superuser:
        powermeter = get_object_or_404(Powermeter, pk=id_powermeter)

        pw_models_list = PowermeterModel.objects.all().exclude(
            status=0).order_by("powermeter_brand")

        post = {'pw_alias': powermeter.powermeter_anotation,
                'pw_model': powermeter.powermeter_model.pk,
                'pw_serial': powermeter.powermeter_serial}

        empresa = request.session['main_building']
        message = ''
        _type = ''

        if request.method == "POST":
            pw_alias = request.POST.get('pw_alias').strip()
            pw_model = request.POST.get('pw_model')
            pw_serial = request.POST.get('pw_serial').strip()

            continuar = True
            if pw_alias == '':
                message = "El Alias del medidor no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(pw_alias):
                message = "El Alias del medidor contiene caracteres inválidos"
                _type = "n_notif"
                pw_alias = ""
                continuar = False

            if pw_model == '':
                message = "El modelo del medidor no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            if pw_serial == '':
                message = "El número serial del medidor no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if powermeter.powermeter_model_id != pw_model and \
                            powermeter.powermeter_serial != pw_serial:
                #Valida por si le da muchos clics al boton
                pwValidate = Powermeter.objects.filter(
                    powermeter_model__pk=pw_model).filter(
                    powermeter_serial=pw_serial)
                if pwValidate:
                    message = "Ya existe un medidor con ese modelo y ese " \
                              "número de serie"
                    _type = "n_notif"
                    continuar = False

            post = {'pw_alias': pw_alias, 'pw_model': int(pw_model),
                    'pw_serial': pw_serial}

            if continuar:
                pw_model = PowermeterModel.objects.get(pk=pw_model)

                powermeter.powermeter_anotation = pw_alias
                powermeter.powermeter_serial = pw_serial
                powermeter.powermeter_model = pw_model
                powermeter.save()
                change_profile_electric_data.delay([pw_serial])
                try:
                    cons_unit = ConsumerUnit.objects.get(
                        profile_powermeter__powermeter=powermeter)
                except ObjectDoesNotExist:
                    pass
                else:
                    ie = IndustrialEquipment.objects.get(
                        building=cons_unit.building)
                    set_alarm_json(ie.building, user)
                    regenerate_ie_config(ie.pk, user)

                message = "Medidor editado exitosamente"
                _type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver medidores eléctricos") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/medidores?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             post=post,
                             modelos=pw_models_list,
                             operation="edit",
                             message=message,
                             type=_type,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_powermeter.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def view_powermeter(request):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW,
                      "Ver medidores eléctricos") or request.user.is_superuser:
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_alias = 'asc'
        order_serial = 'asc'
        order_model = 'asc'
        order_status = 'asc'

        order = "powermeter_anotation" #default order
        if "order_alias" in request.GET:
            if request.GET["order_alias"] == "desc":
                order = "-powermeter_anotation"
                order_alias = "asc"
            else:
                order_alias = "desc"
        else:
            if "order_model" in request.GET:
                if request.GET["order_model"] == "asc":
                    order = "powermeter_model__powermeter_brand"
                    order_model = "desc"
                else:
                    order = "-powermeter_model__powermeter_brand"
                    order_model = "asc"

            if "order_serial" in request.GET:
                if request.GET["order_serial"] == "asc":
                    order = "powermeter_serial"
                    order_serial = "desc"
                else:
                    order = "-powermeter_serial"
                    order_serial = "asc"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "status"
                    order_status = "desc"
                else:
                    order = "-status"
                    order_status = "asc"

        if search:
            lista = Powermeter.objects.filter(
                Q(powermeter_anotation__icontains=request.GET['search']) |
                Q(powermeter_model__powermeter_brand__icontains=
                    request.GET['search']) |
                Q(powermeter_model__powermeter_model__icontains=
                    request.GET['search'])).order_by(order)
        else:
            lista = Powermeter.objects.all().order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_alias=order_alias, order_model=order_model,
                             order_serial=order_serial,
                             order_status=order_status,
                             datacontext=datacontext,
                             company=request.session['company'],
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/powermeters.html",
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_powermeter(request):
    if has_permission(
            request.user,
            UPDATE,
            "Modificar medidores eléctricos") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^powermeter_\w+', key):
                    r_id = int(key.replace("powermeter_", ""))
                    powermeter = get_object_or_404(Powermeter, pk=r_id)
                    if powermeter.status == 0:
                        powermeter.status = 1
                    elif powermeter.status == 1:
                        powermeter.status = 0
                    powermeter.save()

                    try:
                        cons_unit = ConsumerUnit.objects.get(
                            profile_powermeter__powermeter=powermeter)
                    except ObjectDoesNotExist:
                        pass
                    else:
                        ie = IndustrialEquipment.objects.get(
                            building=cons_unit.building)
                        set_alarm_json(ie.building, user)
                        regenerate_ie_config(ie.pk, user)

            mensaje = "Los medidores seleccionados han cambiado su estatus " \
                      "correctamente"
            if "ref" in request.GET:
                return HttpResponseRedirect("/buildings/editar_ie/" +
                                            request.GET['ref'] + "/?msj=" +
                                            mensaje +
                                            "&ntype=n_success")

            return HttpResponseRedirect("/buildings/medidores/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/medidores/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_powermeter(request, id_powermeter):
    if has_permission(
            request.user,
            UPDATE,
            "Modificar medidores eléctricos") or request.user.is_superuser:
        powermeter = get_object_or_404(Powermeter, pk=id_powermeter)
        if powermeter.status == 0:
            powermeter.status = 1
            str_status = "Activo"
        else:
            powermeter.status = 0
            str_status = "Inactivo"

        powermeter.save()
        try:
            cons_unit = ConsumerUnit.objects.get(
                profile_powermeter__powermeter=powermeter)
        except ObjectDoesNotExist:
            pass
        else:
            ie = IndustrialEquipment.objects.get(
                building=cons_unit.building)
            set_alarm_json(ie.building, user)
            regenerate_ie_config(ie.pk, user)
        mensaje = "El estatus del medidor " + powermeter.powermeter_anotation \
                  + " ha cambiado a " + str_status
        _type = "n_success"
        if 'ref' in request.GET:
            if 'see' in request.GET:
                return HttpResponseRedirect("/buildings/ver_ie/" +
                                            request.GET['ref'] + "/?msj=" +
                                            mensaje +
                                            "&ntype=" + _type)
            url = "/buildings/editar_ie/" + request.GET['ref'] + "/?msj=" + \
                  mensaje + "&ntype=" + _type
            return HttpResponseRedirect(url)
        return HttpResponseRedirect("/buildings/medidores/?msj=" + mensaje +
                                    "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def see_powermeter(request, id_powermeter):
    if has_permission(request.user, VIEW,
                      "Ver medidores eléctricos") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']

        location = ''
        powermeter = Powermeter.objects.get(pk=id_powermeter)
        profile_powermeter_objs = ProfilePowermeter.objects.filter(
            powermeter=powermeter).filter(profile_powermeter_status=1)
        if profile_powermeter_objs:
            profile = profile_powermeter_objs[0]
            print profile
            consumer_unit_objs = ConsumerUnit.objects.filter(
                profile_powermeter=profile)
            print consumer_unit_objs
            c_unit = consumer_unit_objs[0]
            location = c_unit.building.building_name

        template_vars = dict(
            datacontext=datacontext,
            powermeter=powermeter,
            location=location,
            company=request.session['company'],
            sidebar=request.session['sidebar']
        )

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/see_powermeter.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

#######################
#Electric Device Types#
#######################
@login_required(login_url='/')
def add_electric_device_type(request):
    if has_permission(request.user, CREATE,
                      "Alta de dispositivos y sistemas eléctricos") or \
            request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        post = ''

        template_vars = dict(datacontext=datacontext,
                             post=post,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            edt_name = request.POST.get('devicetypename').strip()
            edt_description = request.POST.get('devicetypedescription').strip()
            message = ''
            _type = ''

            continuar = True
            if edt_name == '':
                message = "El nombre del Tipo de Equipo Eléctrico no puede " \
                          "quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(edt_name):
                message = "El nombre del Tipo de Equipo Eléctrico contiene " \
                          "caracteres inválidos"
                _type = "n_notif"
                edt_name = ""
                continuar = False

            #Valida por si le da muchos clics al boton
            b_electric_typeValidate = ElectricDeviceType.objects.filter(
                electric_device_type_name=edt_name)
            if b_electric_typeValidate:
                message = "Ya existe un Tipo de Equipo Eléctrico con ese nombre"
                _type = "n_notif"
                continuar = False

            post = {'devicetypename': edt_name,
                    'devicetypedescription': edt_description}

            if continuar:
                newElectricDeviceType = ElectricDeviceType(
                    electric_device_type_name=edt_name,
                    electric_device_type_description=edt_description
                )
                newElectricDeviceType.save()

                template_vars["message"] = "Tipo de Equipo Eléctrico creado " \
                                           "exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver medidores eléctricos") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_equipo_electrico?msj=" +
                        template_vars["message"] +
                        "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_electricdevicetype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def edit_electric_device_type(request, id_edt):
    if has_permission(request.user, UPDATE,
                      "Modificar dispositivos y sistemas eléctricos") or \
            request.user.is_superuser:
        edt_obj = get_object_or_404(ElectricDeviceType, pk=id_edt)
        devicetypename = edt_obj.electric_device_type_name
        devicetypedescription = edt_obj.electric_device_type_description
        post = {'devicetypename': devicetypename,
                'devicetypedescription': devicetypedescription}

        datacontext, b_list = get_buildings_context(request.user)
        empresa = request.session['main_building']
        message = ''
        _type = ''

        if request.method == "POST":
            edt_name = request.POST.get('devicetypename').strip()
            edt_description = request.POST.get('devicetypedescription').strip()

            continuar = True
            if edt_name == '':
                message = "El nombre del Tipo de Equipo Eléctrico no puede " \
                          "quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(edt_name):
                message = "El nombre del Tipo de Equipo Eléctrico contiene " \
                          "caracteres inválidos"
                _type = "n_notif"
                edt_name = ""
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if edt_obj.electric_device_type_name != edt_name:
                #Valida por si le da muchos clics al boton
                e_typeValidate = ElectricDeviceType.objects.filter(
                    electric_device_type_name=edt_name)
                if e_typeValidate:
                    message = "Ya existe un Tipo de Equipo Eléctrico con ese " \
                              "nombre"
                    _type = "n_notif"
                    continuar = False

            post = {'devicetypename': edt_name,
                    'devicetypedescription': edt_description}

            if continuar:
                edt_obj.electric_device_type_name = edt_name
                edt_obj.electric_device_type_description = edt_description
                edt_obj.save()

                message = "Tipo de Equipo Eléctrico editado exitosamente"
                _type = "n_success"
                if has_permission(
                        request.user, VIEW,
                        "Ver dispositivos y sistemas eléctricos") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_equipo_electrico?msj=" +
                        message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             post=post,
                             operation="edit",
                             message=message,
                             type=_type,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_electricdevicetype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def view_electric_device_type(request):
    if has_permission(request.user, VIEW,
                      "Ver dispositivos y sistemas eléctricos") or \
            request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_description = 'asc'
        order_status = 'asc'
        order = "electric_device_type_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-electric_device_type_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_description" in request.GET:
                if request.GET["order_description"] == "asc":
                    order = "electric_device_type_description"
                    order_description = "desc"
                else:
                    order = "-electric_device_type_description"
                    order_description = "asc"
            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "electric_device_type_status"
                    order_status = "desc"
                else:
                    order = "-electric_device_type_status"
                    order_status = "asc"

        if search:
            lista = ElectricDeviceType.objects.filter(
                Q(
                    electric_device_type_name__icontains=request.GET['search']
                ) |
                Q(
                    electric_device_type_description__icontains=
                    request.GET['search']
                )).exclude(electric_device_type_status=2).order_by(order)

        else:
            lista = ElectricDeviceType.objects.all().exclude(
                electric_device_type_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_description=order_description,
                             order_status=order_status,
                             datacontext=datacontext,
                             company=request.session['company'],
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/electricdevicetype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def delete_batch_electric_device_type(request):
    if has_permission(request.user, UPDATE,
                      "Modificar dispositivos y sistemas eléctricos") or \
            request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^edt_\w+', key):
                    r_id = int(key.replace("edt_", ""))
                    edt_obj = get_object_or_404(ElectricDeviceType, pk=r_id)
                    if edt_obj.electric_device_type_status == 0:
                        edt_obj.electric_device_type_status = 1
                    elif edt_obj.electric_device_type_status == 1:
                        edt_obj.electric_device_type_status = 0
                    edt_obj.save()

            mensaje = "Los Tipos de Equipo Eléctrico han cambiado su estatus " \
                      "correctamente"
            return HttpResponseRedirect(
                "/buildings/tipos_equipo_electrico/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/tipos_equipo_electrico/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_electric_device_type(request):
    if has_permission(request.user, UPDATE,
                      "Modificar dispositivos y sistemas eléctricos") or \
            request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^edt_\w+', key):
                    r_id = int(key.replace("edt_", ""))
                    edt_obj = get_object_or_404(ElectricDeviceType, pk=r_id)
                    if edt_obj.electric_device_type_status == 0:
                        edt_obj.electric_device_type_status = 1
                    elif edt_obj.electric_device_type_status == 1:
                        edt_obj.electric_device_type_status = 0
                    edt_obj.save()

            mensaje = "Los Tipos de Equipo Eléctrico han cambiado su estatus " \
                      "correctamente"
            return HttpResponseRedirect(
                "/buildings/tipos_equipo_electrico/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/tipos_equipo_electrico/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def status_electric_device_type(request, id_edt):
    if has_permission(request.user, UPDATE,
                      "Modificar dispositivos y sistemas eléctricos") or \
            request.user.is_superuser:
        edt_obj = get_object_or_404(ElectricDeviceType, pk=id_edt)
        if edt_obj.electric_device_type_status == 0:
            edt_obj.electric_device_type_status = 1
            str_status = "Activo"
        else: #if edt_obj.electric_device_type_status == 1:
            edt_obj.electric_device_type_status = 0
            str_status = "Inactivo"

        edt_obj.save()
        mensaje = "El estatus del tipo de equipo eléctrico ha cambiado a " + \
                  str_status
        _type = "n_success"

        return HttpResponseRedirect(
            "/buildings/tipos_equipo_electrico/?msj=" + mensaje +
            "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

###########
#Companies#
###########
@login_required(login_url='/')
def add_company(request):
    if has_permission(request.user, CREATE,
                      "Alta de empresas") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        post = ''
        message = ''
        _type = ''

        #Get Clusters
        clusters = get_clusters_for_operation("Alta de empresas", CREATE,
                                              request.user)
        #clusters = Cluster.objects.all().exclude(cluster_status = 2)

        #Get Sectors
        sectors = SectoralType.objects.filter(sectoral_type_status=1)

        template_vars = dict(datacontext=datacontext,
                             post=post,
                             clusters=clusters,
                             sectors=sectors,
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            cmp_name = request.POST.get('company_name').strip()
            cmp_description = request.POST.get('company_description').strip()
            cmp_cluster = request.POST.get('company_cluster')
            cmp_sector = request.POST.get('company_sector')

            continuar = True
            if cmp_name == '':
                message = "El nombre de la empresa no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(cmp_name):
                message = "El nombre de la empresa contiene caracteres " \
                          "inválidos"
                _type = "n_notif"
                cmp_name = ""
                continuar = False

            if cmp_cluster == '':
                message = "La empresa debe pertenencer a un grupo de empresas"
                _type = "n_notif"
                continuar = False

            if cmp_sector == '':
                message = "La empresa debe pertenencer a un sector"
                _type = "n_notif"
                continuar = False

            #Valida no puede haber empresas con el mismo nombre
            companyValidate = Company.objects.filter(company_name=cmp_name)
            if companyValidate:
                message = "Ya existe una empresa con ese nombre"
                _type = "n_notif"
                continuar = False

            post = {'cmp_name': cmp_name, 'cmp_description': cmp_description,
                    'cmp_cluster': int(cmp_cluster),
                    'cmp_sector': int(cmp_sector)}

            if continuar:
                #Se obtiene el objeto del sector
                sectorObj = SectoralType.objects.get(pk=cmp_sector)

                newCompany = Company(
                    sectoral_type=sectorObj,
                    company_name=cmp_name,
                    company_description=cmp_description
                )
                newCompany.save()

                #Se relaciona la empresa con el cluster
                #Se obtiene el objeto del cluster
                clusterObj = Cluster.objects.get(pk=cmp_cluster)

                newCompanyCluster = ClusterCompany(
                    cluster=clusterObj,
                    company=newCompany
                )
                newCompanyCluster.save()

                #Guarda la foto
                if 'logo' in request.FILES:
                    handle_company_logo(request.FILES['logo'], newCompany, True)

                template_vars["message"] = "Empresa creada exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver empresas") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/empresas?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_company.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def edit_company(request, id_cpy):
    if has_permission(request.user, UPDATE,
                      "Modificar empresas") or request.user.is_superuser:
        company_clusters = ClusterCompany.objects.filter(id=id_cpy)

        c_clust = company_clusters[0]
        post = {'cmp_id': c_clust.company.id,
                'cmp_name': c_clust.company.company_name,
                'cmp_description': c_clust.company.company_description,
                'cmp_cluster': c_clust.cluster.pk,
                'cmp_sector': c_clust.company.sectoral_type.pk,
                'cmp_logo': c_clust.company.company_logo}

        #Get Clusters
        #clusters = Cluster.objects.all().exclude(cluster_status = 2)
        clusters = get_clusters_for_operation("Modificar empresas", UPDATE,
                                              request.user)
        #Get Sectors
        sectors = SectoralType.objects.filter(sectoral_type_status=1)

        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        message = ''
        _type = ''

        if request.method == "POST":
            cmp_name = request.POST.get('company_name').strip()
            cmp_description = request.POST.get('company_description').strip()
            cmp_cluster = request.POST.get('company_cluster')
            cmp_sector = request.POST.get('company_sector')

            continuar = True
            if cmp_name == '':
                message = "El nombre de la empresa no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(cmp_name):
                message = "El nombre de la empresa contiene caracteres " \
                          "inválidos"
                _type = "n_notif"
                cmp_name = ""
                continuar = False

            if cmp_cluster == '':
                message = "La empresa debe pertenencer a un grupo de empresas"
                _type = "n_notif"
                continuar = False

            if cmp_sector == '':
                message = "La empresa debe pertenencer a un sector"
                _type = "n_notif"
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if company_clusters[0].company.company_name != cmp_name:
                companyValidate = Company.objects.filter(company_name=cmp_name)
                if companyValidate:
                    message = "Ya existe una empresa con ese nombre"
                    _type = "n_notif"
                    continuar = False

            post = {'cmp_id': company_clusters[0].company.id,
                    'cmp_name': cmp_name, 'cmp_description': cmp_description,
                    'cmp_cluster': int(cmp_cluster),
                    'cmp_sector': int(cmp_sector),
                    'cmp_logo': company_clusters[0].company.company_logo}

            if continuar:
                #Actualiza la empresa
                companyObj = Company.objects.get(
                    pk=company_clusters[0].company.pk)
                companyObj.company_name = cmp_name
                companyObj.company_description = cmp_description
                #Se obtiene el objeto del sector
                sectorObj = SectoralType.objects.get(pk=cmp_sector)
                companyObj.sectoral_type = sectorObj
                companyObj.save()

                #Se relaciona la empresa con el cluster
                ComCluster = ClusterCompany.objects.get(
                    pk=company_clusters[0].pk)
                ComCluster.delete()

                #Se obtiene el objeto del cluster
                clusterObj = Cluster.objects.get(pk=cmp_cluster)
                newCompanyCluster = ClusterCompany(
                    cluster=clusterObj,
                    company=companyObj
                )
                newCompanyCluster.save()

                #Guarda la foto
                if 'logo' in request.FILES:
                    handle_company_logo(request.FILES['logo'], companyObj,
                                        False)

                message = "Empresa editada exitosamente"
                _type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver empresas") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/empresas?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             post=post,
                             operation="edit",
                             message=message,
                             clusters=clusters,
                             sectors=sectors,
                             type=_type, sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_company.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def view_companies(request):
    if has_permission(request.user, VIEW,
                      "Ver empresas") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_company = 'asc'
        order_cluster = 'asc'
        order_sector = 'asc'
        order_status = 'asc'
        order = "company__company_name" #default order
        if "order_company" in request.GET:
            if request.GET["order_company"] == "desc":
                order = "-company__company_name"
                order_company = "asc"
            else:
                order_company = "desc"
        else:
            if "order_cluster" in request.GET:
                if request.GET["order_cluster"] == "asc":
                    order = "cluster__cluster_name"
                    order_cluster = "desc"
                else:
                    order = "-cluster__cluster_name"
                    order_cluster = "asc"
            if "order_sector" in request.GET:
                if request.GET["order_sector"] == "asc":
                    order = "company__sectoral_type__sectorial_type_name"
                    order_sector = "desc"
                else:
                    order = "-company__sectoral_type__sectorial_type_name"
                    order_sector = "asc"
            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "company__company_status"
                    order_status = "desc"
                else:
                    order = "-company__company_status"
                    order_status = "asc"

        if search:
            lista = ClusterCompany.objects.filter(
                Q(
                    company__company_name__icontains=request.GET['search']) |
                Q(
                    company__company_description__icontains=
                    request.GET['search']) |
                Q(
                    cluster__cluster_name__icontains=request.GET['search']) |
                Q(
                    company__sectoral_type__sectorial_type_name__icontains=
                    request.GET['search'])).exclude(
                company__company_status=2).order_by(order)

        else:
            lista = ClusterCompany.objects.all().exclude(
                company__company_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_company=order_company,
                             order_cluster=order_cluster,
                             order_sector=order_sector,
                             order_status=order_status,
                             datacontext=datacontext,
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/companies.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_companies(request):
    if has_permission(request.user, DELETE,
                      "Baja de empresas"
                      or "Modificar empresas") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^cmpy_\w+', key):
                    r_id = int(key.replace("cmpy_", ""))
                    cpy_obj = get_object_or_404(Company, pk=r_id)
                    if cpy_obj.company_status == 0:
                        cpy_obj.company_status = 1
                    elif cpy_obj.company_status == 1:
                        cpy_obj.company_status = 0
                    cpy_obj.save()

            mensaje = "Las empresas seleccionadas han cambiado su estatus " \
                      "correctamente"
            return HttpResponseRedirect("/buildings/empresas/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/empresas/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_company(request, id_cpy):
    if has_permission(request.user, UPDATE,
                      "Modificar empresas") or request.user.is_superuser:
        company = get_object_or_404(Company, pk=id_cpy)
        if company.company_status == 0:
            company.company_status = 1
            str_status = "Activo"
        else: #if company.company_status == 1:
            company.company_status = 0
            str_status = "Inactivo"

        company.save()
        mensaje = "El estatus de la empresa " + company.company_name + \
                  " ha cambiado a " + str_status
        _type = "n_success"

        return HttpResponseRedirect("/buildings/empresas/?msj=" + mensaje +
                                    "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def see_company(request, id_cpy):
    if has_permission(request.user, VIEW,
                      "Ver empresas") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']

        company_cluster_objs = ClusterCompany.objects.filter(company__pk=id_cpy)
        company = company_cluster_objs[0]

        template_vars = dict(
            datacontext=datacontext,
            companies=company,
            company=request.session['company'],
            sidebar=request.session['sidebar'])

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/see_company.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def c_center_structures(request):
    if has_permission(request.user, VIEW,
                      "Ver empresas") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']

        clustersObjs = Cluster.objects.all()
        visualizacion = "<div class='hierarchy_container'>"
        for clst in clustersObjs:
            visualizacion += "<div class='hrchy_cluster'>" \
                             "<span class='hrchy_cluster_label'>" + \
                             clst.cluster_name + "</span>"
            companiesObjs = ClusterCompany.objects.filter(cluster=clst)
            visualizacion += "<div>"
            for comp in companiesObjs:
                visualizacion += "<div class='hrchy_company'>" \
                                 "<span class='hrchy_company_label'>" + \
                                 comp.company.company_name + "</span>"
                buildingsObjs = CompanyBuilding.objects.filter(company=comp)
                if buildingsObjs:
                    visualizacion += "<div>"
                    for bld in buildingsObjs:
                        visualizacion += "<div class='hrchy_building'>" \
                                         "<span> - Edificio: " + \
                                         bld.building.building_name + \
                                         "</span></div>"
                    visualizacion += "</div>"
                visualizacion += "</div>"
            visualizacion += "</div>"
            visualizacion += "</div>"
        visualizacion += "</div>"

        template_vars = dict(
            datacontext=datacontext,
            visualizacion=visualizacion,
            empresa=empresa, company=request.session['company'],
            sidebar=request.session['sidebar'])

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/c_centers_structure.html",
            template_vars_template)

    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


###############
#Building Type#
###############

@login_required(login_url='/')
def add_buildingtype(request):
    if has_permission(request.user, CREATE,
                      "Alta de tipos de edificios") or \
            request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''
        message = ""
        _type = ""
        template_vars = dict(datacontext=datacontext,
                             post=post, sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            btype_name = request.POST.get('btype_name').strip()
            btype_description = request.POST.get('btype_description').strip()

            continuar = True
            if btype_name == '':
                message = "El nombre del Tipo de Edificio no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(btype_name):
                message = "El nombre del Tipo de Edificio contiene caracteres" \
                          " inválidos"
                _type = "n_notif"
                btype_name = ""
                continuar = False

            #Valida por si le da muchos clics al boton
            b_typeValidate = BuildingType.objects.filter(
                building_type_name=btype_name)
            if b_typeValidate:
                message = "Ya existe un Tipo de Edificio con ese nombre"
                _type = "n_notif"
                continuar = False

            post = {'btype_name': btype_name,
                    'btype_description': btype_description}

            if continuar:
                newBuildingType = BuildingType(
                    building_type_name=btype_name,
                    building_type_description=btype_description
                )
                newBuildingType.save()

                template_vars["message"] = "Tipo de Edificio creado " \
                                           "exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver empresas") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_edificios?msj=" +
                        template_vars["message"] +
                        "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_buildingtype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def edit_buildingtype(request, id_btype):
    if has_permission(request.user, UPDATE,
                      "Modificar tipo de edificio") or \
            request.user.is_superuser:
        building_type = BuildingType.objects.get(id=id_btype)

        post = {'btype_name': building_type.building_type_name,
                'btype_description': building_type.building_type_description}

        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        _type = ''

        if request.method == "POST":
            btype_name = request.POST.get('btype_name')
            btype_description = request.POST.get('btype_description')

            continuar = True
            if btype_name == '':
                message = "El nombre del Tipo de Edificio no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(btype_name):
                message = "El nombre del Tipo de Edificio contiene caracteres" \
                          " inválidos"
                _type = "n_notif"
                btype_name = ""
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if building_type.building_type_name != btype_name:
                #Valida por si le da muchos clics al boton
                b_typeValidate = BuildingType.objects.filter(
                    building_type_name=btype_name)
                if b_typeValidate:
                    message = "Ya existe un Tipo de Edificio con ese nombre"
                    _type = "n_notif"
                    continuar = False

            post = {'btype_name': btype_name,
                    'btype_description': btype_description}

            if continuar:
                building_type.building_type_name = btype_name
                building_type.building_type_description = btype_description
                building_type.save()

                message = "Tipo de Edificio editado exitosamente"
                _type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver tipos de edificios") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_edificios?msj=" +
                        message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             post=post,
                             operation="edit",
                             message=message,
                             type=_type, sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_buildingtype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def view_buildingtypes(request):
    if has_permission(request.user, VIEW,
                      "Ver tipos de edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']

        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_description = 'asc'
        order_status = 'asc'
        order = "building_type_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-building_type_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_description" in request.GET:
                if request.GET["order_description"] == "asc":
                    order = "building_type_description"
                    order_description = "desc"
                else:
                    order = "-building_type_description"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "building_type_status"
                    order_status = "desc"
                else:
                    order = "-building_type_status"
                    order_status = "asc"

        if search:
            lista = BuildingType.objects.filter(
                Q(building_type_name__icontains=request.GET['search']) |
                Q(building_type_description__icontains=request.GET['search'])
            ).exclude(
                building_type_status=2
            ).order_by(order)

        else:
            lista = BuildingType.objects.all().exclude(
                building_type_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_description=order_description,
                             order_status=order_status,
                             datacontext=datacontext,
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/buildingtype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_buildingtypes(request):
    if has_permission(request.user, UPDATE,
                      "Modificar tipo de edificio") or \
            request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^btype_\w+', key):
                    r_id = int(key.replace("btype_", ""))
                    btype_obj = get_object_or_404(BuildingType, pk=r_id)
                    if btype_obj.building_type_status == 0:
                        btype_obj.building_type_status = 1
                    elif btype_obj.building_type_status == 1:
                        btype_obj.building_type_status = 0
                    btype_obj.save()

            mensaje = "Los tipos de edificios han cambiado su estatus " \
                      "correctamente"
            return HttpResponseRedirect(
                "/buildings/tipos_edificios/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/tipos_edificios/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_buildingtype(request, id_btype):
    if has_permission(request.user, UPDATE,
                      "Modificar tipo de edificio") or \
            request.user.is_superuser:
        building_type = get_object_or_404(BuildingType, pk=id_btype)
        if building_type.building_type_status == 0:
            building_type.building_type_status = 1
            str_status = "Activo"
        else: #if building_type.building_type_status == 1:
            building_type.building_type_status = 0
            str_status = "Inactivo"

        building_type.save()
        mensaje = "El estatus del tipo de edificio " + \
                  building_type.building_type_name + " ha cambiado a " + \
                  str_status
        _type = "n_success"

        return HttpResponseRedirect(
            "/buildings/tipos_edificios/?msj=" + mensaje +
            "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


###############
#Sectoral Type#
###############

@login_required(login_url='/')
def add_sectoraltype(request):
    if has_permission(request.user, CREATE,
                      "Alta de tipos sectores") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        template_vars = dict(datacontext=datacontext,
                             post=post, sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            message = ''
            _type = ''
            stype_name = request.POST.get('stype_name')
            stype_description = request.POST.get('stype_description')

            continuar = True
            if stype_name == '':
                message = "El nombre del tipo de sector no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if not variety.validate_string(stype_name):
                message = "El nombre del tipo de sector contiene caracteres " \
                          "inválidos"
                _type = "n_notif"
                stype_name = ""
                continuar = False

            #Valida por si le da muchos clics al boton
            sectorValidate = SectoralType.objects.filter(
                sectorial_type_name=stype_name)
            if sectorValidate:
                message = "Ya existe un tipo de sector con ese nombre"
                _type = "n_notif"
                continuar = False

            post = {'stype_name': stype_name,
                    'stype_description': stype_description}

            if continuar:
                newSectoralType = SectoralType(
                    sectorial_type_name=stype_name,
                    sectoral_type_description=stype_description
                )
                newSectoralType.save()

                template_vars["message"] = "Tipo de Sector creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver tipos de sectores") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_sectores?msj=" +
                        template_vars["message"] +
                        "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_sectoraltype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def edit_sectoraltype(request, id_stype):
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de sectores") or \
            request.user.is_superuser:
        sectoral_type = SectoralType.objects.get(id=id_stype)

        post = {'stype_name': sectoral_type.sectorial_type_name,
                'stype_description': sectoral_type.sectoral_type_description}

        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        _type = ''

        if request.method == "POST":
            stype_name = request.POST.get('stype_name')
            stype_description = request.POST.get('stype_description')

            continuar = True
            if stype_name == '':
                message = "El nombre del tipo de sector no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if not variety.validate_string(stype_name):
                message = "El nombre del tipo de sector contiene caracteres " \
                          "inválidos"
                _type = "n_notif"
                stype_name = ""
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if sectoral_type.sectorial_type_name != stype_name:
                #Valida por si le da muchos clics al boton
                sectorValidate = SectoralType.objects.filter(
                    sectorial_type_name=stype_name)
                if sectorValidate:
                    message = "Ya existe un tipo de sector con ese nombre"
                    _type = "n_notif"
                    continuar = False

            post = {'stype_name': stype_name,
                    'stype_description': stype_description}

            if continuar:
                sectoral_type.sectorial_type_name = stype_name
                sectoral_type.sectoral_type_description = stype_description
                sectoral_type.save()

                message = "Tipo de Sector editado exitosamente"
                _type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver tipos de sectores") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_sectores?msj=" +
                        message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             post=post,
                             operation="edit",
                             message=message,
                             type=_type, sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_sectoraltype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def view_sectoraltypes(request):
    if has_permission(request.user, VIEW,
                      "Ver tipos de sectores") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']

        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_description = 'asc'
        order_status = 'asc'
        order = "sectorial_type_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-sectorial_type_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_description" in request.GET:
                if request.GET["order_description"] == "asc":
                    order = "sectoral_type_description"
                    order_description = "desc"
                else:
                    order = "-sectoral_type_description"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "sectoral_type_status"
                    order_status = "desc"
                else:
                    order = "-sectoral_type_status"
                    order_status = "asc"

        if search:
            lista = SectoralType.objects.filter(
                Q(sectorial_type_name__icontains=request.GET['search']) |
                Q(sectoral_type_description__icontains=request.GET['search'])
            ).exclude(
                sectoral_type_status=2
            ).order_by(order)
        else:
            lista = SectoralType.objects.all().exclude(
                sectoral_type_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_description=order_description,
                             order_status=order_status,
                             datacontext=datacontext,
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/sectoraltype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_sectoraltypes(request):
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de sectores") or \
            request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^stype_\w+', key):
                    r_id = int(key.replace("stype_", ""))
                    stype_obj = get_object_or_404(SectoralType, pk=r_id)
                    if stype_obj.sectoral_type_status == 0:
                        stype_obj.sectoral_type_status = 1
                    else:
                        stype_obj.sectoral_type_status = 0
                    stype_obj.save()

            mensaje = "Los tipos de sectores seleccionados han cambiado su " \
                      "estatus correctamente"
            return HttpResponseRedirect(
                "/buildings/tipos_sectores/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/tipos_sectores/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_sectoraltype(request, id_stype):
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de sectores") or \
            request.user.is_superuser:
        sectoral_type = get_object_or_404(SectoralType, pk=id_stype)
        if sectoral_type.sectoral_type_status == 0:
            sectoral_type.sectoral_type_status = 1
            str_status = "Activo"
        else:
        #if sectoral_type.sectoral_type_status == 1:
            sectoral_type.sectoral_type_status = 0
            str_status = "Inactivo"

        sectoral_type.save()
        mensaje = "El estatus del sector " + \
                  sectoral_type.sectorial_type_name + " ha cambiado a " + \
                  str_status
        _type = "n_success"

        return HttpResponseRedirect(
            "/buildings/tipos_sectores/?msj=" + mensaje +
            "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


##########################
#Building Attributes Type#
##########################
@login_required(login_url='/')
def add_b_attributes_type(request):
    if has_permission(request.user, CREATE,
                      "Alta de tipos de atributos de edificios") or \
            request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        template_vars = dict(datacontext=datacontext,
                             company=company,
                             post=post, sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            b_attr_type_name = request.POST.get('b_attr_type_name').strip()
            b_attr_type_description = request.POST.get(
                'b_attr_type_description').strip()
            message = ''
            _type = ''

            continuar = True
            if b_attr_type_name == '':
                message = "El nombre del tipo de atributo no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(b_attr_type_name):
                message = "El nombre del Tipo de Atributo contiene " \
                          "caracteres inválidos"
                _type = "n_notif"
                b_attr_type_name = ""
                continuar = False

            #Valida por si le da muchos clics al boton
            b_attribute_typeValidate = BuildingAttributesType.objects.filter(
                building_attributes_type_name=b_attr_type_name)
            if b_attribute_typeValidate:
                message = "Ya existe un Tipo de Atributo con ese nombre"
                _type = "n_notif"
                continuar = False

            post = {'stype_name': b_attr_type_name,
                    'stype_description': b_attr_type_description}

            if continuar:
                newBuildingAttrType = BuildingAttributesType(
                    building_attributes_type_name=b_attr_type_name,
                    building_attributes_type_description=b_attr_type_description
                )
                newBuildingAttrType.save()

                template_vars["message"] = "Tipo de Atributo de Edificio " \
                                           "creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(
                        request.user, VIEW,
                        "Ver tipos de atributos") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_atributos_edificios?msj=" +
                        template_vars["message"] +
                        "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_buildingattributetype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def edit_b_attributes_type(request, id_batype):
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de atributos de edificios") or \
            request.user.is_superuser:
        b_attr_typeObj = BuildingAttributesType.objects.get(id=id_batype)

        batype_description = b_attr_typeObj.building_attributes_type_description
        post = {'batype_name': b_attr_typeObj.building_attributes_type_name,
                'batype_description': batype_description}

        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        _type = ''

        if request.method == "POST":
            b_attr_type_name = request.POST.get('b_attr_type_name').strip()
            b_attr_type_description = request.POST.get(
                'b_attr_type_description').strip()

            continuar = True
            if b_attr_type_name == '':
                message = "El nombre del tipo de atributo no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(b_attr_type_name):
                message = "El nombre del Tipo de Atributo contiene " \
                          "caracteres inválidos"
                _type = "n_notif"
                b_attr_type_name = ""
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if b_attr_typeObj.building_attributes_type_name != b_attr_type_name:
                #Valida por si le da muchos clics al boton
                b_attribute_typeValidate = \
                    BuildingAttributesType.objects.filter(
                        building_attributes_type_name=b_attr_type_name)
                if b_attribute_typeValidate:
                    message = "Ya existe un Tipo de Atributo con ese nombre"
                    _type = "n_notif"
                    continuar = False

            post = {'batype_name': b_attr_type_name,
                    'batype_description': b_attr_type_description}

            if continuar:
                b_attr_typeObj.building_attributes_type_name = b_attr_type_name
                b_attr_typeObj.building_attributes_type_description = \
                    b_attr_type_description
                b_attr_typeObj.save()

                message = "Tipo de Atributo de Edificio editado exitosamente"
                _type = "n_success"
                if has_permission(
                        request.user, VIEW,
                        "Ver tipos de atributos") or request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_atributos_edificios?msj=" +
                        message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             company=company,
                             post=post,
                             operation="edit",
                             message=message,
                             type=_type, sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_buildingattributetype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def view_b_attributes_type(request):
    if has_permission(request.user, VIEW,
                      "Ver tipos de atributos") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']

        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_description = 'asc'
        order_status = 'asc'
        #default order
        order = "building_attributes_type_name"
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-building_attributes_type_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_description" in request.GET:
                if request.GET["order_description"] == "asc":
                    order = "building_attributes_type_description"
                    order_description = "desc"
                else:
                    order = "-building_attributes_type_description"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "building_attributes_type_status"
                    order_status = "desc"
                else:
                    order = "-building_attributes_type_status"

        if search:
            lista = BuildingAttributesType.objects.filter(
                Q(
                    building_attributes_type_name__icontains=
                    request.GET['search']) |
                Q(
                    building_attributes_type_description__icontains=
                    request.GET['search'])
            ).exclude(building_attributes_type_status=2).order_by(order)
        else:
            lista = BuildingAttributesType.objects.all().exclude(
                building_attributes_type_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_description=order_description,
                             order_status=order_status,
                             datacontext=datacontext,
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/buildingattributetype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_b_attributes_type(request, id_batype):
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de atributos de edificios") or \
            request.user.is_superuser:
        b_att_type = get_object_or_404(BuildingAttributesType, pk=id_batype)
        if b_att_type.building_attributes_type_status == 0:
            b_att_type.building_attributes_type_status = 1
            str_status = "Activo"
        else:
        #if b_att_type.building_attributes_type_status == 1:
            b_att_type.building_attributes_type_status = 0
            str_status = "Inactivo"
        b_att_type.save()

        atributo = b_att_type.building_attributes_type_name
        mensaje = "El estatus del Tipo de Atributo " + atributo + \
                  " ha cambiado a " + str_status
        _type = "n_success"

        return HttpResponseRedirect(
            "/buildings/tipos_atributos_edificios/?msj=" + mensaje +
            "&ntype=" + _type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def status_batch_b_attributes_type(request):
    if has_permission(
            request.user, UPDATE,
            "Modificar tipos de atributos de edificios") or \
            request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^batype_\w+', key):
                    r_id = int(key.replace("batype_", ""))
                    b_att_type = get_object_or_404(BuildingAttributesType,
                                                   pk=r_id)
                    if b_att_type.building_attributes_type_status == 0:
                        b_att_type.building_attributes_type_status = 1
                    elif b_att_type.building_attributes_type_status == 1:
                        b_att_type.building_attributes_type_status = 0
                    b_att_type.save()

            mensaje = "Los Tipos de Atributos seleccionados han cambiado su " \
                      "estatus correctamente"
            return HttpResponseRedirect(
                "/buildings/tipos_atributos_edificios/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/tipos_atributos_edificios/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


#######################
#Part of Building Type#
#######################

@login_required(login_url='/')
def add_partbuildingtype(request):
    if has_permission(
            request.user,
            CREATE,
            "Alta de tipos de partes de edificio") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        template_vars = dict(datacontext=datacontext,
                             company=company,
                             post=post, sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            b_part_type_name = request.POST.get('b_part_type_name').strip()
            b_part_type_description = request.POST.get(
                'b_part_type_description').strip()
            message = ''
            _type = ''

            continuar = True
            if b_part_type_name == '':
                message = "El nombre del Tipo de Parte de Edificio no puede " \
                          "quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(b_part_type_name):
                message = "El nombre del Tipo de Parte de Edificio contiene " \
                          "caracteres inválidos"
                _type = "n_notif"
                b_part_type_name = ""
                continuar = False

            #Valida por si le da muchos clics al boton
            partTypeValidate = PartOfBuildingType.objects.filter(
                part_of_building_type_name=b_part_type_name)
            if partTypeValidate:
                message = "Ya existe un Tipo de Parte de Edificio con ese " \
                          "nombre"
                _type = "n_notif"
                continuar = False

            post = {'b_part_type_name': b_part_type_name,
                    'b_part_type_description': b_part_type_description}

            if continuar:
                newPartBuildingType = PartOfBuildingType(
                    part_of_building_type_name=b_part_type_name,
                    part_of_building_type_description=b_part_type_description
                )
                newPartBuildingType.save()

                template_vars["message"] = "Tipo de Parte de Edificio creado " \
                                           "exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver tipos de partes de un edificio") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_partes_edificio?msj=" +
                        template_vars["message"] +
                        "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_partbuilding_type.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def edit_partbuildingtype(request, id_pbtype):
    if has_permission(request.user, UPDATE,
                      "Modificar tipos de atributos de edificios") or \
            request.user.is_superuser:
        building_part_type = PartOfBuildingType.objects.get(id=id_pbtype)

        b_part_type_name = building_part_type.part_of_building_type_name
        b_p_t_desc = building_part_type.part_of_building_type_description
        post = {
            'b_part_type_name': b_part_type_name,
            'b_part_type_description': b_p_t_desc}

        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        _type = ''

        if request.method == "POST":
            b_part_type_name = request.POST.get('b_part_type_name').strip()
            b_part_type_description = request.POST.get(
                'b_part_type_description').strip()

            continuar = True
            if b_part_type_name == '':
                message = "El nombre del Tipo de Parte de Edificio no puede " \
                          "quedar vacío"
                _type = "n_notif"
                continuar = False

            #Valida el nombre (para el caso de los repetidos)
            if building_part_type.part_of_building_type_name != \
                    b_part_type_name:
                #Valida por si le da muchos clics al boton
                partTypeValidate = PartOfBuildingType.objects.filter(
                    part_of_building_type_name=b_part_type_name)
                if partTypeValidate:
                    message = "Ya existe un Tipo de Parte de Edificio con " \
                              "ese nombre"
                    _type = "n_notif"
                    continuar = False
            b_part_type_name = building_part_type.part_of_building_type_name
            b_part_type_description = building_part_type.\
                part_of_building_type_description
            post = {
                'b_part_type_name': b_part_type_name,
                'b_part_type_description': b_part_type_description}

            if continuar:
                building_part_type.part_of_building_type_name = b_part_type_name
                building_part_type.part_of_building_type_description = \
                    b_part_type_description
                building_part_type.save()

                message = "Tipo de Parte de Edificio editado exitosamente"
                _type = "n_success"
                if has_permission(request.user,
                                  VIEW,
                                  "Ver tipos de partes de un edificio") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/tipos_partes_edificio?msj=" +
                        message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             company=company,
                             post=post,
                             operation="edit",
                             message=message,
                             type=_type, sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_partbuilding_type.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def view_partbuildingtype(request):
    if has_permission(
            request.user,
            VIEW,
            "Ver tipos de partes de un edificio") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']

        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_description = 'asc'
        order_status = 'asc'
        order = "part_of_building_type_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-part_of_building_type_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_description" in request.GET:
                if request.GET["order_description"] == "asc":
                    order = "part_of_building_type_description"
                    order_description = "desc"
                else:
                    order = "-part_of_building_type_description"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "part_of_building_type_status"
                    order_status = "desc"
                else:
                    order = "-part_of_building_type_status"
                    order_status = "asc"

        if search:
            lista = PartOfBuildingType.objects.filter(
                Q(
                    part_of_building_type_name__icontains=
                    request.GET['search']) |
                Q(
                    part_of_building_type_description__icontains=
                    request.GET['search'])
            ).exclude(part_of_building_type_status=2).order_by(order)
        else:
            lista = PartOfBuildingType.objects.all().exclude(
                part_of_building_type_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_description=order_description,
                             order_status=order_status,
                             datacontext=datacontext,
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/partofbuildingtype.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_partbuildingtype(request):
    if has_permission(
            request.user,
            UPDATE,
            "Modificar tipos de atributos de edificios") or \
            request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^pb_type_\w+', key):
                    r_id = int(key.replace("pb_type_", ""))
                    part_building_type = get_object_or_404(PartOfBuildingType,
                                                           pk=r_id)
                    if part_building_type.part_of_building_type_status == 0:
                        part_building_type.part_of_building_type_status = 1
                    elif part_building_type.part_of_building_type_status == 1:
                        part_building_type.part_of_building_type_status = 0
                    part_building_type.save()

            mensaje = "Los Tipos de Partes de Edificio han cambiado " \
                      "su estatus correctamente"
            return HttpResponseRedirect(
                "/buildings/tipos_partes_edificio/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/tipos_partes_edificio/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_partbuildingtype(request, id_pbtype):
    if has_permission(
            request.user,
            UPDATE,
            "Modificar tipos de atributos de edificios") or \
            request.user.is_superuser:
        part_building_type = get_object_or_404(PartOfBuildingType, pk=id_pbtype)

        if part_building_type.part_of_building_type_status == 0:
            part_building_type.part_of_building_type_status = 1
            str_status = "Activo"
        else: #if part_building_type.part_of_building_type_status == 1:
            part_building_type.part_of_building_type_status = 0
            str_status = "Inactivo"
        part_building_type.save()

        mensaje = "El estatus del tipo de edificio " + \
                  part_building_type.part_of_building_type_name + \
                  " ha cambiado a " + str_status
        _type = "n_success"

        return HttpResponseRedirect(
            "/buildings/tipos_partes_edificio/?msj=" + mensaje +
            "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


##################
#Part of Building#
##################

@login_required(login_url='/')
def add_partbuilding(request):
    if has_permission(request.user, CREATE,
                      "Alta de partes de edificio") or \
            request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        #Se obtienen los tipos de partes de edificios
        tipos_parte = PartOfBuildingType.objects.all().exclude(
            part_of_building_type_status=0).order_by(
            'part_of_building_type_name')

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.all().exclude(
            building_attributes_type_status=0).order_by(
            'building_attributes_type_name')

        template_vars = dict(datacontext=datacontext,
                             company=company,
                             post=post,
                             tipos_parte=tipos_parte,
                             tipos_atributos=tipos_atributos,
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            b_part_name = request.POST.get('b_part_name').strip()
            b_part_description = request.POST.get('b_part_description').strip()
            b_part_type_id = request.POST.get('b_part_type')
            b_part_building_name = request.POST.get('b_building_name').strip()
            b_part_building_id = request.POST.get('b_building_id')
            b_part_mt2 = request.POST.get('b_part_mt2').strip()
            message = ""
            _type = ""

            continuar = True
            if not b_part_name:
                message = "El nombre de la Parte de Edificio no " \
                          "puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if not b_part_type_id:
                message = "Se debe seleccionar un tipo de parte de edificio"
                _type = "n_notif"
                continuar = False

            if not b_part_building_id:
                message = "Se debe seleccionar un edificio ya registrado"
                _type = "n_notif"
                continuar = False
            if continuar:
                #Valida por si le da muchos clics al boton
                partValidate = PartOfBuilding.objects.filter(
                    part_of_building_name=b_part_name).filter(
                    part_of_building_type__pk=b_part_type_id).filter(
                    building__pk=b_part_building_id)
                if partValidate:
                    message = "Ya existe una Parte de Edificio con ese " \
                              "nombre, ese tipo de parte y en ese edificio"
                    _type = "n_notif"
                    continuar = False

                post = {'b_part_name': b_part_name,
                        'b_part_description': b_part_description,
                        'b_part_building_name': b_part_building_name,
                        'b_part_building_id': b_part_building_id,
                        'b_part_type': int(b_part_type_id),
                        'b_part_mt2': b_part_mt2}

            if continuar:
                #Se obtiene la instancia del edificio
                buildingObj = get_object_or_404(Building, pk=b_part_building_id)

                #Se obtiene la instancia del tipo de parte de edificio
                part_building_type_obj = get_object_or_404(PartOfBuildingType,
                                                           pk=b_part_type_id)

                if not bool(b_part_mt2):
                    b_part_mt2 = '0'
                else:
                    b_part_mt2 = b_part_mt2.replace(",", "")

                newPartBuilding = PartOfBuilding(
                    building=buildingObj,
                    part_of_building_type=part_building_type_obj,
                    part_of_building_name=b_part_name,
                    part_of_building_description=b_part_description,
                    mts2_built=b_part_mt2
                )
                newPartBuilding.save()
                deviceType = ElectricDeviceType.objects.get(
                    electric_device_type_name="Total parte de un edificio")
                newConsumerUnit = ConsumerUnit(
                    building=buildingObj,
                    part_of_building=newPartBuilding,
                    electric_device_type=deviceType,
                    profile_powermeter=VIRTUAL_PROFILE
                )
                newConsumerUnit.save()
                #Add the consumer_unit instance for the DW
                populate_data_warehouse_extended(
                    populate_instants=None,
                    populate_consumer_unit_profiles=True,
                    populate_data=None)

                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')
                        #Se obtiene el objeto tipo de atributo

                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(
                            pk=atr_value_arr[1])

                        newBldPartAtt = BuilAttrsForPartOfBuil(
                            part_of_building=newPartBuilding,
                            building_attributes=attribute_obj,
                            building_attributes_value=atr_value_arr[2]
                        )
                        newBldPartAtt.save()

                template_vars["message"] = "Parte de Edificio creado " \
                                           "exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver partes de un edificio") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/partes_edificio?msj=" +
                        template_vars["message"] +
                        "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_partbuilding.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def edit_partbuilding(request, id_bpart):
    if has_permission(request.user, UPDATE,
                      "Modificar partes de un edificio") or \
            request.user.is_superuser:
        #Se obtienen los tipos de partes de edificios
        tipos_parte = PartOfBuildingType.objects.all().exclude(
            part_of_building_type_status=0).order_by(
            'part_of_building_type_name')

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.all().exclude(
            building_attributes_type_status=0).order_by(
            'building_attributes_type_name')

        building_part = get_object_or_404(PartOfBuilding, pk=id_bpart)

        #Se obtienen todos los atributos
        building_part_attributes = BuilAttrsForPartOfBuil.objects.filter(
            part_of_building=building_part)
        string_attributes = ''
        if building_part_attributes:
            for bp_att in building_part_attributes:
                b_attr_val = str(bp_att.building_attributes_value)
                b_at_pk = str(bp_att.building_attributes.pk)
                b_attr_pk = str(
                    bp_att.building_attributes.building_attributes_type.pk)
                string_attributes += '<div  class="extra_attributes_building">' \
                                     '<span class="delete_attr_icon">' \
                                     '<a href="#eliminar" ' \
                                     'class="delete hidden_icon" ' + \
                                     'title="eliminar atributo"></a></span>' + \
                                     '<span class="tip_attribute_part">' + \
                                     bp_att.building_attributes \
                                         .building_attributes_type \
                                         .building_attributes_type_name + \
                                     '</span>' + \
                                     '<span class="attribute_part">' + \
                                     bp_att.building_attributes.\
                                         building_attributes_name + \
                                     '</span>' + \
                                     '<span class="attribute_value_part">' + \
                                     b_attr_val + \
                                     '</span>' + \
                                     '<input type="hidden" name="atributo_' + \
                                     b_attr_pk + \
                                     '_' + b_at_pk + '" ' + \
                                     'value="' + b_attr_pk + \
                                     ',' + b_at_pk + ',' + b_attr_val + \
                                     '"/></div>'

        descr = building_part.part_of_building_description
        post = {'b_part_name': building_part.part_of_building_name,
                'b_part_description': descr,
                'b_part_building_name': building_part.building.building_name,
                'b_part_building_id': str(building_part.building.pk),
                'b_part_type': building_part.part_of_building_type.id,
                'b_part_mt2': building_part.mts2_built,
                'b_part_attributes': string_attributes}

        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        _type = ''

        if request.method == "POST":
            b_part_name = request.POST.get('b_part_name').strip()
            b_part_description = request.POST.get('b_part_description').strip()
            b_part_type_id = request.POST.get('b_part_type')
            b_part_building_name = request.POST.get('b_building_name').strip()
            b_part_building_id = request.POST.get('b_building_id')
            b_part_mt2 = request.POST.get('b_part_mt2').strip()

            if not bool(b_part_mt2):
                b_part_mt2 = '0'
            else:
                b_part_mt2 = b_part_mt2.replace(",", "")

            continuar = True
            if b_part_name == '':
                message = "El nombre de la Parte de Edificio no puede quedar" \
                          " vacío"
                _type = "n_notif"
                continuar = False

            if b_part_type_id == '':
                message = "Se debe seleccionar un tipo de parte de edificio"
                _type = "n_notif"
                continuar = False

            if b_part_building_id == '':
                message = "Se debe seleccionar un edificio"
                _type = "n_notif"
                continuar = False

            if building_part.part_of_building_name != b_part_name and \
                            building_part.building_id != b_part_building_id \
                and building_part.part_of_building_type_id != b_part_type_id:
                #Valida por si le da muchos clics al boton
                partValidate = PartOfBuilding.objects.filter(
                    part_of_building_name=b_part_name).filter(
                    part_of_building_type__pk=b_part_type_id).filter(
                    building__pk=b_part_building_id)
                if partValidate:
                    message = "Ya existe una Parte de Edificio con ese " \
                              "nombre, ese tipo de parte y en ese edificio"
                    _type = "n_notif"
                    continuar = False

            post = {'b_part_name': b_part_name,
                    'b_part_description': b_part_description,
                    'b_part_building_name': b_part_building_name,
                    'b_part_building_id': b_part_building_id,
                    'b_part_type': int(b_part_type_id),
                    'b_part_mt2': b_part_mt2}

            if continuar:
                #Se obtiene la instancia del edificio
                buildingObj = get_object_or_404(Building, pk=b_part_building_id)

                #Se obtiene la instancia del tipo de parte de edificio
                part_building_type_obj = get_object_or_404(PartOfBuildingType,
                                                           pk=b_part_type_id)

                building_part.building = buildingObj
                building_part.part_of_building_name = b_part_name
                building_part.part_of_building_description = b_part_description
                building_part.part_of_building_type = part_building_type_obj
                building_part.mts2_built = b_part_mt2
                building_part.save()

                #Se eliminan todos los atributos existentes
                builAttrsElim = BuilAttrsForPartOfBuil.objects.filter(
                    part_of_building=building_part)
                builAttrsElim.delete()

                #Se insertan los nuevos
                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')

                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(
                            pk=atr_value_arr[1])

                        newBldPartAtt = BuilAttrsForPartOfBuil(
                            part_of_building=building_part,
                            building_attributes=attribute_obj,
                            building_attributes_value=atr_value_arr[2]
                        )
                        newBldPartAtt.save()

                message = "Parte de Edificio editado exitosamente"
                _type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver partes de un edificio") or \
                        request.user.is_superuser:
                    return HttpResponseRedirect(
                        "/buildings/partes_edificio?msj=" +
                        message +
                        "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             company=company,
                             post=post,
                             tipos_parte=tipos_parte,
                             tipos_atributos=tipos_atributos,
                             operation="edit",
                             message=message,
                             type=_type, sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_partbuilding.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def view_partbuilding(request):
    if has_permission(request.user, VIEW,
                      "Ver partes de un edificio") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']

        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_type = 'asc'
        order_building = 'asc'
        order_status = 'asc'
        order = "part_of_building_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-part_of_building_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_type" in request.GET:
                if request.GET["order_type"] == "asc":
                    order = "part_of_building_type__part_of_building_type_name"
                    order_type = "desc"
                else:
                    order = "-part_of_building_type__part_of_building_type_name"

            if "order_building" in request.GET:
                if request.GET["order_building"] == "asc":
                    order = "building__building_name"
                    order_building = "desc"
                else:
                    order = "-building__building_name"
                    order_building = "asc"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "part_of_building_status"
                    order_status = "desc"
                else:
                    order = "-part_of_building_status"
                    order_status = "asc"

        if search:
            lista = PartOfBuilding.objects.filter(
                Q(part_of_building_name__icontains=request.GET['search']) |
                Q(part_of_building_type__part_of_building_type_name__icontains=
                  request.GET['search']) |
                Q(building__building_name__icontains=request.GET['search'])
            ).order_by(order)
        else:
            lista = PartOfBuilding.objects.all().order_by(order)

        # muestra 10 resultados por pagina
        paginator = Paginator(lista, 10)
        template_vars = dict(order_name=order_name, order_type=order_type,
                             order_building=order_building,
                             order_status=order_status,
                             datacontext=datacontext,
                             company=company,
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/partofbuilding.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_partofbuilding(request):
    if has_permission(request.user, UPDATE,
                      "Modificar partes de un edificio") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^pb_\w+', key):
                    r_id = int(key.replace("pb_", ""))
                    building_part = get_object_or_404(PartOfBuilding, pk=r_id)

                    if building_part.part_of_building_status == 0:
                        building_part.part_of_building_status = 1
                    elif building_part.part_of_building_status == 1:
                        building_part.part_of_building_status = 0

                    building_part.save()

            mensaje = "Las partes de edificios han cambiado su estatus " \
                      "correctamente"
            return HttpResponseRedirect(
                "/buildings/partes_edificio/?msj=" + mensaje +
                "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/buildings/partes_edificio/?msj=" + mensaje +
                "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def status_partofbuilding(request, id_bpart):
    if has_permission(request.user, UPDATE,
                      "Modificar partes de un edificio") or \
            request.user.is_superuser:
        building_part = get_object_or_404(PartOfBuilding, pk=id_bpart)

        if building_part.part_of_building_status == 0:
            building_part.part_of_building_status = 1
            str_status = "activo"
        else:
        #if building_part.part_of_building_status == 1:
            building_part.part_of_building_status = 0
            str_status = "inactivo"

        building_part.save()

        mensaje = "El estatus de la parte de edificio " + \
                  building_part.part_of_building_name + " ha cambiado a " + \
                  str_status
        _type = "n_success"

        return HttpResponseRedirect(
            "/buildings/partes_edificio/?msj=" + mensaje +
            "&ntype=" + _type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def search_buildings(request):
    """ recieves three parameters in request.GET:
    term = string, the name of the building to search
    perm = string, the complete name of the operation we want to check if
        the user has permission
    op = string, the operation to check the permission
        (view, create, update, delete)
    """

    if "term" in request.GET and "perm" in request.GET and "op" in request.GET:
        operation = {
            'view': VIEW,
            'create': CREATE,
            'update': UPDATE,
            'delete': DELETE
        }

        op = operation[request.GET['op']]
        term = request.GET['term']
        perm = request.GET['perm']

        buildings = get_all_buildings_for_operation(perm, op, request.user)
        b_pks = [b.pk for b in buildings]
        buildings = Building.objects.filter(
            building_name__icontains=term,
            pk__in=b_pks).exclude(building_status=0).values(
                "pk", "building_name")
        buildings_arr = []
        for building in buildings:
            buildings_arr.append(
                dict(value=building['building_name'], pk=building['pk'],
                     label=building['building_name']))

        data = simplejson.dumps(buildings_arr)
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404


@login_required(login_url='/')
def get_select_attributes(request, id_attribute_type):
    building_attributes = BuildingAttributes.objects.filter(
        building_attributes_type__pk=id_attribute_type)
    string_to_return = ''
    if building_attributes:
        for b_attr in building_attributes:
            string_to_return += """<li rel="%s">
                                    %s
                                </li>""" % (
                b_attr.pk, b_attr.building_attributes_name)
    else:
        string_to_return = '<li rel="">Sin atributos</li>'

    return HttpResponse(content=string_to_return, content_type="text/html")


###########
#EDIFICIOS#
###########
# noinspection PyArgumentList
@login_required(login_url='/')
def add_building(request):
    if has_permission(request.user, CREATE,
                      "Alta de edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''
        message = ''
        _type = ''
        #Se obtienen las empresas
        empresas_lst = get_all_companies_for_operation("Alta de edificios",
                                                       CREATE, request.user)
        #Se obtienen las tarifas
        tarifas = ElectricRates.objects.all()

        #Se obtienen los tipos de edificios
        tipos_edificio_lst = BuildingType.objects.filter(
            building_type_status=1).order_by('building_type_name')

        #Se obtienen las regiones
        regiones_lst = Region.objects.all()

        #Se obtienen las regiones
        zonas_lst = Timezones.objects.all()

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.filter(
            building_attributes_type_status=1).order_by(
            'building_attributes_type_name')

        template_vars = dict(datacontext=datacontext,
                             company=company,
                             post=post,
                             empresas_lst=empresas_lst,
                             tipos_edificio_lst=tipos_edificio_lst,
                             tarifas=tarifas,
                             regiones_lst=regiones_lst,
                             zonas_lst=zonas_lst,
                             tipos_atributos=tipos_atributos,
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            b_name = request.POST.get('b_name').strip()
            b_description = request.POST.get('b_description').strip()
            b_company = request.POST.get('b_company')
            b_type_arr = request.POST.getlist('b_type')
            b_mt2 = request.POST.get('b_mt2').strip()
            b_electric_rate_id = request.POST.get('b_electric_rate')
            b_country_id = request.POST.get('b_country_id')
            b_country_name = request.POST.get('b_country').strip()
            b_state_id = request.POST.get('b_state_id')
            b_state_name = request.POST.get('b_state').strip()
            b_municipality_id = request.POST.get('b_municipality_id')
            b_municipality_name = request.POST.get('b_municipality').strip()
            b_neighborhood_id = request.POST.get('b_neighborhood_id')
            b_neighborhood_name = request.POST.get('b_neighborhood').strip()
            b_street_id = request.POST.get('b_street_id')
            b_street_name = request.POST.get('b_street').strip()
            b_ext = request.POST.get('b_ext').strip()
            b_int = request.POST.get('b_int').strip()
            b_zip = request.POST.get('b_zip').strip()
            b_long = request.POST.get('b_longitude')
            b_lat = request.POST.get('b_latitude')
            b_region_id = request.POST.get('b_region')
            b_time_zone = request.POST.get('b_time_zone')

            if not bool(b_int):
                b_int = '0'

            if not bool(b_mt2):
                b_mt2 = '0'
            else:
                b_mt2 = b_mt2.replace(",", "")

            continuar = True
            if b_name == '':
                message += "El nombre del Edificio no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(b_name):
                message += "El nombre del Edificio contiene caracteres " \
                           "inválidos"
                _type = "n_notif"
                b_name = ""
                continuar = False

            if b_company == '':
                message += " - Se debe seleccionar una empresa"
                _type = "n_notif"
                continuar = False

            if not b_type_arr:
                message += " - El edificio debe ser al menos de un tipo"
                _type = "n_notif"
                continuar = False

            if b_electric_rate_id == '':
                message += " - Se debe seleccionar un tipo de tarifa"
                _type = "n_notif"
                continuar = False

            if b_ext == '':
                message += " - El edificio debe tener un número exterior"
                _type = "n_notif"
                continuar = False

            if b_zip == '':
                message += " - El edificio debe tener un código postal"
                _type = "n_notif"
                continuar = False

            if b_long == '' and b_lat == '':
                message += " - Debes ubicar el edificio en el mapa"
                _type = "n_notif"
                continuar = False

            if b_region_id == '':
                message += " - El edificio debe pertenecer a una región"
                _type = "n_notif"
                continuar = False

            #Valida por si le da muchos clics al boton
            buildingValidate = Building.objects.filter(building_name=b_name)
            if buildingValidate:
                message = "Ya existe un Edificio con ese nombre"
                _type = "n_notif"
                continuar = False

            post = {
                'b_name': b_name,
                'b_description': b_description,
                'b_company': int(b_company),
                'b_type_arr': b_type_arr,
                'b_mt2': b_mt2,
                'b_electric_rate_id': int(b_electric_rate_id),
                'b_country_id': b_country_id,
                'b_country': b_country_name,
                'b_state_id': b_state_id,
                'b_state': b_state_name,
                'b_municipality_id': b_municipality_id,
                'b_municipality': b_municipality_name,
                'b_neighborhood_id': b_neighborhood_id,
                'b_neighborhood': b_neighborhood_name,
                'b_street_id': b_street_id,
                'b_street': b_street_name,
                'b_ext': b_ext,
                'b_int': b_int,
                'b_zip': b_zip,
                'b_long': b_long,
                'b_lat': b_lat,
                'b_region_id': int(b_region_id),
                'b_time_zone': b_time_zone
            }

            if continuar:
                #se obtiene el objeto de la tarifa
                tarifaObj = get_object_or_404(ElectricRates,
                                              pk=b_electric_rate_id)

                #Se obtiene la compañia
                companyObj = get_object_or_404(Company, pk=b_company)

                #Se obtiene el objeto de la region
                regionObj = get_object_or_404(Region, pk=b_region_id)

                countryObj, stateObj, municipalityObj, neighborhoodObj, \
                streetObj = location_objects(
                    b_country_id, b_country_name,
                    b_state_id, b_state_name, b_municipality_id,
                    b_municipality_name, b_neighborhood_id, b_neighborhood_name,
                    b_street_id, b_street_name)

                #Se crea la cadena con la direccion concatenada
                formatted_address = streetObj.calle_name + " " + b_ext
                if b_int:
                    formatted_address += "-" + b_int
                formatted_address += " Colonia: " + \
                                     neighborhoodObj.colonia_name + " " + \
                                     municipalityObj.municipio_name
                formatted_address += " " + stateObj.estado_name + " " + \
                                     countryObj.pais_name + "C.P." + b_zip

                #Se da de alta el edificio
                newBuilding = Building(
                    building_name=b_name,
                    building_description=b_description,
                    building_formatted_address=formatted_address,
                    pais=countryObj,
                    estado=stateObj,
                    municipio=municipalityObj,
                    colonia=neighborhoodObj,
                    calle=streetObj,
                    region=regionObj,
                    building_external_number=b_ext,
                    building_internal_number=b_int,
                    building_code_zone=b_zip,
                    building_long_address=b_long,
                    building_lat_address=b_lat,
                    electric_rate=tarifaObj,
                    mts2_built=b_mt2,
                )
                newBuilding.save()
                IndustrialEquipment(alias="SA de "+b_name,
                                    building=newBuilding).save()

                #Se da de alta la zona horaria del edificio
                print ("prueba")
                timeZone = Timezones.objects.get(id=b_time_zone)
                newTimeZone = TimezonesBuildings(
                    building = newBuilding,
                    time_zone = timeZone)
                newTimeZone.save()
                #Se da de alta la fecha de corte

                date_init = datetime.datetime.today().utcnow().replace(
                    tzinfo=pytz.utc)
                billing_month = datetime.date(year=date_init.year,
                                              month=date_init.month, day=1)

                new_cut = MonthlyCutDates(
                    building=newBuilding,
                    billing_month=billing_month,
                    date_init=date_init,
                )
                new_cut.save()


                #Se relaciona la compania con el edificio
                newBldComp = CompanyBuilding(
                    company=companyObj,
                    building=newBuilding,
                )
                newBldComp.save()

                #Se dan de alta los tipos de edificio
                for b_type in b_type_arr:
                    #Se obtiene el objeto del tipo de edificio
                    typeObj = get_object_or_404(BuildingType, pk=b_type)
                    bt_n = newBuilding.building_name + " - " + \
                           typeObj.building_type_name
                    newBuildingTypeBuilding = BuildingTypeForBuilding(
                        building=newBuilding,
                        building_type=typeObj,
                        building_type_for_building_name=bt_n
                    )
                    newBuildingTypeBuilding.save()

                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')
                        #Se obtiene el objeto tipo de atributo
                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(
                            pk=atr_value_arr[1])

                        newBldAtt = BuildingAttributesForBuilding(
                            building=newBuilding,
                            building_attributes=attribute_obj,
                            building_attributes_value=atr_value_arr[2]
                        )
                        newBldAtt.save()

                electric_device_type = ElectricDeviceType.objects.get(
                    electric_device_type_name="Total Edificio")
                cu = ConsumerUnit(
                    building=newBuilding,
                    electric_device_type=electric_device_type,
                    profile_powermeter=VIRTUAL_PROFILE
                )
                cu.save()
                #Add the consumer_unit instance for the DW
                populate_data_warehouse_extended(
                    populate_instants=None,
                    populate_consumer_unit_profiles=True,
                    populate_data=None)

                template_vars["message"] = "Edificio creado exitosamente"
                template_vars["type"] = "n_success"

                if has_permission(request.user, VIEW,
                                  "Ver edificios") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/edificios?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/add_building.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def edit_building(request, id_bld):
    if has_permission(request.user, UPDATE,
                      "Modificar edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        _type = ''

        #Se obtienen las empresas
        empresas_lst = get_all_companies_for_operation("Modificar edificios",
                                                       UPDATE, request.user)

        #Se obtienen las tarifas
        tarifas = ElectricRates.objects.all()

        #Se obtiene la zona horaria
        t_zone = Timezones.objects.all()
        t_zone_id = TimezonesBuildings.objects.get(building=id_bld)

        #Se obtienen los tipos de edificios
        tipos_edificio_lst = BuildingType.objects.filter(
            building_type_status=1).order_by('building_type_name')

        #Se obtienen las regiones
        regiones_lst = Region.objects.all()

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.filter(
            building_attributes_type_status=1).order_by(
                'building_attributes_type_name')

        #Se obtiene la información del edificio
        buildingObj = get_object_or_404(Building, pk=id_bld)

        #Se obtiene la compañia
        companyBld = CompanyBuilding.objects.filter(building=buildingObj)

        #Se obtienen los tipos de edificio
        b_type_arr = BuildingTypeForBuilding.objects.filter(
            building=buildingObj).values_list("building_type__pk", flat=True)

        #Se obtienen todos los atributos
        building_attributes = BuildingAttributesForBuilding.objects.filter(
            building=buildingObj).defer("building")
        string_attributes = ''
        if building_attributes:
            for bp_att in building_attributes:
                building_attributes_type_name = bp_att.building_attributes.\
                    building_attributes_type.building_attributes_type_name

                building_attributes_name = bp_att.building_attributes.\
                    building_attributes_name

                building_attributes_type_pk = str(
                    bp_att.building_attributes.building_attributes_type.pk)

                bp_att_building_attributes_pk = str(
                    bp_att.building_attributes.pk)

                bp_att_building_attributes_value = str(
                    bp_att.building_attributes_value)
                string_attributes += '<div  class="extra_attributes_building">' \
                                     '<span class="delete_attr_icon">' \
                                     '<a href="#eliminar" class="delete ' \
                                     'hidden_icon" ' + \
                                     'title="eliminar atributo"></a></span>' + \
                                     '<span class="tip_attribute_part">' + \
                                     building_attributes_type_name + \
                                     '</span>' + \
                                     '<span class="attribute_part">' + \
                                     building_attributes_name + \
                                     '</span>' + \
                                     '<span class="attribute_value_part">' + \
                                     str(bp_att.building_attributes_value) + \
                                     '</span>' + \
                                     '<input type="hidden" name="atributo_' + \
                                     building_attributes_type_pk + \
                                     '_' + bp_att_building_attributes_pk + \
                                     '" ' + 'value="' + \
                                     building_attributes_type_pk + ',' + \
                                     bp_att_building_attributes_pk + ',' + \
                                     bp_att_building_attributes_value + \
                                     '"/></div>'
        #TODO regresar la zona horaria
        post = {
            'b_name': buildingObj.building_name,
            'b_description': buildingObj.building_description,
            'b_company': companyBld[0].company.pk,
            'b_type_arr': b_type_arr,
            'b_mt2': buildingObj.mts2_built,
            'b_electric_rate_id': buildingObj.electric_rate.pk,
            'b_country_id': buildingObj.pais_id,
            'b_country': buildingObj.pais.pais_name,
            'b_state_id': buildingObj.estado_id,
            'b_state': buildingObj.estado.estado_name,
            'b_municipality_id': buildingObj.municipio_id,
            'b_municipality': buildingObj.municipio.municipio_name,
            #'b_timezone': buildingObj.municipio.municipio_name,
            'b_neighborhood_id': buildingObj.colonia_id,
            'b_neighborhood': buildingObj.colonia.colonia_name,
            'b_street_id': buildingObj.calle_id,
            'b_street': buildingObj.calle.calle_name,
            'b_ext': buildingObj.building_external_number,
            'b_int': buildingObj.building_internal_number,
            'b_zip': buildingObj.building_code_zone,
            'b_long': buildingObj.building_long_address,
            'b_lat': buildingObj.building_lat_address,
            'b_region_id': buildingObj.region_id,
            'b_attributes': string_attributes,
            'b_time_zone_id' : t_zone_id.time_zone.id

        }

        if request.method == "POST":
            b_name = request.POST.get('b_name').strip()
            b_description = request.POST.get('b_description').strip()
            b_company = request.POST.get('b_company').strip()
            b_type_arr = request.POST.getlist('b_type')
            b_mt2 = request.POST.get('b_mt2').strip()
            b_electric_rate_id = request.POST.get('b_electric_rate')
            b_country_id = request.POST.get('b_country_id')
            b_state_id = request.POST.get('b_state_id')
            b_municipality_id = request.POST.get('b_municipality_id')
            b_neighborhood_id = request.POST.get('b_neighborhood_id')
            b_street_id = request.POST.get('b_street_id')
            b_ext = request.POST.get('b_ext').strip()
            b_int = request.POST.get('b_int').strip()
            b_zip = request.POST.get('b_zip').strip()
            b_long = request.POST.get('b_longitude')
            b_lat = request.POST.get('b_latitude')
            b_region_id = request.POST.get('b_region')
            b_time_zone = request.POST.get('b_time_zone')

            continuar = True
            if b_name == '':
                message = "El nombre del Edificio no puede quedar vacío"
                _type = "n_notif"
                continuar = False
            elif not variety.validate_string(b_name):
                message = "El nombre del Edificio contiene caracteres inválidos"
                _type = "n_notif"
                b_name = ""
                continuar = False

            if b_company == '':
                message += " - Se debe seleccionar una empresa"
                _type = "n_notif"
                continuar = False

            if not b_type_arr:
                message += " - El edificio debe ser al menos de un tipo"
                _type = "n_notif"
                continuar = False

            if b_electric_rate_id == '':
                message += " - Se debe seleccionar un tipo de tarifa"
                _type = "n_notif"
                continuar = False

            if b_ext == '':
                message += " - El edificio debe tener un número exterior"
                _type = "n_notif"
                continuar = False

            if b_zip == '':
                message += " - El edificio debe tener un código postal"
                _type = "n_notif"
                continuar = False

            if b_long == '' and b_lat == '':
                message += " - Debes ubicar el edificio en el mapa"
                _type = "n_notif"
                continuar = False

            if b_region_id == '':
                message += " - El edificio debe pertenecer a una región"
                _type = "n_notif"
                continuar = False

            #Valida el nombre (para el caso de los repetidos)

            if buildingObj.building_name != b_name:
                #Valida por si le da muchos clics al boton
                buildingValidate = Building.objects.filter(building_name=b_name)
                if buildingValidate:
                    message = "Ya existe un Edificio con ese nombre"
                    _type = "n_notif"
                    continuar = False

            post = {
                'b_name': buildingObj.building_name,
                'b_description': buildingObj.building_description,
                'b_company': companyBld[0].company.pk,
                'b_type_arr': b_type_arr, 'b_mt2': buildingObj.mts2_built,
                'b_electric_rate_id': buildingObj.electric_rate.pk,
                'b_country_id': buildingObj.pais_id,
                'b_country': buildingObj.pais.pais_name,
                'b_state_id': buildingObj.estado_id,
                'b_state': buildingObj.estado.estado_name,
                'b_municipality_id': buildingObj.municipio_id,
                'b_municipality': buildingObj.municipio.municipio_name,
                'b_neighborhood_id': buildingObj.colonia_id,
                'b_neighborhood': buildingObj.colonia.colonia_name,
                'b_street_id': buildingObj.calle_id,
                'b_street': buildingObj.calle.calle_name,
                'b_ext': buildingObj.building_external_number,
                'b_int': buildingObj.building_internal_number,
                'b_zip': buildingObj.building_code_zone,
                'b_long': buildingObj.building_long_address,
                'b_lat': buildingObj.building_lat_address,
                'b_region_id': buildingObj.region_id,
                'b_time_zone_id' : t_zone_id.time_zone.id
            }

            if continuar:
                #se obtiene el objeto de la tarifa
                tarifaObj = get_object_or_404(ElectricRates,
                                              pk=b_electric_rate_id)

                #Se obtiene la compañia
                companyObj = get_object_or_404(Company, pk=b_company)

                #Se obtiene el objeto de la region
                regionObj = get_object_or_404(Region, pk=b_region_id)

                countryObj, stateObj, municipalityObj, neighborhoodObj, \
                streetObj = location_objects(
                    b_country_id, request.POST.get('b_country'),
                    b_state_id, request.POST.get('b_state'), b_municipality_id,
                    request.POST.get('b_municipality'), b_neighborhood_id,
                    request.POST.get('b_neighborhood'),
                    b_street_id, request.POST.get('b_street'))

                #Se crea la cadena con la direccion concatenada
                formatted_address = streetObj.calle_name + " " + b_ext
                if b_int:
                    formatted_address += "-" + b_int
                formatted_address += " Colonia: " + \
                                     neighborhoodObj.colonia_name + " " + \
                                     municipalityObj.municipio_name
                formatted_address += " " + stateObj.estado_name + " " + \
                                     countryObj.pais_name + "C.P." + b_zip
                if b_mt2 == '':
                    b_mt2 = 0
                    #Se edita la info el edificio
                buildingObj.building_name = b_name
                buildingObj.building_description = b_description
                buildingObj.building_formatted_address = formatted_address
                buildingObj.pais = countryObj
                buildingObj.estado = stateObj
                buildingObj.municipio = municipalityObj
                buildingObj.colonia = neighborhoodObj
                buildingObj.calle = streetObj
                buildingObj.region = regionObj
                buildingObj.building_external_number = b_ext
                buildingObj.building_internal_number = b_int
                buildingObj.building_code_zone = b_zip
                buildingObj.building_long_address = b_long
                buildingObj.building_lat_address = b_lat
                buildingObj.electric_rate = tarifaObj
                buildingObj.mts2_built = b_mt2
                buildingObj.save()

                #Se elimina la relacion compania - edificio
                bld_comp = CompanyBuilding.objects.filter(building=buildingObj)
                bld_comp.delete()

                #Se relaciona la compania con el edificio
                newBldComp = CompanyBuilding(
                    company=companyObj,
                    building=buildingObj,
                )
                newBldComp.save()

                #Se eliminan todas las relaciones edificio - tipo
                bld_type = BuildingTypeForBuilding.objects.filter(
                    building=buildingObj)
                bld_type.delete()

                #Se dan de alta los tipos de edificio
                for b_type in b_type_arr:
                    #Se obtiene el objeto del tipo de edificio
                    typeObj = get_object_or_404(BuildingType, pk=b_type)
                    b_name = buildingObj.building_name + " - " + \
                             typeObj.building_type_name
                    newBuildingTypeBuilding = BuildingTypeForBuilding(
                        building=buildingObj,
                        building_type=typeObj,
                        building_type_for_building_name=b_name
                    )
                    newBuildingTypeBuilding.save()

                #Se eliminan los atributos del edificio y se dan de alta
                # los nuevos

                oldAtttributes = BuildingAttributesForBuilding.objects.filter(
                    building=buildingObj)
                oldAtttributes.delete()

                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')
                        #Se obtiene el objeto tipo de atributo
                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(
                            pk=atr_value_arr[1])

                        newBldAtt = BuildingAttributesForBuilding(
                            building=buildingObj,
                            building_attributes=attribute_obj,
                            building_attributes_value=atr_value_arr[2]
                        )
                        newBldAtt.save()
                # Se actualiza zona horaria
                hour_type = Timezones.objects.get(id=b_time_zone)
                t_zone_id.time_zone = hour_type
                t_zone_id.save()

                #Se actualiza el edificio para hacer el cambio de horario en caso de que sea el edificio en uso
                if request.session['main_building'].id == long(id_bld):
                    request.session['timezone']= get_google_timezone(
                                request.session['main_building'])
                    tz = pytz.timezone(request.session.get('timezone'))
                    if tz:
                        timezone.activate(tz)


                message = "Edificio editado exitosamente"
                _type = "n_success"
                if has_permission(request.user, VIEW,
                                  "Ver edificios") or request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/edificios?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             company=company,
                             post=post,
                             empresas_lst=empresas_lst,
                             tipos_edificio_lst=tipos_edificio_lst,
                             tarifas=tarifas,
                             regiones_lst=regiones_lst,
                             zonas_lst=t_zone,
                             tipos_atributos=tipos_atributos,
                             operation="edit",
                             message=message,
                             type=_type, sidebar=request.session['sidebar']
        )

        template_vars_template = RequestContext(request, template_vars)

        return render_to_response(
            "consumption_centers/buildings/add_building.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def info_building(request):
    if has_permission(request.user, UPDATE,
                      "Ver edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        message = ''
        _type = ''

        #Se obtienen los tipos de edificios
        tipos_edificio_lst = BuildingType.objects.filter(
            building_type_status=1).order_by('building_type_name')


        #Se obtiene la información del edificio
        buildingObj = get_object_or_404(Building, pk=empresa.pk)


        #Dirección Concatenada
        address = buildingObj.calle.calle_name+" "+\
                  buildingObj.building_external_number
        if buildingObj.building_internal_number:
            address += "-"+buildingObj.building_internal_number
        address += ". "+buildingObj.colonia.colonia_name+", "+\
                   buildingObj.municipio.municipio_name+" "+\
                   "<BR>"+buildingObj.estado.estado_name+". "+\
                   buildingObj.building_code_zone+". "+\
                   buildingObj.pais.pais_name

        #Se obtiene la compañia
        companyBld = CompanyBuilding.objects.filter(building=buildingObj)

        #Se obtienen los tipos de edificio
        b_type_arr_names = BuildingTypeForBuilding.objects.filter(
            building=buildingObj).values_list(
                "building_type__building_type_name", flat=True)

        #Se obtienen todos los atributos
        building_attributes = BuildingAttributesForBuilding.objects.filter(
            building=buildingObj).defer("building")
        string_attributes = ''
        if building_attributes:
            for bp_att in building_attributes:
                building_attributes_type_name = bp_att.building_attributes.\
                building_attributes_type.building_attributes_type_name

                building_attributes_name = bp_att.building_attributes.\
                building_attributes_name

                string_attributes += '<label class="g3">'+\
                                     building_attributes_type_name+"</label>"+\
                                     '<span class="g5">'+\
                                     building_attributes_name+'</span>'+\
                                     '<span class="g3">'+\
                                     str(bp_att.building_attributes_value)+\
                                     '</span>'

        hierarchy_list = get_hierarchy_list(buildingObj, request.user)

        #Se obtiene el equipo industrial
        industrial_eq = IndustrialEquipment.objects.filter(building = buildingObj)

        #TODO regresar la zona horaria
        post = {
            'b_name': buildingObj.building_name,
            'b_description': buildingObj.building_description,
            'b_company': companyBld[0].company.company_name,
            'b_type_arr_names': b_type_arr_names,
            'b_mt2': buildingObj.mts2_built,
            'b_electric_rate_name': buildingObj.electric_rate.electric_rate_name,
            'b_address': address,
            'b_long': buildingObj.building_long_address,
            'b_lat': buildingObj.building_lat_address,
            'b_region_name': buildingObj.region.region_name,
            'b_attributes': string_attributes,
            'hierarchy': hierarchy_list,
            'industrial_eqp':industrial_eq[0].pk
        }

        template_vars = dict(datacontext=datacontext,
                             company=company,
                             empresa=empresa,
                             post=post,
                             tipos_edificio_lst=tipos_edificio_lst,
                             message=message,
                             type=_type, sidebar=request.session['sidebar']
        )

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/see_building.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

@login_required(login_url='/')
def view_building(request):
    if has_permission(request.user, VIEW,
                      "Ver edificios") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']

        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_state = 'asc'
        order_municipality = 'asc'
        order_company = 'asc'
        order_status = 'asc'
        order = "building__building_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-building__building_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_state" in request.GET:
                if request.GET["order_state"] == "asc":
                    order = "building__estado__estado_name"
                    order_state = "desc"
                else:
                    order = "-building__estado__estado_name"

            if "order_municipality" in request.GET:
                if request.GET["order_municipality"] == "asc":
                    order = "building__municipio__municipio_name"
                    order_municipality = "desc"
                else:
                    order = "-building__municipio__municipio_name"
                    order_municipality = "asc"

            if "order_company" in request.GET:
                if request.GET["order_company"] == "asc":
                    order = "company__company_name"
                    order_company = "desc"
                else:
                    order = "-company__company_name"
                    order_company = "asc"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "building__building_status"
                    order_status = "desc"
                else:
                    order = "-building__building_status"
                    order_status = "asc"

        if search:
            lista = CompanyBuilding.objects.filter(
                Q(building__building_name__icontains=request.GET['search']) |
                Q(building__estado__estado_name__icontains=
                  request.GET['search']) |
                Q(building__municipio__municipio_name__icontains=
                  request.GET['search']) |
                Q(company__company_name__icontains=request.GET['search'])
            ).exclude(building__building_status=2).order_by(order)

        else:
            lista = CompanyBuilding.objects.all().exclude(
                building__building_status=2).order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_state=order_state,
                             order_municipality=order_municipality,
                             order_company=order_company,
                             order_status=order_status,
                             datacontext=datacontext,
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/building.html",
                                  template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_building(request):
    if has_permission(request.user, UPDATE,
                      "Modificar edificios") or request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'status':
            for key in request.POST:
                if re.search('^bld_\w+', key):
                    r_id = int(key.replace("bld_", ""))
                    building = get_object_or_404(Building, pk=r_id)
                    if building.building_status == 0:
                        building.building_status = 1
                    elif building.building_status == 1:
                        building.building_status = 0
                    building.save()

            mensaje = "Los Edificios han cambiado su estatus correctamente"
            return HttpResponseRedirect("/buildings/edificios/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/buildings/edificios/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        datacontext = get_buildings_context(request.user)[0]
        context = {}
        if datacontext:
            context = {"datacontext": datacontext}
        return render_to_response("generic_error.html",
                                  RequestContext(request, context))


@login_required(login_url='/')
def status_building(request, id_bld):
    if has_permission(request.user, UPDATE,
                      "Modificar edificios") or request.user.is_superuser:
        building = get_object_or_404(Building, pk=id_bld)

        if building.building_status == 0:
            building.building_status = 1
            str_status = "Activo"
        else: #if building.building_status == 1:
            building.building_status = 0
            str_status = "Inactivo"

        building.save()

        mensaje = "El estatus del edificio " + building.building_name + \
                  " ha cambiado a " + str_status
        _type = "n_success"

        return HttpResponseRedirect("/buildings/edificios/?msj=" + mensaje +
                                    "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

####################################################
#          CONSUMER UNITS
####################################################


@login_required(login_url='/')
def add_ie(request):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["company"] = request.session['company']
    permission = "Alta de equipos industriales"
    if has_permission(request.user, CREATE,
                      permission) or \
            request.user.is_superuser:

        buildings = get_all_buildings_for_operation(
            permission, CREATE, request.user)
        template_vars['buildings'] = buildings
        if request.method == 'POST':
            template_vars["post"] = request.POST.copy()
            template_vars["post"]['ie_building'] = int(
                template_vars["post"]['ie_building'])
            building = Building.objects.get(pk=int(request.POST['ie_building']))
            ie = IndustrialEquipment(
                alias=request.POST['ie_alias'].strip(),
                description=request.POST['ie_desc'].strip(),
                server=request.POST['ie_server'].strip(),
                building=building,
                modified_by=request.user
            )
            ie.save()
            regenerate_ie_config(ie.pk, request.user)
            message = "El equipo industrial se ha creado exitosamente"
            _type = "n_success"
            if has_permission(request.user, VIEW,
                              "Ver equipos industriales") or \
                    request.user.is_superuser:
                return HttpResponseRedirect(
                    "/buildings/industrial_equipments?msj=" +
                    message +
                    "&ntype=" + _type)
            template_vars["message"] = message
            template_vars["type"] = type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/consumer_units/ind_eq.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def edit_ie(request, id_ie):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["company"] = request.session['company']
    template_vars["operation"] = "edit"
    industrial_eq = get_object_or_404(IndustrialEquipment, pk=int(id_ie))
    template_vars["id_ie"] = id_ie
    permission = "Modificar equipos industriales"
    if has_permission(request.user, UPDATE,
                      permission) or \
            request.user.is_superuser:
        buildings = get_all_buildings_for_operation(
            permission, CREATE, request.user)
        template_vars['buildings'] = buildings
        #Asociated powermeters
        if has_permission(
                request.user,
                CREATE,
                "Asignación de medidores eléctricos a equipos industriales") \
            or request.user.is_superuser:
            order_alias = 'asc'
            order_serial = 'asc'
            order_model = 'asc'
            order_status = 'asc'
            order = "powermeter__powermeter_anotation" #default order
            if "order_alias" in request.GET:
                if request.GET["order_alias"] == "desc":
                    order = "-powermeter__powermeter_anotation"
                    order_alias = "asc"
                else:
                    order_alias = "desc"
            else:
                if "order_model" in request.GET:
                    if request.GET["order_model"] == "asc":
                        order = "powermeter__powermeter_model__powermeter_brand"
                        order_model = "desc"
                    else:
                        order = \
                            "-powermeter__powermeter_model__powermeter_brand"
                        order_model = "asc"

                if "order_serial" in request.GET:
                    if request.GET["order_serial"] == "asc":
                        order = "powermeter__powermeter_serial"
                        order_serial = "desc"
                    else:
                        order = "-powermeter__powermeter_serial"
                        order_serial = "asc"

                if "order_status" in request.GET:
                    if request.GET["order_status"] == "asc":
                        order = "powermeter__status"
                        order_status = "desc"
                    else:
                        order = "-powermeter__status"
                        order_status = "asc"

            lista = PowermeterForIndustrialEquipment.objects.filter(
                industrial_equipment=industrial_eq
            ).order_by(order)
            template_vars['order_alias'] = order_alias
            template_vars['order_model'] = order_model
            template_vars['order_serial'] = order_serial
            template_vars['order_status'] = order_status
            template_vars['powermeters'] = [pm.powermeter for pm in lista]

            if 'msj' in request.GET:
                template_vars['message'] = request.GET['msj']
                template_vars['msg_type'] = request.GET['ntype']

            template_vars['ver_medidores'] = True
        else:
            template_vars['ver_medidores'] = False

        if request.method == 'POST':
            building = Building.objects.get(pk=int(request.POST['ie_building']))
            industrial_eq.alias = request.POST['ie_alias'].strip()
            industrial_eq.description = request.POST['ie_desc'].strip()
            industrial_eq.server = request.POST['ie_server'].strip()
            industrial_eq.building = building
            industrial_eq.modified_by = request.user
            industrial_eq.save()
            regenerate_ie_config(industrial_eq.pk, request.user)
            message = "El equipo industrial se ha actualizado exitosamente"
            _type = "n_success"
            if has_permission(request.user, VIEW,
                              "Ver equipos industriales") or \
                    request.user.is_superuser:
                return HttpResponseRedirect(
                    "/buildings/industrial_equipments?msj=" +
                    message +
                    "&ntype=" + _type)
            template_vars["message"] = message
            template_vars["type"] = type
        template_vars["post"] = dict(ie_alias=industrial_eq.alias,
                                     ie_desc=industrial_eq.description,
                                     ie_server=industrial_eq.server,
                                     ie_building = industrial_eq.building.pk)


    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

    template_vars_template = RequestContext(request, template_vars)

    return render_to_response(
            "consumption_centers/consumer_units/ind_eq.html",
            template_vars_template)


@login_required(login_url='/')
def see_ie(request, id_ie):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']

    if has_permission(request.user, VIEW,
                      "Ver equipos industriales") or request.user.is_superuser:
        template_vars["industrial_eq"] = get_object_or_404(IndustrialEquipment,
                                                           pk=int(id_ie))

        #Asociated powermeters
        if has_permission(request.user, VIEW,
                          "Ver medidores eléctricos") or \
                request.user.is_superuser:
            order_alias = 'asc'
            order_serial = 'asc'
            order_model = 'asc'
            order_status = 'asc'
            order = "powermeter__powermeter_anotation" #default order
            if "order_alias" in request.GET:
                if request.GET["order_alias"] == "desc":
                    order = "-powermeter__powermeter_anotation"
                    order_alias = "asc"
                else:
                    order_alias = "desc"
            else:
                if "order_model" in request.GET:
                    if request.GET["order_model"] == "asc":
                        order = "powermeter__powermeter_model__powermeter_brand"
                        order_model = "desc"
                    else:
                        order = \
                            "-powermeter__powermeter_model__powermeter_brand"
                        order_model = "asc"

                if "order_serial" in request.GET:
                    if request.GET["order_serial"] == "asc":
                        order = "powermeter__powermeter_serial"
                        order_serial = "desc"
                    else:
                        order = "-powermeter__powermeter_serial"
                        order_serial = "asc"

                if "order_status" in request.GET:
                    if request.GET["order_status"] == "asc":
                        order = "powermeter__status"
                        order_status = "desc"
                    else:
                        order = "-powermeter__status"
                        order_status = "asc"

            lista = PowermeterForIndustrialEquipment.objects.filter(
                industrial_equipment=template_vars["industrial_eq"]
            ).order_by(order)
            template_vars['order_alias'] = order_alias
            template_vars['order_model'] = order_model
            template_vars['order_serial'] = order_serial
            template_vars['order_status'] = order_status
            template_vars['powermeters'] = lista

            if 'msj' in request.GET:
                template_vars['message'] = request.GET['msj']
                template_vars['msg_type'] = request.GET['ntype']

            template_vars['ver_medidores'] = True
            if has_permission(
                    request.user,
                    CREATE,
                    "Asignación de medidores eléctricos a equipos industriales"
            ) or request.user.is_superuser:
                template_vars['show_asign'] = True
            else:
                template_vars['show_asign'] = False
        else:
            template_vars['ver_medidores'] = False
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/consumer_units/see_ie.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_ie(request, id_ie):
    if has_permission(request.user,
                      UPDATE,
                      "Modificar equipos industriales") or \
            request.user.is_superuser:
        ind_eq = get_object_or_404(IndustrialEquipment, pk=id_ie)
        if ind_eq.status:
            ind_eq.status = False
            str_status = "Activo"
        else:
            ind_eq.status = True
            str_status = "Activo"
        ind_eq.modified_by = request.user
        ind_eq.save()
        regenerate_ie_config(ind_eq.pk, request.user)
        mensaje = "El estatus del equipo industrial " + ind_eq.alias + \
                  ", ha cambiado a " + str_status
        _type = "n_success"

        return HttpResponseRedirect(
            "/buildings/industrial_equipments/?msj=" + mensaje +
            "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def status_batch_ie(request):
    if has_permission(request.user,
                      UPDATE,
                      "Modificar equipos industriales") or \
            request.user.is_superuser:
        if request.POST['actions'] != '0':
            for key in request.POST:
                if re.search('^equipo_\w+', key):
                    r_id = int(key.replace("equipo_", ""))
                    equipo_ind = get_object_or_404(IndustrialEquipment, pk=r_id)

                    if equipo_ind.status:
                        equipo_ind.status = False
                    else:
                        equipo_ind.status = True

                    equipo_ind.modified_by = request.user
                    equipo_ind.save()
                    regenerate_ie_config(equipo_ind.pk, request.user)

            mensaje = "Los equipos industriales seleccionados han " \
                      "cambiado su estatus correctamente"
            _type = "n_success"
        else:
            mensaje = str("No se ha seleccionado una acción").decode("utf-8")
            _type = "n_notif"
        return HttpResponseRedirect("/buildings/industrial_equipments/?msj=" +
                                    mensaje + "&ntype=" + _type)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def view_ie(request):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["company"] = request.session['company']

    if has_permission(request.user, VIEW,
                      "Ver equipos industriales") or request.user.is_superuser:
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_server = 'asc'
        order_status = 'asc'
        order = "alias" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-alias"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_server" in request.GET:
                if request.GET["order_state"] == "asc":
                    order = "server"
                    order_server = "desc"
                else:
                    order = "-server"

            if "order_status" in request.GET:
                if request.GET["order_status"] == "asc":
                    order = "building__building_status"
                    order_status = "desc"
                else:
                    order = "-building__building_status"
                    order_status = "asc"

        if search:
            lista = IndustrialEquipment.objects.filter(
                Q(alias__icontains=request.GET['search']) | Q(
                    server__icontains=request.GET['search']) | Q(
                    description=request.GET['search'])).order_by(order)

        else:
            lista = IndustrialEquipment.objects.all().order_by(order)

        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars['order_name'] = order_name
        template_vars['order_server'] = order_server
        template_vars['order_status'] = order_status
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/consumer_units/ie_list.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def search_pm(request):
    """Search for a powermeter wich have an alias or serial number containing
     'term'
     returns a json for jquery automplete
    """
    if "term" in request.GET:
        term = request.GET['term']
        pm_in_ie = PowermeterForIndustrialEquipment.objects.all().values_list(
            "powermeter__pk", flat=True)
        powermeters = Powermeter.objects.filter(
            Q(powermeter_anotation__icontains=term) |
            Q(powermeter_serial__icontains=term)
        ).filter(status=1).exclude(pk__in=pm_in_ie).exclude(
            powermeter_anotation="Medidor Virtual").values(
                "pk", "powermeter_anotation", "powermeter_serial")
        medidores = []
        for medidor in powermeters:
            texto = medidor['powermeter_anotation'] + " - " + \
                    medidor['powermeter_serial']
            medidores.append(dict(value=texto, pk=medidor['pk'], label=texto))
        data = simplejson.dumps(medidores)
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404


@login_required(login_url='/')
def asign_pm(request, id_ie):
    if (has_permission(
            request.user,
            CREATE,
            "Asignación de medidores eléctricos a equipos industriales") or
            request.user.is_superuser) and "pm" in request.GET:
        ie = get_object_or_404(IndustrialEquipment, pk=int(id_ie))

        permission = "Asignación de medidores eléctricos a equipos industriales"
        buildings = get_all_buildings_for_operation(permission, CREATE,
                                                    request.user)

        for buil in buildings:
            if buil == ie.building:
                pm = get_object_or_404(Powermeter, pk=int(request.GET['pm']))
                pm_ie = PowermeterForIndustrialEquipment(
                    powermeter=pm, industrial_equipment=ie)
                pm_ie.save()
                ie.modified_by = request.user
                ie.save()
                regenerate_ie_config(ie.pk, request.user)
                pm_data = dict(
                    pm=pm.pk,
                    alias=pm.powermeter_anotation,
                    modelo=pm.powermeter_model.powermeter_model,
                    marca=pm.powermeter_model.powermeter_brand,
                    serie=pm.powermeter_serial,
                    status=pm.status)
                data = simplejson.dumps([pm_data])
                return HttpResponse(content=data,
                                    content_type="application/json")

        else:
            mensaje = "No tiene permisos sobre este edificio"
            data = simplejson.dumps(mensaje)
            return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404


@login_required(login_url='/')
def detach_pm(request, id_ie):
    if (has_permission(
            request.user,
            UPDATE,
            "Modificar asignaciones de medidores eléctricos a equipos "
            "industriales") or
            request.user.is_superuser) and "pm" in request.GET:
        pm = get_object_or_404(Powermeter, pk=int(request.GET['pm']))
        ie = get_object_or_404(IndustrialEquipment, pk=int(id_ie))
        PowermeterForIndustrialEquipment.objects. \
            filter(powermeter=pm, industrial_equipment=ie).delete()
        ie.modified_by = request.user
        ie.save()
        regenerate_ie_config(ie.pk, request.user)
        mensaje = "El medidor se ha desvinculado"
        return HttpResponseRedirect("/buildings/editar_ie/" +
                                    id_ie + "/?msj=" + mensaje +
                                    "&ntype=n_success")
    else:
        raise Http404

# noinspection PyArgumentList,PyTypeChecker
@login_required(login_url='/')
def configure_ie(request, id_ie):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']

    if has_permission(request.user, VIEW,
                      "Ver equipos industriales") or request.user.is_superuser:
        ie = get_object_or_404(IndustrialEquipment, pk=id_ie)
        template_vars['ie'] = ie
        template_vars['last_changed'] = ie.last_changed
        pms = PowermeterForIndustrialEquipment.objects.filter(
            industrial_equipment=ie).values_list("powermeter__pk", flat=True)
        powermeters = ProfilePowermeter.objects.filter(
            pk__in=pms)
        tz = timezone.get_current_timezone()
        if request.method == "POST":
            template_vars['powermeters'] = []
            for pm in powermeters:
                read_time_rate = request.POST['read_time_rate_' + str(pm.pk)]
                send_time_rate = request.POST['send_rate']

                pm.read_time_rate = read_time_rate
                pm.send_time_rate = send_time_rate
                pm.save()
                template_vars['powermeters'].append(
                    dict(pk=pm.pk,
                         anotation=pm.powermeter.powermeter_anotation,
                         read_time_rate=pm.read_time_rate,
                         send_time_rate=pm.send_time_rate))
            ie.monitor_time_rate = request.POST['send_rate']
            ie.check_config_time_rate = request.POST['check_config_time_rate']
            ie.modified_by = request.user
            ie.save()
            regenerate_ie_config(ie.pk, request.user)
            template_vars['message'] = "El equipo industrial ha guardado su" \
                                       " configuración correctamente"
            template_vars['msg_type'] = "n_success"
        else:
            template_vars['powermeters'] = []
            for pm in powermeters:
                time = variety.convert_from_utc(pm.initial_send_time, tz)
                template_vars['powermeters'].append(
                    dict(pk=pm.pk,
                         anotation=pm.powermeter.powermeter_anotation,
                         read_time_rate=pm.read_time_rate,
                         send_time_rate=pm.send_time_rate,
                         initial_send_time=time,
                         send_time_duration=pm.send_time_duration
                    ))
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/consumer_units/configure_times.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def create_hierarchy(request, id_building):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}

    if datacontext:
        template_vars["datacontext"] = datacontext

    template_vars["sidebar"] = request.session['sidebar']
    #template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']

    if has_permission(request.user, CREATE,
                      "Alta de jerarquía de partes") or \
            request.user.is_superuser:
        building = get_object_or_404(Building, pk=id_building)
        _list = get_hierarchy_list(building, request.user)
        template_vars['list'] = _list
        template_vars['building'] = building

        ids_prof = ConsumerUnit.objects.all().values_list(
            "profile_powermeter__pk", flat=True)
        profs = ProfilePowermeter.objects.exclude(
            pk__in=ids_prof).exclude(
                powermeter__powermeter_anotation="No Registrado").exclude(
                    powermeter__powermeter_anotation="Medidor Virtual")
        template_vars['electric_devices'] = ElectricDeviceType.objects.all()
        template_vars['prof_pwmeters'] = profs
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/create_hierarchy.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def add_partbuilding_pop(request, id_building):
    if has_permission(request.user, CREATE,
                      "Alta de partes de edificio") or \
            request.user.is_superuser:
        #Se obtienen los tipos de partes de edificios
        tipos_parte = PartOfBuildingType.objects.all().exclude(
            part_of_building_type_status=0).order_by(
            'part_of_building_type_name')

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.all().exclude(
            building_attributes_type_status=0).order_by(
            'building_attributes_type_name')

        template_vars = dict(
            tipos_parte=tipos_parte,
            tipos_atributos=tipos_atributos,
            building=get_object_or_404(Building,
                                       pk=id_building),
            operation="pop_add"
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/popup_add_partbuilding.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def save_add_part_popup(request):
    if (has_permission(
            request.user,
            CREATE,
            "Alta de partes de edificio") or request.user.is_superuser) \
        and request.method == "POST":
        b_part_name = request.POST.get('b_part_name').strip()
        b_part_description = request.POST.get('b_part_description').strip()
        b_part_type_id = request.POST.get('b_part_type')
        b_part_building_id = request.POST.get('b_building_id')
        b_part_mt2 = request.POST.get('b_part_mt2').strip()

        continuar = True
        if not b_part_name and not b_part_type_id and not b_part_building_id:
            continuar = False
        if continuar:
            #Valida por si le da muchos clics al boton
            partValidate = PartOfBuilding.objects.filter(
                part_of_building_name=b_part_name).filter(
                part_of_building_type__pk=b_part_type_id).filter(
                building__pk=b_part_building_id)
            if partValidate:
                return HttpResponse(status=400)
            else:
                #Se obtiene la instancia del edificio
                buildingObj = get_object_or_404(Building, pk=b_part_building_id)

                #Se obtiene la instancia del tipo de parte de edificio
                part_building_type_obj = get_object_or_404(PartOfBuildingType,
                                                           pk=b_part_type_id)

                if not bool(b_part_mt2):
                    b_part_mt2 = '0'
                else:
                    b_part_mt2 = b_part_mt2.replace(",", "")

                newPartBuilding = PartOfBuilding(
                    building=buildingObj,
                    part_of_building_type=part_building_type_obj,
                    part_of_building_name=b_part_name,
                    part_of_building_description=b_part_description,
                    mts2_built=b_part_mt2
                )
                newPartBuilding.save()
                deviceType = ElectricDeviceType.objects.get(
                    electric_device_type_name="Total parte de un edificio")
                newConsumerUnit = ConsumerUnit(
                    building=buildingObj,
                    part_of_building=newPartBuilding,
                    electric_device_type=deviceType,
                    profile_powermeter=VIRTUAL_PROFILE
                )
                newConsumerUnit.save()
                #Add the consumer_unit instance for the DW
                populate_data_warehouse_extended(
                    populate_instants=None,
                    populate_consumer_unit_profiles=True,
                    populate_data=None)

                for key in request.POST:
                    if re.search('^atributo_\w+', key):
                        atr_value_complete = request.POST.get(key)
                        atr_value_arr = atr_value_complete.split(',')
                        #Se obtiene el objeto tipo de atributo

                        #Se obtiene el objeto atributo
                        attribute_obj = BuildingAttributes.objects.get(
                            pk=atr_value_arr[1])

                        newBldPartAtt = BuilAttrsForPartOfBuil(
                            part_of_building=newPartBuilding,
                            building_attributes=attribute_obj,
                            building_attributes_value=atr_value_arr[2]
                        )
                        newBldPartAtt.save()
                return HttpResponse(content=newConsumerUnit.pk,
                                    content_type="text/plain",
                                    status=200)
        else:
            return HttpResponse(status=400)
    raise Http404


@login_required(login_url='/')
def add_powermeter_popup(request):
    if has_permission(request.user, CREATE,
                      "Alta de medidor electrico") or request.user.is_superuser:
        pw_models_list = PowermeterModel.objects.all().exclude(
            status=0).order_by("powermeter_brand")
        template_vars = dict(modelos=pw_models_list)

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/popup_add_powermeter.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def save_add_powermeter_popup(request):
    if (has_permission(request.user,
                       CREATE,
                       "Alta de medidor electrico") or
            request.user.is_superuser) and request.method == "POST":

        pw_alias = request.POST.get('pw_alias').strip()
        pw_model = request.POST.get('pw_model')
        pw_serial = request.POST.get('pw_serial').strip()
        pw_modbus = 0

        continuar = True
        if pw_alias == '':
            continuar = False
        elif not variety.validate_string(pw_alias):
            pw_alias = ""
            continuar = False

        if pw_model == '':
            continuar = False

        if pw_serial == '':
            continuar = False

        #Valida por si le da muchos clics al boton
        pwValidate = Powermeter.objects.filter(
            powermeter_model__pk=pw_model).filter(
            powermeter_serial=pw_serial)
        if pwValidate:
            continuar = False

        if continuar:
            pw_model = PowermeterModel.objects.get(pk=pw_model)

            newPowerMeter = Powermeter(
                powermeter_model=pw_model,
                powermeter_anotation=pw_alias,
                powermeter_serial=pw_serial,
                modbus_address=pw_modbus
            )
            newPowerMeter.save()
            profile = ProfilePowermeter(powermeter=newPowerMeter)
            profile.save()
            change_profile_electric_data.delay([pw_serial])

            return HttpResponse(content=profile.pk,
                                content_type="text/plain",
                                status=200)
        else:
            return HttpResponse(status=400)
    else:
        raise Http404


@login_required(login_url='/')
def add_electric_device_popup(request):
    if has_permission(request.user, CREATE,
                      "Alta de dispositivos y sistemas eléctricos") or \
            request.user.is_superuser:

        template_vars_template = RequestContext(request,
                                                {"operation": "add_popup"})
        return render_to_response(
            "consumption_centers/buildings/popup_add_electric_device.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def save_add_electric_device_popup(request):
    if has_permission(request.user, CREATE,
                      "Alta de dispositivos y sistemas eléctricos") or \
                    request.user.is_superuser and request.method == "POST":

        edt_name = request.POST['devicetypename'].strip()
        edt_description = request.POST['devicetypedescription'].strip()

        continuar = True
        if edt_name == '':
            continuar = False
        elif not variety.validate_string(edt_name):
            edt_name = ""
            continuar = False

        #Valida por si le da muchos clics al boton
        b_electric_typeValidate = ElectricDeviceType.objects.filter(
            electric_device_type_name=edt_name)
        if b_electric_typeValidate:
            continuar = False

        if continuar:
            newElectricDeviceType = ElectricDeviceType(
                electric_device_type_name=edt_name,
                electric_device_type_description=edt_description
            )
            newElectricDeviceType.save()

            return HttpResponse(content=newElectricDeviceType.pk,
                                content_type="text/plain",
                                status=200)
        else:
            return HttpResponse(status=400)
    else:
        raise Http404


@login_required(login_url='/')
def add_cu(request):
    if (has_permission(
            request.user, CREATE, "Alta de unidades de consumo") or
            request.user.is_superuser) and request.method == "POST":
        post = request.POST
        if post['type_node'] == "1":
            cu = post["node_part"].split("_")
            consumer_unit = get_object_or_404(ConsumerUnit,
                                              pk=int(cu[0]))
            if cu[1] == "cu":
                profile = get_object_or_404(ProfilePowermeter,
                                            pk=int(post['prof_pwr']))
                consumer_unit.profile_powermeter = profile
                consumer_unit.save()
            c_type = "*part"
        else:
            profile = get_object_or_404(ProfilePowermeter,
                                        pk=int(post['prof_pwr']))
            building = get_object_or_404(Building, pk=int(post['building']))
            electric_device_type = get_object_or_404(ElectricDeviceType,
                                                     pk=int(post['node_part']))
            consumer_unit = ConsumerUnit(
                building=building,
                electric_device_type=electric_device_type,
                profile_powermeter=profile
            )
            consumer_unit.save()
            #Add the consumer_unit instance for the DW
            populate_data_warehouse_extended(
                    populate_instants=None,
                    populate_consumer_unit_profiles=True,
                    populate_data=None)
            c_type = "*consumer_unit"
        content = str(consumer_unit.pk) + c_type
        return HttpResponse(content=content,
                            content_type="text/plain",
                            status=200)
    else:
        raise Http404


@login_required(login_url='/')
def del_cu(request, id_cu):
    if (has_permission(request.user, DELETE,"Eliminar unidades de consumo") or\
        has_permission(request.user, UPDATE,"Modificar unidades de consumo")\
        or request.user.is_superuser):
        cu = get_object_or_404(ConsumerUnit, pk=int(id_cu))
        HierarchyOfPart.objects.filter(consumer_unit_composite=cu).delete()
        HierarchyOfPart.objects.filter(consumer_unit_leaf=cu).delete()
        cu.profile_powermeter.profile_powermeter_status = False
        cu.profile_powermeter.save()
        return HttpResponse(content="",
                            content_type="text/plain",
                            status=200)
    else:
        raise Http404


@login_required(login_url='/')
def popup_edit_partbuilding(request, cu_id):
    if has_permission(request.user, UPDATE,
                      "Modificar partes de un edificio") or \
            request.user.is_superuser:
        #Se obtienen los tipos de partes de edificios
        tipos_parte = PartOfBuildingType.objects.all().exclude(
            part_of_building_type_status=0).order_by(
            'part_of_building_type_name')

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.all().exclude(
            building_attributes_type_status=0).order_by(
            'building_attributes_type_name')
        cu = get_object_or_404(ConsumerUnit, pk=int(cu_id))

        building_part = cu.part_of_building

        #Se obtienen todos los atributos
        building_part_attributes = BuilAttrsForPartOfBuil.objects.filter(
            part_of_building=building_part)
        string_attributes = ''
        if building_part_attributes:
            for bp_att in building_part_attributes:
                string_attributes += \
                    '<div  class="extra_attributes_div">' \
                    '<span class="delete_attr_icon">' \
                    '<a href="#eliminar" class="delete ' \
                    'hidden_icon" ' + \
                    'title="eliminar atributo"></a></span>' + \
                    '<span class="tip_attribute_part">' + \
                    bp_att.building_attributes.building_attributes_type.\
                        building_attributes_type_name + \
                    '</span>' + \
                    '<span class="attribute_part">' + \
                    bp_att.building_attributes.building_attributes_name + \
                    '</span>' + \
                    '<span class="attribute_value_part">' + \
                    str(bp_att.building_attributes_value) + \
                    '</span>' + \
                    '<input type="hidden" name="atributo_' + \
                    str(bp_att.building_attributes.building_attributes_type.pk
                    ) + '_' + str(bp_att.building_attributes.pk) + '" ' + \
                    'value="' + str(
                        bp_att.building_attributes.building_attributes_type.pk
                    ) + ',' + str(bp_att.building_attributes.pk) + ',' + \
                    str(bp_att.building_attributes_value) + '"/></div>'

        post = {'b_part_name': building_part.part_of_building_name,
                'b_part_description':
                    building_part.part_of_building_description,
                'b_part_building_id': str(building_part.building.pk),
                'b_part_type': building_part.part_of_building_type.id,
                'b_part_mt2': building_part.mts2_built,
                'b_part_attributes': string_attributes,
        }
        template_vars = dict(post=post,
                             tipos_parte=tipos_parte,
                             tipos_atributos=tipos_atributos,
                             operation="pop_edit",
                             building=building_part.building,
                             cu=cu.pk
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/popup_add_partbuilding.html",
            template_vars_template)
    else:
        raise Http404


@login_required(login_url='/')
def save_edit_part_popup(request, cu_id):
    if (has_permission(request.user, UPDATE,
                       "Modificar partes de un edificio") or
            request.user.is_superuser) and request.method == "POST":
        b_part_name = request.POST.get('b_part_name').strip()
        b_part_description = request.POST.get('b_part_description').strip()
        b_part_type_id = request.POST.get('b_part_type')

        b_part_mt2 = request.POST.get('b_part_mt2').strip()

        cu = get_object_or_404(ConsumerUnit, pk=int(cu_id))
        building_part = cu.part_of_building

        if not bool(b_part_mt2):
            b_part_mt2 = '0'
        else:
            b_part_mt2 = b_part_mt2.replace(",", "")

        continuar = True
        if b_part_name == '':
            continuar = False

        if b_part_type_id == '':
            continuar = False

        if continuar:
            #Se obtiene la instancia del tipo de parte de edificio
            part_building_type_obj = get_object_or_404(PartOfBuildingType,
                                                       pk=b_part_type_id)

            building_part.part_of_building_name = b_part_name
            building_part.part_of_building_description = b_part_description
            building_part.part_of_building_type = part_building_type_obj
            building_part.mts2_built = b_part_mt2
            building_part.save()

            #Se eliminan todos los atributos existentes
            builAttrsElim = BuilAttrsForPartOfBuil.objects.filter(
                part_of_building=building_part)
            builAttrsElim.delete()

            #Se insertan los nuevos
            for key in request.POST:
                if re.search('^atributo_\w+', key):
                    atr_value_complete = request.POST.get(key)
                    atr_value_arr = atr_value_complete.split(',')

                    #Se obtiene el objeto atributo
                    attribute_obj = BuildingAttributes.objects.get(
                        pk=atr_value_arr[1])

                    newBldPartAtt = BuilAttrsForPartOfBuil(
                        part_of_building=building_part,
                        building_attributes=attribute_obj,
                        building_attributes_value=atr_value_arr[2]
                    )
                    newBldPartAtt.save()

            return HttpResponse(content=cu.pk,
                                content_type="text/plain",
                                status=200)
        else:
            return HttpResponse(status=400)
    else:
        raise Http404


@login_required(login_url='/')
def edit_cu(request, cu_id):
    if (has_permission(request.user, UPDATE,
                       "Modificar unidades de consumo") or has_permission(
            request.user, CREATE, "Alta de unidades de consumo") or
            request.user.is_superuser) and request.method == "POST":
        post = request.POST

        consumer_unit = get_object_or_404(ConsumerUnit, pk=int(cu_id))

        if post['prof_pwr_edit'] != "0":
            if post['prof_pwr_edit'] == "del_pw":
                profile = VIRTUAL_PROFILE
            else:
                profile = get_object_or_404(ProfilePowermeter,
                                            pk=int(post['prof_pwr_edit']))
            consumer_unit.profile_powermeter = profile

        if post['edit_part'] == "cu":
            if post['node_part_edit'] != "0":
                device_t = get_object_or_404(ElectricDeviceType,
                                             pk=int(post['node_part_edit']))
                consumer_unit.electric_device_type = device_t
        consumer_unit.save()
        return HttpResponse(status=200)
    else:
        raise Http404


@login_required(login_url='/')
def add_hierarchy_node(request):
    if (has_permission(request.user, CREATE,
                       "Alta de jerarquía de partes") or
            request.user.is_superuser) and request.method == "POST":
        parent_cu = get_object_or_404(ConsumerUnit, pk=int(request.POST['pp']))
        parent_part = parent_cu.part_of_building

        pp = True if request.POST['pw'] == "1" else False

        if request.POST['pl'] != '':
            cu_leaf = get_object_or_404(ConsumerUnit,
                                        pk=int(request.POST['pl']))
            part_leaf = cu_leaf.part_of_building

            h = HierarchyOfPart(part_of_building_composite=parent_part,
                                part_of_building_leaf=part_leaf,
                                ExistsPowermeter=pp)
            h.save()
            ie_building = cu_leaf.building
            ie = IndustrialEquipment.objects.get(building=ie_building)
            set_alarm_json(ie_building, request.user)
            regenerate_ie_config(ie.pk, request.user)
            return HttpResponse(status=200)
        elif request.POST['cl'] != '':
            cu_leaf = get_object_or_404(ConsumerUnit,
                                        pk=int(request.POST['cl']))
            h = HierarchyOfPart(part_of_building_composite=parent_part,
                                consumer_unit_leaf=cu_leaf,
                                ExistsPowermeter=pp)
            h.save()
            ie_building = cu_leaf.building
            ie = IndustrialEquipment.objects.get(building=ie_building)
            set_alarm_json(ie_building, user)
            regenerate_ie_config(ie.pk, user)

            return HttpResponse(status=200)
        else:
            raise Http404
    else:
        raise Http404


@login_required(login_url='/')
def reset_hierarchy(request):
    if (has_permission(request.user, UPDATE,
                       "Modificar jerarquía de partes de edificios") or
            request.user.is_superuser) and request.method == "POST":
        building = get_object_or_404(Building, pk=int(request.POST['building']))
        cus = ConsumerUnit.objects.filter(building=building)
        ie = IndustrialEquipment.objects.get(building=building)
        parts = []
        consumer_u = []
        for cu in cus:
            if cu.part_of_building:
                parts.append(cu.part_of_building.pk)
            else:
                consumer_u.append(cu.pk)

            param = ElectricParameters.objects.all()[0]
            if cu.profile_powermeter.powermeter.powermeter_anotation != \
                    "Medidor Virtual":
                alarm_cu = Alarms.objects.get_or_create(
                    alarm_identifier="Interrupción de Datos",
                    electric_parameter=param,
                    consumer_unit=cu)
                PowermeterForIndustrialEquipment.objects.get_or_create(
                    powermeter=cu.profile_powermeter.powermeter,
                    industrial_equipment=ie
                )

        h = HierarchyOfPart.objects.filter(
            Q(part_of_building_composite__pk__in=parts) |
            Q(part_of_building_leaf__pk__in=parts) |
            Q(consumer_unit_composite__pk__in=consumer_u) |
            Q(consumer_unit_leaf__pk__in=consumer_u)
        )
        if h:
            h.delete()
        return HttpResponse(status=200)

    else:
        raise Http404


@login_required(login_url='/')
def pw_meditions(request, id_pw):
    if request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}

        if datacontext:
            template_vars["datacontext"] = datacontext

        template_vars["sidebar"] = request.session['sidebar']
        template_vars["empresa"] = request.session['main_building']
        template_vars["company"] = request.session['company']

        pw = get_object_or_404(ProfilePowermeter, pk=int(id_pw))
        if "inicio" not in request.GET:
            f1 = ""
        else:
            f1 = request.GET['inicio']
        if "fin" not in request.GET:
            f2 = ""
        else:
            f2 = request.GET['fin']
        fechas = dict(f1_init=f1, f1_end=f2)
        f1, f2 = get_intervals_1(fechas)
        data = ElectricDataTemp.objects.filter(
            medition_date__range=(f1, f2),
            profile_powermeter=pw)
        data = ThemedElectricDataTempTable(data, prefix="")
        RequestConfig(request, paginate={"per_page": 300}).configure(data)

        template_vars["electric_data"] = data

        return render(request, "consumption_centers/meditions_table.html",
                      template_vars)

    else:
        raise Http404

##==========##

@login_required(login_url='/')
def view_cutdates(request):
    datacontext = get_buildings_context(request.user)[0]
    if request.user.is_superuser:
        empresa = request.session['main_building']

        order_billing = 'asc'
        order = "-billing_month" #default order
        if "order_billing" in request.GET:
            if request.GET["order_billing"] == "desc":
                order = "billing_month"
                order_billing = "asc"
            else:
                order_billing = "desc"

        lista = MonthlyCutDates.objects.filter(
            building=request.session['main_building']).order_by(order)

        tipo_tarifa = empresa.electric_rate

        contenedorMonthly = []
        for lst in lista:

            mCutDateObj = dict()
            mCutDateObj['billing_month'] = lst.billing_month
            mCutDateObj['date_init'] = lst.date_init
            mCutDateObj['date_end'] = lst.date_end
            mCutDateObj['pk'] = lst.pk

            if tipo_tarifa.pk == 1:
                historico = HMHistoricData.objects.filter(monthly_cut_dates = lst )
            elif tipo_tarifa.pk == 2:
                historico = DacHistoricData.objects.filter(monthly_cut_dates = lst )
            elif tipo_tarifa.pk == 3:
                historico = T3HistoricData.objects.filter(monthly_cut_dates = lst )

            if historico:
                mCutDateObj['historico'] = True
            else:
                mCutDateObj['historico'] = False
            contenedorMonthly.append(mCutDateObj)

        paginator = Paginator(contenedorMonthly, 12) # muestra 10 resultados por pagina
        template_vars = dict(order_billing=order_billing,
                             datacontext=datacontext,
                             empresa=empresa,
                             company=request.session['company'],
                             sidebar=request.session['sidebar'])
        # Make sure page request is an int. If not, deliver first page.
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            pag_user = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pag_user = paginator.page(paginator.num_pages)

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/buildings/cutdates.html",
                                  template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


# noinspection PyArgumentList
@login_required(login_url='/')
def set_cutdate(request, id_cutdate):
    datacontext = get_buildings_context(request.user)[0]
    if request.user.is_superuser:
        empresa = request.session['main_building']
        post = ''

        message = ""
        _type = ""

        cutdate_obj = get_object_or_404(MonthlyCutDates, pk=id_cutdate)

        #Crea un arreglo con las horas
        horas = []
        hr = 1
        while hr < 13:
            horas.append(str(hr).zfill(2))
            hr += 1

        #Crea un arreglo con los minutos
        minutos = []
        mn = 0
        while mn < 60:
            minutos.append(str(mn).zfill(2))
            mn += 1

        s_date = cutdate_obj.date_init.astimezone(
            tz=timezone.get_current_timezone())
        s_date_str = s_date.strftime('%I %M %p').split(" ")

        e_ihour = None
        e_iminute = None
        e_ampm = None

        if cutdate_obj.date_end:
            e_date = cutdate_obj.date_end.astimezone(
                tz=timezone.get_current_timezone())
            e_date_str = e_date.strftime('%I %M %p').split(" ")
            e_ihour = e_date_str[0]
            e_iminute = e_date_str[1]
            e_ampm = e_date_str[2]

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             cutdate=cutdate_obj,
                             s_ihour=s_date_str[0],
                             s_iminute=s_date_str[1],
                             s_ampm=s_date_str[2],
                             e_ihour=e_ihour,
                             e_iminute=e_iminute,
                             e_ampm=e_ampm,
                             i_hours=horas,
                             i_minutes=minutos,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            init_str = request.POST.get('date_init').strip()
            end_str = request.POST.get('date_end').strip()

            init_hour = request.POST.get('init_hour')
            init_minutes = request.POST.get('init_minutes')
            init_ampm = request.POST.get('init_ampm')

            end_hour = request.POST.get('end_hour')
            end_minutes = request.POST.get('end_minutes')
            end_ampm = request.POST.get('end_ampm')

            cd_before = None
            cd_before_flag = False
            cd_after = None
            cd_after_flag = False
            continue_flag = True


            #TODO: Cambiar por las nuevas funciones de zonas horarias (De Local a UTC)
            time_str = init_str + " " + init_hour + ":" + init_minutes + \
                       " " + init_ampm
            s_date_str = time.strptime(time_str, "%Y-%m-%d  %I:%M %p")
            s_date_utc_tuple = time.gmtime(time.mktime(s_date_str))
            s_date_utc = datetime.datetime(year=s_date_utc_tuple[0],
                                           month=s_date_utc_tuple[1],
                                           day=s_date_utc_tuple[2],
                                           hour=s_date_utc_tuple[3],
                                           minute=s_date_utc_tuple[4],
                                           tzinfo=pytz.utc)

            e_date_str = time.strptime(
                end_str + " " + end_hour + ":" + end_minutes + " " + end_ampm,
                "%Y-%m-%d  %I:%M %p")
            e_date_utc_tuple = time.gmtime(time.mktime(e_date_str))
            e_date_utc = datetime.datetime(year=e_date_utc_tuple[0],
                                           month=e_date_utc_tuple[1],
                                           day=e_date_utc_tuple[2],
                                           hour=e_date_utc_tuple[3],
                                           minute=e_date_utc_tuple[4],
                                           tzinfo=pytz.utc)

            template_vars['post'] = post

            #Si se modificó la fecha inicial es necesario modificar el
            # mes anterior
            if cutdate_obj.date_init != s_date_utc:
                month_before = cutdate_obj.billing_month + relativedelta(
                    months=-1)
                cutdate_before = MonthlyCutDates.objects.filter(
                    billing_month=month_before).filter(
                    building=request.session['main_building'])

                if cutdate_before:
                    cd_before_flag = True
                    if s_date_utc <= cutdate_before[0].date_init:
                        message = "La fecha de inicio invade todo el periodo" \
                                  " del mes anterior."
                        _type = "n_notif"
                        continue_flag = False
                    else:
                        cd_before = cutdate_before[0]

            if cutdate_obj.date_end:
                #Si el registro tiene fecha final, significa que se esta
                # modificando un mes intermedio, y es necesario modificar
                # el mes siguiente
                month_after = cutdate_obj.billing_month + relativedelta(
                    months=+1)
                cutdate_after = MonthlyCutDates.objects.filter(
                    billing_month=month_after).filter(
                    building=request.session['main_building'])
                if cutdate_after:
                    cd_after_flag = True
                    if cutdate_after[0].date_end:
                        if e_date_utc >= cutdate_after[0].date_end:
                            message = "La fecha final invade todo el periodo" \
                                      " del mes siguiente."
                            _type = "n_notif"
                            continue_flag = False
                        else:
                            cd_after = cutdate_after[0]
                    else:
                        cd_after = cutdate_after[0]

            if continue_flag:
                #Si hay cambio de fechas en mes anterior
                if cd_before_flag:
                    #Se guardan las fechas en la tabla de MonthlyCutDates
                    cd_before.date_end = s_date_utc
                    cd_before.save()

                    #Se recalcula el mes anterior ya con las nuevas fechas.
                    save_historic_delay.delay(cd_before,
                                              request.session['main_building'])

                #Si hay cambio de fechas en mes siguiente
                if cd_after_flag:
                    #Se guardan las fechas en la tabla de MonthlyCutDates
                    cd_after.date_init = e_date_utc
                    cd_after.save()

                    #Si la fecha final del mes siguiente no es nula,
                    # se crea el historico
                    if cd_after.date_end:
                        save_historic_delay.delay(
                            cd_after, request.session['main_building'])
                else:
                    #Se crea el nuevo mes
                    new_cut = MonthlyCutDates(
                        building=request.session['main_building'],
                        billing_month=cutdate_obj.billing_month + relativedelta(
                            months=+1),
                        date_init=e_date_utc
                    )
                    new_cut.save()

                cutdate_obj.date_init = s_date_utc
                cutdate_obj.date_end = e_date_utc
                cutdate_obj.save()

                #Se calcula el mes actual
                save_historic_delay.delay(cutdate_obj,
                                          request.session['main_building'])

                template_vars["message"] = "Fechas de Corte establecidas " \
                                           "correctamente"
                template_vars["type"] = "n_success"

                if request.user.is_superuser:
                    return HttpResponseRedirect("/buildings/fechas_corte?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")

            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/set_cutdate.html",
            template_vars_template)

    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def set_cutdate_bill_show(request, id_cutdate):
    datacontext = get_buildings_context(request.user)[0]
    if request.user.is_superuser:
        empresa = request.session['main_building']

        cutdate_obj = get_object_or_404(MonthlyCutDates, pk=id_cutdate)

        #Crea un arreglo con las horas
        horas = []
        hr = 1
        while hr < 13:
            horas.append(str(hr).zfill(2))
            hr += 1

        #Crea un arreglo con los minutos
        minutos = []
        mn = 0
        while mn < 60:
            minutos.append(str(mn).zfill(2))
            mn += 1

        #Se genera el string de la fecha de inicio
        s_date_str = cutdate_obj.date_init.astimezone(
            timezone.get_current_timezone()).strftime("%d/%m/%Y %I:%M %p")

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             cutdate=cutdate_obj,
                             s_date_str=s_date_str,
                             i_hours=horas,
                             i_minutes=minutos,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/set_cutdate_bill.html",
            template_vars_template)

    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def set_cutdate_bill(request):
    if "date" in request.GET and "cutdate" in request.GET:

        date = request.GET['date']
        id_cutdate = request.GET['cutdate']

        cutdate_obj = get_object_or_404(MonthlyCutDates, pk=id_cutdate)

        e_date_str = time.strptime(date, "%d/%m/%Y  %I:%M %p")
        e_date_utc_tuple = time.gmtime(time.mktime(e_date_str))
        e_date_utc = datetime.datetime(year=e_date_utc_tuple[0],
                                       month=e_date_utc_tuple[1],
                                       day=e_date_utc_tuple[2],
                                       hour=e_date_utc_tuple[3],
                                       minute=e_date_utc_tuple[4],
                                       tzinfo=pytz.utc)

        continuar = True
        message = ''
        status = 'OK'

        if e_date_utc <= cutdate_obj.date_init:
            continuar = False
            status = 'Error'
            message = 'La fecha final no puede ser menor o igual a la fecha' \
                      ' de inicio'

        if continuar:
            #Se guarda la fecha de corte
            cutdate_obj.date_end = e_date_utc
            cutdate_obj.save()

            #Se crea el nuevo mes
            new_cut = MonthlyCutDates(
                building=request.session['main_building'],
                billing_month=cutdate_obj.billing_month + relativedelta(
                    months=+1),
                date_init=e_date_utc
            )
            new_cut.save()
            #Se guarda el historico
            save_historic_delay.delay(cutdate_obj,
                                      request.session['main_building'])

            status = 'OK'

        response = dict(status=status,
                        message=message
        )

        data = simplejson.dumps(response)
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404


def obtenerHistorico_r(actual_month_arr):
    arr_historico = []
    #Obtener 5 meses antes
    ind = 5
    building = actual_month_arr['corte'].building

    while ind >= 0:
        month_before = actual_month_arr['corte'].billing_month + relativedelta(
            months=-ind)

        mtl = MonthlyCutDates.objects.filter(billing_month=month_before).filter(
            building=building)

        month_str = ''
        if month_before.month == 1:
            month_str = 'Ene'
        elif month_before.month == 2:
            month_str = 'Feb'
        elif month_before.month == 3:
            month_str = 'Mar'
        elif month_before.month == 4:
            month_str = 'Abr'
        elif month_before.month == 5:
            month_str = 'May'
        elif month_before.month == 6:
            month_str = 'Jun'
        elif month_before.month == 7:
            month_str = 'Jul'
        elif month_before.month == 8:
            month_str = 'Ago'
        elif month_before.month == 9:
            month_str = 'Sep'
        elif month_before.month == 10:
            month_str = 'Oct'
        elif month_before.month == 11:
            month_str = 'Nov'
        elif month_before.month == 12:
            month_str = 'Dic'

        dict_periodo = dict(fecha=month_str + ' ' + str(month_before.year),
                            kw_base=0, kw_intermedio=0, kw_punta=0,
                            demanda_maxima=0, total_kwh=0, kvarh=0,
                            factor_potencia=0, factor_carga=0, costo_promedio=0)

        if not ind is 0:

            if mtl:
                monthly_cut_dates = mtl[0]

                if building.electric_rate_id == 1:
                    cfe_hist_objs = HMHistoricData.objects.filter(
                        monthly_cut_dates=monthly_cut_dates)

                    if cfe_hist_objs:
                        historico = cfe_hist_objs[0]

                        dict_periodo["kw_base"] = historico.KW_base
                        dict_periodo["kw_intermedio"] = historico.KW_intermedio
                        dict_periodo["kw_punta"] = historico.KW_punta
                        dict_periodo["demanda_maxima"] = historico.billable_demand
                        dict_periodo["total_kwh"] = historico.KWH_total
                        dict_periodo["kvarh"] = historico.KVARH
                        dict_periodo["factor_potencia"] = historico.power_factor
                        dict_periodo["factor_carga"] = historico.charge_factor
                        dict_periodo["costo_promedio"] = historico.average_rate

                elif building.electric_rate_id == 2:
                    cfe_hist_objs = DacHistoricData.objects.filter(
                        monthly_cut_dates=monthly_cut_dates)

                    if cfe_hist_objs:
                        historico = cfe_hist_objs[0]

                        dict_periodo["total_kwh"] = historico.KWH_total
                        dict_periodo["costo_promedio"] = historico.average_rate

                elif building.electric_rate_id == 3:
                    cfe_hist_objs = T3HistoricData.objects.filter(
                        monthly_cut_dates=monthly_cut_dates)

                    if cfe_hist_objs:
                        historico = cfe_hist_objs[0]

                        dict_periodo["demanda_maxima"] = historico.max_demand
                        dict_periodo["total_kwh"] = historico.KWH_total
                        dict_periodo["factor_potencia"] = historico.power_factor
                        dict_periodo["factor_carga"] = historico.charge_factor
                        dict_periodo["costo_promedio"] = historico.average_rate

            arr_historico.append(dict_periodo)

        else:
            #Se inserta el mes actual
            if building.electric_rate_id == 1:
                dict_periodo["kw_base"] = actual_month_arr["kw_base"]
                dict_periodo["kw_intermedio"] = actual_month_arr["kw_intermedio"]
                dict_periodo["kw_punta"] = actual_month_arr["kw_punta"]
                dict_periodo["demanda_maxima"] = actual_month_arr['demanda_facturable']
                dict_periodo["total_kwh"] = actual_month_arr['kwh_totales']
                dict_periodo["kvarh"] = actual_month_arr['kvarh_totales']
                dict_periodo["factor_potencia"] = actual_month_arr['factor_potencia']
                dict_periodo["factor_carga"] = actual_month_arr['factor_carga']
                if actual_month_arr['kwh_totales']:
                    dict_periodo["costo_promedio"] = actual_month_arr['subtotal'] / actual_month_arr['kwh_totales']
                else:
                    dict_periodo["costo_promedio"] = 0

            elif building.electric_rate_id == 2:
                dict_periodo["total_kwh"] = actual_month_arr['kwh_totales']
                if actual_month_arr['kwh_totales']:
                    dict_periodo["costo_promedio"] = actual_month_arr['costo_energia']/ actual_month_arr['kwh_totales']
                else:
                    dict_periodo["costo_promedio"] = 0

            elif building.electric_rate_id == 3:
                dict_periodo["demanda_maxima"] = actual_month_arr['kw_totales']
                dict_periodo["total_kwh"] = actual_month_arr['kwh_totales']
                dict_periodo["factor_potencia"] = actual_month_arr['factor_potencia']
                dict_periodo["factor_carga"] = actual_month_arr['factor_carga']
                if actual_month_arr['kwh_totales']:
                    dict_periodo["costo_promedio"] = actual_month_arr['subtotal']/ actual_month_arr['kwh_totales']
                else:
                    dict_periodo["costo_promedio"] = 0

            arr_historico.append(dict_periodo)

        ind -= 1

    return arr_historico


# noinspection PyArgumentList
@login_required(login_url='/')
def cfe_desglose(request):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW,
                      "Consultar recibo CFE") or request.user.is_superuser:
        set_default_session_vars(request, datacontext)

        today = datetime.datetime.today().replace(
            hour=0, minute=0, second=0, tzinfo=timezone.get_current_timezone())
        month = int(today.month)
        year = int(today.year)
        dict(one=1, two=2)
        month_list = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
                      5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
                      9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre',
                      12: 'Diciembre'}
        year_list = {2010: 2010, 2011: 2011, 2012: 2012, 2013: 2013}

        template_vars = {"type": "cfe", "datacontext": datacontext,
                         'empresa': request.session['main_building'],
                         'month': month, 'year': year, 'month_list': month_list,
                         'year_list': year_list,
                         'sidebar': request.session['sidebar']
        }

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/cfe_desglose.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html",
                                  RequestContext(request,
                                                 {"datacontext": datacontext}))


# noinspection PyArgumentList
@login_required(login_url='/')
def cfe_desglose_calcs(request):
    """Estoy en los calculos del desglose
    Renders the cfe bill and the historic data chart
    """
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW,
                      "Consultar recibo CFE") or request.user.is_superuser:
        if not request.session['consumer_unit']:
            return HttpResponse(
                content=MSG_PERMIT_ERROR)

        set_default_session_vars(request, datacontext)

        template_vars = {"type": "cfe", "datacontext": datacontext,
                         'empresa': request.session['main_building']
        }

        kwh_netos = 0
        kvarh_netos = 0
        demanda_max = 0
        demanda_min = 1000000

        if request.method == "GET":
            s_date_str = request.GET['init_d']
            e_date_str = request.GET['end_d']

            s_date = datetime.datetime.strptime(s_date_str, "%Y-%m-%d")
            e_date = datetime.datetime.strptime(e_date_str, "%Y-%m-%d")

            #print "s_date", s_date
            #print "e_date", e_date

            #Se obtiene el edificio
            building = request.session['main_building']

            #Se obtiene la tarifa del edificio
            # electric_rate = building.electric_rate_id

            #Se obtiene el medidor padre del edificio
            main_cu = ConsumerUnit.objects.get(
                building=building,
                electric_device_type__electric_device_type_name=
                "Total Edificio")
            #Se obtienen todos los medidores necesarios
            consumer_units = get_consumer_units(main_cu)

            if consumer_units:
                for c_unit in consumer_units:
                    pr_powermeter = c_unit.profile_powermeter.powermeter

                    #Se obtienen los KW, para obtener la demanda maxima
                    lecturas_totales = ElectricRateForElectricData.objects.\
                        filter(
                            electric_data__profile_powermeter__powermeter__pk=
                            pr_powermeter.pk
                        ).filter(
                            electric_data__medition_date__range=(s_date, e_date)
                        ).order_by('electric_data__medition_date')
                    kw_t = obtenerDemanda_kw(lecturas_totales)
                    kw_mt = obtenerDemandaMin_kw(lecturas_totales)

                    if kw_t > demanda_max:
                        demanda_max = kw_t

                    if kw_mt < demanda_min:
                        demanda_min = kw_mt

                    #Se obtienen los kwh de ese periodo de tiempo.
                    kwh_lecturas = ElectricDataTemp.objects.filter(
                        profile_powermeter=pr_powermeter,
                        medition_date__range=(s_date, e_date)
                    ).order_by('medition_date')
                    total_lecturas = len(kwh_lecturas)

                    if kwh_lecturas:
                        kwh_inicial = kwh_lecturas[0].TotalkWhIMPORT
                        kwh_final = kwh_lecturas[total_lecturas - 1].\
                            TotalkWhIMPORT

                        kwh_netos += int(ceil(kwh_final - kwh_inicial))

                    #Se obtienen los kvarhs por medidor
                    kvarh_netos += obtenerKVARH_total(pr_powermeter, s_date,
                                                      e_date)

            #Factor de Potencia
            factor_potencia_total = factorpotencia(kwh_netos, kvarh_netos)

            resultado = dict(kwh=kwh_netos, kvarh=kvarh_netos,
                             dem_max=demanda_max, dem_min=demanda_min,
                             fpotencia=factor_potencia_total)

            template_vars['resultados'] = resultado
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response(
                "consumption_centers/graphs/desglose.html",
                template_vars_template)
        else:
            raise Http404
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def montly_analitics(request):
    edificio = request.session['main_building']
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {}
    if datacontext:
        template_vars["datacontext"] = datacontext
    template_vars['building'] = edificio
    template_vars["sidebar"] = request.session['sidebar']
    template_vars["empresa"] = request.session['main_building']
    template_vars["company"] = request.session['company']
    template_vars["consumer_unit"] = request.session['consumer_unit']
    if has_permission(request.user, VIEW, "Consumo Energético Mensual") or \
            request.user.is_superuser:

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/montly_analitics.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def montly_data_for_building(request, year, month):
    if has_permission(request.user, VIEW, "Consultar recibo CFE") or \
            request.user.is_superuser:
        data = getDailyReports(request.session['consumer_unit'],
                               int(month), int(year))

        response_data = simplejson.dumps(data)
        return HttpResponse(content=response_data,
                            content_type="application/json")
    else:
        raise Http404


@login_required(login_url='/')
def montly_data_hfor_building(request, year, month):
    if has_permission(request.user, VIEW, "Consultar recibo CFE") or \
            request.user.is_superuser:
        data = getMonthlyReport(request.session['consumer_unit'],
                                int(month), int(year))

        response_data = simplejson.dumps([data])
        return HttpResponse(content=response_data,
                            content_type="application/json")
    else:
        raise Http404


@login_required(login_url='/')
def montly_data_w_for_building(request, year, month):
    if has_permission(request.user, VIEW, "Consultar recibo CFE") or \
            request.user.is_superuser:
        datos = getWeeklyReport(request.session['consumer_unit'],
                                int(month), int(year))

        response_data = simplejson.dumps(datos)

        return HttpResponse(content=response_data,
                            content_type="application/json")
    else:
        raise Http404


@login_required(login_url='/')
def month_analitics_day(request):
    if has_permission(request.user, VIEW, "Consultar recibo CFE") or \
            request.user.is_superuser:
        fecha = datetime.datetime.strptime(request.GET['date'], "%Y-%m-%d")
        electric_rate = \
            request.session['consumer_unit'].building.electric_rate_id
        try:
            day_data = DailyData.objects.get(
                consumer_unit=request.session['consumer_unit'],
                data_day=fecha)
        except ObjectDoesNotExist:
            diccionario = dict(empty="true")
        else:
            diccionario = dict(empty="false",
                               electric_rate=str(electric_rate),
                               c_tot=str(day_data.KWH_total),
                               c_base=str(day_data.KWH_base),
                               c_int=str(day_data.KWH_intermedio),
                               c_punta=str(day_data.KWH_punta),
                               d_max=str(day_data.max_demand),
                               d_max_time=str(day_data.max_demand_time),
                               cost_p=str(day_data.KWH_cost),
                               pf=str(day_data.power_factor),
                               kvarh=str(day_data.KVARH))
        response_data = simplejson.dumps([diccionario])
        return HttpResponse(content=response_data,
                            content_type="application/json")
    else:
        raise Http404


# noinspection PyArgumentList
@login_required(login_url='/')
def billing_analisis_header(request):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {"type": "cfe", "datacontext": datacontext,
                         'empresa': request.session['main_building'],
                         'company': request.session['company'],
                         'sidebar': request.session['sidebar'],
                         'user':request.user }
    if has_permission(request.user, VIEW, "Análisis de facturación") or \
            request.user.is_superuser:
        set_default_session_vars(request, datacontext)

        building = request.session['main_building']
        #Se obtiene el tipo de tarifa del edificio
        tipo_tarifa = building.electric_rate

        if tipo_tarifa.pk == 1:
            years = [__date.year for __date in HMHistoricData.objects.all().
                    dates('monthly_cut_dates__billing_month','year')]
        elif tipo_tarifa.pk == 2:
            years = [__date.year for __date in DacHistoricData.objects.all().
                    dates('monthly_cut_dates__billing_month','year')]
        elif tipo_tarifa.pk == 3:
            years = [__date.year for __date in T3HistoricData.objects.all().
                    dates('monthly_cut_dates__billing_month','year')]

        template_vars['years'] = years[::-1]

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/graphs/analisis_facturacion.html",
                                  template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html",
                                  template_vars_template)


# noinspection PyArgumentList
@login_required(login_url='/')
def billing_c_analisis_header(request):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {"type": "cfe", "datacontext": datacontext,
                         'empresa': request.session['main_building'],
                         'company': request.session['company'],
                         'sidebar': request.session['sidebar'],
                         'user':request.user }
    if has_permission(request.user, VIEW, "Análisis de costo de facturación") \
            or request.user.is_superuser:
        set_default_session_vars(request, datacontext)

        building = request.session['main_building']
        #Se obtiene el tipo de tarifa del edificio
        tipo_tarifa = building.electric_rate

        if tipo_tarifa.pk == 1:
            years = [__date.year for __date in ElectricRatesDetail.objects.
                all().dates('date_init', 'year')]
        elif tipo_tarifa.pk == 2:
            years = [__date.year for __date in DACElectricRateDetail.objects.
                all().dates('date_init', 'year')]
        elif tipo_tarifa.pk == 3:
            years = [__date.year for __date in ThreeElectricRateDetail.objects.
                all().dates('date_init', 'year')]
        template_vars['years'] = years[::-1]

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/graphs/analisis_costo_facturacion.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html",
                                  template_vars_template)


# noinspection PyArgumentList
@login_required(login_url='/')
def power_performance_header(request):
    datacontext = get_buildings_context(request.user)[0]
    template_vars = {"type": "cfe", "datacontext": datacontext,
                         'empresa': request.session['main_building'],
                         'company': request.session['company'],
                         'sidebar': request.session['sidebar'],
                         'user':request.user }
    if has_permission(request.user, VIEW, "Desempeño energético") or \
            request.user.is_superuser:
        set_default_session_vars(request, datacontext)

        building = request.session['main_building']
        #Se obtiene el tipo de tarifa del edificio
        tipo_tarifa = building.electric_rate

        if tipo_tarifa.pk == 1:
            years = [__date.year for __date in HMHistoricData.objects.all().
                dates('monthly_cut_dates__billing_month','year')]
        elif tipo_tarifa.pk == 2:
            years = [__date.year for __date in DacHistoricData.objects.all().
                dates('monthly_cut_dates__billing_month','year')]
        elif tipo_tarifa.pk == 3:
            years = [__date.year for __date in T3HistoricData.objects.all().
                dates('monthly_cut_dates__billing_month','year')]
        template_vars['years'] = years[::-1]

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/graphs/desempenio_energetico.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html",
                                  template_vars_template)


def getMonthName(index):
    if index == 1:
        return 'Ene'
    elif index == 2:
        return 'Feb'
    elif index == 3:
        return 'Mar'
    elif index == 4:
        return 'Abr'
    elif index == 5:
        return 'May'
    elif index == 6:
        return 'Jun'
    elif index == 7:
        return 'Jul'
    elif index == 8:
        return 'Ago'
    elif index == 9:
        return 'Sep'
    elif index == 10:
        return 'Oct'
    elif index == 11:
        return 'Nov'
    elif index == 12:
        return 'Dic'


def billing_analisis(request):
    """Renders the cfe bill and the historic data chart"""
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW, "Análisis de facturación") or \
            request.user.is_superuser:
        if not request.session['consumer_unit']:
            return HttpResponse(
                content=MSG_PERMIT_ERROR)

        set_default_session_vars(request, datacontext)

        template_vars = dict(datacontext=datacontext,
                             empresa=request.session['main_building'])

        building = request.session['main_building']

        #Se obtiene el tipo de tarifa del edificio
        tipo_tarifa = building.electric_rate

        compare_years_flag = False
        graph_kwh_arr = []
        graph_money_arr = []
        y01_kwh = 0
        y02_kwh = 0
        y01_money = 0
        y02_money = 0

        if request.GET:
            report_type = int(request.GET['report_type'])

            #Si el tipo de reporte es anual:
            if report_type == 0:
                template_vars['tipo_reporte'] = 1

                year_01 = int(request.GET['year01'])
                template_vars['year_01'] = year_01
                if request.GET.__contains__('year02'):
                    compare_years_flag = True
                    year_02 = int(request.GET['year02'])
                    template_vars['year_02'] = year_02

                num_mesesdatos = 0
                #Se hace un ciclo para recorrer los 12 meses del año
                for i in range(12):
                    #Esta bandera sirve para sumar unicamente los meses del año
                    suma_mes_y02 = False

                    datos_kwh = dict()
                    datos_money = dict()
                    mes = i+1
                    if tipo_tarifa.pk == 1:
                        year_01_data = HMHistoricData.objects.filter(
                            monthly_cut_dates__building = building,
                            monthly_cut_dates__billing_month__year = year_01,
                            monthly_cut_dates__billing_month__month = mes)
                    elif tipo_tarifa.pk == 2:
                        year_01_data = DacHistoricData.objects.filter(
                            monthly_cut_dates__building = building,
                            monthly_cut_dates__billing_month__year = year_01,
                            monthly_cut_dates__billing_month__month = mes)
                    elif tipo_tarifa.pk == 3:
                        year_01_data = T3HistoricData.objects.filter(
                            monthly_cut_dates__building = building,
                            monthly_cut_dates__billing_month__year = year_01,
                            monthly_cut_dates__billing_month__month = mes)

                    datos_kwh['mes'] = getMonthName(i+1)
                    datos_money['mes'] = getMonthName(i+1)
                    if year_01_data:
                        datos_kwh['kwh_01'] = year_01_data[0].KWH_total
                        datos_money['total_01'] = year_01_data[0].total
                        #Se va haciendo la suma
                        y01_kwh += year_01_data[0].KWH_total
                        y01_money += year_01_data[0].total
                        #Se aumenta la cuenta de meses con datos
                        num_mesesdatos += 1
                        suma_mes_y02 = True
                    else:
                        datos_kwh['kwh_01'] = 0
                        datos_money['total_01'] = 0

                    if compare_years_flag:
                        if tipo_tarifa.pk == 1:
                            year_02_data = HMHistoricData.objects.filter(
                                monthly_cut_dates__building = building,
                                monthly_cut_dates__billing_month__year = year_02,
                                monthly_cut_dates__billing_month__month = mes)
                        elif tipo_tarifa.pk == 2:
                            year_02_data = DacHistoricData.objects.filter(
                                monthly_cut_dates__building = building,
                                monthly_cut_dates__billing_month__year = year_02,
                                monthly_cut_dates__billing_month__month = mes)
                        elif tipo_tarifa.pk == 3:
                            year_02_data = T3HistoricData.objects.filter(
                                monthly_cut_dates__building = building,
                                monthly_cut_dates__billing_month__year = year_02,
                                monthly_cut_dates__billing_month__month = mes)

                        if year_02_data:
                            datos_kwh['kwh_02'] = year_02_data[0].KWH_total
                            datos_money['total_02'] = year_02_data[0].total

                            #Unicamente si hay match con el mes de año 1, sumo
                            if suma_mes_y02:
                                y02_kwh += year_02_data[0].KWH_total
                                y02_money += year_02_data[0].total
                        else:
                            datos_kwh['kwh_02'] = 0
                            datos_money['total_02'] = 0

                    graph_kwh_arr.append(datos_kwh)
                    graph_money_arr.append(datos_money)
                template_vars['kwh_data'] = graph_kwh_arr
                template_vars['money_data'] = graph_money_arr

                if compare_years_flag:

                    difference_qty = y02_kwh - y01_kwh
                    if y02_kwh:
                        difference_pc_kwh = (float(y01_kwh) * 100.0 / float(
                            y02_kwh)) - 100.0
                    else:
                        difference_pc_kwh = 0

                    difference_money = y02_money - y01_money
                    if y02_money:
                        difference_pc_money = (float(y01_money) * 100.0 / float(
                            y02_money)) - 100.0
                    else:
                        difference_pc_money = 0

                    template_vars['compare_years'] = True
                    template_vars['kwh_total_01'] = y01_kwh
                    template_vars['kwh_total_02'] = y02_kwh


                    if difference_pc_kwh > 0:
                        template_vars['positive_kwh'] = 1
                    elif difference_pc_kwh < 0:
                        template_vars['positive_kwh'] = -1
                    else:
                        template_vars['positive_kwh'] = 0
                    template_vars['diff_kwh_pc'] = fabs(difference_pc_kwh)
                    template_vars['diff_kwh_qty'] = fabs(difference_qty)

                    template_vars['money_total_01'] = y01_money
                    template_vars['money_total_02'] = y02_money

                    if difference_pc_money > 0:
                        template_vars['positive_money'] = 1
                    elif difference_pc_money < 0:
                        template_vars['positive_money'] = -1
                    else:
                        template_vars['positive_money'] = 0
                    template_vars['diff_money_pc'] = fabs(difference_pc_money)
                    template_vars['diff_money_qty'] = fabs(difference_money)

                else:
                    #Se calcula el promedio únicamente con los meses con datos
                    if num_mesesdatos > 0:
                        kwh_average = float(y01_kwh)/float(num_mesesdatos)
                        money_average = float(y01_money)/float(num_mesesdatos)
                    else:
                        kwh_average = 0
                        money_average = 0

                    template_vars['compare_years'] = False
                    template_vars['kwh_average'] = kwh_average
                    template_vars['money_average'] = money_average
                    template_vars['kwh_total'] = y01_kwh
                    template_vars['money_total'] = y01_money

            else:
                #Si el tipo de reporte es mensual
                template_vars['tipo_reporte'] = 2

                month_01 = int(request.GET['month_01'])
                year_01 = int(request.GET['year_01'])
                month_02 = int(request.GET['month_02'])
                year_02 = int(request.GET['year_02'])

                template_vars['mes_01'] = getMonthName(month_01) \
                                          + ' ' + str(year_01)
                template_vars['mes_02'] = getMonthName(month_02) \
                                          + ' ' + str(year_02)

                if tipo_tarifa.pk == 1:
                    template_vars['tarifa'] = 1
                    m01_data = HMHistoricData.objects.filter(
                        monthly_cut_dates__building = building,
                        monthly_cut_dates__billing_month__month = month_01,
                        monthly_cut_dates__billing_month__year = year_01)
                    m02_data = HMHistoricData.objects.filter(
                        monthly_cut_dates__building = building,
                        monthly_cut_dates__billing_month__month = month_02,
                        monthly_cut_dates__billing_month__year = year_02)

                    if m01_data:
                        m01 = m01_data[0]
                        template_vars['m01_kwh'] = m01.KWH_total
                        template_vars['m01_money'] = m01.total
                        template_vars['m01_kw'] = m01.KW_base +\
                                                  m01.KW_intermedio + \
                                                  m01.KW_punta
                        template_vars['m01_base'] = m01.KWH_base
                        template_vars['m01_intermedio'] = m01.KWH_intermedio
                        template_vars['m01_punta'] = m01.KWH_punta
                        template_vars['m01_t_base'] = m01.KWH_base_rate
                        template_vars['m01_t_intermedio'] = m01.KWH_intermedio_rate
                        template_vars['m01_t_punta'] = m01.KWH_punta_rate
                    else:
                        template_vars['m01_kwh'] = 0
                        template_vars['m01_money'] = 0
                        template_vars['m01_kw'] = 0
                        template_vars['m01_base'] = 0
                        template_vars['m01_intermedio'] = 0
                        template_vars['m01_punta'] = 0
                        #Obtiene la tarifa directamente de su tabla

                        tarifasObj = ElectricRatesDetail.objects.filter(
                            electric_rate=1, region=building.region,
                            date_init__month=month_01, date_init__year=year_01)
                        if tarifasObj:
                            tarifas = tarifasObj[0]
                            template_vars['m01_t_base'] = tarifas.KWHB
                            template_vars['m01_t_intermedio'] = tarifas.KWHI
                            template_vars['m01_t_punta'] = tarifas.KWHP
                        else:
                            template_vars['m01_t_base'] = 0
                            template_vars['m01_t_intermedio'] = 0
                            template_vars['m01_t_punta'] = 0

                    if m02_data:
                        m02 = m02_data[0]
                        template_vars['m02_kwh'] = m02.KWH_total
                        template_vars['m02_money'] = m02.total
                        template_vars['m02_kw'] = m02.KW_base\
                                                  + m02.KW_intermedio \
                                                  + m02.KW_punta
                        template_vars['m02_base'] = m02.KWH_base
                        template_vars['m02_intermedio'] = m02.KWH_intermedio
                        template_vars['m02_punta'] = m02.KWH_punta
                        template_vars['m02_t_base'] = m02.KWH_base_rate
                        template_vars['m02_t_intermedio'] = m02.KWH_intermedio_rate
                        template_vars['m02_t_punta'] = m02.KWH_punta_rate
                    else:
                        template_vars['m02_kwh'] = 0
                        template_vars['m02_money'] = 0
                        template_vars['m02_kw'] = 0
                        template_vars['m02_base'] = 0
                        template_vars['m02_intermedio'] = 0
                        template_vars['m02_punta'] = 0
                        #Obtiene la tarifa directamente de su tabla

                        tarifasObj = ElectricRatesDetail.objects.filter(
                            electric_rate=1, region=building.region,
                            date_init__month=month_02, date_init__year=year_02)
                        if tarifasObj:
                            tarifas = tarifasObj[0]
                            template_vars['m02_t_base'] = tarifas.KWHB
                            template_vars['m02_t_intermedio'] = tarifas.KWHI
                            template_vars['m02_t_punta'] = tarifas.KWHP
                        else:
                            template_vars['m02_t_base'] = 0
                            template_vars['m02_t_intermedio'] = 0
                            template_vars['m02_t_punta'] = 0

                    #Si estan los datos, obtiene los porcentajes de diferencia
                    #Porcentaje de Kilowatts hora
                    if template_vars['m02_kwh']:
                        diff_kwh = (float(
                            template_vars['m01_kwh']) *
                             100.0 / float(template_vars['m02_kwh'])) - 100.0
                        if diff_kwh > 0:
                            template_vars['positive_kwh'] = 1
                        elif diff_kwh < 0:
                            template_vars['positive_kwh'] = -1
                        else:
                            template_vars['positive_kwh'] = 0
                        template_vars['diff_kwh'] = fabs(diff_kwh)

                    else:
                        template_vars['diff_kwh'] = 0

                    #Porcentaje de Dinero
                    if template_vars['m02_money']:
                        diff_money = (float(
                            template_vars['m01_money']) *
                            100.0 / float(template_vars['m02_money'])) - 100.0
                        if diff_money > 0:
                            template_vars['positive_money'] = 1
                        elif diff_money < 0:
                            template_vars['positive_money'] = -1
                        else:
                            template_vars['positive_money'] = 0
                        template_vars['diff_money'] = fabs(diff_money)
                    else:
                        template_vars['diff_money'] = 0

                    #Porcentaje de Kilowatts
                    if template_vars['m02_kw']:
                        diff_kw = (float(
                            template_vars['m01_kw']) *
                            100.0 / float(template_vars['m02_kw'])) - 100.0
                        if diff_kw > 0:
                            template_vars['positive_kw'] = 1
                        elif diff_kw < 0:
                            template_vars['positive_kw'] = -1
                        else:
                            template_vars['positive_kw'] = 0
                        template_vars['diff_kw'] = fabs(diff_kw)
                    else:
                        template_vars['diff_kw'] = 0

                    #Porcentaje de Tarifa Base
                    if template_vars['m02_t_base']:
                        diff_base = (float(
                            template_vars['m01_t_base']) *
                            100.0 / float(template_vars['m02_t_base'])) - 100.0
                        if diff_base > 0:
                            template_vars['positive_b'] = 1
                        elif diff_base < 0:
                            template_vars['positive_b'] = -1
                        else:
                            template_vars['positive_b'] = 0
                        template_vars['diff_tbase'] = fabs(diff_base)
                    else:
                        template_vars['diff_tbase'] = 0

                    #Porcentaje de Tarifa Intermedio
                    if template_vars['m02_t_intermedio']:
                        diff_int = (float(
                            template_vars['m01_t_intermedio']) *
                            100.0 / float(template_vars['m02_t_intermedio'])) \
                                                     - 100.0
                        if diff_int > 0:
                            template_vars['positive_i'] = 1
                        elif diff_int < 0:
                            template_vars['positive_i'] = -1
                        else:
                            template_vars['positive_i'] = 0
                        template_vars['diff_tint'] = fabs(diff_int)
                    else:
                        template_vars['diff_tint'] = 0

                    #Porcentaje de Tarifa Punta
                    if template_vars['m02_t_punta']:
                        diff_pt = (float(
                            template_vars['m01_t_punta']) * 100.0 /
                            float(template_vars['m02_t_punta'])) - 100.0
                        if diff_pt > 0:
                            template_vars['positive_p'] = 1
                        elif diff_pt < 0:
                            template_vars['positive_p'] = -1
                        else:
                            template_vars['positive_p'] = 0
                        template_vars['diff_tpunta'] = fabs(diff_pt)
                    else:
                        template_vars['diff_tpunta'] = 0

                elif tipo_tarifa.pk == 2:

                    template_vars['tarifa'] = 2
                    m01_data = DacHistoricData.objects.filter(
                        monthly_cut_dates__building=building,
                        monthly_cut_dates__billing_month__month=month_01,
                        monthly_cut_dates__billing_month__year=year_01)
                    m02_data = DacHistoricData.objects.filter(
                        monthly_cut_dates__building=building,
                        monthly_cut_dates__billing_month__month=month_02,
                        monthly_cut_dates__billing_month__year=year_02)
                    if m01_data:
                        m01 = m01_data[0]
                        template_vars['m01_kwh'] = m01.KWH_total
                        template_vars['m01_money'] = m01.total
                        template_vars['m01_t_kwh'] = m01.KWH_rate
                        template_vars['m01_t_month'] = m01.monthly_rate
                    else:
                        template_vars['m01_kwh'] = 0
                        template_vars['m01_money'] = 0
                        template_vars['m01_t_kwh'] = 0
                        template_vars['m01_t_month'] = 0

                    if m02_data:
                        m02 = m02_data
                        template_vars['m02_kwh'] = m02.KWH_total
                        template_vars['m02_money'] = m02.total
                        template_vars['m02_t_kwh'] = m02.KWH_rate
                        template_vars['m02_t_month'] = m02.monthly_rate
                    else:
                        template_vars['m02_kwh'] = 0
                        template_vars['m02_money'] = 0
                        template_vars['m02_t_kwh'] = 0
                        template_vars['m02_t_month'] = 0

                    #Si estan los datos, obtiene los porcentajes de diferencia
                    #Porcentaje de Kilowatts hora
                    if template_vars['m02_kwh']:
                        diff_kwh = (float(
                            template_vars['m01_kwh']) * 100.0 /
                            float(template_vars['m02_kwh'])) - 100.0
                        if diff_kwh > 0:
                            template_vars['positive_kwh'] = 1
                        elif diff_kwh < 0:
                            template_vars['positive_kwh'] = -1
                        else:
                            template_vars['positive_kwh'] = 0

                        template_vars['diff_kwh'] = fabs(diff_kwh)

                    else:
                        template_vars['diff_kwh'] = 0

                    #Porcentaje de Dinero
                    if template_vars['m02_money']:
                        diff_money = (float(
                            template_vars['m01_money']) * 100.0 /
                            float(template_vars['m02_money'])) - 100.0
                        if diff_money > 0:
                            template_vars['positive_money'] = 1
                        elif diff_money < 0:
                            template_vars['positive_money'] = -1
                        else:
                            template_vars['positive_money'] = 0
                        template_vars['diff_money'] = fabs(diff_money)
                    else:
                        template_vars['diff_money'] = 0

                    #Porcentaje de Tarifa por Kilowatt Hora
                    if template_vars['m02_t_kwh']:
                        template_vars['diff_t_kwh'] = (float(
                            template_vars['m01_t_kwh']) * 100.0 /
                            float(template_vars['m02_t_kwh'])) - 100.0
                    else:
                        template_vars['diff_t_kwh'] = 0

                    #Porcentaje de Tarifa Mensual
                    if template_vars['m02_t_month']:
                        template_vars['diff_t_month'] = (float(
                            template_vars['m01_t_month']) * 100.0 /
                            float(template_vars['m02_t_month'])) - 100.0
                    else:
                        template_vars['diff_t_month'] = 0

                elif tipo_tarifa.pk == 3:

                    template_vars['tarifa'] = 3
                    m01_data = T3HistoricData.objects.filter(
                        monthly_cut_dates__building=building,
                        monthly_cut_dates__billing_month__month=month_01,
                        monthly_cut_dates__billing_month__year=year_01)
                    m02_data = T3HistoricData.objects.filter(
                        monthly_cut_dates__building = building,
                        monthly_cut_dates__billing_month__month=month_02,
                        monthly_cut_dates__billing_month__year=year_02)
                    if m01_data:
                        m01 = m01_data[0]
                        template_vars['m01_kwh'] = m01.KWH_total
                        template_vars['m01_money'] = m01.total
                        template_vars['m01_kw'] = m01.max_demand
                        template_vars['m01_t_kwh'] = m01.KWH_rate
                        template_vars['m01_t_kw'] = m01.demand_rate
                    else:
                        template_vars['m01_kwh'] = 0
                        template_vars['m01_money'] = 0
                        template_vars['m01_kw'] = 0
                        template_vars['m01_t_kwh'] = 0
                        template_vars['m01_t_kw'] = 0

                    if m02_data:
                        m02 = m02_data[0]
                        template_vars['m02_kwh'] = m02.KWH_total
                        template_vars['m02_money'] = m02.total
                        template_vars['m02_kw'] = m02.max_demand
                        template_vars['m02_t_kwh'] = m02.KWH_rate
                        template_vars['m02_t_kw'] = m02.demand_rate
                    else:
                        template_vars['m02_kwh'] = 0
                        template_vars['m02_money'] = 0
                        template_vars['m02_kw'] = 0
                        template_vars['m02_t_kwh'] = 0
                        template_vars['m02_t_kw'] = 0

                    #Si estan los datos, obtiene los porcentajes de diferencia
                    #Porcentaje de Kilowatts hora
                    if template_vars['m02_kwh']:
                        diff_kwh = (float(
                            template_vars['m01_kwh']) * 100.0 / float(
                            template_vars['m02_kwh'])) - 100.0

                        if diff_kwh > 0:
                            template_vars['positive_kwh'] = 1
                        elif diff_kwh < 0:
                            template_vars['positive_kwh'] = -1
                        else:
                            template_vars['positive_kwh'] = 0

                        template_vars['diff_kwh'] = fabs(diff_kwh)

                    else:
                        template_vars['diff_kwh'] = 0

                    #Porcentaje de Dinero
                    if template_vars['m02_money']:
                        diff_money = (float(
                            template_vars['m01_money']) * 100.0 / float(
                            template_vars['m02_money'])) - 100.0
                        if diff_money > 0:
                            template_vars['positive_money'] = 1
                        elif diff_money < 0:
                            template_vars['positive_money'] = -1
                        else:
                            template_vars['positive_money'] = 0
                        template_vars['diff_money'] = fabs(diff_money)
                    else:
                        template_vars['diff_money'] = 0

                    #Porcentaje de Kilowatts
                    if template_vars['m02_kw']:
                        diff_kw = (float(
                            template_vars['m01_kw']) * 100.0 / float(
                            template_vars['m02_kw'])) - 100.0
                        if diff_kw > 0:
                            template_vars['positive_kw'] = 1
                        elif diff_kw < 0:
                            template_vars['positive_kw'] = -1
                        else:
                            template_vars['positive_kw'] = 0
                        template_vars['diff_kw'] = fabs(diff_kw)
                    else:
                        template_vars['diff_kw'] = 0

                    #Porcentaje de Tarifa por Kilowatt Hora
                    if template_vars['m02_t_kwh']:
                        template_vars['diff_t_kwh'] = (float(
                            template_vars['m01_t_kwh']) * 100.0 / float(
                            template_vars['m02_t_kwh'])) - 100.0
                    else:
                        template_vars['diff_t_kwh'] = 0

                    #Porcentaje de Tarifa por Kilowatt
                    if template_vars['m02_t_kw']:
                        template_vars['diff_t_kw'] = (float(
                            template_vars['m01_t_kw']) * 100.0 / float(
                            template_vars['m02_t_kw'])) - 100.0
                    else:
                        template_vars['diff_t_kw'] = 0

            template_vars_template = RequestContext(request, template_vars)
            return render_to_response(
                "consumption_centers/graphs/analisis_facturacion_frame.html",
                template_vars_template)

    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def billing_cost_analisis(request):
    """Renders the cfe bill and the historic data chart"""
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW, "Análisis de costo de facturación") \
            or request.user.is_superuser:
        if not request.session['consumer_unit']:
            return HttpResponse(
                content=MSG_PERMIT_ERROR)

        set_default_session_vars(request, datacontext)

        template_vars = dict(datacontext=datacontext,
                             empresa=request.session['main_building'])

        building = request.session['main_building']

        #Se obtiene el tipo de tarifa del edificio
        tipo_tarifa = building.electric_rate

        compare_years_flag = False

        graph_kdf_arr = []
        graph_kwhp_arr = []
        graph_kwhi_arr = []
        graph_kwhb_arr = []

        graph_m_rate_arr = []
        graph_kwh_arr = []
        graph_kw_arr = []

        #Dac - Region Baja California y BCS, tienen tarifas para Verano e Inv.
        graph_p01_kwh_arr = []
        graph_p02_kwh_arr = []
        periodo_1_dac = ''
        periodo_2_dac = ''

        if request.GET:
            year_01 = int(request.GET['year01'])
            template_vars['year_01'] = year_01
            if request.GET.__contains__('year02'):
                compare_years_flag = True
                template_vars['compare_years'] = True
                year_02 = int(request.GET['year02'])
                template_vars['year_02'] = year_02

            if tipo_tarifa.pk == 1:

                template_vars['tarifa'] = 1

                for i in range(12):
                    mes = i+1

                    datos_kdf = dict()
                    datos_kwhp = dict()
                    datos_kwhi = dict()
                    datos_kwhb = dict()
                    year_01_data = ElectricRatesDetail.objects.filter(
                        region = building.region,
                        date_init__month = mes, date_init__year = year_01
                    )

                    datos_kdf['mes'] = getMonthName(i+1)
                    datos_kwhp['mes'] = getMonthName(i+1)
                    datos_kwhi['mes'] = getMonthName(i+1)
                    datos_kwhb['mes'] = getMonthName(i+1)

                    if year_01_data:
                        datos_kdf['kdf_01'] = year_01_data[0].KDF
                        datos_kwhp['kwhp_01'] = year_01_data[0].KWHP
                        datos_kwhi['kwhi_01'] = year_01_data[0].KWHI
                        datos_kwhb['kwhb_01'] = year_01_data[0].KWHB
                    else:
                        datos_kdf['kdf_01'] = 0
                        datos_kwhp['kwhp_01'] = 0
                        datos_kwhi['kwhi_01'] = 0
                        datos_kwhb['kwhb_01'] = 0

                    if compare_years_flag:
                        year_02_data = ElectricRatesDetail.objects.filter(
                            region = building.region,
                            date_init__month = mes, date_init__year = year_02
                        )
                        if year_02_data:
                            datos_kdf['kdf_02'] = year_02_data[0].KDF
                            datos_kwhp['kwhp_02'] = year_02_data[0].KWHP
                            datos_kwhi['kwhi_02'] = year_02_data[0].KWHI
                            datos_kwhb['kwhb_02'] = year_02_data[0].KWHB
                        else:
                            datos_kdf['kdf_02'] = 0
                            datos_kwhp['kwhp_02'] = 0
                            datos_kwhi['kwhi_02'] = 0
                            datos_kwhb['kwhb_02'] = 0

                    graph_kdf_arr.append(datos_kdf)
                    graph_kwhp_arr.append(datos_kwhp)
                    graph_kwhi_arr.append(datos_kwhi)
                    graph_kwhb_arr.append(datos_kwhb)

            elif tipo_tarifa.pk == 2:

                template_vars['tarifa'] = 2
                template_vars['dac_region1_2'] = False
                if building.region_id == 1 or building.region_id == 2:
                    template_vars['dac_region1_2'] = True


                for i in range(12):
                    mes = i+1

                    datos_monthrate = dict()
                    datos_kwh = dict()
                    datos_p01_kwh = dict()
                    datos_p02_kwh = dict()

                    #Si la region es Baja California o Baja California Sur
                    #Se obtienen los datos para Verano e Invierno
                    if template_vars['dac_region1_2']:
                        year_01_data = DACElectricRateDetail.objects.filter(
                            region = building.region,
                            date_init__month = mes, date_init__year = year_01
                        ).order_by('date_interval')

                        datos_monthrate['mes'] = getMonthName(i+1)
                        datos_p01_kwh['mes'] = getMonthName(i+1)
                        datos_p02_kwh['mes'] = getMonthName(i+1)

                        if year_01_data:

                            datos_monthrate['m_rate_01'] = year_01_data[0].month_rate
                            datos_p01_kwh['kwh_01'] = year_01_data[0].kwh_rate
                            datos_p02_kwh['kwh_01'] = year_01_data[1].kwh_rate

                            if periodo_1_dac == '':
                                periodo_1_dac = year_01_data[0].date_interval.interval_identifier

                            if periodo_2_dac == '':
                                periodo_2_dac = year_01_data[1].date_interval.interval_identifier

                        else:
                            datos_monthrate['m_rate_01'] = 0
                            datos_p01_kwh['kwh_01'] = 0
                            datos_p02_kwh['kwh_01'] = 0

                    else:
                        year_01_data = DACElectricRateDetail.objects.filter(
                            region = building.region,
                            date_init__month = mes, date_init__year = year_01
                        ).order_by('date_interval')

                        datos_monthrate['mes'] = getMonthName(i+1)
                        datos_kwh['mes'] = getMonthName(i+1)

                        if year_01_data:
                            datos_monthrate['m_rate_01'] = year_01_data[0].month_rate
                            datos_kwh['kwh_01'] = year_01_data[0].kwh_rate
                        else:
                            datos_monthrate['m_rate_01'] = 0
                            datos_kwh['kwh_01'] = 0


                    if compare_years_flag:
                        if building.region_id == 1 or building.region_id == 2:
                            year_02_data = DACElectricRateDetail.objects.filter(
                                region = building.region,
                                date_init__month = mes, date_init__year = year_02
                            ).order_by('date_interval')

                            print "y2", year_02_data

                            if year_02_data:
                                datos_monthrate['m_rate_02'] = year_02_data[0].month_rate
                                datos_p01_kwh['kwh_02'] = year_02_data[0].kwh_rate
                                datos_p02_kwh['kwh_02'] = year_02_data[1].kwh_rate

                            else:
                                datos_monthrate['m_rate_02'] = 0
                                datos_p01_kwh['kwh_02'] = 0
                                datos_p02_kwh['kwh_02'] = 0

                        else:
                            year_02_data = DACElectricRateDetail.objects.filter(
                                region = building.region,
                                date_init__month = mes, date_init__year = year_02
                            )

                            if year_02_data:
                                datos_monthrate['m_rate_02'] = year_02_data[0].month_rate
                                datos_kwh['kwh_02'] = year_02_data[0].kwh_rate
                            else:
                                datos_monthrate['m_rate_02'] = 0
                                datos_kwh['kwh_02'] = 0

                    graph_m_rate_arr.append(datos_monthrate)
                    if template_vars['dac_region1_2']:
                        graph_p01_kwh_arr.append(datos_p01_kwh)
                        graph_p02_kwh_arr.append(datos_p02_kwh)
                    else:
                        graph_kwh_arr.append(datos_kwh)

            elif tipo_tarifa.pk == 3:

                template_vars['tarifa'] = 3

                for i in range(12):
                    mes = i + 1

                    datos_kw = dict()
                    datos_kwh = dict()

                    year_01_data = ThreeElectricRateDetail.objects.filter(
                        date_init__month = mes, date_init__year = year_01
                    )

                    datos_kw['mes'] = getMonthName(i+1)
                    datos_kwh['mes'] = getMonthName(i+1)

                    if year_01_data:
                        datos_kw['kw_01'] = year_01_data[0].kw_rate
                        datos_kwh['kwh_01'] = year_01_data[0].kwh_rate
                    else:
                        datos_kw['kw_01'] = 0
                        datos_kwh['kwh_01'] = 0

                    if compare_years_flag:
                        year_02_data = ThreeElectricRateDetail.objects.filter(
                            date_init__month=mes, date_init__year=year_02
                        )

                        if year_02_data:
                            datos_kw['kw_02'] = year_02_data[0].kw_rate
                            datos_kwh['kwh_02'] = year_02_data[0].kwh_rate
                        else:
                            datos_kw['kw_02'] = 0
                            datos_kwh['kwh_02'] = 0

                    graph_kw_arr.append(datos_kw)
                    graph_kwh_arr.append(datos_kwh)

            if tipo_tarifa.pk == 1:
                template_vars['kdf_data'] = graph_kdf_arr
                template_vars['kwhp_data'] = graph_kwhp_arr
                template_vars['kwhi_data'] = graph_kwhi_arr
                template_vars['kwhb_data'] = graph_kwhb_arr
            elif tipo_tarifa.pk == 2:
                template_vars['mrate_data'] = graph_m_rate_arr
                template_vars['kwh_data'] = graph_kwh_arr
                template_vars['p1_kwh'] = graph_p01_kwh_arr
                template_vars['p2_kwh'] = graph_p02_kwh_arr
                template_vars['periodo_1'] = periodo_1_dac
                template_vars['periodo_2'] = periodo_2_dac

            elif tipo_tarifa.pk == 3:
                template_vars['kw_data'] = graph_kw_arr
                template_vars['kwh_data'] = graph_kwh_arr

            template_vars_template = RequestContext(request, template_vars)
            return render_to_response(
                "consumption_centers/graphs/analisis_costo_f_frame.html",
                template_vars_template)

    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def power_performance(request):
    """Renders the cfe bill and the historic data chart"""
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, VIEW, "Desempeño energético") or \
            request.user.is_superuser:
        if not request.session['consumer_unit']:
            return HttpResponse(
                content=MSG_PERMIT_ERROR)

        set_default_session_vars(request, datacontext)

        template_vars = dict(datacontext=datacontext,
                             empresa=request.session['main_building'])

        building = request.session['main_building']

        #Se obtiene el tipo de tarifa del edificio
        tipo_tarifa = building.electric_rate

        compare_years_flag = False

        atributos_completos = []

        if request.GET:
            year_01 = int(request.GET['year01'])
            template_vars['year_01'] = year_01
            if request.GET.__contains__('year02'):
                compare_years_flag = True
                template_vars['compare_years'] = True
                year_02 = int(request.GET['year02'])
                template_vars['year_02'] = year_02


            #Para el edificio, obtiene sus atributos con sus valores
            b_attributes = BuildingAttributesForBuilding.objects.filter(building=building)
            #datos_kwh['mes'] = getMonthName(i+1)
            #datos_money['mes'] = getMonthName(i+1)
            if b_attributes:
                for attr in b_attributes:

                    atributo_dic = dict()

                    nombre_attr = attr.building_attributes.building_attributes_name
                    unidad_attr = attr.building_attributes.building_attributes_units_of_measurement
                    valor_attr = float(attr.building_attributes_value)

                    atributo_dic['nombre'] = nombre_attr
                    atributo_dic['nombre_seguro'] = nombre_attr.lower().replace(' ','_')
                    atributo_dic['unidad'] = unidad_attr
                    atributo_dic['atr_total'] = valor_attr

                    #Arreglo que almacena el dictionario mensual (valores para graficar)
                    datos_mensuales = []

                    num_meses = 0
                    num_meses2 = 0
                    suma_kwh = 0
                    suma_kwh2 = 0

                    if tipo_tarifa.pk == 1:

                        template_vars['tarifa'] = 1

                        for i in range(12):
                            mes = i+1

                            dict_mensual = dict()
                            dict_mensual['mes'] = getMonthName(mes)


                            year_01_data = HMHistoricData.objects.filter(
                                monthly_cut_dates__building = building,
                                monthly_cut_dates__billing_month__year = year_01,
                                monthly_cut_dates__billing_month__month = mes)

                            if year_01_data:
                                dict_mensual['kwh_01'] = float(year_01_data[0].KWH_total) / valor_attr
                                suma_kwh += dict_mensual['kwh_01']
                                num_meses += 1
                            else:
                                dict_mensual['kwh_01'] = 0

                            if compare_years_flag:
                                year_02_data = HMHistoricData.objects.filter(
                                    monthly_cut_dates__building = building,
                                    monthly_cut_dates__billing_month__year = year_02,
                                    monthly_cut_dates__billing_month__month = mes)

                                if year_02_data:
                                    dict_mensual['kwh_02'] = float(year_02_data[0].KWH_total) / valor_attr
                                    suma_kwh2 += dict_mensual['kwh_02']
                                    num_meses2 += 1
                                else:
                                    dict_mensual['kwh_02'] = 0

                            datos_mensuales.append(dict_mensual)

                    elif tipo_tarifa.pk == 2:

                        template_vars['tarifa'] = 2

                        for i in range(12):
                            mes = i+1

                            dict_mensual = dict()
                            dict_mensual['mes'] = getMonthName(mes)

                            year_01_data = DacHistoricData.objects.filter(
                                monthly_cut_dates__building = building,
                                monthly_cut_dates__billing_month__year = year_01,
                                monthly_cut_dates__billing_month__month = mes)

                            if year_01_data:
                                dict_mensual['kwh_01'] = float(year_01_data[0].KWH_total) / valor_attr
                                suma_kwh += dict_mensual['kwh_01']
                                num_meses += 1
                            else:
                                dict_mensual['kwh_01'] = 0

                            if compare_years_flag:
                                year_02_data = DacHistoricData.objects.filter(
                                    monthly_cut_dates__building = building,
                                    monthly_cut_dates__billing_month__year = year_02,
                                    monthly_cut_dates__billing_month__month = mes)

                                if year_02_data:
                                    dict_mensual['kwh_02'] = float(year_02_data[0].KWH_total) / valor_attr
                                    suma_kwh2 += dict_mensual['kwh_02']
                                    num_meses2 += 1
                                else:
                                    dict_mensual['kwh_02'] = 0

                            datos_mensuales.append(dict_mensual)

                    elif tipo_tarifa.pk == 3:

                        template_vars['tarifa'] = 3

                        for i in range(12):

                            mes = i+1

                            dict_mensual = dict()
                            dict_mensual['mes'] = getMonthName(mes)

                            year_01_data = T3HistoricData.objects.filter(
                                monthly_cut_dates__building = building,
                                monthly_cut_dates__billing_month__year = year_01,
                                monthly_cut_dates__billing_month__month = mes)

                            if year_01_data:
                                dict_mensual['kwh_01'] = float(year_01_data[0].KWH_total) / valor_attr
                                suma_kwh += dict_mensual['kwh_01']
                                num_meses += 1
                            else:
                                dict_mensual['kwh_01'] = 0

                            if compare_years_flag:
                                year_02_data = T3HistoricData.objects.filter(
                                    monthly_cut_dates__building = building,
                                    monthly_cut_dates__billing_month__year = year_02,
                                    monthly_cut_dates__billing_month__month = mes)

                                if year_02_data:
                                    dict_mensual['kwh_02'] = float(year_02_data[0].KWH_total) / valor_attr
                                    suma_kwh2 += dict_mensual['kwh_02']
                                    num_meses2 += 1
                                else:
                                    dict_mensual['kwh_02'] = 0

                            datos_mensuales.append(dict_mensual)

                    atributo_dic['valores'] = datos_mensuales
                    atributo_dic['y01_promedio'] = float(suma_kwh)/float(num_meses)
                    if compare_years_flag:
                        atributo_dic['y02_promedio'] = float(suma_kwh2)/float(num_meses2)
                        diff_promedios = (float(atributo_dic['y01_promedio']) *
                            100.0 / float(atributo_dic['y02_promedio'])) - 100.0

                        if diff_promedios > 0:
                            atributo_dic['positive_b'] = 1
                        elif diff_promedios < 0:
                            atributo_dic['positive_b'] = -1
                        else:
                            template_vars['positive_b'] = 0
                        atributo_dic['variacion'] = fabs(diff_promedios)

                    atributos_completos.append(atributo_dic)

            template_vars['contenedor_global'] = atributos_completos

            template_vars_template = RequestContext(request, template_vars)
            return render_to_response(
                "consumption_centers/graphs/desempenio_energetico_frame.html",
                template_vars_template)

    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def parse_csv(request):
    datacontext = get_buildings_context(request.user)[0]
    if request.user.is_superuser:
        set_default_session_vars(request, datacontext)
        template_variables = dict(
            datacontext=datacontext,
            empresa=request.session['main_building'])
        todays_date = datetime.datetime.now().strftime("%Y/%m/%d/")
        todays_dir = datetime.datetime.now().strftime("%Y-%m-%d/")
        message = ''
        if request.method == "POST":
            #parse csv files

            dir_path = os.path.join(settings.PROJECT_PATH, FILE_FOLDER)
            try:
                files = os.listdir(dir_path+todays_dir)
            except OSError:
                message = "No se ha subido ningún archivo"
            else:
                dir_path += todays_dir
                for _file in files:
                    restore_data.delay(_file, dir_path)
                else:
                    message = "Las tareas de recuperación se han registrado " \
                              "exitosamente"

        delete_file_url = "/del_file/"+todays_date
        media_folder = "/static/media/csv_files/"+todays_dir
        all_files_url = "/get_all_files/"+todays_date

        template_variables['message'] = message
        template_variables['delete_file_url'] = delete_file_url
        template_variables['media_folder'] = media_folder
        template_variables['all_files_url'] = all_files_url

        variables_template = RequestContext(request, template_variables)
        return render_to_response("consumption_centers/parse_form.html",
                                  variables_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


# noinspection PyArgumentList
@login_required(login_url='/')
def view_tags(request):
    datacontext = get_buildings_context(request.user)[0]
    if request.user.is_superuser:
        empresa = request.session['main_building']
        post = ''

        message = ""
        _type = ""

        #Se obtiene el dia actual
        today = datetime.datetime.now()

        year = int(today.year)

        monthly_years = []
        for yr in range(2012,year+1):
            monthly_years.append(yr)

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             today = today,
                             monthly_years=monthly_years,
                             company=request.session['company'],
                             sidebar=request.session['sidebar'],
                             consumer_unit=request.session['consumer_unit']
        )



        if request.method == "POST":
            template_vars["post"] = request.POST
            init_str = request.POST.get('date_init').strip()
            end_str = request.POST.get('date_end').strip()

            s_date_str = time.strptime(init_str, "%Y-%m-%d")
            s_date_utc_tuple = time.gmtime(time.mktime(s_date_str))
            s_date = datetime.datetime(year=s_date_utc_tuple[0],
                                           month=s_date_utc_tuple[1],
                                           day=s_date_utc_tuple[2])

            e_date_str = time.strptime(end_str, "%Y-%m-%d")
            e_date_utc_tuple = time.gmtime(time.mktime(e_date_str))
            e_date = datetime.datetime(year=e_date_utc_tuple[0],
                                       month=e_date_utc_tuple[1],
                                       day=e_date_utc_tuple[2])


            consumer_unit = request.session['consumer_unit']
            profile_powermeter = consumer_unit.profile_powermeter

            tags_dict = []

            #Timedelta para recorrer todos los dias
            dia = datetime.timedelta(days=1)

            #Se consiguen cada uno de los tags
            while s_date <= e_date:
                tags = ElectricDataTags.objects.filter(
                    electric_data__profile_powermeter = profile_powermeter,
                    electric_data__medition_date__gte = s_date,
                    electric_data__medition_date__lt = s_date+dia
                ).order_by('electric_data__medition_date')


                arr_tags = []

                for tg in tags:
                    ar_val = []
                    ar_val.append(tg.electric_data.medition_date.astimezone(timezone.get_current_timezone()).strftime('%d-%m-%Y %H:%M'))
                    ar_val.append(tg.electric_rates_periods.period_type)
                    ar_val.append(tg.identifier)
                    arr_tags.append(ar_val)

                s_date = s_date + dia

                tags_dict.append(arr_tags)


            template_vars["s_date"] = init_str
            template_vars["e_date"] = end_str
            template_vars["tags"] = tags_dict

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/electrictags.html",
            template_vars_template)

    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def retag_ajax(request):
    if "s_date" in request.GET and "e_date" in request.GET:
        consumer_unit = request.session['consumer_unit']
        profile_powermeter = consumer_unit.profile_powermeter

        init_str = request.GET['s_date']
        end_str = request.GET['e_date']

        s_date_str = time.strptime(init_str, "%Y-%m-%d")
        s_date_utc_tuple = time.gmtime(time.mktime(s_date_str))
        s_date = datetime.datetime(year=s_date_utc_tuple[0],
                                   month=s_date_utc_tuple[1],
                                   day=s_date_utc_tuple[2])

        e_date_str = time.strptime(end_str, "%Y-%m-%d")
        e_date_utc_tuple = time.gmtime(time.mktime(e_date_str))
        e_date = datetime.datetime(year=e_date_utc_tuple[0],
                                   month=e_date_utc_tuple[1],
                                   day=e_date_utc_tuple[2])

        #Reetiqueta los diarios
        tag_n_daily_report.delay(consumer_unit.pk, s_date, e_date)

        resp_dic = dict()
        resp_dic["status"] = "Success"
        data = simplejson.dumps(resp_dic)
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404


def daily_ajax(request):
    if "s_date" in request.GET and "e_date" in request.GET:
        consumer_unit = request.session['consumer_unit']

        init_str = request.GET['s_date']
        end_str = request.GET['e_date']

        s_date_str = time.strptime(init_str, "%Y-%m-%d")
        s_date_utc_tuple = time.gmtime(time.mktime(s_date_str))
        s_date = datetime.datetime(year=s_date_utc_tuple[0],
                                   month=s_date_utc_tuple[1],
                                   day=s_date_utc_tuple[2])

        e_date_str = time.strptime(end_str, "%Y-%m-%d")
        e_date_utc_tuple = time.gmtime(time.mktime(e_date_str))
        e_date = datetime.datetime(year=e_date_utc_tuple[0],
                                   month=e_date_utc_tuple[1],
                                   day=e_date_utc_tuple[2])

        daily_report_period.delay(consumer_unit.building,
                                  consumer_unit, s_date, e_date)

        resp_dic = dict()
        resp_dic["status"] = "Success"
        data = simplejson.dumps(resp_dic)
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404


def monthly_ajax(request):
    if "month" in request.GET and "year" in request.GET:
        consumer_unit = request.session['consumer_unit']

        month = int(request.GET['month'])
        year = int(request.GET['year'])

        calculateMonthlyReportCU.delay(consumer_unit, month, year)

        resp_dic = dict()
        resp_dic["status"] = "Success"
        data = simplejson.dumps(resp_dic)
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404


@login_required(login_url='/')
def wizard(request):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, UPDATE,
                      "Alta de equipos industriales") or \
            request.user.is_superuser:
        clusters = get_clusters_for_operation("Alta de equipos industriales",
                                              CREATE, request.user)
        operation = Object.objects.filter(
            object_name="Alta de equipos industriales").values("pk")[0]['pk']
        template_vars = dict(datacontext=datacontext,
                             sidebar=request.session['sidebar'],
                             company=request.session['company'],
                             clusters=clusters,
                             operation=operation
                             )

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("wizard.html", template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def add_cluster_pop(request):
    datacontext = get_buildings_context(request.user)[0]
    if has_permission(request.user, CREATE, "Alta de grupos de empresas") or \
            request.user.is_superuser:
        empresa = request.session['main_building']
        message = ''
        _type = ''
        #Se obtienen los sectores
        sectores = SectoralType.objects.filter(sectoral_type_status=1)
        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             sectores=sectores,
                             company=request.session['company'],
                             sidebar=request.session['sidebar']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/popups/popup_add_cluster.html",
            template_vars_template)

    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def save_add_cluster_popup(request):
    if has_permission(request.user, CREATE, "Alta de grupos de empresas") or \
            request.user.is_superuser and request.method == "POST":
        template_vars = dict()
        template_vars["post"] = request.POST
        clustername = request.POST.get('clustername').strip()
        clusterdescription = request.POST.get('clusterdescription').strip()
        clustersector = request.POST.get('clustersector')

        continuar = True
        message = ''
        _type = ''
        if clustername == '':
            message = "El nombre del Cluster no puede quedar vacío"
            _type = "n_notif"
            continuar = False
        elif not variety.validate_string(clustername):
            message = "El nombre del Cluster contiene caracteres inválidos"
            _type = "n_notif"
            clustername = ""
            continuar = False

        if clustersector == '':
            message = "El Cluster debe pertenecer a un tipo de sector"
            _type = "n_notif"
            continuar = False


        #Valida por si le da muchos clics al boton
        clusterValidate = Cluster.objects.filter(cluster_name=clustername)
        if clusterValidate:
            message = "Ya existe un cluster con ese nombre"
            _type = "n_notif"
            continuar = False

        post = {'clustername': clustername,
                'clusterdescription': clusterdescription,
                'clustersector': int(clustersector)}
        template_vars['post'] = post

        template_vars["post"] = post
        template_vars["message"] = message
        template_vars["type"] = _type

        if continuar:
            sector_type = SectoralType.objects.get(pk=clustersector)

            newCluster = Cluster(
                sectoral_type=sector_type,
                cluster_description=clusterdescription,
                cluster_name=clustername,
            )
            newCluster.save()
            template_vars["cluster_new"] = newCluster.pk
            template_vars["message"] = "Cluster de Empresas creado " \
                                       "exitosamente"
            template_vars["type"] = "n_success"
        return HttpResponse(content=simplejson.dumps(template_vars),
                            content_type="application/json", status=200)
    else:
        raise Http404


@login_required(login_url='/')
def add_company_pop(request):
    if has_permission(request.user, CREATE,
                      "Alta de empresas") or request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        post = ''
        #Get Clusters
        clusters = get_clusters_for_operation("Alta de empresas", CREATE,
                                              request.user)
        #Get Sectors
        sectors = SectoralType.objects.filter(sectoral_type_status=1)
        company = int(request.GET['company'])
        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             post=post,
                             clusters=clusters,
                             sectors=sectors,
                             ref_company=company,
                             company=request.session['company'],
                             sidebar=request.session['sidebar'])
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/popups/popup_add_company.html",
            template_vars_template)

    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def save_add_company_popup(request):
    if has_permission(
            request.user, CREATE,
            "Alta de empresas") or request.user.is_superuser and \
            request.method == "POST":
        template_vars = dict()
        template_vars["post"] = request.POST
        cmp_name = request.POST.get('company_name').strip()
        cmp_description = request.POST.get('company_description').strip()
        cmp_cluster = request.POST.get('company_cluster')
        cmp_sector = request.POST.get('company_sector')

        message = ''
        _type = ''

        continuar = True
        if cmp_name == '':
            message = "El nombre de la empresa no puede quedar vacío"
            _type = "n_notif"
            continuar = False
        elif not variety.validate_string(cmp_name):
            message = "El nombre de la empresa contiene caracteres " \
                      "inválidos"
            _type = "n_notif"
            cmp_name = ""
            continuar = False

        if cmp_cluster == '':
            message = "La empresa debe pertenencer a un grupo de empresas"
            _type = "n_notif"
            continuar = False

        if cmp_sector == '':
            message = "La empresa debe pertenencer a un sector"
            _type = "n_notif"
            continuar = False

        #Valida no puede haber empresas con el mismo nombre
        companyValidate = Company.objects.filter(company_name=cmp_name)
        if companyValidate:
            message = "Ya existe una empresa con ese nombre"
            _type = "n_notif"
            continuar = False

        post = {'cmp_name': cmp_name, 'cmp_description': cmp_description,
                'cmp_cluster': int(cmp_cluster),
                'cmp_sector': int(cmp_sector)}

        if continuar:
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type
            #Se obtiene el objeto del sector
            sectorObj = SectoralType.objects.get(pk=cmp_sector)

            newCompany = Company(
                sectoral_type=sectorObj,
                company_name=cmp_name,
                company_description=cmp_description
            )
            newCompany.save()
            template_vars["company_new"] = newCompany.pk
            #Se relaciona la empresa con el cluster
            #Se obtiene el objeto del cluster
            clusterObj = Cluster.objects.get(pk=cmp_cluster)

            newCompanyCluster = ClusterCompany(
                cluster=clusterObj,
                company=newCompany
            )
            newCompanyCluster.save()

            #Guarda la foto
            if 'logo' in request.FILES:
                handle_company_logo(request.FILES['logo'], newCompany, True)

            template_vars["message"] = "Empresa creada exitosamente"
            template_vars["type"] = "n_success"

        return HttpResponse(content=simplejson.dumps(template_vars),
                        content_type="application/json", status=200)
    else:
        raise Http404


@login_required(login_url='/')
def add_building_pop(request):
    if has_permission(request.user, CREATE,
                      "Alta de edificios") or request.user.is_superuser:
        #Se obtienen las empresas
        empresas_lst = get_all_companies_for_operation("Alta de edificios",
                                                       CREATE, request.user)
        empresa = int(request.GET['company'])
        #Se obtienen las tarifas
        tarifas = ElectricRates.objects.all()

        #Se obtienen los tipos de edificios
        tipos_edificio_lst = BuildingType.objects.filter(
            building_type_status=1).order_by('building_type_name')

        #Se obtienen las regiones
        regiones_lst = Region.objects.all()

        #Se obtienen los tipos de atributos de edificios
        tipos_atributos = BuildingAttributesType.objects.filter(
            building_attributes_type_status=1).order_by(
                'building_attributes_type_name')

        template_vars = dict(empresas_lst=empresas_lst,
                             tipos_edificio_lst=tipos_edificio_lst,
                             tarifas=tarifas,
                             regiones_lst=regiones_lst,
                             tipos_atributos=tipos_atributos,
                             empresa=empresa
        )

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/popups/popup_add_building.html",
            template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)[0]
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def save_add_building_popup(request):
    if has_permission(
            request.user, CREATE,
            "Alta de edificios") or request.user.is_superuser and \
            request.method == "POST":
        template_vars = dict()
        message = ''
        _type = ''
        template_vars["post"] = request.POST
        b_name = request.POST.get('b_name').strip()
        b_description = request.POST.get('b_description').strip()
        b_company = request.POST.get('b_company')
        b_type_arr = request.POST.getlist('b_type')
        b_mt2 = request.POST.get('b_mt2').strip()
        b_electric_rate_id = request.POST.get('b_electric_rate')
        b_country_id = request.POST.get('b_country_id')
        b_country_name = request.POST.get('b_country').strip()
        b_state_id = request.POST.get('b_state_id')
        b_state_name = request.POST.get('b_state').strip()
        b_municipality_id = request.POST.get('b_municipality_id')
        b_municipality_name = request.POST.get('b_municipality').strip()
        b_neighborhood_id = request.POST.get('b_neighborhood_id')
        b_neighborhood_name = request.POST.get('b_neighborhood').strip()
        b_street_id = request.POST.get('b_street_id')
        b_street_name = request.POST.get('b_street').strip()
        b_ext = request.POST.get('b_ext').strip()
        b_int = request.POST.get('b_int').strip()
        b_zip = request.POST.get('b_zip').strip()
        b_long = request.POST.get('b_longitude')
        b_lat = request.POST.get('b_latitude')
        b_region_id = request.POST.get('b_region')

        if not bool(b_int):
            b_int = '0'

        if not bool(b_mt2):
            b_mt2 = '0'
        else:
            b_mt2 = b_mt2.replace(",", "")

        continuar = True
        if b_name == '':
            message += "El nombre del Edificio no puede quedar vacío"
            _type = "n_notif"
            continuar = False
        elif not variety.validate_string(b_name):
            message += "El nombre del Edificio contiene caracteres " \
                       "inválidos"
            _type = "n_notif"
            b_name = ""
            continuar = False

        if b_company == '':
            message += " - Se debe seleccionar una empresa"
            _type = "n_notif"
            continuar = False

        if not b_type_arr:
            message += " - El edificio debe ser al menos de un tipo"
            _type = "n_notif"
            continuar = False

        if b_electric_rate_id == '':
            message += " - Se debe seleccionar un tipo de tarifa"
            _type = "n_notif"
            continuar = False

        if b_ext == '':
            message += " - El edificio debe tener un número exterior"
            _type = "n_notif"
            continuar = False

        if b_zip == '':
            message += " - El edificio debe tener un código postal"
            _type = "n_notif"
            continuar = False

        if b_long == '' and b_lat == '':
            message += " - Debes ubicar el edificio en el mapa"
            _type = "n_notif"
            continuar = False

        if b_region_id == '':
            message += " - El edificio debe pertenecer a una región"
            _type = "n_notif"
            continuar = False

        #Valida por si le da muchos clics al boton
        buildingValidate = Building.objects.filter(building_name=b_name)
        if buildingValidate:
            message = "Ya existe un Edificio con ese nombre"
            _type = "n_notif"
            continuar = False

        post = {
            'b_name': b_name,
            'b_description': b_description,
            'b_company': int(b_company),
            'b_type_arr': b_type_arr,
            'b_mt2': b_mt2,
            'b_electric_rate_id': int(b_electric_rate_id),
            'b_country_id': b_country_id,
            'b_country': b_country_name,
            'b_state_id': b_state_id,
            'b_state': b_state_name,
            'b_municipality_id': b_municipality_id,
            'b_municipality': b_municipality_name,
            'b_neighborhood_id': b_neighborhood_id,
            'b_neighborhood': b_neighborhood_name,
            'b_street_id': b_street_id,
            'b_street': b_street_name,
            'b_ext': b_ext,
            'b_int': b_int,
            'b_zip': b_zip,
            'b_long': b_long,
            'b_lat': b_lat,
            'b_region_id': int(b_region_id)
        }

        if continuar:
            #se obtiene el objeto de la tarifa
            tarifaObj = get_object_or_404(ElectricRates,
                                          pk=b_electric_rate_id)

            #Se obtiene la compañia
            companyObj = get_object_or_404(Company, pk=b_company)

            #Se obtiene el objeto de la region
            regionObj = get_object_or_404(Region, pk=b_region_id)

            countryObj, stateObj, municipalityObj, neighborhoodObj, \
            streetObj = location_objects(
                b_country_id, b_country_name,
                b_state_id, b_state_name, b_municipality_id,
                b_municipality_name, b_neighborhood_id, b_neighborhood_name,
                b_street_id, b_street_name)

            #Se crea la cadena con la direccion concatenada
            formatted_address = streetObj.calle_name + " " + b_ext
            if b_int:
                formatted_address += "-" + b_int
            formatted_address += " Colonia: " + \
                                 neighborhoodObj.colonia_name + " " + \
                                 municipalityObj.municipio_name
            formatted_address += " " + stateObj.estado_name + " " + \
                                 countryObj.pais_name + "C.P." + b_zip

            #Se da de alta el edificio
            newBuilding = Building(
                building_name=b_name,
                building_description=b_description,
                building_formatted_address=formatted_address,
                pais=countryObj,
                estado=stateObj,
                municipio=municipalityObj,
                colonia=neighborhoodObj,
                calle=streetObj,
                region=regionObj,
                building_external_number=b_ext,
                building_internal_number=b_int,
                building_code_zone=b_zip,
                building_long_address=b_long,
                building_lat_address=b_lat,
                electric_rate=tarifaObj,
                mts2_built=b_mt2,
            )
            newBuilding.save()
            IndustrialEquipment(alias="SA de "+b_name,
                                building=newBuilding).save()
            template_vars["building"] = newBuilding.pk
            #Se da de alta la fecha de corte

            date_init = datetime.datetime.today().utcnow().replace(
                tzinfo=pytz.utc)
            billing_month = datetime.date(year=date_init.year,
                                          month=date_init.month, day=1)

            new_cut = MonthlyCutDates(
                building=newBuilding,
                billing_month=billing_month,
                date_init=date_init,
            )
            new_cut.save()

            #Se relaciona la compania con el edificio
            newBldComp = CompanyBuilding(
                company=companyObj,
                building=newBuilding,
            )
            newBldComp.save()

            #Se dan de alta los tipos de edificio
            for b_type in b_type_arr:
                #Se obtiene el objeto del tipo de edificio
                typeObj = get_object_or_404(BuildingType, pk=b_type)
                bt_n = newBuilding.building_name + " - " + \
                       typeObj.building_type_name
                newBuildingTypeBuilding = BuildingTypeForBuilding(
                    building=newBuilding,
                    building_type=typeObj,
                    building_type_for_building_name=bt_n
                )
                newBuildingTypeBuilding.save()

            for key in request.POST:
                if re.search('^atributo_\w+', key):
                    atr_value_complete = request.POST.get(key)
                    atr_value_arr = atr_value_complete.split(',')
                    #Se obtiene el objeto tipo de atributo
                    #Se obtiene el objeto atributo
                    attribute_obj = BuildingAttributes.objects.get(
                        pk=atr_value_arr[1])

                    newBldAtt = BuildingAttributesForBuilding(
                        building=newBuilding,
                        building_attributes=attribute_obj,
                        building_attributes_value=atr_value_arr[2]
                    )
                    newBldAtt.save()

            electric_device_type = ElectricDeviceType.objects.get(
                electric_device_type_name="Total Edificio")
            cu = ConsumerUnit(
                building=newBuilding,
                electric_device_type=electric_device_type,
                profile_powermeter=VIRTUAL_PROFILE
            )
            cu.save()
            #Add the consumer_unit instance for the DW
            populate_data_warehouse_extended(
                populate_instants=None,
                populate_consumer_unit_profiles=True,
                populate_data=None)

            template_vars["message"] = "Edificio creado exitosamente"
            template_vars["type"] = "n_success"

        template_vars["post"] = post

        return HttpResponse(content=simplejson.dumps(template_vars),
                        content_type="application/json", status=200)
    else:
        raise Http404


@login_required(login_url='/')
def create_hierarchy_pop(request, id_building):
    template_vars = dict()

    if has_permission(request.user, CREATE,
                      "Alta de jerarquía de partes") or \
            request.user.is_superuser:
        building = get_object_or_404(Building, pk=id_building)
        _list = get_hierarchy_list(building, request.user)
        template_vars['list'] = _list
        template_vars['building'] = building

        ids_prof = ConsumerUnit.objects.all().values_list(
            "profile_powermeter__pk", flat=True)
        profs = ProfilePowermeter.objects.exclude(
            pk__in=ids_prof).exclude(
                powermeter__powermeter_anotation="No Registrado").exclude(
                    powermeter__powermeter_anotation="Medidor Virtual")
        template_vars['electric_devices'] = ElectricDeviceType.objects.all()
        template_vars['prof_pwmeters'] = profs
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            "consumption_centers/buildings/popups/popup_create_hierarchy.html",
            template_vars_template)
    else:
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def refresh_ie_config(request):
    building = get_object_or_404(Building, pk=int(request.POST['building']))
    ie = IndustrialEquipment.objects.get(building=building)
    regenerate_ie_config(ie.pk, request.user)
    set_alarm_json(building, request.user)
    return HttpResponse(status=200)