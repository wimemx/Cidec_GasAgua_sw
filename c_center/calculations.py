# -*- coding: utf-8 -*-
# Create your views here.

#standard library imports
import collections
import pytz, datetime
import threading
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

def consumoAcumuladoKWH(building, fecha_inicio, fecha_fin):
    suma_lecturas = 0
    lecturas = DailyData.objects.filter(building = building, 
                                        data_day__gte = fecha_inicio, 
                                        data_day__lte = fecha_fin).aggregate(
        Sum('KWH_total'))
    if lecturas:
        suma_lecturas = lecturas['KWH_total__sum']
    return suma_lecturas


def demandaMaxima(building, fecha_inicio, fecha_fin):
    demanda_max = 0
    lecturas = DailyData.objects.filter(building=building,
                                        data_day__gte=fecha_inicio,
                                        data_day__lte=fecha_fin).order_by(
        '-max_demand')
    if lecturas:
        demanda_max = lecturas[0].max_demand
    return demanda_max


def demandaMinima(building, fecha_inicio, fecha_fin):
    demanda_min = 0
    lecturas = DailyData.objects.filter(building=building,
                                        data_day__gte=fecha_inicio,
                                        data_day__lte=fecha_fin).order_by(
        'min_demand')
    if lecturas:
        demanda_min = lecturas[0].min_demand
    return demanda_min


def promedioKWH(building, fecha_inicio, fecha_fin):
    promedio = 0
    t_lecturas = DailyData.objects.filter(building = building, 
                                        data_day__gte = fecha_inicio, 
                                        data_day__lte = fecha_fin)
    if t_lecturas:
        suma_lecturas = DailyData.objects.filter(building = building, 
                                                data_day__gte = fecha_inicio, 
                                                data_day__lte = fecha_fin).aggregate(
            Sum('KWH_total'))
        total_lecturas = len(t_lecturas)
        promedio = suma_lecturas['KWH_total__sum'] / total_lecturas
    return promedio


def desviacionStandardKWH(building, fecha_inicio, fecha_fin):
    suma = 0
    desviacion = 0
    lecturas = DailyData.objects.filter(building = building, 
                                        data_day__gte = fecha_inicio, 
                                        data_day__lte = fecha_fin)
    if lecturas:
        promedio = promedioKWH(building, fecha_inicio, fecha_fin)
        nmenosuno = len(lecturas)-1
        for kwh in lecturas:
            n_m = kwh.KWH_total - promedio
            suma += n_m**2
        desviacion = sqrt(suma/nmenosuno)
    return desviacion


