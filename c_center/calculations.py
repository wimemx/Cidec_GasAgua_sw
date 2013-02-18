# -*- coding: utf-8 -*-
# Create your views here.

#standard library imports
import collections
import pytz, datetime
from time import strftime
from math import *
from decimal import *
from calendar import monthrange

#related third party imports
from django.template import RequestContext
from django.http import *
from django.shortcuts import render_to_response
from django.db.models.aggregates import *
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from dateutil.relativedelta import *

#local application/library specific imports

from c_center.models import *
from electric_rates.models import *

def demandafacturable(kwbase, kwintermedio, kwpunta, fri, frb):
    df = 0

    primermax = kwintermedio - kwpunta
    if primermax < 0:
        primermax = 0

    segundomax = kwbase - max(kwintermedio, kwpunta)
    if segundomax < 0:
        segundomax = 0

    df = kwpunta + fri * primermax + frb * segundomax

    return int(ceil(df))


def demandafacturable_tarifa(kwbase, kwintermedio, kwpunta, tarifa):
    df = 0
    #Se obtienen los Factores de Reduccion en base a la zona,
    # la tarifa y la fecha
    factores_reduccion = ElectricRatesDetail.objects.get(id=tarifa)
    fri = factores_reduccion.FRI
    frb = factores_reduccion.FRB
    primermax = kwintermedio - kwpunta
    if primermax < 0:
        primermax = 0
    segundomax = kwbase - max(kwintermedio, kwpunta)
    if segundomax < 0:
        segundomax = 0
    df = Decimal(str(kwpunta)) + Decimal(str(fri)) * Decimal(
        str(primermax)) + Decimal(str(frb)) * Decimal(str(segundomax))
    return int(ceil(df))


def demandafacturable_total(kwbase, kwintermedio, kwpunta, fri, frb):
    df = 0
    primermax = kwintermedio - kwpunta
    if primermax < 0:
        primermax = 0
    segundomax = kwbase - max(kwintermedio, kwpunta)
    if segundomax < 0:
        segundomax = 0
    df = kwpunta + fri * primermax + frb * segundomax
    return int(ceil(df))


def costoenergia(kwbase, kwintermedio, kwpunta, tarifa_kwhb, tarifa_kwhi,
                 tarifa_kwhp):
    costo_energia = 0

    costo_energia = kwbase * tarifa_kwhb + kwintermedio * tarifa_kwhi + \
                    kwpunta * tarifa_kwhp

    return costo_energia


def costoenergia_tarifa(kwbase, kwintermedio, kwpunta, tarifa_id):
    costo_energia = 0

    try:
        #Se obtienen las tarifas para cada kw
        tarifas = ElectricRatesDetail.objects.get(id=tarifa_id)

        tarifa_kwbase = tarifas.KWHB
        tarifa_kwintermedio = tarifas.KWHI
        tarifa_kwpunta = tarifas.KWHP

    except ElectricRatesDetail.DoesNotExist:
        tarifa_kwbase = 0
        tarifa_kwintermedio = 0
        tarifa_kwpunta = 0

    costo_energia = Decimal(str(kwbase)) * Decimal(
        str(tarifa_kwbase)) + Decimal(str(kwintermedio)) * Decimal(
        str(tarifa_kwintermedio)) + Decimal(str(kwpunta)) * Decimal(
        str(tarifa_kwpunta))

    return costo_energia


def costoenergia_total(kwbase, kwintermedio, kwpunta, tarifa_kwbase,
                       tarifa_kwintermedio, tarifa_kwpunta):
    costo_energia = 0

    costo_energia = kwbase * tarifa_kwbase + kwintermedio * \
                    tarifa_kwintermedio + kwpunta * \
                    tarifa_kwpunta

    return costo_energia


def costodemandafacturable(demandaf, tarifa_demanda):
    return (demandaf * tarifa_demanda)


def costodemandafacturable_tarifa(demandaf, tarifa_id):
    precio = 0
    #Se obtiene el precio de la demanda
    tarifas = ElectricRatesDetail.objects.get(id=tarifa_id)
    tarifa_demanda = tarifas.KDF
    return (demandaf * tarifa_demanda)


def costodemandafacturable_total(demandaf, tarifa_demanda):
    return (demandaf * tarifa_demanda)


def fpbonificacionrecargo(fp):
    fp_valor = 0
    if fp != 0:
        if fp < 90:
            fp_valor = Decimal(str(3.0 / 5.0)) * (
                (Decimal(str(90.0)) / fp) - 1) * 100
        else:
            fp_valor = Decimal(str(1.0 / 4.0)) * (
                1 - (Decimal(str(90.0)) / fp)) * 100

    return float(fp_valor)


def costofactorpotencia(fp, costo_energia, costo_df):
    costo_fp = 0

    if fp < 90:
        costo_fp = float(
            (costo_energia + costo_df) / 100) * fpbonificacionrecargo(fp)
    else:
        costo_fp = float(
            (costo_energia + costo_df) / 100) * fpbonificacionrecargo(fp) * -1

    return costo_fp


def obtenerSubtotal(costo_energia, costo_df, costo_fp):
    return (float(costo_energia) + float(costo_df) + float(costo_fp))


def obtenerIva(c_subtotal, iva):
    iva = iva / 100.0
    return float(c_subtotal) * float(iva)


def obtenerTotal(c_subtotal, iva):
    iva = iva / 100.0 + 1
    return float(c_subtotal) * float(iva)


def factorpotencia(kwh, kvarh):
    fp = 0

    if kwh != 0 or kvarh != 0:
        square_kwh = Decimal(str(pow(kwh, 2)))
        square_kvarh = Decimal(str(pow(kvarh, 2)))
        fp = (Decimal(str(kwh)) / Decimal(
            str(pow((square_kwh + square_kvarh), .5)))) * 100
    return fp


def obtenerDemanda(arr_kw):
    demanda_maxima = 0
    if arr_kw:
        try:
            longitud = len(arr_kw)
            if longitud >= 3:
                for indice, demanda in enumerate(arr_kw):
                    if indice + 1 < (longitud - 1) and indice + 2 <= (
                            longitud - 1):
                        prom = (Decimal(str(arr_kw[indice])) + Decimal(
                            str(arr_kw[indice + 1])) + Decimal(
                            str(arr_kw[indice + 2]))) / Decimal(3.0)
                        if prom > demanda_maxima:
                            demanda_maxima = int(ceil(prom))
            else:
                demanda_maxima = 0

        except IndexError:
            print "IndexError"
            demanda_maxima = 0
        except TypeError:
            print "TypeError"
            demanda_maxima = 0

    return demanda_maxima


def obtenerFestivos(year):
    """
    Obtiene los dias festivos almacenados en la tabla Holidays.
    Regresa una lista con las fechas exactas de los dias festivos para este año

    Ejemplo:
    1, 01 -> 1 de enero de 2012
    1-Lun, 02 = 1er Lunes de Febrero 2012 -> 6 de febrero de 2012


    """
    lista_festivos = []

    actual_year = year
    holidays = Holydays.objects.all()

    lst_days = {}
    lst_days['1'] = 'Lun'
    lst_days['2'] = 'Mar'
    lst_days['3'] = 'Mie'
    lst_days['4'] = 'Jue'
    lst_days['5'] = 'Vie'
    lst_days['6'] = 'Sab'
    lst_days['0'] = 'Dom'

    if holidays:
        for hday in holidays:
            f_var = hday.day.split('-')
            if len(f_var) > 1:
                dia_mes = 1
                ahorita = 1
                n_day = f_var[0]
                w_day = f_var[1]
                month_days = monthrange(actual_year, hday.month)
                while(dia_mes < month_days[1] - 1):
                    #st_time = time.strptime("%02d" % (c_day)+" "+"%02d" % (
                    # mes)+" "+str(actual_year), "%d %m %Y")
                    st_time = time.strptime(
                        "%02d" % (dia_mes) + " " + "%02d" % (
                            hday.month) + " " + str(actual_year), "%d %m %Y")
                    week_day = strftime("%w", st_time)
                    if lst_days[week_day] == w_day:
                        if ahorita == int(n_day):
                            lista_festivos.append(strftime("%d %m %Y", st_time))
                            break
                        else:
                            ahorita += 1

                    dia_mes += 1
            else:
                # Si es 1 de diciembre, se verifica que sea año de elecciones.
                # En caso afirmativo se agrega a la lista de dias festivos
                if int(hday.day) == 1 and int(hday.month) == 12:
                    if (actual_year - 1946) % 6 == 0:
                        st_time = time.strptime(
                            "%02d" % int(hday.day) + " " + "%02d" % int(
                                hday.month) + " " + str(actual_year),
                            "%d %m %Y")
                        lista_festivos.append(strftime("%d %m %Y", st_time))
                else:
                    st_time = time.strptime(
                        "%02d" % int(hday.day) + " " + "%02d" % int(
                            hday.month) + " " + str(actual_year), "%d %m %Y")
                    lista_festivos.append(strftime("%d %m %Y", st_time))

    return lista_festivos


def obtenerCatalogoGrupos():
    """

    Se regresa un catálogo que indica a qué grupo pertenece cada día de la
    semana.

    """
    group_days_bd = Groupdays.objects.all();
    group_days = {}

    if group_days_bd:
        for g_days in group_days_bd:
            if g_days.sunday:
                group_days[0] = g_days.id
            if g_days.monday:
                group_days[1] = g_days.id
            if g_days.tuesday:
                group_days[2] = g_days.id
            if g_days.wednesday:
                group_days[3] = g_days.id
            if g_days.thursday:
                group_days[4] = g_days.id
            if g_days.friday:
                group_days[5] = g_days.id
            if g_days.saturday:
                group_days[6] = g_days.id
            if g_days.holydays:
                group_days[7] = g_days.id

    return group_days


