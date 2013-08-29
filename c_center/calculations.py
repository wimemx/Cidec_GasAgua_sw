# -*- coding: utf-8 -*-
# Create your views here.

#standard library imports
import pytz
import datetime
import json
from time import strftime
from math import *
from decimal import *
from calendar import monthrange

#related third party imports
from django.http import *
from django.db.models.aggregates import *
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

#local application/library specific imports
from c_center.models import *
from electric_rates.models import *

CATALOGO_GRUPOS = None
HOLYDAYS = None


def consumoAcumuladoKWH(consumer, fecha_inicio, fecha_fin):
    """ Gets the sum of the daily kWh in an interval

    :param consumer: ConsumerUnit Object
    :param fecha_inicio: Datetime
    :param fecha_fin: Datetime
    :return: the sum of the daily kWh for the interval
    """
    suma_lecturas = 0
    lecturas = DailyData.objects.filter(
        consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin).aggregate(
            Sum('KWH_total'))
    if lecturas:
        suma_lecturas = lecturas['KWH_total__sum']
    return suma_lecturas


def kvarhDiariosPeriodo(consumer, fecha_inicio, fecha_fin):
    """ Gets the sum of the daily kVArh in an interval

    :param consumer: ConsumerUnit Object
    :param fecha_inicio: Datetime
    :param fecha_fin: Datetime
    :return: the sum of the daily kVArh for the interval
    """
    kvarh = 0
    lecturas = DailyData.objects.filter(
        consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin).aggregate(
            Sum('KVARH'))
    if lecturas:
        kvarh = lecturas['KVARH__sum']
    return kvarh


def demandaMaxima(consumer, fecha_inicio, fecha_fin):
    """ Gets the max demand in a given interval

    :param consumer: ConsumerUnit object
    :param fecha_inicio: datetime
    :param fecha_fin: datetime
    :return: the max demand
    """
    demanda_max = 0
    lecturas = DailyData.objects.filter(consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin).order_by('-max_demand')
    if lecturas:
        demanda_max = lecturas[0].max_demand
    return demanda_max


def demandaMinima(consumer, fecha_inicio, fecha_fin):
    """ Gets the min demand in a given interval

    :param consumer: ConsumerUnit object
    :param fecha_inicio: datetime
    :param fecha_fin: datetime
    :return: the min demand
    """
    demanda_min = 0
    lecturas = DailyData.objects.filter(
        consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin).exclude(min_demand=0).order_by('min_demand')
    if lecturas:
        demanda_min = lecturas[0].min_demand
    return demanda_min


def promedioKW(consumer, fecha_inicio, fecha_fin):
    """ Gets the average demand in a given interval

    :param consumer: ConsumerUnit object
    :param fecha_inicio: datetime
    :param fecha_fin: datetime
    :return: average kW
    """
    suma_lecturas = DailyData.objects.filter(
        consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin).aggregate(Avg("max_demand"))

    return suma_lecturas['max_demand__avg'] if suma_lecturas['max_demand__avg'] else 0


def max_minKWH(consumer, fecha_inicio, fecha_fin, min_max):
    """ Gets the min or max values of ElectricDataTemp for consumer
    :param consumer: ConsumerUnit object
    :param fecha_inicio: datetime|date initial date
    :param fecha_fin: datetime|date final date
    :param min_max: string "min" to return the min TotalkWhIMPORT value
    :return: value
    """
    if min_max == "min":
        order = "KWH_total"
    else:
        order = "-KWH_total"
    val = 0
    lecturas = DailyData.objects.filter(
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin, KWH_total__gt=0,
        consumer_unit=consumer
    ).values('KWH_total').order_by(order)
    if lecturas:
        val = lecturas[0]['KWH_total']
    return val


def promedioKWH(consumer, fecha_inicio, fecha_fin):
    """Gets the average kWh between dates

    :param consumer: ConsumerUnit object
    :param fecha_inicio: Date
    :param fecha_fin: Date
    :return: KWH_total__avg
    """
    suma_lecturas = DailyData.objects.filter(
        consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin).aggregate(Avg('KWH_total'))
    return suma_lecturas['KWH_total__avg'] if suma_lecturas['KWH_total__avg'] else 0


