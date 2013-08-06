# -*- coding: utf-8 -*-
# Create your views here.
import pytz
import datetime
import json as simplejson
from time import strftime
from calendar import monthrange

from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.context import RequestContext
from django.db.models import Q
from django.utils import timezone
from rbac.rbac_functions import get_buildings_context
from electric_rates.models import *
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.contrib.auth.decorators import login_required

from c_center.c_center_functions import set_default_session_vars, \
    crawler_hm_rate, crawler_DAC_rate, crawler_t3_rate

#"""
#Tarifa 3
#"""


def add_tarifa3(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        template_vars = dict(
            datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            t3_month = request.POST.get('month').strip()
            t3_kw = request.POST.get('kw_rate').strip()
            t3_kwh = request.POST.get('kwh_rate').strip()
            message = ""
            _type = ""

            continuar = True
            if t3_month == '':
                message = "Se debe seleccionar el mes"
                _type = "n_notif"
                continuar = False

            if t3_kw == '':
                message = "La tarifa de Demanda Máxima no puede quedar vacía"
                _type = "n_notif"
                continuar = False

            if t3_kwh == '':
                message = "La tarifa de KWH no puede quedar vacía"
                _type = "n_notif"
                continuar = False

            #Se parsea el mes para ponerlo en el formato debido
            arr_month = t3_month.split('/')
            billing_month = datetime.date(year=int(arr_month[1]), month=int(arr_month[0]), day=1)
            last_day = monthrange(int(arr_month[1]),int(arr_month[0]))
            billing_end = datetime.date(year=int(arr_month[1]), month=int(arr_month[0]), day=last_day[1])

            #Se verifica que no haya una tarifa ya registrada para ese mes
            bmonth_exists = ThreeElectricRateDetail.objects.filter(date_init__lte = billing_month).\
            filter(date_end__gte = billing_month)
            if bmonth_exists:
                message = "Ya hay una tarifa registrada para este mes"
                _type = "n_notif"
                continuar = False
                t3_month = ''

            post = {'month': t3_month, 'kw_rate':t3_kw, 'kwh_rate':t3_kwh }

            if continuar:
                #Se guarda la nueva tarifa
                newT3 = ThreeElectricRateDetail(
                    kw_rate = t3_kw,
                    kwh_rate = t3_kwh,
                    date_init = billing_month,
                    date_end = billing_end
                )
                newT3.save()

                template_vars["message"] = "Cuota registrada exitosamente"
                template_vars["type"] = "n_success"

                if request.user.is_superuser:
                    return HttpResponseRedirect("/electric_rates/tarifa3/?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")

            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("electric_rates/add_tarifa3.html", template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext":datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def edit_tarifa3(request, id_t3):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']

        #Se obtiene la tarifa seleccionada
        t3_obj = get_object_or_404(ThreeElectricRateDetail, pk = id_t3)

        month_str = str(t3_obj.date_init.month)+'/'+str(t3_obj.date_init.year)
        post = {'month': month_str, 'kw_rate':t3_obj.kw_rate, 'kwh_rate':t3_obj.kwh_rate }

        template_vars = dict(
            datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            operation="edit",
            sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST
            t3_kw = request.POST.get('kw_rate').strip()
            t3_kwh = request.POST.get('kwh_rate').strip()
            message = ""
            _type = ""

            continuar = True
            if t3_kw == '':
                message = "La tarifa de Demanda Máxima no puede quedar vacía"
                _type = "n_notif"
                continuar = False

            if t3_kwh == '':
                message = "La tarifa de KWH no puede quedar vacía"
                _type = "n_notif"
                continuar = False

            post = {'kw_rate':t3_kw, 'kwh_rate':t3_kwh }

            if continuar:
                #Se guarda la nueva tarifa
                t3_obj.kw_rate = t3_kw
                t3_obj.kwh_rate = t3_kwh
                t3_obj.save()

                template_vars["message"] = "Cuota editada exitosamente"
                template_vars["type"] = "n_success"

                return HttpResponseRedirect("/electric_rates/tarifas/3/")

            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("electric_rates/add_tarifa3.html", template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext":datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)

def view_tarifa_3(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if request.user.is_superuser:
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_date = 'asc'
        order = "-date_init" #default order
        if "order_name" in request.GET:
            if request.GET["order_date"] == "desc":
                order = "date_init"
                order_date = "asc"
            else:
                order_date = "desc"

        if search:
            lista = ThreeElectricRateDetail.objects.filter(Q(date_init__icontains=request.GET['search'])|Q(
                date_end__icontains=request.GET['search'])).order_by(order)
        else:
            lista = ThreeElectricRateDetail.objects.all().order_by(order)

        paginator = Paginator(lista, 12) # muestra 10 resultados por pagina
        template_vars = dict(order_date=order_date,
            datacontext=datacontext, empresa=empresa, company=request.session['company'],
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

        template_vars['paginacion']=pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']


        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("electric_rates/tarifa3.html", template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext":datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


#"""
#Tarifa HM
#"""

def add_tarifaHM(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''
        message = ''

        #Se obtienen las regiones
        regiones_lst = Region.objects.all()

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            regiones_lst=regiones_lst,
            sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST

            hm_month = request.POST.get('month').strip()
            hm_region = request.POST.get('t_region').strip()
            hm_demanda = request.POST.get('demand_rate').strip()
            hm_kwhp = request.POST.get('kwh_punta').strip()
            hm_kwhi = request.POST.get('kwh_int').strip()
            hm_kwhb = request.POST.get('kwh_base').strip()
            hm_fri = request.POST.get('fri').strip()
            hm_frb = request.POST.get('frb').strip()

            message = ""
            _type = ""

            continuar = True
            if hm_month == '':
                message = "Se debe seleccionar el mes"
                _type = "n_notif"
                continuar = False

            if hm_region == '':
                message = "Se debe seleccionar una región"
                _type = "n_notif"
                continuar = False
                hm_region = 0

            if hm_demanda == '':
                message = "El cargo de Demanda Facturable no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if hm_kwhp == '':
                message = "El cargo de KWH Punta no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if hm_kwhi == '':
                message = "El cargo de KWH Intermedio no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if hm_kwhb == '':
                message = "El cargo de KWH Base no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if hm_fri == '':
                message = "El cargo de FRI no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if hm_frb == '':
                message = "El cargo de FRB no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            #Se parsea el mes para ponerlo en el formato debido
            arr_month = hm_month.split('/')
            billing_month = datetime.date(year=int(arr_month[1]), month=int(arr_month[0]), day=1)
            last_day = monthrange(int(arr_month[1]),int(arr_month[0]))
            billing_end = datetime.date(year=int(arr_month[1]), month=int(arr_month[0]), day=last_day[1])

            if continuar:

                #Se obtiene el objeto de la region
                regionObj = get_object_or_404(Region, pk=hm_region)

                #Se verifica que no haya una tarifa ya registrada para ese mes
                bmonth_exists = ElectricRatesDetail.objects.filter(date_init__lte = billing_month).\
                filter(date_end__gte = billing_month).filter(region=regionObj)

                if bmonth_exists:
                    message = "Ya hay una tarifa registrada para este mes"
                    _type = "n_notif"
                    continuar = False
                    hm_month = ''

            post = {
                'month': hm_month,
                'region': int(hm_region),
                'demand_rate': hm_demanda,
                'kwh_punta': hm_kwhp,
                'kwh_int': hm_kwhi,
                'kwh_base': hm_kwhb,
                'fri': hm_fri,
                'frb': hm_frb
            }

            if continuar:

                #Se obtiene el objeto de la tarifa HM
                HM_erate = get_object_or_404(ElectricRates, pk = 1)

                #Se da de alta la nueva cuota
                newHM = ElectricRatesDetail(
                    electric_rate=HM_erate,
                    KDF=hm_demanda,
                    KWHP=hm_kwhp,
                    KWHI=hm_kwhi,
                    KWHB=hm_kwhb,
                    FRI=hm_fri,
                    FRB=hm_frb,
                    KWDMM=0,
                    KWHEC=0,
                    date_init=billing_month,
                    date_end=billing_end,
                    region=regionObj
                )
                newHM.save()

                template_vars["message"] = "Cuota registrada exitosamente"
                template_vars["type"] = "n_success"

                if request.user.is_superuser:
                    return HttpResponseRedirect("/electric_rates/tarifaHM?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("electric_rates/add_tarifaHM.html", template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext":datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)



def edit_tarifaHM(request, id_hm):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']

        #Se obtiene la tarifa seleccionada
        hm_obj = get_object_or_404(ElectricRatesDetail, pk = id_hm)

        month_str = str(hm_obj.date_init.month)+'/'+str(hm_obj.date_init.year)
        post = {
            'month':month_str,
            'region':int(hm_obj.region_id),
            'region_name': hm_obj.region.region_name,
            'demand_rate':hm_obj.KDF,
            'kwh_punta':hm_obj.KWHP,
            'kwh_int':hm_obj.KWHI,
            'kwh_base':hm_obj.KWHB,
            'fri':hm_obj.FRI,
            'frb':hm_obj.FRB
        }

        #Se obtienen las regiones
        regiones_lst = Region.objects.all()

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            operation="edit",
            regiones_lst=regiones_lst,
            sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST

            hm_demanda = request.POST.get('demand_rate').strip()
            hm_kwhp = request.POST.get('kwh_punta').strip()
            hm_kwhi = request.POST.get('kwh_int').strip()
            hm_kwhb = request.POST.get('kwh_base').strip()
            hm_fri = request.POST.get('fri').strip()
            hm_frb = request.POST.get('frb').strip()

            message = ""
            _type = ""

            continuar = True

            if hm_demanda == '':
                message = "El cargo de Demanda Facturable no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if hm_kwhp == '':
                message = "El cargo de KWH Punta no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if hm_kwhi == '':
                message = "El cargo de KWH Intermedio no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if hm_kwhb == '':
                message = "El cargo de KWH Base no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if hm_fri == '':
                message = "El cargo de FRI no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if hm_frb == '':
                message = "El cargo de FRB no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            post = {
                'month': month_str,
                'region': int(hm_obj.region_id),
                'demand_rate': hm_demanda,
                'kwh_punta': hm_kwhp,
                'kwh_int': hm_kwhi,
                'kwh_base': hm_kwhb,
                'fri': hm_fri,
                'frb': hm_frb
            }

            if continuar:
                #Se edita la cuota
                hm_obj.KDF = hm_demanda
                hm_obj.KWHP = hm_kwhp
                hm_obj.KWHI = hm_kwhi
                hm_obj.KWHB = hm_kwhb
                hm_obj.FRI = hm_fri
                hm_obj.FRB = hm_frb

                hm_obj.save()

                template_vars["message"] = "Cuota registrada exitosamente"
                template_vars["type"] = "n_success"

                return HttpResponseRedirect("/electric_rates/tarifas/HM/")

            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("electric_rates/add_tarifaHM.html", template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext":datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_tarifa_HM(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if request.user.is_superuser:
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_date = 'asc'
        order = "-date_init" #default order
        if "order_name" in request.GET:
            if request.GET["order_date"] == "desc":
                order = "date_init"
                order_date = "asc"
            else:
                order_date = "desc"

        if search:
            lista = ElectricRatesDetail.objects.filter(Q(region__region_name__icontains=request.GET['search'])).\
            order_by(order)
        else:
            lista = ElectricRatesDetail.objects.all().order_by(order)

        paginator = Paginator(lista, 12) # muestra 10 resultados por pagina
        template_vars = dict(order_date=order_date,
            datacontext=datacontext, empresa=empresa, company=request.session['company'],
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

        template_vars['paginacion']=pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']


        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("electric_rates/tarifaHM.html", template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext":datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)



#"""
#Tarifa DAC
#"""


def add_tarifaDac(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']
        post = ''

        #Se obtienen las regiones
        regiones_lst = Region.objects.all()

        #Se obtienen los periodos de verano e invierno
        periodos_lst = DateIntervals.objects.filter(electric_rate__pk = 2)

        template_vars = dict(datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            regiones_lst=regiones_lst,
            periodos_lst=periodos_lst, sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST

            dac_month = request.POST.get('month').strip()
            dac_region = request.POST.get('t_region').strip()
            dac_periodo = request.POST.get('t_periodo').strip()
            dac_m_rate = request.POST.get('monthly_rate').strip()
            dac_kwh = request.POST.get('kwh_rate').strip()
            message = ""
            _type = ""

            continuar = True
            if dac_month == '':
                message = "Se debe seleccionar el mes"
                _type = "n_notif"
                continuar = False

            if dac_region == '':
                message = "Se debe seleccionar una región"
                _type = "n_notif"
                continuar = False
                dac_region = 0

            if dac_periodo == '':
                dac_periodo = 0

            if dac_m_rate == '':
                message = "El cargo mensual no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if dac_kwh == '':
                message = "La tarifa de KWH no puede quedar vacía"
                _type = "n_notif"
                continuar = False

            #Se parsea el mes para ponerlo en el formato debido
            arr_month = dac_month.split('/')
            billing_month = datetime.date(year=int(arr_month[1]), month=int(arr_month[0]), day=1)
            last_day = monthrange(int(arr_month[1]),int(arr_month[0]))
            billing_end = datetime.date(year=int(arr_month[1]), month=int(arr_month[0]), day=last_day[1])

            if continuar:
                #Si se selecciono periodo, se obtiene el objeto.
                periodoObj = None
                if dac_periodo != 0:
                    periodoObj = get_object_or_404(DateIntervals, pk = dac_periodo)

                #Se obtiene el objeto de la region
                regionObj = get_object_or_404(Region, pk=dac_region)

                #Se verifica que no haya una tarifa ya registrada para ese mes
                bmonth_exists = DACElectricRateDetail.objects.filter(date_init__lte = billing_month).\
                filter(date_end__gte = billing_month).filter(region=regionObj).filter(date_interval=periodoObj)

                if bmonth_exists:
                    message = "Ya hay una tarifa registrada para este mes"
                    _type = "n_notif"
                    continuar = False
                    dac_month = ''


            post = {
                'month': dac_month,
                'region': int(dac_region),
                'periodo': int(dac_periodo),
                'monthly_rate': dac_m_rate,
                'kwh_rate': dac_kwh
            }

            if continuar:

                #Se da de alta la nueva cuota
                newDac = DACElectricRateDetail(
                    region=regionObj,
                    date_interval=periodoObj,
                    month_rate=dac_m_rate,
                    kwh_rate=dac_kwh,
                    date_init=billing_month,
                    date_end=billing_end,
                )
                newDac.save()

                template_vars["message"] = "Cuota registrada exitosamente"
                template_vars["type"] = "n_success"

                if request.user.is_superuser:
                    return HttpResponseRedirect("/electric_rates/tarifaDac?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")
            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("electric_rates/add_tarifaDac.html", template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext":datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)



def edit_tarifaDac(request, id_dac):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        datacontext = get_buildings_context(request.user)
        empresa = request.session['main_building']
        company = request.session['company']

        #Se obtienen las regiones
        regiones_lst = Region.objects.all()

        #Se obtienen los periodos de verano e invierno
        periodos_lst = DateIntervals.objects.filter(electric_rate__pk = 2)

        #Se obtiene la tarifa seleccionada
        dac_obj = get_object_or_404(DACElectricRateDetail, pk = id_dac)

        month_str = str(dac_obj.date_init.month)+'/'+str(dac_obj.date_init.year)

        if dac_obj.date_interval_id:
            d_interval = int(dac_obj.date_interval_id)
        else:
            d_interval = 0
        post = {
            'month': month_str,
            'region': int(dac_obj.region_id),
            'region_name': dac_obj.region.region_name,
            'periodo': d_interval,
            'monthly_rate': dac_obj.month_rate,
            'kwh_rate': dac_obj.kwh_rate
        }

        template_vars = dict(
            datacontext=datacontext,
            empresa=empresa,
            company=company,
            post=post,
            operation="edit",
            regiones_lst=regiones_lst,
            periodos_lst=periodos_lst,
            sidebar=request.session['sidebar']
        )

        if request.method == "POST":
            template_vars["post"] = request.POST

            dac_m_rate = request.POST.get('monthly_rate').strip()
            dac_kwh = request.POST.get('kwh_rate').strip()
            message = ""
            _type = ""

            continuar = True

            if dac_m_rate == '':
                message = "El cargo mensual no puede quedar vacío"
                _type = "n_notif"
                continuar = False

            if dac_kwh == '':
                message = "La tarifa de KWH no puede quedar vacía"
                _type = "n_notif"
                continuar = False

            post = {
                'monthly_rate':dac_m_rate,
                'kwh_rate':dac_kwh
            }

            if continuar:

                #Se edita la cuota con los nuevos datos

                dac_obj.month_rate = dac_m_rate
                dac_obj.kwh_rate = dac_kwh
                dac_obj.save()

                template_vars["message"] = "Cuota editada exitosamente"
                template_vars["type"] = "n_success"

                return HttpResponseRedirect("/electric_rates/tarifas/DAC/")

            template_vars["post"] = post
            template_vars["message"] = message
            template_vars["type"] = _type

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("electric_rates/add_tarifaDac.html", template_vars_template)
    else:
        datacontext = get_buildings_context(request.user)
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext":datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def view_tarifa_DAC(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    datacontext = get_buildings_context(request.user)
    if request.user.is_superuser:
        empresa = request.session['main_building']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_date = 'asc'
        order = "-date_init" #default order
        if "order_name" in request.GET:
            if request.GET["order_date"] == "desc":
                order = "date_init"
                order_date = "asc"
            else:
                order_date = "desc"

        if search:
            lista = DACElectricRateDetail.objects.filter(Q(region__region_name__icontains=request.GET['search'])).\
            order_by(order)
        else:
            lista = DACElectricRateDetail.objects.all().order_by(order)

        paginator = Paginator(lista, 12) # muestra 10 resultados por pagina
        template_vars = dict(order_date=order_date,
            datacontext=datacontext, empresa=empresa, company=request.session['company'],
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

        template_vars['paginacion']=pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']


        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("electric_rates/tarifaDac.html", template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext":datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


@login_required(login_url='/')
def tarifa_header(request, tarifa_n):
    datacontext = get_buildings_context(request.user)[0]
    if request.user.is_superuser:
        set_default_session_vars(request, datacontext)
        template_vars = {"type": "cfe", "datacontext": datacontext,
                         'company': request.session['company'],
                         'sidebar': request.session['sidebar']}
        year_list = []
        if tarifa_n == 'HM':
            year_list = [__date.year for __date in ElectricRatesDetail.objects.all().dates('date_init','year')]
            template_vars['tipo_tarifa'] = 'HM'

        elif tarifa_n == 'DAC':
            year_list = [__date.year for __date in DACElectricRateDetail.objects.all().dates('date_init','year')]
            template_vars['tipo_tarifa'] = 'DAC'

        elif tarifa_n == '3':
            year_list = [__date.year for __date in ThreeElectricRateDetail.objects.all().dates('date_init','year')]
            template_vars['tipo_tarifa'] = 'T3'

        today = datetime.datetime.now()

        year = int(today.year)

        crawler_year_list = []
        for yr in range(2012,year+1):
            crawler_year_list.append(yr)

        template_vars['year'] = year
        template_vars['year_list'] = year_list
        template_vars['crawler_year_list'] = crawler_year_list


        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("electric_rates/tarifa_header.html",
                                  template_vars_template)
    else:
        template_vars = {"type": "cfe", "datacontext": datacontext,
                         'empresa': request.session['main_building'],
                         'company': request.session['company'],
                         'sidebar': request.session['sidebar']}
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html",
                                  RequestContext(request,
                                                 {"datacontext": datacontext})
                                    ,template_vars_template)


def getRatesTable(request):

    response_html = ''
    crler_resp = ''

    datacontext = get_buildings_context(request.user)[0]
    if request.user.is_superuser:

        set_default_session_vars(request, datacontext)

        template_vars = dict(type="cfe", datacontext=datacontext,
                             empresa=request.session['main_building'])

        if request.GET:
            year = int(request.GET['year'])
            if 'crawler' in request.GET:
                crler_resp = request.GET['crawler']
        else:
            #Obtener la fecha actual
            today = datetime.datetime.today()
            year = int(today.year)

        rate_type = request.GET['tarifa']

        if rate_type == 'HM':
            template_vars['tarifas'] = getHM_table(year)
            response_html = 'electric_rates/tarifaHM_table.html'
        elif rate_type == 'DAC':
            template_vars['tarifas'] = getDAC_table(year)
            response_html = 'electric_rates/tarifaDAC_table.html'
        elif rate_type == 'T3':
            template_vars['tarifas'] = getT3_table(year)
            response_html = 'electric_rates/tarifa3_table.html'

        if crler_resp:
            if crler_resp == 'Success':
                template_vars['message'] = 'La tarifa para el mes seleccionado se ha obtenido exitosamente'
                template_vars['msg_type'] = 'n_success'
            elif crler_resp == 'Fail':
                template_vars['message'] = 'La tarifa para el mes seleccionado no pudo obtenerse. Compruebe que tenga acceso a Internet'
                template_vars['msg_type'] = 'n_notif'
            elif crler_resp == 'Error_Month':
                template_vars['message'] = 'La tarifa para el mes seleccionado todavía no está disponible'
                template_vars['msg_type'] = 'n_notif'

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response(
            response_html,
            template_vars_template)
    else:
        template_vars = {}
        if datacontext:
            template_vars = {"datacontext": datacontext}
        template_vars["sidebar"] = request.session['sidebar']
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("generic_error.html", template_vars_template)


def getHM_table(year):
    regions_dict = dict()

    #Se obtienen todas las regiones
    regiones = Region.objects.all().order_by('region_name')
    for region in regiones:
        #Se obtienen las tarifas para ese año
        tarifasHM = ElectricRatesDetail.objects.filter(
            region=region,
            date_init__year=year)
        if tarifasHM:
            arregloDemanda = [None] * 12
            arregloKWHP = [None] * 12
            arregloKWHI = [None] * 12
            arregloKWHB = [None] * 12
            arregloFRI = [None] * 12
            arregloFRB = [None] * 12
            arregloIds = [None] * 12
            for tf in tarifasHM:
                arregloDemanda[tf.date_init.month-1] = tf.KDF
                arregloKWHP[tf.date_init.month-1] = tf.KWHP
                arregloKWHI[tf.date_init.month-1] = tf.KWHI
                arregloKWHB[tf.date_init.month-1] = tf.KWHB
                arregloFRI[tf.date_init.month-1] = tf.FRI
                arregloFRB[tf.date_init.month-1] = tf.FRB
                arregloIds[tf.date_init.month-1] = tf.pk

            arregloContenedor = [arregloDemanda, arregloKWHP, arregloKWHI,
                                 arregloKWHB, arregloFRI, arregloFRB,
                                 arregloIds]
            regions_dict[region.region_name] = arregloContenedor

    return regions_dict


def getDAC_table(year):
    regions_dict = dict()

    #Se obtienen todas las regiones
    regiones = Region.objects.all().order_by('region_name')
    for region in regiones:
        #Se obtienen las tarifas para ese año
        tarifasDAC = DACElectricRateDetail.objects.filter(region = region,
                    date_init__year = year)

        if tarifasDAC:
            arregloMes = [None] * 12
            arregloKWH = [None] * 12
            arregloIds = [None] * 12
            for tf in tarifasDAC:
                arregloMes[tf.date_init.month-1] = tf.month_rate
                arregloKWH[tf.date_init.month-1] = tf.kwh_rate
                arregloIds[tf.date_init.month-1] = tf.pk

            arregloContenedor = [arregloMes, arregloKWH, arregloIds]
            regions_dict[region.region_name] = arregloContenedor

    return regions_dict

def getT3_table(year):
    tarifas3 = ThreeElectricRateDetail.objects.filter(date_init__year = year)
    arregloKWH = [None] * 12
    arregloKW = [None] * 12
    arregloIds = [None] * 12
    for t3 in tarifas3:
        arregloKWH[t3.date_init.month-1] = t3.kwh_rate
        arregloKW[t3.date_init.month-1] = t3.kw_rate
        arregloIds[t3.date_init.month-1] = t3.pk
    arregloContenedor = [arregloKWH, arregloKW, arregloIds]

    return arregloContenedor

@login_required(login_url='/')
def getMonthRate(request):
    status = ""
    if request.GET:
        year = int(request.GET['year'])
        month = int(request.GET['month'])
        rate_type = request.GET['tarifa']

        #Se obtiene el mes actual
        requested_month = datetime.datetime(year, month, 1)
        current_month = datetime.datetime.now()
        if requested_month > current_month:
            status = "Error_Month"
        else:
            if rate_type == 'HM':
                if crawler_hm_rate(year, month):
                    status = "Success"
                else:
                    status = "Fail"
            elif rate_type == 'DAC':
                if crawler_DAC_rate(year, month):
                    status = "Success"
                else:
                    status = "Fail"
            elif rate_type == 'T3':
                if crawler_t3_rate(year, month):
                    status = "Success"
                else:
                    status = "Fail"
    else:
        status = "No GET Request"

    data = simplejson.dumps(status)
    return HttpResponse(content=data, content_type="application/json")