def obtenerGrupo(catalogo_grupos, fecha):
    """
    A partir de una fecha, se obtiene a qué grupo de días pertenece: Lun a
    Vie, Sab o Dom y Festivos

    """

    num_dia = 0

    dias_festivos = obtenerFestivos(fecha.year)
    #if (str(fecha.day)+" "+str(fecha.month)+" "+str(fecha.year)) in
    # dias_festivos:
    if fecha in dias_festivos:
        num_dia = 7
    else:
        st_time = time.strptime(
            str(fecha.day) + " " + str(fecha.month) + " " + str(fecha.year),
            "%d %m %Y")
        num_dia = strftime("%w", st_time)

    return catalogo_grupos[int(num_dia)]


def obtenerTipoPeriodo(fecha, region, tarifa, catalogo_grupos):
    """
    Se obtiene el tipo de periodo de una lectura, en base a la fecha y hora
    en que fue tomada, región y tarifa.

    """
    grupo_id = obtenerGrupo(catalogo_grupos, fecha)
    horario_ver_inv = [date.pk for date in DateIntervals.objects.filter(
        date_init__lte=datetime.date(fecha.year, fecha.month,
                                     fecha.day)).filter(
        date_end__gte=datetime.date(fecha.year, fecha.month,
                                    fecha.day))]#.filter(region = region)

    electric_type = ElectricRatesPeriods.objects.filter(region=region).filter(
        electric_rate=tarifa).filter(date_interval__in=horario_ver_inv).filter(
        groupdays=grupo_id).filter(
        time_init__lte=datetime.time(fecha.hour, fecha.minute)).filter(
        time_end__gte=datetime.time(fecha.hour, fecha.minute))

    return electric_type[0].period_type


def obtenerTipoPeriodoObj(fecha, region):
    """
    Se obtiene el tipo de periodo de una lectura, en base a la fecha y hora
    en que fue tomada, región y tarifa.

    """
    catalogo_grupos = obtenerCatalogoGrupos()
    grupo_id = obtenerGrupo(catalogo_grupos, fecha)
    horario_ver_inv = [date.pk for date in DateIntervals.objects.filter(
        date_init__lte=datetime.date(fecha.year, fecha.month,
                                     fecha.day)).filter(
        date_end__gte=datetime.date(fecha.year, fecha.month,
                                    fecha.day))]#.filter(region = region)

    """
    electric_type = ElectricRatesPeriods.objects.filter(region=region).filter(
        date_interval__in=horario_ver_inv).filter(groupdays=grupo_id).filter(
        time_init__lte=datetime.time(fecha.hour, fecha.minute)).filter(
        time_end__gte=datetime.time(fecha.hour, fecha.minute))
    """

    electric_type = ElectricRatesPeriods.objects.filter(region=region).filter(
        date_interval__in=horario_ver_inv).filter(groupdays=grupo_id).filter(
        Q(time_init__lte=fecha),Q(
            time_end__gte=fecha))

    return electric_type[0]


def obtenerHorarioVeranoInvierno(fecha, tarifa_id):
    horario = DateIntervals.objects.filter(
        date_init__lte=datetime.date(fecha.year, fecha.month,
                                     fecha.day)).filter(
        date_end__gte=datetime.date(fecha.year, fecha.month, fecha.day)).filter(
        electric_rate=tarifa_id)
    return horario[0]


def obtenerKWTarifa(pr_powermeter, tarifa_id):
    valores_periodo = {}

    tarifaObj = ElectricRatesDetail.objects.get(id=tarifa_id)

    fecha_inicio = str(tarifaObj.date_init) + " 00:00:00"
    fecha_fin = str(tarifaObj.date_end) + " 23:59:59"

    lecturas_base = ElectricRateForElectricData.objects.filter(
        electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk) \
        .filter(
        electric_data__medition_date__range=(fecha_inicio, fecha_fin)).filter(
        electric_rates_periods__period_type='base').order_by(
        'electric_data__medition_date')
    kw_base_t = obtenerDemanda_kw(lecturas_base)
    valores_periodo['base'] = kw_base_t

    lecturas_intermedio = ElectricRateForElectricData.objects.filter(
        electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk) \
        .filter(
        electric_data__medition_date__range=(fecha_inicio, fecha_fin)).filter(
        electric_rates_periods__period_type='intermedio').order_by(
        'electric_data__medition_date')
    kw_intermedio_t = obtenerDemanda_kw(lecturas_intermedio)
    valores_periodo['intermedio'] = kw_intermedio_t

    lecturas_punta = ElectricRateForElectricData.objects.filter(
        electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk) \
        .filter(
        electric_data__medition_date__range=(fecha_inicio, fecha_fin)).filter(
        electric_rates_periods__period_type='punta').order_by(
        'electric_data__medition_date')
    kw_punta_t = obtenerDemanda_kw(lecturas_punta)
    valores_periodo['punta'] = kw_punta_t

    return valores_periodo


def obtenerKWTarifa__(pr_powermeter, tarifa_id, region,
                      tipo_tarifa):#, lectura, catalogo_grupos):
    """
    Recibe el medidor.
    tarifa_id = Identificar de las tarifas de un mes
    tipo_tarifa = Tarifa que tiene contratada (HM, OM...)

    """
    tarifaObj = ElectricRatesDetail.objects.get(id=tarifa_id)

    fecha_inicio = str(tarifaObj.date_init) + " 00:00:00"
    fecha_fin = str(tarifaObj.date_end) + " 23:59:59"
    lecturasObj = ElectricDataTemp.objects.filter(
        profile_powermeter=pr_powermeter,
        medition_date__range=(fecha_inicio, fecha_fin)).order_by(
        'medition_date')

    catalogo_grupos = obtenerCatalogoGrupos();

    demanda_base = []
    demanda_intermedio = []
    demanda_punta = []

    valores_periodo = {}

    if lecturasObj:
        for lectura in lecturasObj:
            tipo_periodo = obtenerTipoPeriodo(lectura.medition_date, region,
                                              tipo_tarifa, catalogo_grupos)
            if tipo_periodo == 'base':
                demanda_base.append(lectura.kW)
            elif tipo_periodo == 'intermedio':
                demanda_intermedio.append(lectura.kW)
            elif tipo_periodo == 'punta':
                demanda_punta.append(lectura.kW)

        valores_periodo['base'] = obtenerDemanda(demanda_base)
        valores_periodo['intermedio'] = obtenerDemanda(demanda_intermedio)
        valores_periodo['punta'] = obtenerDemanda(demanda_punta)
    else:
        valores_periodo['base'] = 0
        valores_periodo['intermedio'] = 0
        valores_periodo['punta'] = 0

    return valores_periodo


def obtenerKWhNetosTarifa(pr_powermeter, tarifa_id):
    tarifaObj = ElectricRatesDetail.objects.get(id=tarifa_id)
    fecha_inicio = str(tarifaObj.date_init) + " 00:00:00"
    fecha_fin = str(tarifaObj.date_end) + " 23:59:59"

    kwh_netos = 0
    lecturasObj = ElectricDataTemp.objects.filter(
        profile_powermeter=pr_powermeter,
        medition_date__range=(fecha_inicio, fecha_fin)).order_by(
        'medition_date')
    if lecturasObj:
        total_lecturas = len(lecturasObj)
        kwh_inicial = lecturasObj[0].TotalkWhIMPORT
        kwh_final = lecturasObj[total_lecturas - 1].TotalkWhIMPORT
        kwh_netos = kwh_final - kwh_inicial

    return kwh_netos


def obtenerKWhTarifa(pr_powermeter, tarifa_id, region, tarifa_hm):
    """
    Recibe el medidor.
    tarifa_id = Identificar de las tarifas de un mes
    tipo_tarifa = Tarifa que tiene contratada (HM, OM...)

    """
    tarifaObj = ElectricRatesDetail.objects.get(id=tarifa_id)

    fecha_inicio = str(tarifaObj.date_init) + " 00:00:00"
    fecha_fin = str(tarifaObj.date_end) + " 23:59:59"
    lecturasObj = ElectricDataTemp.objects.filter(
        profile_powermeter=pr_powermeter,
        medition_date__range=(fecha_inicio, fecha_fin)).order_by(
        'medition_date')

    catalogo_grupos = obtenerCatalogoGrupos();

    kwh_base = []
    kwh_intermedio = []
    kwh_punta = []

    valores_kwh = {}
    valores_kwh['base'] = 0
    valores_kwh['intermedio'] = 0
    valores_kwh['punta'] = 0

    tipo_tarifa_global = None
    kwh_primero = None
    kwh_ultimo = None

    if lecturasObj:
        for lectura in lecturasObj:
            tipo_tarifa_actual = obtenerTipoPeriodo(lectura.medition_date,
                                                    region, tarifa_hm,
                                                    catalogo_grupos)

            if not tipo_tarifa_global:
                tipo_tarifa_global = tipo_tarifa_actual

            #Primer Lectura
            if not kwh_primero:
                kwh_primero = lectura.TotalkWhIMPORT
            kwh_ultimo = lectura.TotalkWhIMPORT

            if tipo_tarifa_global != tipo_tarifa_actual:
                kwh_netos = kwh_ultimo - kwh_primero

                if tipo_tarifa_global == 'base':
                    kwh_base.append(kwh_netos)
                    valores_kwh['base'] += kwh_netos
                elif tipo_tarifa_global == 'intermedio':
                    kwh_intermedio.append(kwh_netos)
                    valores_kwh['intermedio'] += kwh_netos
                elif tipo_tarifa_global == 'punta':
                    kwh_punta.append(kwh_netos)
                    valores_kwh['punta'] += kwh_netos

                kwh_primero = kwh_ultimo
                tipo_tarifa_global = tipo_tarifa_actual

        kwh_netos = kwh_ultimo - kwh_primero

        if tipo_tarifa_global == 'base':
            kwh_base.append(kwh_netos)
            valores_kwh['base'] += kwh_netos
        elif tipo_tarifa_global == 'intermedio':
            kwh_intermedio.append(kwh_netos)
            valores_kwh['intermedio'] += kwh_netos
        elif tipo_tarifa_global == 'punta':
            kwh_punta.append(kwh_netos)
            valores_kwh['punta'] += kwh_netos
    else:
        valores_kwh['base'] = 0
        valores_kwh['intermedio'] = 0
        valores_kwh['punta'] = 0

    return valores_kwh


