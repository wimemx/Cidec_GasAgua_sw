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
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

#local application/library specific imports
from c_center.models import *
from electric_rates.models import *


def consumoAcumuladoKWH(consumer, fecha_inicio, fecha_fin):
    suma_lecturas = 0
    lecturas = DailyData.objects.filter(consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin).aggregate(
        Sum('KWH_total'))
    if lecturas:
        suma_lecturas = lecturas['KWH_total__sum']
    return suma_lecturas


def demandaMaxima(consumer, fecha_inicio, fecha_fin):
    demanda_max = 0
    lecturas = DailyData.objects.filter(consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin).order_by('-max_demand')
    if lecturas:
        demanda_max = lecturas[0].max_demand
    return demanda_max


def demandaMinima(consumer, fecha_inicio, fecha_fin):
    demanda_min = 0
    lecturas = DailyData.objects.filter(
        consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin).exclude(min_demand=0).order_by('min_demand')
    if lecturas:
        demanda_min = lecturas[0].min_demand
    return demanda_min


def promedioKW(consumer, fecha_inicio, fecha_fin):
    suma_lecturas = ElectricDataTemp.objects.filter(
        profile_powermeter=consumer.profile_powermeter,
        medition_date__gte=fecha_inicio,
        medition_date__lte=fecha_fin).aggregate(Avg('kW'))
    return suma_lecturas['kW__avg'] if suma_lecturas['kW__avg'] else 0


def max_minKWH(consumer, fecha_inicio, fecha_fin, min_max):
    """ Gets the min or max values of ElectricDataTemp for consumer
    :param consumer: ConsumerUnit object
    :param fecha_inicio: datetime|date initial date
    :param fecha_fin: datetime|date final date
    :param min_max: string "min" to return the min TotalkWhIMPORT value
    :return:
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
    suma_lecturas = DailyData.objects.filter(
        consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin).aggregate(Avg('KWH_total'))
    return suma_lecturas['KWH_total__avg'] if suma_lecturas['KWH_total__avg'] else 0


def desviacionStandardKWH(consumer, fecha_inicio, fecha_fin):
    suma = 0
    desviacion = 0
    lecturas = DailyData.objects.filter(consumer_unit=consumer,
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
    mediana = 0
    lecturas = DailyData.objects.filter(consumer_unit=consumer,
        data_day__gte=fecha_inicio,
        data_day__lte=fecha_fin).order_by(
        'KWH_total')
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
    costo_energia = kwbase * tarifa_kwhb + kwintermedio * tarifa_kwhi +\
                    kwpunta * tarifa_kwhp

    return costo_energia


def costodemandafacturable(demandaf, tarifa_demanda):
    return demandaf * tarifa_demanda


def fpbonificacionrecargo(fp):
    fp_valor = 0
    if fp != 0:
        if fp < 90:
            fp_valor = Decimal(str(3.0 / 5.0)) * (
                (Decimal(str(90.0)) / Decimal(str(fp))) - 1) * 100
        else:
            fp_valor = Decimal(str(1.0 / 4.0)) * (
                1 - (Decimal(str(90.0)) / Decimal(str(fp)))) * 100

    return float(fp_valor)


def costofactorpotencia(fp, costo_energia, costo_df):
    if fp < 90:
        costo_fp = float(
            (costo_energia + costo_df) / 100) * fpbonificacionrecargo(fp)
    else:
        costo_fp = float(
            (costo_energia + costo_df) / 100) * fpbonificacionrecargo(fp) * -1

    return costo_fp


def obtenerSubtotal(costo_energia, costo_df, costo_fp):
    return float(costo_energia) + float(costo_df) + float(costo_fp)


def obtenerIva(c_subtotal, iva):
    iva /= 100.0
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
    return float(fp)


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
            f_var = hday.day.split('-')
            if len(f_var) > 1:
                dia_mes = 1
                ahorita = 1
                n_day = f_var[0]
                w_day = f_var[1]
                month_days = monthrange(actual_year, hday.month)
                while dia_mes < month_days[1] - 1:
                    #st_time = time.strptime("%02d" % (c_day)+" "+"%02d" % (
                    # mes)+" "+str(actual_year), "%d %m %Y")
                    st_time = time.strptime(
                        "%02d" % dia_mes + " " + "%02d" % (
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
    A partir de una fecha, se obtiene a qué grupo de días pertenece: Lun a
    Vie, Sab o Dom y Festivos

    """
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
            fecha.day))]
            #.filter(region = region)

    electric_type = ElectricRatesPeriods.objects.filter(region=region).filter(
        date_interval__in=horario_ver_inv).filter(groupdays=grupo_id).filter(
        Q(time_init__lte=fecha), Q(
            time_end__gt=fecha))

    return electric_type[0]