def desviacionStandardKWH(consumer, fecha_inicio, fecha_fin):
    """Returns the standard deviation for the kWh

    :param consumer: ConsumerUnit object
    :param fecha_inicio: date
    :param fecha_fin: date
    :return: float standard deviation
    """
    suma = 0
    desviacion = 0
    lecturas = DailyData.objects.filter(
        consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin)
    if lecturas:
        promedio = promedioKWH(consumer, fecha_inicio, fecha_fin)
        nmenosuno = len(lecturas) - 1
        for kwh in lecturas:
            n_m = kwh.KWH_total - promedio
            suma += n_m ** 2
        if nmenosuno != 0:
            desviacion = sqrt(suma / nmenosuno)
    return desviacion


def medianaKWH(consumer, fecha_inicio, fecha_fin):
    """Gets and returns the kWh median in a period of time

    :param consumer: ConsumerUnit
    :param fecha_inicio: Date
    :param fecha_fin: Date
    :return: kWh median
    """
    mediana = 0
    lecturas = DailyData.objects.filter(
        consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin).order_by('KWH_total')
    if lecturas:
        longitud = len(lecturas)
        if longitud % 2 is 0:
            #Si es par
            mediana = (lecturas[longitud / 2].KWH_total + lecturas[
                      (longitud / 2) - 1].KWH_total) / 2
        else:
            #Si es impar
            mediana = lecturas[longitud / 2].KWH_total
    return mediana


def demandafacturable(kwbase, kwintermedio, kwpunta, fri, frb):
    """Gets the facturable demand given the following parameters

    :param kwbase: float
    :param kwintermedio: float
    :param kwpunta: float
    :param fri: float
    :param frb: float
    :return: int
    """
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
    """Gets and returns the energy cost

    :param kwbase: number
    :param kwintermedio: number
    :param kwpunta:  number
    :param tarifa_kwhb: number
    :param tarifa_kwhi: number
    :param tarifa_kwhp: number
    :return: number
    """
    costo_energia = kwbase * tarifa_kwhb + kwintermedio * tarifa_kwhi +\
                    kwpunta * tarifa_kwhp

    return costo_energia


def costodemandafacturable(demandaf, tarifa_demanda):
    """calculates the cost of the facturable demand

    :param demandaf: number
    :param tarifa_demanda: number
    :return: number
    """
    return demandaf * tarifa_demanda


def fpbonificacionrecargo(fp):
    """Calculates the bonifications for the power factor

    :param fp: float power factor
    :return: float
    """
    fp_valor = 0
    if fp != 0:
        if fp < 90:
            fp_valor = Decimal(str(3.0 / 5.0)) * (
                (Decimal(str(90.0)) / Decimal(str(fp))) - 1) * 100
        else:
            fp_valor = Decimal(str(1.0 / 4.0)) * (1 - (Decimal(str(90.0)) / Decimal(str(fp)))) * 100
    print "bonificacion", fp_valor
    return float(fp_valor)


def costofactorpotencia(fp, costo_energia, costo_df):
    """Returns the cost per power factor

    :param fp: float
    :param costo_energia: float
    :param costo_df:float
    :return: float
    """
    if fp < 90:
        costo_fp = float(
            (costo_energia + costo_df) / 100) * fpbonificacionrecargo(fp)
    else:
        costo_fp = float(
            (costo_energia + costo_df) / 100) * fpbonificacionrecargo(fp) * -1
    print "costo factor potencia en funcion", costo_fp
    return costo_fp


def obtenerSubtotal(costo_energia, costo_df, costo_fp):
    """Gets the subtotal for costo_energia, costo_df, costo_fp

    :param costo_energia: number
    :param costo_df: number
    :param costo_fp: number
    :return: float
    """
    return float(costo_energia) + float(costo_df) + float(costo_fp)


def obtenerIva(c_subtotal, iva):
    """Calculates the IVA

    :param c_subtotal: number
    :param iva: number
    :return: float
    """
    iva /= 100.0
    return float(c_subtotal) * float(iva)


def obtenerTotal(c_subtotal, iva):
    """Sums the total for c_subtotal, iva

    :param c_subtotal: number
    :param iva: number
    :return: number
    """
    iva = iva / 100.0 + 1
    return float(c_subtotal) * float(iva)