def obtenerKVARHTarifa(pr_powermeter, tarifa_id):
    tarifaObj = ElectricRatesDetail.objects.get(id=tarifa_id)
    fecha_inicio = str(tarifaObj.date_init) + " 00:00:00"
    fecha_fin = str(tarifaObj.date_end) + " 23:59:59"

    kvarh_netos = 0
    lecturasObj = ElectricDataTemp.objects.filter(
        profile_powermeter=pr_powermeter,
        medition_date__range=(fecha_inicio, fecha_fin)).order_by(
        'medition_date')
    if lecturasObj:
        total_lecturas = len(lecturasObj)
        kvarh_inicial = lecturasObj[0].TotalkvarhIMPORT
        kvarh_final = lecturasObj[total_lecturas - 1].TotalkvarhIMPORT
        kvarh_netos = kvarh_final - kvarh_inicial

    return kvarh_netos


def obtenerKVARH_total(pr_powermeter, start_date, end_date):
    kvarh_netos = 0
    lecturasObj = ElectricDataTemp.objects.filter(
        profile_powermeter__powermeter=pr_powermeter,
        medition_date__gte=start_date,
        medition_date__lte=end_date).order_by('medition_date')
    if lecturasObj:
        total_lecturas = len(lecturasObj)
        kvarh_inicial = lecturasObj[0].TotalkvarhIMPORT
        kvarh_final = lecturasObj[total_lecturas - 1].TotalkvarhIMPORT
        kvarh_netos = kvarh_final - kvarh_inicial

    return int(ceil(kvarh_netos))


def obtenerFPTarifa(pr_powermeter, tarifa_id):
    kvarh = obtenerKVARHTarifa(pr_powermeter, tarifa_id)
    kwh = obtenerKWhNetosTarifa(pr_powermeter, tarifa_id)
    return factorpotencia(kwh, kvarh)


def obtenerDemandaMaximaTarifa(pr_powermeter, tarifa_id):
    tarifaObj = ElectricRatesDetail.objects.get(id=tarifa_id)
    fecha_inicio = str(tarifaObj.date_init) + " 00:00:00"
    fecha_fin = str(tarifaObj.date_end) + " 23:59:59"

    lecturasObj = ElectricRateForElectricData.objects.filter(
        electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk) \
        .filter(
        electric_data__medition_date__range=(fecha_inicio, fecha_fin)).order_by(
        'electric_data__medition_date')

    return obtenerDemanda_kw(lecturasObj)


def obtenerFactorCargaTarifa(pr_powermeter, tarifa_id):
    factor_carga = 0

    tarifaObj = ElectricRatesDetail.objects.get(id=tarifa_id)
    m_range = monthrange(tarifaObj.date_init.year, tarifaObj.date_init.month)
    num_dias = m_range[1]
    num_horas = 24 * num_dias
    demanda_maxima = obtenerDemandaMaximaTarifa(pr_powermeter, tarifa_id)
    energia_consumida = obtenerKWhNetosTarifa(pr_powermeter, tarifa_id)

    if demanda_maxima != 0 and energia_consumida != 0:
        factor_carga = (energia_consumida / (demanda_maxima * num_horas)) * 100

    return factor_carga


def obtenerCostoPromedioKWH(tarifa_id):
    costo = 0
    tarifaObj = ElectricRatesDetail.objects.get(id=tarifa_id)
    costo = (tarifaObj.KWHB + tarifaObj.KWHI + tarifaObj.KWHP) / Decimal(
        str(3.0))
    return costo


def obtenerHistorico(pr_powermeter, tarifa_id, region, num_meses, tipo_tarifa):
    arr_historico = []

    tarifaObj = ElectricRatesDetail.objects.get(id=tarifa_id)
    fecha_fin = tarifaObj.date_init
    fecha_inicio = fecha_fin + relativedelta(months=-num_meses)

    tarifasPeriodo = ElectricRatesDetail.objects.filter(region=region).filter(
        date_init__range=(fecha_inicio, fecha_fin)).order_by('date_init')
    for tarifaPer in tarifasPeriodo:
        dict_periodo = {}
        dict_periodo["fecha"] = tarifaPer.date_init
        dict_kw = obtenerKWTarifa(pr_powermeter, tarifaPer.id)
        dict_periodo["kw_base"] = dict_kw['base']
        dict_periodo["kw_intermedio"] = dict_kw['intermedio']
        dict_periodo["kw_punta"] = dict_kw['punta']
        dict_periodo["demanda_maxima"] = obtenerDemandaMaximaTarifa(
            pr_powermeter, tarifaPer.id)
        dict_periodo["total_kwh"] = obtenerKWhNetosTarifa(pr_powermeter,
                                                          tarifaPer.id)
        dict_periodo["kvarh"] = obtenerKVARHTarifa(pr_powermeter, tarifaPer.id)
        dict_periodo["factor_potencia"] = factorpotencia(
            dict_periodo["total_kwh"],
            obtenerKVARHTarifa(pr_powermeter, tarifaPer.id))
        dict_periodo["factor_carga"] = obtenerFactorCargaTarifa(pr_powermeter,
                                                                tarifaPer.id)
        dict_periodo["costo_promedio"] = obtenerCostoPromedioKWH(tarifaPer.id)

        arr_historico.append(dict_periodo)

    return arr_historico


def obtenerDemanda_kw(lecturas_kw):
    demanda_maxima = 0
    if lecturas_kw:
        try:
            longitud = len(lecturas_kw)
            if longitud >= 3:
                low = lecturas_kw[0].electric_data.kW
                middle = lecturas_kw[1].electric_data.kW
                high = lecturas_kw[2].electric_data.kW
                demanda_maxima = (low + middle + high) / 3
                for indice in range(3, longitud):
                    low, middle = middle, high
                    high = lecturas_kw[indice].electric_data.kW
                    prom = (low + middle + high) / 3
                    if prom > demanda_maxima:
                        demanda_maxima = prom
            else:
                demanda_maxima = 0

        except IndexError:
            print "IndexError"
            demanda_maxima = 0
        except TypeError:
            print "TypeError"
            demanda_maxima = 0
    return int(ceil(demanda_maxima))


def obtenerDemandaMin_kw(lecturas_kw):
    demanda_min = 0
    if lecturas_kw:
        try:
            longitud = len(lecturas_kw)
            if longitud >= 3:
                low = lecturas_kw[0].electric_data.kW
                middle = lecturas_kw[1].electric_data.kW
                high = lecturas_kw[2].electric_data.kW
                demanda_min = (low + middle + high) / 3
                for indice in range(3, longitud):
                    low, middle = middle, high
                    high = lecturas_kw[indice].electric_data.kW
                    prom = (low + middle + high) / 3
                    if prom < demanda_min:
                        demanda_min = prom
            else:
                demanda_min = 0

        except IndexError:
            print "IndexError"
            demanda_min = 0
        except TypeError:
            print "TypeError"
            demanda_min = 0
    return int(ceil(demanda_min))


def getMonths(start_date, end_date):
    dt1 = time.strptime(start_date, "%Y-%m-%d %H:%M:%S")
    dt2 = time.strptime(end_date, "%Y-%m-%d %H:%M:%S")
    start_month = dt1.tm_mon
    end_months = (dt2.tm_year - dt1.tm_year) * 12 + dt2.tm_mon + 1
    dates = [datetime.datetime(year=yr, month=mn, day=1) for (yr, mn) in (
        ((m - 1) / 12 + dt1.tm_year, (m - 1) % 12 + 1) for m in range(
        start_month, end_months)
    )]

    final_months = []
    b_inicio = True
    for idx, dt in enumerate(dates):
        days_m = monthrange(dt.year, dt.month)
        days_m[1]
        if idx == 0:
            s_m = start_date
            b_inicio = False
        else:
            s_m = str(dt.year) + "-" + str(dt.month) + "-01 00:00:00"
        if idx == len(dates) - 1:
            e_m = end_date
        else:
            e_m = str(dt.year) + "-" + str(dt.month) + "-" + str(
                days_m[1]) + " 23:59:59"
        t = s_m, e_m
        final_months.append(t)

    return final_months