def obtenerHorarioVeranoInvierno(fecha, tarifa_id):
    horario = DateIntervals.objects.filter(
        date_init__lte=datetime.date(fecha.year, fecha.month,
            fecha.day)).filter(
        date_end__gte=datetime.date(fecha.year, fecha.month, fecha.day)).\
            filter(electric_rate=tarifa_id)
    return horario[0]


def get_time_saving_type(request):
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
        ultima_fecha = lecturasObj[total_lecturas - 1].medition_date

        #Se obtiene la siguiente lectura
        nextReading = ElectricDataTemp.objects.filter(
            profile_powermeter=profile_powermeter,
            medition_date__gt = ultima_fecha)\
        .order_by('medition_date')

        #Se revisa que la siguiente lectura sea menor a 10 min.
        tenmin_delta = datetime.timedelta(minutes=10)

        if nextReading:
            if nextReading[0].medition_date < (ultima_fecha + tenmin_delta):
                kvarh_final = nextReading[0].TotalkvarhIMPORT

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
            last_id = lecturasObj[total_lecturas - 1].id
            siguiente_lectura = ElectricDataTemp.objects.filter(
                profile_powermeter=profile_powermeter, pk__gt=last_id).\
                    order_by('medition_date')
            if siguiente_lectura:
                #print "Id:", siguiente_lectura[0].id
                kvarh_final = siguiente_lectura[0].TotalkvarhIMPORT

        #print "1er KVARH", kvarh_inicial
        #print "2da KVARH", kvarh_final
        kvarh_netos = kvarh_final - kvarh_inicial

    return int(ceil(kvarh_netos))

def obtenerDemanda_kw_valores(valores_kw):
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
            print "IndexError"
            demanda_maxima = 0
        except TypeError:
            print "TypeError"
            demanda_maxima = 0
    return int(ceil(demanda_maxima))


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

@csrf_exempt
def tag_reading(request):
    if request.method == 'POST':
        #Obtiene el Id de la medicion
        reading_id = request.REQUEST.get("id_reading", "")
        if reading_id:
            daytag_reading(reading_id)
        return HttpResponse(content='', content_type=None, status=200)
    return HttpResponse(content='', content_type=None, status=404)