def medianaKWH(building, fecha_inicio, fecha_fin):
    mediana = 0
    lecturas = DailyData.objects.filter(building=building,
                                        data_day__gte=fecha_inicio,
                                        data_day__lte=fecha_fin).order_by(
        'KWH_total')
    if lecturas:
        longitud = len(lecturas)
        if longitud % 2 is 0: #Si es par
            mediana = (lecturas[longitud / 2].KWH_total + lecturas[
                (longitud / 2) - 1].KWH_total) / 2
        else: #Si es impar
            mediana = lecturas[longitud / 2].KWH_total
    return mediana


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
                while (dia_mes < month_days[1] - 1):
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

    #La fecha se formatea a "dia mes año" sin guiones, solo espacios. 
    fecha_formato = fecha.strftime("%d %m %Y")
    if fecha_formato in dias_festivos:
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
        Q(time_init__lte=fecha), Q(
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

def obtenerKVARH_total(pr_powermeter, start_date, end_date):
    kvarh_netos = 0
    lecturasObj = ElectricDataTemp.objects.filter(
        profile_powermeter__powermeter=pr_powermeter,
        medition_date__gte=start_date,
        medition_date__lt=end_date).order_by('medition_date')
    if lecturasObj:
        total_lecturas = len(lecturasObj)
        kvarh_inicial = lecturasObj[0].TotalkvarhIMPORT
        kvarh_final = lecturasObj[total_lecturas - 1].TotalkvarhIMPORT
        kvarh_netos = kvarh_final - kvarh_inicial

    return int(ceil(kvarh_netos))

def obtenerKVARH(profile_powermeter, start_date, end_date):
    kvarh_netos = 0
    lecturasObj = ElectricDataTemp.objects.filter(
        profile_powermeter=profile_powermeter,
        medition_date__gte=start_date,
        medition_date__lt=end_date).order_by('medition_date')
    if lecturasObj:
        total_lecturas = len(lecturasObj)
        kvarh_inicial = lecturasObj[0].TotalkvarhIMPORT
        kvarh_final = lecturasObj[total_lecturas - 1].TotalkvarhIMPORT
        kvarh_netos = kvarh_final - kvarh_inicial

    return int(ceil(kvarh_netos))

def obtenerKVARH_dia(profile_powermeter, start_date, end_date, kvarh_anterior):
    kvarh_netos = 0
    lecturasObj = ElectricDataTemp.objects.filter(
        profile_powermeter=profile_powermeter,
        medition_date__gte=start_date,
        medition_date__lt=end_date).order_by('medition_date')
    if lecturasObj:
        total_lecturas = len(lecturasObj)
        #Obtengo la primer lectura
        kvarh_inicial = lecturasObj[0].TotalkvarhIMPORT
        kvarh_final = lecturasObj[total_lecturas - 1].TotalkvarhIMPORT

        #Se verifica el kvarh_anterior
        if kvarh_anterior:
            #Se obtiene la siguiente lectura
            last_id = lecturasObj[total_lecturas-1].id
            siguiente_lectura = ElectricDataTemp.objects.filter(
                profile_powermeter=profile_powermeter, pk__gt = last_id).order_by('medition_date')
            if siguiente_lectura:
                print "Id:", siguiente_lectura[0].id
                kvarh_final = siguiente_lectura[0].TotalkvarhIMPORT

        print "1er KVARH", kvarh_inicial
        print "2da KVARH", kvarh_final
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


def batch_tag():
    pw_arr = [3, 5, 28, 29, 30, 31, 32, 33, 6, 7, 22, 24, 25, 26, 27]
    pwermeters = ProfilePowermeter.objects.filter(pk__in=pw_arr)
    for pw in pwermeters:
        print pw
        tag_reading_batch(pw)
    print "all powermeters sent"


def tag_reading_batch(profile_pm):
    #readingsObj = ElectricDataTemp.objects.filter(pk__gte=1241619)
    #readingsObj = ElectricDataTemp.objects.all()

    #Obtener los medidores
    #Obtener sus lecturas, ordenandolos por fechas

    print "tagging..." + profile_pm.powermeter.powermeter_anotation
    readingsObj = ElectricDataTemp.objects.filter(
        profile_powermeter=profile_pm).order_by(
        "medition_date")

    for readingObj in readingsObj:
        print "medition_date: " + str(readingObj.pk) + \
              str(readingObj.medition_date)
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

                else:  # Si será un registro para un nuevo medidor
                    tag = hex(0)
                    #Guarda el registro etiquetado
                newTaggedReading = ElectricRateForElectricData(
                    electric_rates_periods=reading_period_type,
                    electric_data=readingObj,
                    identifier=tag
                )
                newTaggedReading.save()

    print "Done", profile_pm


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
def tag_reading_ids():
    readingsObj = ElectricDataTemp.objects.filter(
        profile_powermeter__pk=28).filter(
        medition_date__gte=datetime.datetime(2012, 12, 31)).filter(
        medition_date__lte=datetime.datetime(2013, 1, 12)).order_by(
        "medition_date")

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
                        last_reading_type = last_reading[0]. \
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


def tag_reading_unique_id(reading_id):

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

                #Se obtiene la lectura anterior
                #Obtiene las ultimas lecturas de ese medidor
                last_reading = ElectricRateForElectricData.objects.filter(
                    electric_data__profile_powermeter=readingObj.profile_powermeter,
                    electric_data__pk__lt = readingObj.pk).order_by(
                    "-electric_data__medition_date")
                #Si existen registros para ese medidor
                print "    Ultima lectura:", last_reading[0].id," - ", last_reading[0].electric_rates_periods.period_type
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
    return True

def reTagHolidays():

    #Se obtienen los perfiles
    all_profiles = ProfilePowermeter.objects.all()

    dias_festivos_2012 = obtenerFestivos(2012)
    dias_festivos_2013 = obtenerFestivos(2013)

    dias_festivos = dias_festivos_2012 + dias_festivos_2013

    for profile in all_profiles:
        print "Perfil: ", profile.id
        for dia_f in dias_festivos:
            print "Dia Festivo:", dia_f
            #Se agregan las horas
            finicio_str = time.strptime(dia_f+" 00:00:00", "%d %m %Y %H:%M:%S")
            finicio_arr = time.gmtime(time.mktime(finicio_str))
            finicio_utc = datetime.datetime(year= finicio_arr[0], month=finicio_arr[1], day=finicio_arr[2],
                hour=finicio_arr[3], minute=finicio_arr[4], second=finicio_arr[5], tzinfo = pytz.utc)

            ffin_str = time.strptime(dia_f+" 23:59:59", "%d %m %Y %H:%M:%S")
            ffin_arr = time.gmtime(time.mktime(ffin_str))
            ffin_utc = datetime.datetime(year= ffin_arr[0], month=ffin_arr[1], day=ffin_arr[2], hour=ffin_arr[3],
                minute=ffin_arr[4], second=ffin_arr[5], tzinfo = pytz.utc)

            electricReadings = ElectricDataTemp.objects.filter(profile_powermeter = profile,
                medition_date__gte = finicio_utc, medition_date__lte = ffin_utc).order_by('medition_date')

            if electricReadings:
                for electObj in electricReadings:
                    print "Etiquetando Id:", electObj.pk
                    try:
                        ElectricRateForElectricData.objects.get(electric_data = electObj).delete()
                    except ElectricRateForElectricData.DoesNotExist :
                        pass
                    else:
                        tag_reading_unique_id(electObj.pk)

    print "Done with Holidays"