def tarifaHM_mensual(pr_powermeter, start_date, end_date, region_id,
                     tarifa_HM_id):
    #Guardará los diccionarios con los totales por mes.
    arr_mensual = []

    demanda_facturable_total = 0
    factor_potencia_total = 0
    costo_energia_total = 0
    costo_demanda_facturable = 0
    costo_factor_potencia = 0
    subtotal_final = 0
    total_final = 0

    kwh_base_totales = 0
    kwh_intermedio_totales = 0
    kwh_punta_totales = 0
    kwh_totales = 0

    kvarh_totales = 0

    tarifa_kwh_base = 0
    tarifa_kwh_intermedio = 0
    tarifa_kwh_punta = 0

    historico = False

    months = getMonths(start_date, end_date)

    ultima_tarifa = 0

    fecha_hoy = datetime.datetime.now()
    f01 = start_date.split(" ")
    f02 = f01[0].split("-")
    fecha_mes = datetime.datetime(year=int(f02[0]), month=int(f02[1]),
                                  day=int(f02[2]))

    if fecha_mes < fecha_hoy:
        for m in months:
            historico = True

            kw_base_t = 0
            kw_intermedio_t = 0
            kw_punta_t = 0
            kwh_base_t = 0
            kwh_intermedio_t = 0
            kwh_punta_t = 0
            kwh_totales_mes = 0

            #Diccionario que guarda los totales por mes
            dict_mes = {}
            lecturas_base = ElectricRateForElectricData.objects.filter(
                electric_data__profile_powermeter__powermeter__pk
                =pr_powermeter.pk).filter(
                electric_data__medition_date__range=(m[0], m[1])).filter(
                electric_rates_periods__period_type='base').order_by(
                'electric_data__medition_date')
            kw_base_t = obtenerDemanda_kw(lecturas_base)
            dict_mes["kw_base"] = kw_base_t

            lecturas_intermedio = ElectricRateForElectricData.objects.filter(
                electric_data__profile_powermeter__powermeter__pk
                =pr_powermeter.pk).filter(
                electric_data__medition_date__range=(m[0], m[1])).filter(
                electric_rates_periods__period_type='intermedio').order_by(
                'electric_data__medition_date')
            kw_intermedio_t = obtenerDemanda_kw(lecturas_intermedio)
            dict_mes["kw_intermedio"] = kw_intermedio_t

            lecturas_punta = ElectricRateForElectricData.objects.filter(
                electric_data__profile_powermeter__powermeter__pk
                =pr_powermeter.pk).filter(
                electric_data__medition_date__range=(m[0], m[1])).filter(
                electric_rates_periods__period_type='punta').order_by(
                'electric_data__medition_date')
            kw_punta_t = obtenerDemanda_kw(lecturas_punta)
            dict_mes["kw_punta"] = kw_punta_t

            lecturas_identificadores = ElectricRateForElectricData.objects \
                .filter(
                electric_data__profile_powermeter__powermeter__pk
                =pr_powermeter.pk). \
                filter(electric_data__medition_date__range=(m[0], m[1])). \
                order_by("electric_data__medition_date").values(
                "identifier").annotate(Count("identifier"))

            ultima_lectura = 0
            kwh_por_periodo = []

            for lectura in lecturas_identificadores:
                electric_info = ElectricRateForElectricData.objects.filter(
                    identifier=lectura["identifier"]). \
                    filter(
                    electric_data__profile_powermeter__powermeter__pk
                    =pr_powermeter.pk). \
                    filter(electric_data__medition_date__range=(m[0], m[1])). \
                    order_by("electric_data__medition_date")

                num_lecturas = len(electric_info)
                #print "Num Lecturas:",num_lecturas
                primer_lectura = electric_info[0].electric_data.TotalkWhIMPORT
                ultima_lectura = electric_info[
                    num_lecturas - 1].electric_data.TotalkWhIMPORT
                #print "Primer:",primer_lectura
                #print "Ultima:",ultima_lectura

                #Obtener el tipo de periodo: Base, punta, intermedio
                tipo_periodo = electric_info[
                    0].electric_rates_periods.period_type
                t = primer_lectura, tipo_periodo
                kwh_por_periodo.append(t)

            kwh_periodo_long = len(kwh_por_periodo)

            for idx, kwh_p in enumerate(kwh_por_periodo):
                print "Veamos:", kwh_p
                inicial = kwh_p[0]
                periodo = kwh_p[1]
                if idx + 1 <= kwh_periodo_long - 1:
                    kwh_p2 = kwh_por_periodo[idx + 1]
                    final = kwh_p2[0]
                else:
                    final = ultima_lectura

                kwh_netos = final - inicial

                if periodo == 'base':
                    kwh_base_t += kwh_netos
                elif periodo == 'intermedio':
                    kwh_intermedio_t += kwh_netos
                elif periodo == 'punta':
                    kwh_punta_t += kwh_netos

            kwh_base_t = int(ceil(kwh_base_t))
            dict_mes["kwh_base"] = kwh_base_t

            kwh_intermedio_t = int(ceil(kwh_intermedio_t))
            dict_mes["kwh_intermedio"] = kwh_intermedio_t

            kwh_punta_t = int(ceil(ceil(kwh_punta_t)))
            dict_mes["kwh_punta"] = kwh_punta_t

            kwh_totales_mes = kwh_base_t + kwh_intermedio_t + kwh_punta_t
            dict_mes["kwh_totales"] = kwh_totales_mes

            kwh_base_totales += kwh_base_t
            kwh_intermedio_totales += kwh_intermedio_t
            kwh_punta_totales += kwh_punta_t

            kwh_totales += kwh_totales_mes

            fecha_mes = time.strptime(m[0], "%Y-%m-%d %H:%M:%S")

            #Obtiene el id de la tarifa correspondiente para el mes en cuestion
            tarifasObj = ElectricRatesDetail.objects.filter(
                electric_rate=tarifa_HM_id).filter(region=region_id).filter(
                date_init__lte=datetime.date(fecha_mes.tm_year,
                                             fecha_mes.tm_mon,
                                             fecha_mes.tm_mday)).filter(
                date_end__gte=datetime.date(fecha_mes.tm_year, fecha_mes.tm_mon,
                                            fecha_mes.tm_mday))

            tarifa_id = tarifasObj[0].id
            ultima_tarifa = tarifa_id

            dict_mes["tarifa_kwhb"] = tarifasObj[0].KWHB
            tarifa_kwh_base += tarifasObj[0].KWHB

            dict_mes["tarifa_kwhi"] = tarifasObj[0].KWHI
            tarifa_kwh_intermedio += tarifasObj[0].KWHI

            dict_mes["tarifa_kwhp"] = tarifasObj[0].KWHP
            tarifa_kwh_punta += tarifasObj[0].KWHP

            dict_mes["tarifa_df"] = tarifasObj[0].KDF


            #Demanda Facturable
            df_t = demandafacturable_tarifa(kw_base_t, kw_intermedio_t,
                                            kw_punta_t, tarifa_id)
            dict_mes["demanda_facturable"] = df_t

            demanda_facturable_total += df_t

            #KVarh
            kvarh_t = obtenerKVARHTarifa(pr_powermeter, tarifa_id)
            dict_mes["kvarh"] = kvarh_t

            kvarh_totales += kvarh_t

            #Factor de Potencia
            fp = factorpotencia(kwh_totales_mes, kvarh_t)
            dict_mes["factor_pt"] = fp
            factor_potencia_total += fp

            #Costo Energía
            c_energia = costoenergia_tarifa(kwh_base_t, kwh_intermedio_t,
                                            kwh_punta_t, tarifa_id)
            dict_mes["c_energia"] = c_energia
            costo_energia_total += c_energia

            #Costo Demanda Facturable
            c_df_t = costodemandafacturable_tarifa(df_t, tarifa_id)
            dict_mes["c_df"] = c_df_t
            costo_demanda_facturable += c_df_t

            #Costo Factor Potencia
            c_factorpotencia = costofactorpotencia(fp, c_energia, c_df_t)
            dict_mes["c_fp"] = c_factorpotencia
            costo_factor_potencia += c_factorpotencia

            #Subtotal
            c_subtotal = obtenerSubtotal(c_energia, c_df_t, c_factorpotencia)
            dict_mes["subtotal"] = c_subtotal
            subtotal_final += c_subtotal

            #Total
            c_total = obtenerTotal(c_subtotal, 16)
            dict_mes["total"] = c_total
            total_final += c_total

            arr_mensual.append(dict_mes)

    diccionario_final_cfe = {}
    diccionario_final_cfe['costo_energia'] = costo_energia_total
    diccionario_final_cfe['costo_dfacturable'] = costo_demanda_facturable
    diccionario_final_cfe['costo_fpotencia'] = costo_factor_potencia
    diccionario_final_cfe['subtotal'] = subtotal_final
    diccionario_final_cfe['iva'] = obtenerIva(subtotal_final, 16)
    diccionario_final_cfe['total'] = total_final
    diccionario_final_cfe['meses'] = arr_mensual
    diccionario_final_cfe['ultima_tarifa'] = ultima_tarifa
    diccionario_final_cfe['historico'] = historico

    """
    diccionario_final_cfe['kw_base'] = KW_BASES_TOTALES
    diccionario_final_cfe['kw_intermedio'] = KW_INTERMEDIO_TOTALES
    diccionario_final_cfe['kw_punta'] = KW_PUNTA_TOTALES
    diccionario_final_cfe['kwh_totales'] = kwh_totales
    diccionario_final_cfe['kvarh_totales'] = kvarh_totales
    diccionario_final_cfe['kwh_base'] = kwh_base_totales
    diccionario_final_cfe['kwh_intermedio'] = kwh_intermedio_totales
    diccionario_final_cfe['kwh_punta'] = kwh_punta_totales
    diccionario_final_cfe['demanda_facturable'] = demanda_facturable_total
    diccionario_final_cfe['factor_potencia'] =
    factor_potencia_total/numero_tarifas
    diccionario_final_cfe['tarifa_kwhb'] = tarifa_kwh_base/numero_tarifas
    diccionario_final_cfe['tarifa_kwhi'] = tarifa_kwh_intermedio/numero_tarifas
    diccionario_final_cfe['tarifa_kwhp'] = tarifa_kwh_punta/numero_tarifas
    """

    return diccionario_final_cfe