def factorpotencia(kwh, kvarh):
    """Calculates the powerfactor from the kwh and kvarh

    :param kwh: number
    :param kvarh: number
    :return: float
    """
    fp = 0
    if kwh is None:
        kwh = 0
    if kvarh is None:
        kvarh = 0
    if kwh != 0 or kvarh != 0:
        square_kwh = Decimal(str(pow(kwh, 2)))
        square_kvarh = Decimal(str(pow(kvarh, 2)))
        fp = (Decimal(str(kwh)) / Decimal(
            str(pow((square_kwh + square_kvarh), .5)))) * 100
        print "fp funcion factorpotencia", fp
    return float(fp)


def obtenerDemanda(arr_kw):
    """Obtains the demand

    :param arr_kw: number
    :return: int
    """
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
            print "obtenerDemanda - IndexError"
            demanda_maxima = 0
        except TypeError:
            print "obtenerDemanda - TypeError"
            demanda_maxima = 0

    return demanda_maxima


def obtenerFestivos(year):
    """Obtiene los dias festivos almacenados en la tabla Holidays.
    Regresa una lista con las fechas exactas de los dias festivos para este año

    :param year: The year of the holydays we want to obtain
    Ejemplo:
    1, 01 -> 1 de enero de 2012
    1-Lun, 02 = 1er Lunes de Febrero 2012 -> 6 de febrero de 2012
    """
    lista_festivos = []

    actual_year = year
    holidays = Holydays.objects.all().values('month', "day")

    lst_days = dict()
    lst_days['1'] = 'Lun'
    lst_days['2'] = 'Mar'
    lst_days['3'] = 'Mie'
    lst_days['4'] = 'Jue'
    lst_days['5'] = 'Vie'
    lst_days['6'] = 'Sab'
    lst_days['0'] = 'Dom'

    if holidays:
        for hday in holidays:
            f_var = hday['day'].split('-')
            if len(f_var) > 1:
                dia_mes = 1
                ahorita = 1
                n_day = f_var[0]
                w_day = f_var[1]
                month_days = monthrange(actual_year, hday['month'])
                while dia_mes < month_days[1] - 1:
                    #st_time = time.strptime("%02d" % (c_day)+" "+"%02d" % (
                    # mes)+" "+str(actual_year), "%d %m %Y")
                    st_time = time.strptime(
                        "%02d" % dia_mes + " " + "%02d" % (
                            hday['month']) + " " + str(actual_year), "%d %m %Y")
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
                if int(hday['day']) == 1 and int(hday['month']) == 12:
                    if (actual_year - 1946) % 6 == 0:
                        st_time = time.strptime(
                            "%02d" % int(hday['day']) + " " + "%02d" % int(
                                hday['month']) + " " + str(actual_year),
                            "%d %m %Y")
                        lista_festivos.append(strftime("%d %m %Y", st_time))
                else:
                    st_time = time.strptime(
                        "%02d" % int(hday['day']) + " " + "%02d" % int(
                            hday['month']) + " " + str(actual_year), "%d %m %Y")
                    lista_festivos.append(strftime("%d %m %Y", st_time))

    return lista_festivos


def obtenerCatalogoGrupos():
    """Se regresa un catálogo que indica a qué grupo pertenece cada día de la
    semana.
    """
    group_days_bd = Groupdays.objects.all().values(
        "pk",
        "sunday",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "holydays")
    group_days = {}

    if group_days_bd:
        for g_days in group_days_bd:
            if g_days['sunday']:
                group_days[0] = g_days["pk"]
            if g_days['monday']:
                group_days[1] = g_days["pk"]
            if g_days['tuesday']:
                group_days[2] = g_days["pk"]
            if g_days['wednesday']:
                group_days[3] = g_days["pk"]
            if g_days['thursday']:
                group_days[4] = g_days["pk"]
            if g_days['friday']:
                group_days[5] = g_days["pk"]
            if g_days['saturday']:
                group_days[6] = g_days["pk"]
            if g_days['holydays']:
                group_days[7] = g_days["pk"]

    return group_days