def daytag_reading(reading_id):
    """
        Tag the readings. Separate days
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
                profile_powermeter=readingObj.profile_powermeter)

            if consumerUnitObj:
                buildingObj = Building.objects.get(
                    id=consumerUnitObj[0].building.id)

                #La hora de la medicion (UTC) se convierte a hora local
                fecha_zhor = readingObj.medition_date.astimezone(
                    tz=timezone.get_current_timezone())
                #Obtiene el periodo de la lectura actual
                reading_period_type = obtenerTipoPeriodoObj(fecha_zhor,
                                                            buildingObj.region)

                #Obtiene las ultimas lecturas de ese medidor
                last_reading = ElectricDataTags.objects.filter(
                    electric_data__profile_powermeter=readingObj.profile_powermeter,
                    electric_data__medition_date__lt = readingObj.medition_date).\
                order_by("-electric_data__medition_date")

                #Si existen registros para ese medidor
                if last_reading:
                    #Se revisa la hora local de la ultima lectura.
                    #Si la lectura es de un día nuevo, el identificador se reinicia a 1

                    fecha_anterior = last_reading[0].electric_data.medition_date.\
                    astimezone(tz=timezone.get_current_timezone())

                    if fecha_anterior.hour == 23 and fecha_zhor.hour == 0:
                        tag = 1
                    else:
                        #Obtiene el periodo de la ultima lectura de ese medidor
                        last_reading_type = last_reading[0].\
                        electric_rates_periods.period_type

                        #    Se compara el periodo actual con el periodo del ultimo registro.
                        #    Si los periodos son iguales, el identificador será el mismo

                        if reading_period_type.period_type == last_reading_type:
                            tag = last_reading[0].identifier
                        else:
                            #Si los periodos son diferentes, al identificador anterior,
                            # se le sumara 1.
                            tag = int(last_reading[0].identifier) + 1

                else: #Si será un registro para un nuevo medidor
                    tag = 1

                #Guarda el registro etiquetado
                newTaggedReading = ElectricDataTags(
                    electric_rates_periods=reading_period_type,
                    electric_data=readingObj,
                    identifier=str(tag)
                )
                newTaggedReading.save()

                return True
        return False
    except ObjectDoesNotExist:
        return False

def daytag_day(day, profile_powermeter):

    next_day = day + datetime.timedelta(days=1)

    #Se obtienen todas las lecturas para ese profile powermeter

    readings =  ElectricDataTemp.objects.filter(
        profile_powermeter=profile_powermeter, medition_date__gte=day,
        medition_date__lt=next_day).\
    order_by('pk')

    for rd in readings:
        daytag_reading(rd.pk)

    print "Tags Per Day - Done"


def daytag_month(month, year, profile_powermeter):
    num_days_arr = monthrange(year, month)

    actual_day = datetime.datetime(year,month,1)

    day_delta = datetime.timedelta(days=1)

    no_dia =  0
    while no_dia < num_days_arr[1]:
        daytag_day(actual_day,profile_powermeter)
        actual_day = actual_day + day_delta
        no_dia += 1

    print "Tags month: " + str(month) +" - Done"


def daytag_period(actual_day, end_day, profile_powermeter):

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
    #Se obtienen los perfiles
    all_profiles = ProfilePowermeter.objects.all()
    for profile in all_profiles:
        daytag_period(start_day, end_day, profile)

    print "All ProfilePowermeters - Day Tag Done"

def getKWHSimplePerDay(s_date, e_date, profile_powermeter):
    kwh_netos = 0

    #Se obtienen los kwh de ese periodo de tiempo.
    kwh_lecturas = ElectricDataTemp.objects.filter(
        profile_powermeter=profile_powermeter).\
    filter(medition_date__gte=s_date).filter(
        medition_date__lt=e_date).\
    order_by('medition_date')
    total_lecturas = len(kwh_lecturas)

    if kwh_lecturas:
        #print "Profile",
        # kwh_lecturas[0].profile_powermeter_id
        #print "Primer Lectura",
        # kwh_lecturas[0].id, "-", kwh_lecturas[0].medition_date
        #print "Ultima Lectura", kwh_lecturas[total_lecturas - 1].id,
        # "-", kwh_lecturas[total_lecturas - 1].medition_date
        kwh_inicial = kwh_lecturas[0].TotalkWhIMPORT
        kwh_final = kwh_lecturas[total_lecturas - 1].TotalkWhIMPORT

        kwh_netos = int(ceil(kwh_final - kwh_inicial))

    return kwh_netos

def getKWHperDay(s_date, e_date, profile_powermeter):

    kwh_container = dict()
    kwh_container['base'] = 0
    kwh_container['intermedio'] = 0
    kwh_container['punta'] = 0

    #KWH
    #Se obtienen todos los identificadores para los KWH
    lecturas_identificadores = ElectricDataTags.objects\
    .filter(
        electric_data__profile_powermeter = profile_powermeter).\
    filter(electric_data__medition_date__gte=s_date).filter(
        electric_data__medition_date__lt=e_date).\
    order_by("electric_data__medition_date").values(
        "identifier").annotate(Count("identifier"))

    if lecturas_identificadores:
        ultima_lectura = 0
        ultima_fecha = None
        #ultimo_id = None
        kwh_por_periodo = []

        for lectura in lecturas_identificadores:

            electric_info = ElectricDataTags.objects.filter(
                identifier=lectura["identifier"]).\
            filter(
                electric_data__profile_powermeter=profile_powermeter).\
            filter(
                electric_data__medition_date__gte=s_date
            ).filter(electric_data__medition_date__lt=e_date).\
            order_by("electric_data__medition_date")

            num_lecturas = len(electric_info)

            primer_lectura = electric_info[0].electric_data.TotalkWhIMPORT
            ultima_lectura = electric_info[
                             num_lecturas - 1].electric_data.TotalkWhIMPORT
            ultima_fecha = electric_info[
                           num_lecturas - 1].electric_data.medition_date

            """
            print electric_info[0].electric_data.pk,"-",\
            electric_info[0].electric_data.medition_date,"Primer Lectura:", \
                primer_lectura,"-", \
                electric_info[num_lecturas-1].electric_data.pk,"-",\
            electric_info[num_lecturas-1].electric_data.medition_date, \
                " Ultima Lectura:",ultima_lectura
            """

            #Obtener el tipo de periodo: Base, punta, intermedio
            tipo_periodo = electric_info[
                           0].electric_rates_periods.period_type
            t = primer_lectura, tipo_periodo
            kwh_por_periodo.append(t)


        nextReading = ElectricDataTemp.objects.filter(
            profile_powermeter=profile_powermeter,
            medition_date__gt = ultima_fecha)\
        .order_by('medition_date')

        #Se revisa que la siguiente lectura sea menor a 10 min.
        tenmin_delta = datetime.timedelta(minutes=10)

        if nextReading:
            if nextReading[0].medition_date < (ultima_fecha + tenmin_delta):
                ultima_lectura = nextReading[0].TotalkWhIMPORT
                #print "Ultima Lectura", nextReading[0].pk,"-",nextReading[0].medition_date

        kwh_periodo_long = len(kwh_por_periodo)

        kwh_base = 0
        kwh_intermedio = 0
        kwh_punta = 0

        for idx, kwh_p in enumerate(kwh_por_periodo):
            #print "Lectura:", kwh_p[0], "-:",kwh_p[1]
            inicial = kwh_p[0]
            periodo_t = kwh_p[1]
            if idx + 1 <= kwh_periodo_long - 1:
                kwh_p2 = kwh_por_periodo[idx + 1]
                final = kwh_p2[0]
            else:
                final = ultima_lectura

            kwh_netos = final - inicial
            #print "Inicial:",inicial,"Final:",final, "Netos:",kwh_netos

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