def tarifaHM_total(pr_powermeter, start_date, end_date, region_id,
                   tarifa_HM_id):
    demanda_facturable_total = 0
    factor_potencia_total = 0
    costo_energia_total = 0
    costo_demanda_facturable = 0
    costo_factor_potencia = 0
    subtotal_final = 0
    total_final = 0

    kw_totales = 0
    kw_base_totales = 0
    kw_intermedio_totales = 0
    kw_punta_totales = 0
    kwh_base_totales = 0
    kwh_intermedio_totales = 0
    kwh_punta_totales = 0
    kwh_totales = 0

    kvarh_totales = 0

    tarifa_kwh_base = 0
    tarifa_kwh_intermedio = 0
    tarifa_kwh_punta = 0

    months = getMonths(start_date, end_date)
    numero_tarifas = len(months)

    lecturas_base = ElectricRateForElectricData.objects.filter(
        electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk) \
        .filter(
        electric_data__medition_date__range=(start_date, end_date)).filter(
        electric_rates_periods__period_type='base').order_by(
        'electric_data__medition_date')
    kw_base_totales = obtenerDemanda_kw(lecturas_base)

    lecturas_intermedio = ElectricRateForElectricData.objects.filter(
        electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk) \
        .filter(
        electric_data__medition_date__range=(start_date, end_date)).filter(
        electric_rates_periods__period_type='intermedio').order_by(
        'electric_data__medition_date')
    kw_intermedio_totales = obtenerDemanda_kw(lecturas_intermedio)

    lecturas_punta = ElectricRateForElectricData.objects.filter(
        electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk) \
        .filter(
        electric_data__medition_date__range=(start_date, end_date)).filter(
        electric_rates_periods__period_type='punta').order_by(
        'electric_data__medition_date')
    kw_punta_totales = obtenerDemanda_kw(lecturas_punta)

    lecturas_identificadores = ElectricRateForElectricData.objects.filter(
        electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk). \
        filter(electric_data__medition_date__range=(start_date, end_date)). \
        order_by("electric_data__medition_date").values("identifier").annotate(
        Count("identifier"))

    ultima_lectura = 0
    kwh_por_periodo = []

    for lectura in lecturas_identificadores:
        electric_info = ElectricRateForElectricData.objects.filter(
            identifier=lectura["identifier"]). \
            filter(
            electric_data__profile_powermeter__powermeter__pk=pr_powermeter
            .pk). \
            order_by("electric_data__medition_date")

        num_lecturas = len(electric_info)
        primer_lectura = electric_info[0].electric_data.TotalkWhIMPORT
        ultima_lectura = electric_info[
            num_lecturas - 1].electric_data.TotalkWhIMPORT

        #Obtener el tipo de periodo: Base, punta, intermedio
        tipo_periodo = electric_info[0].electric_rates_periods.period_type
        t = primer_lectura, tipo_periodo
        kwh_por_periodo.append(t)

    kwh_periodo_long = len(kwh_por_periodo)

    for idx, kwh_p in enumerate(kwh_por_periodo):
        inicial = kwh_p[0]
        periodo = kwh_p[1]
        if idx + 1 <= kwh_periodo_long - 1:
            kwh_p2 = kwh_por_periodo[idx + 1]
            final = kwh_p2[0]
        else:
            final = ultima_lectura

        kwh_netos = final - inicial

        if periodo == 'base':
            kwh_base_totales += kwh_netos
        elif periodo == 'intermedio':
            kwh_intermedio_totales += kwh_netos
        elif periodo == 'punta':
            kwh_punta_totales += kwh_netos

    kwh_totales = kwh_base_totales + kwh_intermedio_totales + kwh_punta_totales

    #Se obtienen los promedios de las tarifas

    t_df = 0
    t_kwhb = 0
    t_kwhi = 0
    t_kwhp = 0
    t_fri = 0
    t_frb = 0
    ultima_tarifa = None

    for m in months:
        fecha_mes = time.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        #Obtiene el id de la tarifa correspondiente para el mes en cuestion
        tarifasObj = ElectricRatesDetail.objects.filter(
            electric_rate=tarifa_HM_id).filter(region=region_id).filter(
            date_init__lte=datetime.date(fecha_mes.tm_year, fecha_mes.tm_mon,
                                         fecha_mes.tm_mday)).filter(
            date_end__gte=datetime.date(fecha_mes.tm_year, fecha_mes.tm_mon,
                                        fecha_mes.tm_mday))

        ultima_tarifa = tarifasObj[0].id

        t_df += tarifasObj[0].KDF
        t_kwhb += tarifasObj[0].KWHB
        t_kwhi += tarifasObj[0].KWHI
        t_kwhp += tarifasObj[0].KWHP
        t_fri += tarifasObj[0].FRI
        t_frb += tarifasObj[0].FRB

    t_df += t_df / numero_tarifas
    t_kwhb += t_kwhb / numero_tarifas
    t_kwhi += t_kwhi / numero_tarifas
    t_kwhp += t_kwhp / numero_tarifas
    t_fri += t_fri / numero_tarifas
    t_frb += t_frb / numero_tarifas

    #Demanda Facturable
    demanda_facturable_total = demandafacturable_total(kw_base_totales,
                                                       kw_intermedio_totales,
                                                       kw_punta_totales, t_fri,
                                                       t_frb)

    #KVarh
    kvarh_totales = obtenerKVARH_total(pr_powermeter, start_date, end_date)

    #Factor de Potencia
    factor_potencia_total = factorpotencia(kwh_totales, kvarh_totales)

    #Costo Energía
    costo_energia_total = costoenergia_total(kwh_base_totales,
                                             kwh_intermedio_totales,
                                             kwh_punta_totales, t_kwhb, t_kwhi,
                                             t_kwhp)

    #Costo Demanda Facturable
    costo_demanda_facturable = costodemandafacturable_total(
        demanda_facturable_total, t_df)

    #Costo Factor Potencia
    costo_factor_potencia = costofactorpotencia(factor_potencia_total,
                                                costo_energia_total,
                                                costo_demanda_facturable)

    #Subtotal
    subtotal_final = obtenerSubtotal(costo_energia_total,
                                     costo_demanda_facturable,
                                     costo_factor_potencia)

    #Total
    total_final = obtenerTotal(subtotal_final, 16)

    diccionario_final_cfe = {}
    diccionario_final_cfe['costo_energia'] = costo_energia_total
    diccionario_final_cfe['costo_dfacturable'] = costo_demanda_facturable
    diccionario_final_cfe['costo_fpotencia'] = costo_factor_potencia
    diccionario_final_cfe['subtotal'] = subtotal_final
    diccionario_final_cfe['iva'] = obtenerIva(subtotal_final, 16)
    diccionario_final_cfe['total'] = total_final
    diccionario_final_cfe['kw_base'] = kw_base_totales
    diccionario_final_cfe['kw_intermedio'] = kw_intermedio_totales
    diccionario_final_cfe['kw_punta'] = kw_punta_totales
    diccionario_final_cfe['kwh_totales'] = kwh_totales
    diccionario_final_cfe['kvarh_totales'] = kvarh_totales
    diccionario_final_cfe['kwh_base'] = kwh_base_totales
    diccionario_final_cfe['kwh_intermedio'] = kwh_intermedio_totales
    diccionario_final_cfe['kwh_punta'] = kwh_punta_totales
    diccionario_final_cfe['demanda_facturable'] = demanda_facturable_total
    diccionario_final_cfe['factor_potencia'] = factor_potencia_total
    diccionario_final_cfe['tarifa_kwhb'] = t_kwhb
    diccionario_final_cfe['tarifa_kwhi'] = t_kwhi
    diccionario_final_cfe['tarifa_kwhp'] = t_kwhp
    diccionario_final_cfe['tarifa_df'] = t_df
    diccionario_final_cfe['ultima_tarifa'] = ultima_tarifa

    return diccionario_final_cfe