def obtenerGrupo(catalogo_grupos, fecha):
    """A partir de una fecha, se obtiene a qué grupo de días pertenece: Lun a
    Vie, Sab o Dom y Festivos
    :param catalogo_grupos: array of days
    :param fecha: date
    """
    if HOLYDAYS is None:
        global HOLYDAYS
        HOLYDAYS = obtenerFestivos(fecha.year)
        dias_festivos = HOLYDAYS
    else:
        dias_festivos = HOLYDAYS
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

    :param fecha: Datetime
    :param region: Region object
    :param tarifa: Tarifa Object
    :param catalogo_grupos: array
    """

    grupo_id = obtenerGrupo(catalogo_grupos, fecha)
    horario_ver_inv = DateIntervals.objects.filter(
        date_init__lte=datetime.date(fecha.year,
                                     fecha.month,
                                     fecha.day),
        date_end__gte=datetime.date(fecha.year,
                                    fecha.month,
                                    fecha.day)).values_list("pk", flat=True)

    electric_type = ElectricRatesPeriods.objects.filter(region=region).filter(
        electric_rate=tarifa,
        date_interval__in=horario_ver_inv,
        groupdays=grupo_id,
        time_init__lte=datetime.time(fecha.hour, fecha.minute),
        time_end__gte=datetime.time(fecha.hour, fecha.minute)
    ).values("period_type")

    return electric_type[0]['period_type']


def obtenerTipoPeriodoObj(fecha, region):
    """
    Se obtiene el tipo de periodo de una lectura, en base a la fecha y hora
    en que fue tomada, región y tarifa.

    :param fecha: Datetime
    :param region: Region Object
    """
    if CATALOGO_GRUPOS is None:
        global CATALOGO_GRUPOS
        CATALOGO_GRUPOS = obtenerCatalogoGrupos()
        catalogo_grupos = CATALOGO_GRUPOS
    else:
        catalogo_grupos = CATALOGO_GRUPOS
    grupo_id = obtenerGrupo(catalogo_grupos, fecha)
    horario_ver_inv = DateIntervals.objects.filter(
        date_init__lte=datetime.date(fecha.year,
                                     fecha.month,
                                     fecha.day),
        date_end__gte=datetime.date(fecha.year,
                                    fecha.month,
                                    fecha.day)).values_list("pk", flat=True)

    electric_type = ElectricRatesPeriods.objects.filter(
        region=region,
        date_interval__in=horario_ver_inv,
        groupdays=grupo_id, time_init__lte=fecha, time_end__gt=fecha).values(
            "pk", "period_type")[:1]

    return electric_type[0]


def obtenerHorarioVeranoInvierno(fecha, tarifa_id):
    """Checks if the date is DST for a electric rate

    :param fecha: datetime
    :param tarifa_id: Tarifa Object
    :return:
    """
    horario = DateIntervals.objects.filter(
        date_init__lte=datetime.date(fecha.year, fecha.month,
            fecha.day)).filter(
        date_end__gte=datetime.date(fecha.year, fecha.month, fecha.day)).\
            filter(electric_rate=tarifa_id)
    return horario[0]


def get_time_saving_type(request):
    """Returns a JSON containing DST info

    :param request: request object with ie_id key in GET
    :return:HttpResponse a JSON :raise: Http404
    """
    if "ie_id" in request.GET:
        try:
            ie_id = request.GET['ie_id']
        except ValueError:
            raise Http404
        else:
            ie = get_object_or_404(IndustrialEquipment, pk=ie_id)
            electric_rate = ie.building.electric_rate.pk
            time_saving = obtenerHorarioVeranoInvierno(datetime.date.today(),
                                                       electric_rate)
            if time_saving.interval_period == 1:
                time_saving = 'Verano'
            else:
                time_saving = 'Invierno'
            time_saving = dict(time_saving=time_saving.interval_period)
            return HttpResponse(content=json.dumps(time_saving),
                                status=200,
                                mimetype="application/json")
    else:
        raise Http404


def obtenerKWhNetosTarifa(pr_powermeter, tarifa_id):
    """Obtains total kWh

    :param pr_powermeter: ProfilePowermeter object
    :param tarifa_id: int Tarifa id
    :return: float kwh_netos
    """
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


def obtenerKVARH_total(pr_powermeter, start_date, end_date):
    """Obtains total kVAh

    :param pr_powermeter: ProfilePowermeter object
    :param start_date: datetime
    :param end_date: datetime
    :return: float kVAh
    """
    kvarh_netos = 0
    lecturasObj = ElectricDataTemp.objects.filter(
        profile_powermeter__powermeter=pr_powermeter,
        medition_date__gte=start_date,
        medition_date__lt=end_date).order_by('medition_date').values(
            "TotalkvarhIMPORT")
    if lecturasObj:
        total_lecturas = len(lecturasObj)
        kvarh_inicial = lecturasObj[0]['TotalkvarhIMPORT']
        kvarh_final = lecturasObj[total_lecturas - 1]['TotalkvarhIMPORT']
        kvarh_netos = kvarh_final - kvarh_inicial

    return int(ceil(kvarh_netos))


def obtenerKVARH(profile_powermeter, start_date, end_date):
    """Obtains kVArh in a given timeframe for a profile_powermeter

    :param profile_powermeter: ProfilePowermeter object
    :param start_date: datetime
    :param end_date: datetime
    :return: float
    """
    kvarh_netos = 0
    lecturasObj = ElectricDataTemp.objects.filter(
        profile_powermeter=profile_powermeter,
        medition_date__gte=start_date,
        medition_date__lt=end_date).order_by('medition_date').values(
            "TotalkvarhIMPORT", "medition_date")
    if lecturasObj:
        total_lecturas = len(lecturasObj)
        kvarh_inicial = lecturasObj[0]['TotalkvarhIMPORT']
        kvarh_final = lecturasObj[total_lecturas - 1]['TotalkvarhIMPORT']
        ultima_fecha = lecturasObj[total_lecturas - 1]['medition_date']

        #Se obtiene la siguiente lectura
        nextReading = ElectricDataTemp.objects.filter(
            profile_powermeter=profile_powermeter,
            medition_date__gt=ultima_fecha).order_by('medition_date').values(
                "medition_date", "TotalkvarhIMPORT")

        #Se revisa que la siguiente lectura sea menor a 10 min.
        tenmin_delta = datetime.timedelta(minutes=10)

        if nextReading:
            if nextReading[0]['medition_date'] < (ultima_fecha + tenmin_delta):
                kvarh_final = nextReading[0]['TotalkvarhIMPORT']

        kvarh_netos = kvarh_final - kvarh_inicial

    return int(ceil(kvarh_netos))


def obtenerKVARH_dia(profile_powermeter, start_date, end_date, kvarh_anterior):
    """Obtains the total kVArh for a day

    :param profile_powermeter:
    :param start_date:
    :param end_date:
    :param kvarh_anterior:
    :return:
    """
    kvarh_netos = 0
    lecturasObj = ElectricDataTemp.objects.filter(
        profile_powermeter=profile_powermeter,
        medition_date__gte=start_date,
        medition_date__lt=end_date).order_by('medition_date').values(
            "TotalkvarhIMPORT", "pk")
    if lecturasObj:
        total_lecturas = len(lecturasObj)
        #Obtengo la primer lectura
        kvarh_inicial = lecturasObj[0]["TotalkvarhIMPORT"]
        kvarh_final = lecturasObj[total_lecturas - 1]["TotalkvarhIMPORT"]

        #Se verifica el kvarh_anterior
        if kvarh_anterior:
            #Se obtiene la siguiente lectura
            last_id = lecturasObj[total_lecturas - 1]["pk"]
            siguiente_lectura = ElectricDataTemp.objects.filter(
                profile_powermeter=profile_powermeter, pk__gt=last_id
            ).order_by('medition_date').values("TotalkvarhIMPORT")[:1]
            if siguiente_lectura:
                kvarh_final = siguiente_lectura[0]['TotalkvarhIMPORT']

        kvarh_netos = kvarh_final - kvarh_inicial

    return int(ceil(kvarh_netos))


def obtenerDemanda_kw_valores(valores_kw):
    """ Obtains the max emand from triplets of values

    :param valores_kw: values
    :return: int max demand
    """
    demanda_maxima = 0
    if valores_kw:
        try:
            longitud = len(valores_kw)
            if longitud >= 3:
                low = valores_kw[0]
                middle = valores_kw[0]
                high = valores_kw[0]
                demanda_maxima = (low + middle + high) / 3
                for indice in range(3, longitud):
                    low, middle = middle, high
                    high = valores_kw[indice]
                    prom = (low + middle + high) / 3
                    if prom > demanda_maxima:
                        demanda_maxima = prom
            else:
                demanda_maxima = 0

        except IndexError:
            print "obtenerDemanda_kw_valores - IndexError"
            demanda_maxima = 0
        except TypeError:
            print "obtenerDemanda_kw_valores - TypeError"
            demanda_maxima = 0
    return int(ceil(demanda_maxima))


def obtenerDemandaMin_kw(lecturas_kw):
    """Obtains the min emand from triplets of values

    :param lecturas_kw: values
    :return: int min demand
    """
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
            print "obtenerDemandaMin_kw - IndexError"
            demanda_min = 0
        except TypeError:
            print "obtenerDemandaMin_kw - TypeError"
            demanda_min = 0
    return int(ceil(demanda_min))


@csrf_exempt
def tag_reading(request):
    """Service to tag electric data

    :param request: request object via POST with id_reading key
    :return:
    """
    if request.method == 'POST':
        #Obtiene el Id de la medicion
        reading_id = request.REQUEST.get("id_reading", "")
        if reading_id:
            daytag_reading(reading_id)
        return HttpResponse(content='', content_type=None, status=200)
    return HttpResponse(content='', content_type=None, status=404)


def daytag_reading(reading_id):
    """Tag the readings. Separate days
    :param reading_id: id of ElectricDataTemp
    """
    try:
        readingObj = ElectricDataTemp.objects.get(id=reading_id)
        #Si la lectura proviene de cualquier medidor menos del No Asignado
        if readingObj.profile_powermeter.pk != 4:
            #Se obtiene el Consumer Unit, para poder obtener el edificio, una
            # vez obtenido el edificio, se puede obtener la region y la tarifa

            #Se revisa que esa medición no este etiquetada. Si es así, la borra
            tagged_reading = ElectricDataTags.objects.filter(
                electric_data=readingObj)
            if tagged_reading:
                tagged_reading.delete()

            consumerUnitObj = ConsumerUnit.objects.filter(
                profile_powermeter=readingObj.profile_powermeter).values(
                    "building__pk")

            if consumerUnitObj:
                buildingObj = Building.objects.get(
                    id=consumerUnitObj[0]["building__pk"])

                #La hora de la medicion (UTC) se convierte a hora local
                fecha_zhor = readingObj.medition_date.astimezone(
                    tz=timezone.get_current_timezone())
                #Obtiene el periodo de la lectura actual
                reading_period_type = obtenerTipoPeriodoObj(fecha_zhor,
                                                            buildingObj.region)

                #Obtiene las ultimas lecturas de ese medidor
                last_reading = ElectricDataTags.objects.filter(
                    electric_data__profile_powermeter=
                    readingObj.profile_powermeter,
                    electric_data__medition_date__lt=
                    readingObj.medition_date).order_by(
                        "-electric_data__medition_date"
                    ).values(
                        "electric_data__medition_date",
                        "electric_rates_periods__period_type",
                        "identifier")[:1]

                #Si existen registros para ese medidor
                if last_reading:
                    #Se revisa la hora local de la ultima lectura.
                    #Si la lectura es de un día nuevo,
                    # el identificador se reinicia a 1

                    fecha_anterior = last_reading[0]\
                        ["electric_data__medition_date"].astimezone(
                            tz=timezone.get_current_timezone())

                    if fecha_anterior.hour == 23 and fecha_zhor.hour == 0:
                        tag = 1
                    else:
                        #Obtiene el periodo de la ultima lectura de ese medidor
                        last_reading_type = last_reading[0]\
                            ["electric_rates_periods__period_type"]

                        #    Se compara el periodo actual con el periodo del
                        # ultimo registro.
                        #    Si los periodos son iguales, el identificador
                        # será el mismo

                        if reading_period_type['period_type'] == \
                                last_reading_type:
                            tag = last_reading[0]["identifier"]
                        else:
                            #Si los periodos son diferentes al identificador
                            # anterior, se le sumara 1.
                            tag = int(last_reading[0]['identifier']) + 1
                #Si será un registro para un nuevo medidor
                else:
                    tag = 1

                #Guarda el registro etiquetado
                period_type = ElectricRatesPeriods.objects.get(
                    pk=reading_period_type["pk"])
                newTaggedReading = ElectricDataTags(
                    electric_rates_periods=period_type,
                    electric_data=readingObj,
                    identifier=str(tag)
                )
                newTaggedReading.save()

                return True
        return False
    except ObjectDoesNotExist:
        return False


def daytag_day(day, profile_powermeter):
    """Tags a whole day

    :param day: Date
    :param profile_powermeter: Profile Powermeter Object
    """
    next_day = day + datetime.timedelta(days=1)

    #Se obtienen todas las lecturas para ese profile powermeter

    readings = ElectricDataTemp.objects.filter(
        profile_powermeter=profile_powermeter, medition_date__gte=day,
        medition_date__lt=next_day).order_by('pk')

    for rd in readings:
        daytag_reading(rd.pk)

    print "Tags Per Day - Done"


def daytag_month(month, year, profile_powermeter):
    """Tags a whole month

    :param month: the month to tag
    :param year: the year of the month
    :param profile_powermeter: ProfilePowermeter object
    """
    num_days_arr = monthrange(year, month)

    actual_day = datetime.datetime(year, month, 1)

    day_delta = datetime.timedelta(days=1)

    no_dia =  0
    while no_dia < num_days_arr[1]:
        daytag_day(actual_day,profile_powermeter)
        actual_day = actual_day + day_delta
        no_dia += 1

    print "Tags month: " + str(month) + " - Done"


def daytag_period(actual_day, end_day, profile_powermeter):
    """generates and save tags for a period

    :param actual_day: date
    :param end_day: date
    :param profile_powermeter: ProfilePowermeter object
    """
    ElectricDataTags.objects.filter(
        electric_data__profile_powermeter=profile_powermeter,
        electric_data__medition_date__gte=actual_day,
        electric_data__medition_date__lte=end_day).delete()
    day_delta = datetime.timedelta(days=1)

    while actual_day <= end_day:
        daytag_day(actual_day,profile_powermeter)
        actual_day = actual_day + day_delta

    print "Tags for Period - Done"


def daytag_period_allProfilePowermeters(start_day, end_day):
    """tags all the meditions for a given interval

    :param start_day: date
    :param end_day: date
    """
    #Se obtienen los perfiles
    all_profiles = ProfilePowermeter.objects.all()
    for profile in all_profiles:
        daytag_period(start_day, end_day, profile)

    print "All ProfilePowermeters - Day Tag Done"


def getKWHSimplePerDay(s_date, e_date, profile_powermeter):
    """Gets the kWh for a profile_powermeter in a time frame

    :param s_date: datetime
    :param e_date: datetime
    :param profile_powermeter: ProfilePowermeter object
    :return: int total kWh
    """
    kwh_netos = 0

    #Se obtienen los kwh de ese periodo de tiempo.
    kwh_lecturas = ElectricDataTemp.objects.filter(
        profile_powermeter=profile_powermeter,
        medition_date__gte=s_date,
        medition_date__lt=e_date).order_by('medition_date').values(
            "TotalkWhIMPORT")
    total_lecturas = kwh_lecturas.count()

    if kwh_lecturas:
        kwh_inicial = kwh_lecturas[0]['TotalkWhIMPORT']
        kwh_final = kwh_lecturas[total_lecturas - 1]['TotalkWhIMPORT']

        kwh_netos = int(ceil(kwh_final - kwh_inicial))

    return kwh_netos


def getKWHperDay(s_date, e_date, profile_powermeter):
    """ get the kWh for a day, for a profile_powermeter

    :param s_date: Date
    :param e_date: Date
    :param profile_powermeter: ProfilePowermeter object
    :return: int
    """
    kwh_container = dict()
    kwh_container['base'] = 0
    kwh_container['intermedio'] = 0
    kwh_container['punta'] = 0

    #KWH
    #Se obtienen todos los identificadores para los KWH
    lecturas_identificadores = ElectricDataTags.objects.filter(
        electric_data__profile_powermeter = profile_powermeter,
        electric_data__medition_date__gte=s_date,
        electric_data__medition_date__lt=e_date).order_by(
            "electric_data__medition_date").values("identifier").annotate(
                Count("identifier"))

    if lecturas_identificadores:
        ultima_lectura = 0
        ultima_fecha = None
        #ultimo_id = None
        kwh_por_periodo = []

        for lectura in lecturas_identificadores:

            electric_info = ElectricDataTags.objects.filter(
                identifier=lectura["identifier"],
                electric_data__profile_powermeter=profile_powermeter,
                electric_data__medition_date__gte=s_date,
                electric_data__medition_date__lt=e_date).order_by(
                    "electric_data__medition_date"
                ).values(
                    "electric_data__TotalkWhIMPORT",
                    "electric_data__medition_date",
                    "electric_rates_periods__period_type"
                )

            num_lecturas = len(electric_info)

            primer_lectura = electric_info[0]['electric_data__TotalkWhIMPORT']
            ultima_lectura = electric_info[
                             num_lecturas - 1]['electric_data__TotalkWhIMPORT']
            ultima_fecha = electric_info[
                           num_lecturas - 1]['electric_data__medition_date']


            #Obtener el tipo de periodo: Base, punta, intermedio
            tipo_periodo = electric_info[
                           0]['electric_rates_periods__period_type']
            t = primer_lectura, tipo_periodo
            kwh_por_periodo.append(t)

        nextReading = ElectricDataTemp.objects.filter(
            profile_powermeter=profile_powermeter,
            medition_date__gt=ultima_fecha).order_by('medition_date').values(
                "medition_date",
                "TotalkWhIMPORT"
            )[:1]

        #Se revisa que la siguiente lectura sea menor a 10 min.
        tenmin_delta = datetime.timedelta(minutes=10)

        if nextReading:
            if nextReading[0]["medition_date"] < (ultima_fecha + tenmin_delta):
                ultima_lectura = nextReading[0]['TotalkWhIMPORT']

        kwh_periodo_long = len(kwh_por_periodo)

        kwh_base = 0
        kwh_intermedio = 0
        kwh_punta = 0

        for idx, kwh_p in enumerate(kwh_por_periodo):
            inicial = kwh_p[0]
            periodo_t = kwh_p[1]
            if idx + 1 <= kwh_periodo_long - 1:
                kwh_p2 = kwh_por_periodo[idx + 1]
                final = kwh_p2[0]
            else:
                final = ultima_lectura

            kwh_netos = final - inicial

            if periodo_t == 'base':
                kwh_base += kwh_netos
            elif periodo_t == 'intermedio':
                kwh_intermedio += kwh_netos
            elif periodo_t == 'punta':
                kwh_punta += kwh_netos

        kwh_container['base'] = int(ceil(kwh_base))
        kwh_container['intermedio'] = int(ceil(kwh_intermedio))
        kwh_container['punta'] = int(ceil(kwh_punta))

    return kwh_container


def getKWperDay(s_date, e_date, profile_powermeter):
    """Gets all the kWh in base, intermediate, and peak

    :param s_date: Datetime
    :param e_date: Datetime
    :param profile_powermeter: ProfilePowermeter object
    :return: dict kw_container
    """
    kw_container = dict()
    kw_container['base'] = 0
    kw_container['intermedio'] = 0
    kw_container['punta'] = 0

    lecturas_base = ElectricDataTags.objects.filter(
        electric_data__profile_powermeter=profile_powermeter).\
    filter(electric_data__medition_date__gte=s_date).filter(
        electric_data__medition_date__lt=e_date).\
    filter(electric_rates_periods__period_type='base').\
    aggregate(Max('electric_data__kW_import_sliding_window_demand'))

    kw_container['base'] = lecturas_base['electric_data__kW_import_sliding_window_demand__max']


    lecturas_intermedio = ElectricDataTags.objects.filter(
        electric_data__profile_powermeter=profile_powermeter).\
    filter(electric_data__medition_date__gte=s_date).filter(
        electric_data__medition_date__lt=e_date).\
    filter(
        electric_rates_periods__period_type='intermedio').\
    aggregate(Max('electric_data__kW_import_sliding_window_demand'))

    kw_container['intermedio'] = lecturas_intermedio['electric_data__kW_import_sliding_window_demand__max']

    lecturas_punta = ElectricDataTags.objects.filter(
        electric_data__profile_powermeter=profile_powermeter).\
    filter(electric_data__medition_date__gte=s_date).filter(
        electric_data__medition_date__lt=e_date).\
    filter(electric_rates_periods__period_type='punta').\
    aggregate(Max('electric_data__kW_import_sliding_window_demand'))

    kw_container['punta'] = lecturas_punta['electric_data__kW_import_sliding_window_demand__max']

    return kw_container
