# -*- coding: utf-8 -*-
# Create your views here.

from django.http import *
from math import *
from decimal import *

import collections
import datetime
from time import strftime

from calendar import monthrange


from c_center.models import *
from electric_rates.models import *

def demandafacturable(kwbase, kwintermedio, kwpunta, region, tarifa, fecha):
    df = 0

    #Se obtienen los Factores de Reduccion en base a la zona, la tarifa y la fecha
    factores_reduccion = ElectricRatesDetail.objects.filter(electric_rate = tarifa).filter(region_id = region).filter(date_init__lte = datetime.date(fecha.year, fecha.month, fecha.day)).filter(date_end__gte = datetime.date(fecha.year, fecha.month, fecha.day))
    fri = factores_reduccion[0].FRI
    frb = factores_reduccion[0].FRB
    print fri
    print frb

    primermax = kwintermedio - kwpunta
    if primermax < 0:
        primermax = 0

    segundomax = kwbase-max(kwintermedio, kwpunta)
    if segundomax < 0:
        segundomax = 0

    df = kwpunta + fri * primermax + frb * segundomax

    return int(ceil(df))


def costoenergia(kwbase, kwintermedio, kwpunta, region, tarifa, fecha):
    costo_energia = 0

    #Se obtienen las tarifas para cada kw
    tarifas = ElectricRatesDetail.objects.filter(electric_rate = tarifa).filter(region_id = region).filter(date_init__lte = datetime.date(fecha.year, fecha.month, fecha.day)).filter(date_end__gte = datetime.date(fecha.year, fecha.month, fecha.day))
    tarifa_kwbase = tarifas[0].KWHB
    tarifa_kwintermedio = tarifas[0].KWHI
    tarifa_kwpunta = tarifas[0].KWHP

    costo_energia = kwbase*tarifa_kwbase + kwintermedio*tarifa_kwintermedio + kwpunta*tarifa_kwpunta

    return costo_energia

def costodemandafacturable(demandaf, region, tarifa, fecha):
    precio = 0

    #Se obtiene el precio de la demanda
    tarifas = ElectricRatesDetail.objects.filter(electric_rate = tarifa).filter(region_id = region).filter(date_init__lte = datetime.date(fecha.year, fecha.month, fecha.day)).filter(date_end__gte = datetime.date(fecha.year, fecha.month, fecha.day))
    tarifa_demanda = tarifas[0].KDF

    return (demandaf * tarifa_demanda)


def fpbonificacionrecargo(fp):
    fp_valor = 0

    if fp < 90:
        fp_valor = Decimal(3.0/5.0)*((Decimal(90.0)/fp)-1)*100
    else:
        fp_valor = Decimal(1.0/4.0)*(1-(Decimal(90.0)/fp))*100

    return float(fp_valor)

def costofactorpotencia(fp, costo_energia, costo_df):
    costo_fp = 0

    if fp < 90:
        costo_fp = float((costo_energia + costo_df)/100)*fpbonificacionrecargo(fp)
    else:
        costo_fp = float((costo_energia + costo_df)/100)*fpbonificacionrecargo(fp)*-1

    return costo_fp


def obtenerSubtotal(costo_energia, costo_df, costo_fp):
    return (float(costo_energia) + float(costo_df) + float(costo_fp))

def obtenerIva(c_subtotal, iva):
    iva = iva/100.0
    return float(c_subtotal)*float(iva)

def obtenerTotal(c_subtotal, iva):
    iva = iva/100.0 + 1
    return float(c_subtotal)*float(iva)

def factorpotencia(kwh, kvarh):
    return (kwh/Decimal(pow((pow(kwh,2)+pow(kvarh,2)),.5)))*100

def obtenerDemanda(arr_kw):
    demanda_maxima = 0
    if arr_kw:
        try:
            longitud = len(arr_kw)
            if longitud >= 3:
                for indice, demanda in enumerate(arr_kw):
                    if indice+1 < (longitud -1) and indice + 2 <= (longitud - 1):
                        prom = (arr_kw[indice] + arr_kw[indice+1] + arr_kw[indice+2])/Decimal(3.0)
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
                month_days = monthrange(actual_year,hday.month)
                while(dia_mes < month_days[1]-1):
                    #st_time = time.strptime("%02d" % (c_day)+" "+"%02d" % (mes)+" "+str(actual_year), "%d %m %Y")
                    st_time = time.strptime("%02d" % (dia_mes)+" "+"%02d" % (hday.month)+" "+str(actual_year), "%d %m %Y")
                    week_day = strftime("%w", st_time)
                    if lst_days[week_day] == w_day:
                        if ahorita == int(n_day):
                            lista_festivos.append(strftime("%d %m %Y",st_time))
                            break
                        else:
                            ahorita += 1

                    dia_mes += 1
            else:
                # Si es 1 de diciembre, se verifica que sea año de elecciones.
                # En caso afirmativo se agrega a la lista de dias festivos
                if int(hday.day) == 1 and int(hday.month) == 12:
                    if (actual_year - 1946)%6 == 0:
                        st_time = time.strptime("%02d" % int(hday.day)+" "+"%02d" % int(hday.month)+" "+str(actual_year), "%d %m %Y")
                        lista_festivos.append(strftime("%d %m %Y", st_time))
                else:
                    st_time = time.strptime("%02d" % int(hday.day)+" "+"%02d" % int(hday.month)+" "+str(actual_year), "%d %m %Y")
                    lista_festivos.append(strftime("%d %m %Y", st_time))

    return lista_festivos