def tarifaHM(building, pr_powermeter, month, year):
    status = 'OK'
    diccionario_final_cfe = {}
    diccionario_final_cfe['status'] = status

    demanda_facturable_total = 0
    factor_potencia_total = 0
    costo_energia_total = 0
    costo_demanda_facturable = 0
    costo_factor_potencia = 0
    subtotal_final = 0
    total_final = 0

    kw_totales = 0
    kw_base_totales = 0
    kw_intermedio_totales = 0
    kw_punta_totales = 0
    kwh_base_totales = 0
    kwh_intermedio_totales = 0
    kwh_punta_totales = 0
    kwh_totales = 0

    kvarh_totales = 0

    tarifa_kwh_base = 0
    tarifa_kwh_intermedio = 0
    tarifa_kwh_punta = 0
    tarifa_fri = 0
    tarifa_frb = 0
    tarifa_demanda_facturable = 0

    kwh_base_t = 0
    kwh_intermedio_t = 0
    kwh_punta_t = 0

    #Se obtiene la región
    region = building.region
    #Se obtiene el tipo de tarifa (HM)
    hm_id = building.electric_rate

    billing_month = datetime.date(year=year, month=month, day=1)
    try:
        month_cut_dates = MonthlyCutDates.objects.get(building=building,
                                                      billing_month=billing_month)
    except MonthlyCutDates.DoesNotExist:
        mensaje = "La fecha de corte para este mes no está definida"
        status = 'ERROR'
        diccionario_final_cfe['mensaje'] = mensaje
        diccionario_final_cfe['status'] = status
    else:
        s_date = datetime.datetime(year=month_cut_dates.date_init.year,
                                   month=month_cut_dates.date_init.month,
                                   day=month_cut_dates.date_init.day,
                                   hour=0, minute=0, second=0,
                                   tzinfo=timezone.get_current_timezone()
        )

        #Si la fecha de fin no es nula
        if month_cut_dates.date_end:
            e_date = datetime.datetime(year=month_cut_dates.date_end.year,
                                       month=month_cut_dates.date_end.month,
                                       day=month_cut_dates.date_end.day,
                                       hour=0, minute=0, second=0,
                                       tzinfo=timezone.get_current_timezone()
            )
        else: #Si la fecha de fin es nula, se toma el dia de hoy
            e_date = datetime.datetime.today().replace(hour=0, minute=0,
                                                       second=0,
                                                       tzinfo=timezone.get_current_timezone())
            billing_month = e_date

        print "Fecha Inicial:", s_date, " - Fecha Final:", e_date
        periodo = str(s_date.day) + '/' + str(s_date.month) + "/" + str(
            s_date.year) + " - " + str(e_date.day) + '/' + str(
            e_date.month) + "/" + str(e_date.year)

        #Se obtienen directamente los kw Base, Intermedio y Punta.
        dict_mes = {}
        lecturas_base = ElectricRateForElectricData.objects.filter(
            electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk).filter(
            electric_data__medition_date__range=(s_date, e_date)).filter(
            electric_rates_periods__period_type='base').order_by(
            'electric_data__medition_date')
        kw_base_t = obtenerDemanda_kw(lecturas_base)
        diccionario_final_cfe["kw_base"] = kw_base_t

        lecturas_intermedio = ElectricRateForElectricData.objects.filter(
            electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk).filter(
            electric_data__medition_date__range=(s_date, e_date)).filter(
            electric_rates_periods__period_type='intermedio').order_by(
            'electric_data__medition_date')
        kw_intermedio_t = obtenerDemanda_kw(lecturas_intermedio)
        diccionario_final_cfe["kw_intermedio"] = kw_intermedio_t

        lecturas_punta = ElectricRateForElectricData.objects.filter(
            electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk).filter(
            electric_data__medition_date__range=(s_date, e_date)).filter(
            electric_rates_periods__period_type='punta').order_by(
            'electric_data__medition_date')
        kw_punta_t = obtenerDemanda_kw(lecturas_punta)
        diccionario_final_cfe["kw_punta"] = kw_punta_t

        #Se obtienen todos los identificadores para los KWH
        lecturas_identificadores = ElectricRateForElectricData.objects.filter(
            electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk). \
            filter(electric_data__medition_date__range=(s_date, e_date)). \
            order_by("electric_data__medition_date").values("identifier").annotate(
            Count("identifier"))

        ultima_lectura = 0
        kwh_por_periodo = []

        for lectura in lecturas_identificadores:
            electric_info = ElectricRateForElectricData.objects.filter(
                identifier=lectura["identifier"]). \
                filter(
                electric_data__profile_powermeter__powermeter__pk=pr_powermeter.pk). \
                filter(electric_data__medition_date__range=(s_date, e_date)). \
                order_by("electric_data__medition_date")

            num_lecturas = len(electric_info)
            primer_lectura = electric_info[0].electric_data.TotalkWhIMPORT
            ultima_lectura = electric_info[
                num_lecturas - 1].electric_data.TotalkWhIMPORT
            #print electric_info[0].electric_data.pk,"Primer Lectura:",primer_lectura,"-",electric_info[num_lecturas-1].electric_data.pk," Ultima Lectura:",ultima_lectura

            #Obtener el tipo de periodo: Base, punta, intermedio
            tipo_periodo = electric_info[0].electric_rates_periods.period_type
            t = primer_lectura, tipo_periodo
            kwh_por_periodo.append(t)

        kwh_periodo_long = len(kwh_por_periodo)

        for idx, kwh_p in enumerate(kwh_por_periodo):
            #print "Lectura:", kwh_p[0], "-:",kwh_p[1]
            inicial = kwh_p[0]
            periodo = kwh_p[1]
            if idx + 1 <= kwh_periodo_long - 1:
                kwh_p2 = kwh_por_periodo[idx + 1]
                final = kwh_p2[0]
            else:
                final = ultima_lectura

            kwh_netos = final - inicial
            #print "Inicial:",inicial,"Final:",final, "Netos:",kwh_netos

            if periodo == 'base':
                kwh_base_t += kwh_netos
            elif periodo == 'intermedio':
                kwh_intermedio_t += kwh_netos
            elif periodo == 'punta':
                kwh_punta_t += kwh_netos

        kwh_base_t = int(ceil(kwh_base_t))
        diccionario_final_cfe["kwh_base"] = kwh_base_t

        kwh_intermedio_t = int(ceil(kwh_intermedio_t))
        diccionario_final_cfe["kwh_intermedio"] = kwh_intermedio_t

        kwh_punta_t = int(ceil(ceil(kwh_punta_t)))
        diccionario_final_cfe["kwh_punta"] = kwh_punta_t

        kwh_totales = kwh_base_t + kwh_intermedio_t + kwh_punta_t
        diccionario_final_cfe["kwh_totales"] = kwh_totales

        #Obtiene el id de la tarifa correspondiente para el mes en cuestion
        tarifasObj = ElectricRatesDetail.objects.filter(
            electric_rate=hm_id).filter(region=region).filter(
            date_init__lte=billing_month).filter(date_end__gte=billing_month)
        if tarifasObj:
            tarifa_kwh_base = tarifasObj[0].KWHB
            tarifa_kwh_intermedio = tarifasObj[0].KWHI
            tarifa_kwh_punta = tarifasObj[0].KWHP
            tarifa_fri = tarifasObj[0].FRI
            tarifa_frb = tarifasObj[0].FRB
            tarifa_demanda_facturable = tarifasObj[0].KDF

        print "Tarifa:", tarifasObj

        print "kwh_base:", diccionario_final_cfe["kwh_base"]
        print "kwh_intermedio:", diccionario_final_cfe["kwh_intermedio"]
        print "kwh_punta:", diccionario_final_cfe["kwh_punta"]
        print "kwh Totales:", diccionario_final_cfe["kwh_totales"]

        #Demanda Facturable
        df_t = demandafacturable(kw_base_t, kw_intermedio_t, kw_punta_t,
                                 tarifa_fri, tarifa_frb)

        #KVarh
        kvarh_totales = obtenerKVARH_total(pr_powermeter, s_date, e_date)

        #Factor de Potencia
        factor_potencia_total = factorpotencia(kwh_totales, kvarh_totales)

        #Costo Energía
        costo_energia_total = costoenergia(kwh_base_t, kwh_intermedio_t,
                                           kwh_punta_t, tarifa_kwh_base,
                                           tarifa_kwh_intermedio,
                                           tarifa_kwh_punta)

        #Costo Demanda Facturable
        costo_demanda_facturable = costodemandafacturable(df_t,
                                                          tarifa_demanda_facturable)

        #Costo Factor Potencia
        costo_factor_potencia = costofactorpotencia(factor_potencia_total,
                                                    costo_energia_total,
                                                    costo_demanda_facturable)

        #Subtotal
        subtotal_final = obtenerSubtotal(costo_energia_total,
                                         costo_demanda_facturable,
                                         costo_factor_potencia)

        #Total
        total_final = obtenerTotal(subtotal_final, 16)

        diccionario_final_cfe['periodo'] = periodo
        diccionario_final_cfe['demanda_facturable'] = df_t
        diccionario_final_cfe['factor_potencia'] = factor_potencia_total
        diccionario_final_cfe['kvarh_totales'] = kvarh_totales
        diccionario_final_cfe['tarifa_kwhb'] = tarifa_kwh_base
        diccionario_final_cfe['tarifa_kwhi'] = tarifa_kwh_intermedio
        diccionario_final_cfe['tarifa_kwhp'] = tarifa_kwh_punta
        diccionario_final_cfe['tarifa_df'] = tarifa_demanda_facturable
        diccionario_final_cfe['costo_energia'] = costo_energia_total
        diccionario_final_cfe['costo_dfacturable'] = costo_demanda_facturable
        diccionario_final_cfe['costo_fpotencia'] = costo_factor_potencia
        diccionario_final_cfe['subtotal'] = subtotal_final
        diccionario_final_cfe['iva'] = obtenerIva(subtotal_final, 16)
        diccionario_final_cfe['total'] = total_final

    return diccionario_final_cfe


def tarifaDAC(building, pr_powermeter, month, year):
    status = 'OK'
    diccionario_final_cfe = {}
    diccionario_final_cfe['status'] = status

    tarifa_kwh = 0
    tarifa_mes = 0
    kwh_final = 0
    kwh_inicial = 0
    costo_energia = 0
    iva = 0
    total = 0

    #Se obtiene la region
    region = building.region

    billing_month = datetime.date(year=year, month=month, day=1)
    try:
        month_cut_dates = MonthlyCutDates.objects.get(building=building,
                                                      billing_month=billing_month)
    except MonthlyCutDates.DoesNotExist:
        mensaje = "La fecha de corte para este mes no está definida"
        status = 'ERROR'
        diccionario_final_cfe['mensaje'] = mensaje
        diccionario_final_cfe['status'] = status
    else:
        s_date = datetime.datetime(year=month_cut_dates.date_init.year,
                                   month=month_cut_dates.date_init.month,
                                   day=month_cut_dates.date_init.day,
                                   hour=0, minute=0, second=0,
                                   tzinfo=timezone.get_current_timezone()
        )

        #Si la fecha de fin no es nula
        if month_cut_dates.date_end:
            e_date = datetime.datetime(year=month_cut_dates.date_end.year,
                                       month=month_cut_dates.date_end.month,
                                       day=month_cut_dates.date_end.day,
                                       hour=0, minute=0, second=0,
                                       tzinfo=timezone.get_current_timezone()
            )
        else: #Si la fecha de fin es nula, se toma el dia de hoy
            e_date = datetime.datetime.today().replace(hour=0, minute=0,
                                                       second=0,
                                                       tzinfo=timezone.get_current_timezone())
            billing_month = e_date

        periodo = str(s_date.day) + '/' + str(s_date.month) + "/" + str(
            s_date.year) + " - " + str(e_date.day) + '/' + str(
            e_date.month) + "/" + str(e_date.year)

        #Para las regiones BC y BCS es necesario obtener revisar si se aplica Tarifa de Verano o de Invierno
        if region.pk == 1 or region.pk == 2:
            tf_ver_inv = obtenerHorarioVeranoInvierno(mes_facturacion, 2)
            tarifasObj = DACElectricRateDetail.objects.filter(
                region=region.pk).filter(date_interval=tf_ver_inv).filter(
                date_init__lte=billing_month).filter(
                date_end__gte=billing_month)
            if tarifasObj:
                tarifa_kwh = tarifasObj[0].kwh_rate
                tarifa_mes = tarifasObj[0].month_rate

        else:
            tarifasObj = DACElectricRateDetail.objects.filter(
                region=region.pk).filter(date_interval=None).filter(
                date_init__lte=billing_month).filter(
                date_end__gte=billing_month)
            if tarifasObj:
                tarifa_kwh = tarifasObj[0].kwh_rate
                tarifa_mes = tarifasObj[0].month_rate

        print "Fecha Inicio:", s_date
        print "Fecha Fin:", e_date
        print "Tarifa kwh:", tarifa_kwh
        print "Tarifa mensual:", tarifa_mes

        #Se obtienen los kwh de ese periodo de tiempo.
        kwh_lecturas = ElectricDataTemp.objects.filter(
            profile_powermeter=pr_powermeter,
            medition_date__range=(s_date, e_date)).order_by('medition_date')
        total_lecturas = len(kwh_lecturas)

        if kwh_lecturas:
            print "1er Lectura:", kwh_lecturas[0].medition_date.astimezone(
                tz=timezone.get_current_timezone()), " Id:", kwh_lecturas[0].id
            kwh_inicial = kwh_lecturas[0].TotalkWhIMPORT
            print "2da Lectura:", kwh_lecturas[
                total_lecturas - 1].medition_date.astimezone(
                tz=timezone.get_current_timezone()), " Id:", kwh_lecturas[
                total_lecturas - 1].id
            kwh_final = kwh_lecturas[total_lecturas - 1].TotalkWhIMPORT

        kwh_netos = int(ceil(kwh_final - kwh_inicial))
        print "Kwh Netos:", kwh_netos
        importe = kwh_netos * tarifa_kwh
        costo_energia = importe + tarifa_mes
        iva = costo_energia * Decimal(str(.16))
        total = costo_energia + iva
        print "Energia kwh ",
        print "IVA:", float(iva)
        print "Total:", float(total)

        diccionario_final_cfe['periodo'] = periodo
        diccionario_final_cfe['kwh_totales'] = kwh_netos
        diccionario_final_cfe['tarifa_kwh'] = tarifa_kwh
        diccionario_final_cfe['tarifa_mes'] = tarifa_kwh
        diccionario_final_cfe['importe'] = importe
        diccionario_final_cfe['costo_energia'] = float(costo_energia)
        diccionario_final_cfe['iva'] = float(iva)
        diccionario_final_cfe['total'] = float(total)

    return diccionario_final_cfe


def obtenerHistoricoTodos():
    #Se obtienen todos los edificios
    buildings_list = Building.objects.all()
    if buildings_list:
        for building in buildings_list:
            building_cut_dates = MonthlyCutDates.objects.filter(
                building=building)
            if building_cut_dates:
                for cut_date in building_cut_dates:
                    #Tarifa HM
                    if building.electric_rate == 1:
                        obtenerHistoricoHM(building, powermeter, cut_date)
                    #Tarifa DAC
                    elif building.electric_rate == 2:
                        obtenerHistoricoDAC(cut_date)


def obtenerHistoricoHM():
    arr_historico = []

    dict_periodo = {}
    dict_periodo["fecha"] = datetime.datetime(year=2012, month=8, day=1)
    dict_kw = 0
    dict_periodo["kw_base"] = 8
    dict_periodo["kw_intermedio"] = 24
    dict_periodo["kw_punta"] = 15
    dict_periodo["demanda_maxima"] = 17
    dict_periodo["total_kwh"] = 1487
    dict_periodo["kvarh"] = 159
    dict_periodo["factor_potencia"] = 98.13
    dict_periodo["factor_carga"] = 14.48
    dict_periodo["costo_promedio"] = 2.0553
    arr_historico.append(dict_periodo)

    dict_periodo = {}
    dict_periodo["fecha"] = datetime.datetime(year=2012, month=9, day=1)
    dict_kw = 0
    dict_periodo["kw_base"] = 27
    dict_periodo["kw_intermedio"] = 32
    dict_periodo["kw_punta"] = 10
    dict_periodo["demanda_maxima"] = 28
    dict_periodo["total_kwh"] = 2438
    dict_periodo["kvarh"] = 544
    dict_periodo["factor_potencia"] = 97.61
    dict_periodo["factor_carga"] = 13.81
    dict_periodo["costo_promedio"] = 3.1828

    arr_historico.append(dict_periodo)

    return arr_historico


def obtenerHistoricoDAC(cut_date):
    #Precio MEdio
    #Kwh Totales
    pass


def fechas_corte(dia_corte, mes, anio):
    dias_mes = monthrange(anio, mes)
    dias = dias_mes[1]
    if dias <= dia_corte:
        fecha_final = str(anio) + "-" + str(mes) + "-" + str(dias) + " 23:59:59"

        fecha_inicial = str(anio) + "-" + str(mes) + "-01 00:00:00"

    else:
        fecha_final = str(anio) + "-" + str(mes) + "-" + str(
            dia_corte) + " 23:59:59"
        e_date = datetime.date(anio, mes, dia_corte)

        s_date = e_date + relativedelta(months=-1)

        fecha_inicial = str(s_date.year) + "-" + str(s_date.month) + "-" + str(
            s_date.day) + " 00:00:00"

    return fecha_inicial, fecha_final


def fechas_corte_2(dia_corte, mes, anio):
    fecha_inicial = ''
    fecha_final = ''

    if dia_corte < 15:
        fecha_inicial = str(anio) + "-" + str(mes) + "-" + str(
            dia_corte) + " 00:00:00"

        s_date = datetime.date(anio, mes, dia_corte)

        e_date = s_date + relativedelta(months=-1)
        fecha_final = str(e_date.year) + "-" + str(e_date.month) + "-" + str(
            e_date.day) + " 00:00:00"
    else:
        dias_mes = monthrange(anio, mes)
        dias = dias_mes[1]
        if dias <= dia_corte:
            fecha_final = str(anio) + "-" + str(mes) + "-" + str(
                dias) + " 00:00:00"
            s_date = datetime.date(anio, mes, dias)

            e_date = s_date + relativedelta(months=-1)
            fecha_inicial = str(e_date.year) + "-" + str(
                e_date.month) + "-" + str(e_date.day) + " 00:00:00"
        else:
            fecha_final = str(anio) + "-" + str(mes) + "-" + str(
                dia_corte) + " 00:00:00"
            s_date = datetime.date(anio, mes, dia_corte)

            e_date = s_date + relativedelta(months=-1)
            fecha_inicial = str(e_date.year) + "-" + str(
                e_date.month) + "-" + str(e_date.day) + " 00:00:00"

    return fecha_inicial, fecha_final