def obtenerCatalogoGrupos():
    """
    Se regresa un catálogo que indica a qué grupo pertenece cada día de la semana.
    """
    group_days_bd = Groupdays.objects.all()
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
    A partir de una fecha, se obtiene a qué grupo de días pertenece: Lun a Vie, Sab o Dom y Festivos

    """

    num_dia = 0

    dias_festivos = obtenerFestivos(fecha.year)
    #if (str(fecha.day)+" "+str(fecha.month)+" "+str(fecha.year)) in dias_festivos:
    if fecha in dias_festivos:
        num_dia = 7
    else:
        st_time = time.strptime(str(fecha.day)+" "+str(fecha.month)+" "+str(fecha.year), "%d %m %Y")
        num_dia = strftime("%w", st_time)

    return catalogo_grupos[int(num_dia)]



def obtenerTipoPeriodo(fecha, region, tarifa, catalogo_grupos):
    """
    Se obtiene el tipo de periodo de una lectura, en base a la fecha y hora en que fue tomada, región y tarifa.

    """
    grupo_id = obtenerGrupo(catalogo_grupos, fecha)
    horario_ver_inv = [date.pk for date in DateIntervals.objects.filter(date_init__lte= datetime.date(fecha.year,fecha.month,fecha.day)).filter(date_end__gte = datetime.date(fecha.year,fecha.month,fecha.day))]#.filter(region = region)

    electric_type = ElectricRatesPeriods.objects.filter(region = region).filter(electric_rate = tarifa).filter(date_interval__in = horario_ver_inv).filter(groupdays = grupo_id).filter(time_init__lte = datetime.time(fecha.hour,fecha.minute)).filter(time_end__gte = datetime.time(fecha.hour,fecha.minute))

    return electric_type[0].period_type


def tarifaHM(pr_powermeter, start_date, end_date, region):
    readings = ElectricData.objects.filter(profile_powermeter = pr_powermeter, medition_date__range=(start_date, end_date)).order_by('medition_date')

    catalogo_grupos = obtenerCatalogoGrupos()

    tarifa = 1
    tarifas_id = []

    tipo_tarifa_g = None
    tarifa_g = None
    kwh_primero = None
    kwh_ultimo = None

    kwh_base_arr = []
    kwh_intermedio_arr = []
    kwh_punta_arr = []

    relacion_tarifa_lectura = collections.defaultdict(dict)
    relacion_tarifa_kwh_periodo = {}

    if readings:
        for reading in readings:
            l_tar_co = ElectricRatesDetail.objects.filter(electric_rate = tarifa).filter(region_id = region).filter(date_init__lte = datetime.date(reading.medition_date.year,reading.medition_date.month,reading.medition_date.day)).filter(date_end__gte = datetime.date(reading.medition_date.year,reading.medition_date.month,reading.medition_date.day))


            #Se guarda una relación: Tarifa - Lectura - Tipo de Tarifa
            #Ej: Tarifa Junio - Lectura No. 6789 - Intermedio

            relacion_tarifa_lectura[l_tar_co[0].id][reading.id] = obtenerTipoPeriodo(reading.medition_date, region, tarifa,catalogo_grupos)


            #    Un lapso dado puede abarcar varios meses, los cuales tendran diferentes tarifas.
            #    Para realizar los calculos, es necesario identificar los kwh de cada periodo: base, intermedio y punta,
            #    de cada mes/tarifa.
            #    Para cada mes/tarifa se obtienen todos los periodos base, intermedio y punta en base a las lecturas.
            #    Para cada periodo (base, intermedio, punta) se obtienen todas las lecturas de kwh.
            #    Se obtienen los kwh netos de ese periodo restando la ultima lectura del periodo, con la primer lectura.

            tipo_tarifa_actual = obtenerTipoPeriodo(reading.medition_date, region, tarifa,catalogo_grupos)
            tarifa_actual = l_tar_co[0].id

            if not kwh_primero:
                kwh_primero = reading.kWhIMPORT
            kwh_ultimo = reading.kWhIMPORT


            if not tipo_tarifa_g:
                tipo_tarifa_g = tipo_tarifa_actual

            if not tarifa_g:
                tarifa_g = tarifa_actual

            #Cambia la tarifa
            if tarifa_g != tarifa_actual:
                tarifas_id.append(tarifa_g)

                kwh_netos = kwh_ultimo - kwh_primero


                if tipo_tarifa_g == 'base':
                    kwh_base_arr.append(kwh_netos)
                elif tipo_tarifa_g == 'intermedio':
                    kwh_intermedio_arr.append(kwh_netos)
                elif tipo_tarifa_g == 'punta':
                    kwh_punta_arr.append(kwh_netos)

                kwh_netos = None
                kwh_primero = kwh_ultimo
                kwh_ultimo = None

                if not kwh_primero:
                    kwh_primero = reading.kWhIMPORT
                kwh_ultimo = reading.kWhIMPORT

                relacion_tarifa_kwh_periodo[tarifa_g,'base'] = kwh_base_arr
                relacion_tarifa_kwh_periodo[tarifa_g,'intermedio'] = kwh_intermedio_arr
                relacion_tarifa_kwh_periodo[tarifa_g,'punta'] = kwh_punta_arr

                #Se reinician los arreglos
                kwh_base_arr = []
                kwh_intermedio_arr = []
                kwh_punta_arr = []

                #La nueva tarifa global es la tarifa actual
                tarifa_g = tarifa_actual

                #El nuevo tipo de tarifa global es el tipo de tarifa actual
                tipo_tarifa_g = tipo_tarifa_actual

            #Cambia únicamente el tipo de tarifa
            if tipo_tarifa_g != tipo_tarifa_actual:

                kwh_netos = kwh_ultimo - kwh_primero

                if tipo_tarifa_g == 'base':
                    kwh_base_arr.append(kwh_netos)
                elif tipo_tarifa_g == 'intermedio':
                    kwh_intermedio_arr.append(kwh_netos)
                elif tipo_tarifa_g == 'punta':
                    kwh_punta_arr.append(kwh_netos)

                kwh_netos = None
                kwh_primero = kwh_ultimo

                tipo_tarifa_g = tipo_tarifa_actual

        kwh_netos = kwh_ultimo - kwh_primero

        if tipo_tarifa_g == 'base':
            kwh_base_arr.append(kwh_netos)
        elif tipo_tarifa_g == 'intermedio':
            kwh_intermedio_arr.append(kwh_netos)
        elif tipo_tarifa_g == 'punta':
            kwh_punta_arr.append(kwh_netos)

        relacion_tarifa_kwh_periodo[tarifa_g,'base'] = kwh_base_arr
        relacion_tarifa_kwh_periodo[tarifa_g,'intermedio'] = kwh_intermedio_arr
        relacion_tarifa_kwh_periodo[tarifa_g,'punta'] = kwh_punta_arr
        tarifas_id.append(tarifa_g)


        #Variables que contienen toda la informacion del recibo de CFE
        demanda_facturable_total = 0
        factor_potencia_total = 0
        costo_energia_total = 0
        costo_demanda_facturable = 0
        costo_factor_potencia = 0
        subtotal_final = 0
        iva_total = 0
        total_final = 0
        kw_totales = 0
        kw_base_totales = 0
        kw_intermedio_totales = 0
        kw_punta_totales = 0
        kwh_totales = 0
        kwh_base_totales = 0
        kwh_intermedio_totales = 0
        kwh_punta_totales = 0

        #Variables que contienen las tarifas de kwh base, kwh intermedio, kwh punta
        tarifa_kwh_base = 0
        tarifa_kwh_intermedio = 0
        tarifa_kwh_punta = 0


        numero_tarifas = len(tarifas_id)
        for tarifa_id in tarifas_id:

            tarifasObj = ElectricRatesDetail.objects.get(id = tarifa_id)
            #Obtiene las tarifas del mes
            tarifa_kwh_base += tarifasObj.KWHB
            tarifa_kwh_intermedio += tarifasObj.KWHI
            tarifa_kwh_punta += tarifasObj.KWHP

            kwarh = 96
            kw_base = []
            kw_intermedio = []
            kw_punta = []

            kwh_base = 0
            arr_kwh_base = relacion_tarifa_kwh_periodo[tarifa_id,'base']
            for kwh_b in arr_kwh_base:
                kwh_base += kwh_b

            #Kwh_ Base Totales del Periodo
            kwh_base_totales += kwh_base

            kwh_intermedio = 0
            arr_kwh_intermedio = relacion_tarifa_kwh_periodo[tarifa_id,'intermedio']
            for kwh_i in arr_kwh_intermedio:
                kwh_intermedio += kwh_i

            #Kwh_ Intermedio Totales del Periodo
            kwh_intermedio_totales += kwh_intermedio

            kwh_punta = 0
            arr_kwh_punta = relacion_tarifa_kwh_periodo[tarifa_id,'punta']
            for kwh_p in arr_kwh_punta:
                kwh_punta += kwh_p

            #kWh_ Punta Totales del Periodo
            kwh_punta_totales += kwh_punta

            #kWh totales
            kwh_totales_tarifa = kwh_base + kwh_intermedio + kwh_punta

            #kWh totales de un periodo dado.
            kwh_totales += kwh_totales_tarifa

            for lectura_id in relacion_tarifa_lectura[tarifa_id]:
                #Se obtiene la lectura
                lct = ElectricData.objects.get(id=lectura_id)

                if relacion_tarifa_lectura[tarifa_id][lectura_id] == 'base':
                    kw_base.append(lct.kW)
                elif relacion_tarifa_lectura[tarifa_id][lectura_id] == 'intermedio':
                    kw_intermedio.append(lct.kW)
                elif relacion_tarifa_lectura[tarifa_id][lectura_id] == 'punta':
                    kw_punta.append(lct.kW)


            #Se obtienen las demandas máximas de base, intermedio y punta
            demanda_kw_base = obtenerDemanda(kw_base)
            demanda_kw_intermedio = obtenerDemanda(kw_intermedio)
            demanda_kw_punta = obtenerDemanda(kw_punta)

            kw_base_totales += demanda_kw_base
            kw_intermedio_totales += demanda_kw_intermedio
            kw_punta_totales += demanda_kw_punta

            d_facturable = demandafacturable(demanda_kw_base,demanda_kw_intermedio,demanda_kw_punta,region,tarifa, lct.medition_date)
            demanda_facturable_total += d_facturable

            c_energia = costoenergia(kwh_base, kwh_intermedio, kwh_punta, region, tarifa, lct.medition_date)
            costo_energia_total += c_energia

            c_dfacturable = costodemandafacturable(d_facturable, region, tarifa, lct.medition_date)
            costo_demanda_facturable += c_dfacturable

            fp = factorpotencia(kwh_totales_tarifa, kwarh)
            factor_potencia_total += fp

            c_factorpotencia = costofactorpotencia(fp, c_energia, c_dfacturable)
            costo_factor_potencia += c_factorpotencia

            c_subtotal = obtenerSubtotal(c_energia, c_dfacturable, c_factorpotencia)
            subtotal_final += c_subtotal

            c_total = obtenerTotal(c_subtotal,16)
            total_final += c_total

            """
            print "KW Base:", demanda_kw_base
            print "KW Intermedio:", demanda_kw_intermedio
            print "KW Punta:", demanda_kw_punta
            print "KWh Base:", kwh_base
            print "KWh Intermedio:", kwh_intermedio
            print "KWh Punta:", kwh_punta
            print "Demanda Facturable:", d_facturable
            print "Factor Potencia:", fp
            print "Costo de Energia:", c_energia
            print "Costo de Demanda Facturable, c_dfacturable
            print "Costo de Factor Potencia:", c_factorpotencia
            print "Subtotal", c_subtotal
            print "Iva", obtenerIva(c_subtotal, 16)
            print "Total", c_total
            print "Termina una tarifa"

            """

        diccionario_final_cfe = {'costo_energia': costo_energia_total,
                                 'costo_dfacturable': costo_demanda_facturable,
                                 'costo_fpotencia': costo_factor_potencia,
                                 'subtotal': subtotal_final,
                                 'iva': obtenerIva(subtotal_final, 16),
                                 'total': total_final,
                                 'kw_base': kw_base_totales,
                                 'kw_intermedio': kw_intermedio_totales,
                                 'kw_punta': kw_punta_totales,
                                 'kwh_totales': kwh_totales,
                                 'kwh_base': kwh_base_totales,
                                 'kwh_intermedio': kwh_intermedio_totales,
                                 'kwh_punta': kwh_punta_totales,
                                 'demanda_facturable': demanda_facturable_total,
                                 'factor_potencia': factor_potencia_total / numero_tarifas,
                                 'tarifa_kwhb': tarifa_kwh_base / numero_tarifas,
                                 'tarifa_kwhi': tarifa_kwh_intermedio / numero_tarifas,
                                 'tarifa_kwhp': tarifa_kwh_punta / numero_tarifas}

    return diccionario_final_cfe