def recibocfe(request):
    #Obtiene los registros de un medidor en un determinado periodo de tiempo
    pr_powermeter = Powermeter.objects.get(pk=3)
    region = 2
    tipo_tarifa = 1
    start_date = '2012-08-19 00:00:00'
    end_date = '2012-08-21 23:59:59'

    #tarifaHM_new(pr_powermeter,start_date,end_date,region,1)

    #comprobacionCFE()
    #generaFechas()
    tag_reading_batch()

    variables = RequestContext(request, vars)
    return render_to_response('consumption_centers/cfe.html', variables)

def tag_reading_batch():
    #readingsObj = ElectricDataTemp.objects.filter(pk__gte=1241619)
    #readingsObj = ElectricDataTemp.objects.all()

    #Obtener los medidores
    #Obtener sus lecturas, ordenandolos por fechas

    print "entra"
    readingsObj = ElectricDataTemp.objects.filter(
        profile_powermeter__pk=28, medition_date__gte=datetime.datetime(2013,01,01)).order_by(
        "medition_date")

    for readingObj in readingsObj:
        print "por cada lectura", readingObj.pk
        #Si la lectura proviene de cualquier medidor menos del No Asignado
        if readingObj.profile_powermeter.pk != 4:
            tag = None
            #Se revisa que esa medicion no este etiquetada ya.
            tagged_reading = ElectricRateForElectricData.objects.filter(
                electric_data=readingObj)
            #if not tagged_reading:
            #Se obtiene el Consumer Unit, para poder obtener el edificio, una vez obtenido el edificio, se puede obtener la region y la tarifa
            try:
                consumerUnitObj = ConsumerUnit.objects.get(
                    profile_powermeter=readingObj.profile_powermeter)
            except ObjectDoesNotExist:
                continue
            else:
                buildingObj = Building.objects.get(
                    id=consumerUnitObj.building.id)

                #Obtiene el periodo de la lectura actual
                fecha_zhor = readingObj.medition_date.astimezone(
                    tz=timezone.get_current_timezone())
                #reading_period_type = obtenerTipoPeriodoObj(readingObj.medition_date, buildingObj.region, buildingObj.electric_rate)
                reading_period_type = obtenerTipoPeriodoObj(fecha_zhor,
                                                            buildingObj.region)
                print reading_period_type

                #Obtiene las ultimas lecturas de ese medidor
                last_reading = ElectricRateForElectricData.objects.filter(
                    electric_data__profile_powermeter=readingObj.profile_powermeter).order_by(
                    "-electric_data__medition_date")
                #Si existen registros para ese medidor
                if last_reading:
                    #Obtiene el periodo de la ultima lectura de ese medidor
                    last_reading_type = last_reading[
                        0].electric_rates_periods.period_type

                    #    Se compara el periodo actual con el periodo del ultimo registro.
                    #    Si los periodos son iguales, el identificador será el mismo

                    if reading_period_type.period_type == last_reading_type:
                        tag = last_reading[0].identifier
                    else:
                        #Si los periodos son diferentes, al identificador anterior, se le sumara 1.
                        tag = last_reading[0].identifier
                        tag = hex(int(tag, 16) + int(1))
                        #print "ID:", readingObj.pk, "-Tag Anterior:",
                        #last_reading[
                        #0].identifier, "-Nuevo Tag:", tag, "Tipo Actual:", reading_period_type.period_type, "Tipo Anterior:", last_reading_type, "ID Anterior:",
                        #last_reading[0].pk

                else: #Si será un registro para un nuevo medidor
                    tag = hex(0)


                #Guarda el registro etiquetado
                newTaggedReading, created = ElectricRateForElectricData.objects.get_or_create(
                    electric_data=readingObj
                )
                newTaggedReading.electric_rates_periods=reading_period_type
                newTaggedReading.identifier=tag
                newTaggedReading.save()

    print "Acabe"


def multiply():
    data = ElectricDataTemp.objects.filter(
        medition_date__gte=datetime.datetime(2012, 9,
                                             20, 0, 0, 0)).order_by(
        "-medition_date")
    for dato in data:
        if dato.TotalkWhIMPORT < 1000:
            dato.TotalkWhIMPORT *= 1000
            dato.TotalkvarhIMPORT *= 1000
            dato.save()
    print ":D"

#Etiquetado de datos por rango de ids
def tag_reading_ids(id_start, id_end):

    readingsObj = ElectricDataTemp.objects.filter(id__gte = id_start).filter(id__lte = id_end).order_by("medition_date")

    for readingObj in readingsObj:
        #Si la lectura proviene de cualquier medidor menos del No Asignado
        if readingObj.profile_powermeter.pk != 4:
            tag = None
            #Se revisa que esa medicion no este etiquetada ya.
            tagged_reading = ElectricRateForElectricData.objects.filter(
                electric_data=readingObj)
            if not tagged_reading:
                #Se obtiene el Consumer Unit, para poder obtener el edificio, una vez obtenido el edificio, se puede obtener la region y la tarifa
                consumerUnitObj = ConsumerUnit.objects.filter(
                    profile_powermeter=readingObj.profile_powermeter)
                buildingObj = Building.objects.get(
                    id=consumerUnitObj[0].building.id)

                #Obtiene el periodo de la lectura actual
                fecha_zhor = readingObj.medition_date.astimezone(
                    tz=timezone.get_current_timezone())
                #reading_period_type = obtenerTipoPeriodoObj(readingObj.medition_date, buildingObj.region, buildingObj.electric_rate)
                reading_period_type = obtenerTipoPeriodoObj(fecha_zhor,
                                                            buildingObj.region)

                #Obtiene las ultimas lecturas de ese medidor
                last_reading = ElectricRateForElectricData.objects.filter(
                    electric_data__profile_powermeter=readingObj.profile_powermeter).order_by(
                    "-electric_data__medition_date")
                #Si existen registros para ese medidor
                if last_reading:
                    #Obtiene el periodo de la ultima lectura de ese medidor
                    last_reading_type = last_reading[
                        0].electric_rates_periods.period_type

                    #    Se compara el periodo actual con el periodo del ultimo registro.
                    #    Si los periodos son iguales, el identificador será el mismo

                    if reading_period_type.period_type == last_reading_type:
                        tag = last_reading[0].identifier
                    else:
                        #Si los periodos son diferentes, al identificador anterior, se le sumara 1.
                        tag = last_reading[0].identifier
                        tag = hex(int(tag, 16) + int(1))
                        #print "ID:", readingObj.pk, "-Tag Anterior:",
                        #last_reading[
                        #0].identifier, "-Nuevo Tag:", tag, "Tipo Actual:", reading_period_type.period_type, "Tipo Anterior:", last_reading_type, "ID Anterior:",
                        #last_reading[0].pk

                else: #Si será un registro para un nuevo medidor
                    tag = hex(0)


                #Guarda el registro etiquetado
                newTaggedReading = ElectricRateForElectricData(
                    electric_rates_periods=reading_period_type,
                    electric_data=readingObj,
                    identifier=tag
                )
                newTaggedReading.save()

    print "Acabe"

@csrf_exempt
def tag_reading(request):
    if request.method == 'POST':

        #Obtiene el Id de la medicion
        reading_id = request.REQUEST.get("id_reading", "")
        if reading_id:
            tag = None
            readingObj = ElectricDataTemp.objects.get(id=reading_id)
            #Si la lectura proviene de cualquier medidor menos del No Asignado
            if readingObj.profile_powermeter.pk != 4:
                #Se revisa que esa medicion no este etiquetada ya.
                tagged_reading = ElectricRateForElectricData.objects.filter(
                    electric_data=readingObj)
                if not tagged_reading:
                    #Se obtiene el Consumer Unit, para poder obtener el edificio, una vez obtenido el edificio, se puede obtener la region y la tarifa
                    consumerUnitObj = ConsumerUnit.objects.filter(
                        profile_powermeter=readingObj.profile_powermeter)
                    buildingObj = Building.objects.get(
                        id=consumerUnitObj[0].building.id)

                    #Obtiene el periodo de la lectura actual
                    fecha_zhor = readingObj.medition_date.astimezone(
                        tz=timezone.get_current_timezone())
                    #reading_period_type = obtenerTipoPeriodoObj(readingObj.medition_date, buildingObj.region, buildingObj.electric_rate)
                    reading_period_type = obtenerTipoPeriodoObj(fecha_zhor,
                                                                buildingObj.region)

                    #Obtiene las ultimas lecturas de ese medidor
                    last_reading = ElectricRateForElectricData.objects.filter(
                        electric_data__profile_powermeter=readingObj.profile_powermeter).order_by(
                        "-electric_data__medition_date")
                    #Si existen registros para ese medidor
                    if last_reading:
                        #Obtiene el periodo de la ultima lectura de ese medidor
                        last_reading_type = last_reading[0].\
                            electric_rates_periods.period_type

                        #    Se compara el periodo actual con el periodo del ultimo registro.
                        #    Si los periodos son iguales, el identificador será el mismo

                        if reading_period_type.period_type == last_reading_type:
                            tag = last_reading[0].identifier
                        else:
                            #Si los periodos son diferentes, al identificador anterior, se le sumara 1.
                            tag = last_reading[0].identifier
                            tag = hex(int(tag, 16) + int(1))

                    else: #Si será un registro para un nuevo medidor
                        tag = hex(0)


                    #Guarda el registro etiquetado
                    newTaggedReading = ElectricRateForElectricData(
                        electric_rates_periods=reading_period_type,
                        electric_data=readingObj,
                        identifier=tag
                    )

                    newTaggedReading.save()
        return HttpResponse(content='', content_type=None, status=200)
    return HttpResponse(content='', content_type=None, status=404)