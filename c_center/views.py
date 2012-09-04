#standard library imports
from datetime import  timedelta, datetime
from dateutil.relativedelta import relativedelta
import re
import time
import pdb
#related third party imports

#local application/library specific imports
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.context import RequestContext
from django.utils import timezone

from c_center.models import Building, ElectricData, ProfilePowermeter
from rbac.models import Operation, DataContextPermission
from rbac.rbac_functions import  has_permission
from c_center.calculations import tarifaHM_total, obtenerHistorico
from c_center.models import ConsumerUnit
import json as simplejson


VIEW = Operation.objects.get(operation_name="view")
CREATE = Operation.objects.get(operation_name="create")
DELETE = Operation.objects.get(operation_name="delete")
UPDATE = Operation.objects.get(operation_name="update")

def get_intervals_1(get):
    """ get the interval for the graphs

    by default we get the data from the last 3 months

    """
    f1_init = datetime.today() - relativedelta( months = +1 )
    f1_end = datetime.today()

    if "f1_init" in get:
        f1_init = time.strptime(get['f1_init'], "%d/%m/%Y")
        f1_init = datetime(f1_init.tm_year, f1_init.tm_mon, f1_init.tm_mday)
        f1_end = time.strptime(get['f1_end'], "%d/%m/%Y")
        f1_end = datetime(f1_end.tm_year, f1_end.tm_mon, f1_end.tm_mday)

    return f1_init,f1_end

def get_intervals_fecha(get):

    """ get the interval for the graphs

        by default we get the data from the last 3 months

        """
    f1_init = datetime.today() - relativedelta( months = +1 )
    f1_init = str(f1_init.year)+"-"+str(f1_init.month)+"-"+str(f1_init.day)+" 00:00:00"
    f1_end = datetime.today()
    f1_end = str(f1_end.year)+"-"+str(f1_end.month)+"-"+str(f1_end.day)+" 23:59:59"


    if "f1_init" in get:
        f1_init = get['f1_init']
        f1_init=str.split(str(f1_init),"/")
        f1_init = str(f1_init[2])+"-"+str(f1_init[1])+"-"+str(f1_init[0])+" 00:00:00"
        f1_end = get['f1_end']
        f1_end = str.split(str(f1_end),"/")
        f1_end = str(f1_end[2])+"-"+str(f1_end[1])+"-"+str(f1_end[0])+" 23:59:59"
    return f1_init, f1_end


def get_intervals_2(get):
    """ gets the second date interval """
    f2_init = time.strptime(get['f2_init'], "%d/%m/%Y")
    f2_init = datetime(f2_init.tm_year, f2_init.tm_mon, f2_init.tm_mday)
    f2_end = time.strptime(get['f2_end'], "%d/%m/%Y")
    f2_end = datetime(f2_end.tm_year, f2_end.tm_mon, f2_end.tm_mday)

    return f2_init, f2_end

def main_page(request):
    """ in the mean time the main view is the graphics view """
    if has_permission(request.user, VIEW, "graphs") or request.user.is_superuser:
        #has perm to view graphs, now check what can the user see
        datacontext = DataContextPermission.objects.filter(user_role__user=request.user)

        if 'main_building' not in request.session:
            #sets the default building
            request.session['main_building'] = datacontext[0].building
        template_vars = {"type":"graphs", "datacontext":datacontext,'empresa':request.session['main_building']}
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/main.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def cfe_bill(request):
    if has_permission(request.user, VIEW, "CFE bill") or request.user.is_superuser:
        datacontext = DataContextPermission.objects.filter(user_role__user=request.user)
        if not request.session['main_building']:
            #sets the default building
            request.session['main_building'] = datacontext[0].building
        powermeter = ConsumerUnit.objects.get(building=request.session['main_building'])
        profile_pm = powermeter.profile_powermeter
        powermeter = powermeter.profile_powermeter.powermeter
        start_date, end_date = get_intervals_fecha(request.GET)

        t_hm=tarifaHM_total(powermeter, start_date, end_date, request.session['main_building'].region, request.session['main_building'].electric_rate)

        arr_historico=obtenerHistorico(profile_pm, t_hm['ultima_tarifa'],request.session['main_building'].region, 3, request.session['main_building'].electric_rate)

        template_vars={"type":"cfe", "datacontext":datacontext,
                       'empresa':request.session['main_building'],
                       'tarifaHM': t_hm,
                       'historico': arr_historico}
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/cfe.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def potencia_activa(request):
    template_vars = {"type":"kw"}

    #second interval, None by default
    f2_init = None
    f2_end = None

    f1_init, f1_end = get_intervals_1(request.GET)

    if request.GET:

        if "f2_init" in request.GET:
            #comparacion con un intervalo
            template_vars['fi'], template_vars['ff'] = f1_init, f1_end
            template_vars['fi2'], template_vars['ff2'] = get_intervals_2(request.GET)
            template_vars['building']=request.session['main_building'].pk
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/graphs/potencia_activa.html", template_vars_template)
        else:
            #graficas de un edificio
            buildings = [request.session['main_building'].pk]
            template_vars['building_names'] = []
            template_vars['building_names'].append(get_object_or_404(Building, pk = request.session['main_building'].pk))

            f1_init, f1_end = get_intervals_1(request.GET)
            if request.method == "GET":
                for key in request.GET:
                    if re.search('^compare_to\d+', key):
                        #graficas comparativas de 2 o mas edificios
                        buildings.append(int(request.GET[key]))
                        template_vars['building_names'].append(get_object_or_404(Building, pk = int(request.GET[key])))

                template_vars['buildings'] = simplejson.dumps(buildings)

            template_vars['fi'], template_vars['ff'] = f1_init, f1_end
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/graphs/potencia_activa_b.html", template_vars_template)
    else:
        return HttpResponse(content="", content_type="text/html")


def graficas(request):
    template_vars = {'fi': get_intervals_1(request.GET)[0], 'ff': get_intervals_1(request.GET)[1]}

    #second interval, None by default

    if request.GET:
        if "graph" not in request.GET:
            raise Http404
        else:
            template_vars['tipo']=request.GET["graph"]
            buildings = [request.session['main_building'].pk]

            if "f2_init" in request.GET:
                #comparacion con un intervalo
                template_vars['fi2'], template_vars['ff2'] = get_intervals_2(request.GET)
            else:
                #graficas de un edificio

                template_vars['building_names'] = []
                template_vars['building_names'].append(get_object_or_404(Building, pk = request.session['main_building'].pk))

                if request.method == "GET":
                    for key in request.GET:
                        if re.search('^compare_to\d+', key):
                            #graficas comparativas de 2 o mas edificios
                            buildings.append(int(request.GET[key]))
                            template_vars['building_names'].append(get_object_or_404(Building, pk = int(request.GET[key])))

            template_vars['buildings'] = simplejson.dumps(buildings)

            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/graphs/test_graph.html", template_vars_template)
    else:
        return HttpResponse(content="Wrong", content_type="text/html")

def grafica_datos(request):
    f1_init, f1_end = get_intervals_1(request.GET)
    buildings = []
    for key in request.GET:
        if re.search('^building\d+', key):
            building = get_object_or_404(Building, pk=int(request.GET[key]))
            buildings.append(building)

    if len(buildings) > 0:
        data=get_KW_json_b(buildings, f1_init, f1_end)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def get_kw_data_boris(request):
    f1_init, f1_end = get_intervals_1(request.GET)
    buildings = []
    if "f2_init" in request.GET:
        f2_init, f2_end = get_intervals_2(request.GET)
        #esto comparando con otro intervalo de tiempo
        #tengo que sacar los datos de los dos intervalos y homologar las fechas
        #como intervalos regulares de tiempo
        building = Building.objects.get(pk=int(request.GET["building0"]))
        meditions1 = get_medition_in_time(building, f1_init, f1_end)
        meditions2 = get_medition_in_time(building, f2_init, f2_end)
        len1=len(meditions1)
        len2=len(meditions2)
        cont=0
        compared_meditions=[]

        if len1 > len2:
            for medition in meditions1:
                cont+=1
                kw2 = 0 if cont > len2 else meditions2[cont-1].kW
                date2= 0 if cont > len2 else int(time.mktime(meditions2[cont-1].medition_date.timetuple()))
                compared_meditions.append(dict(time1=int(time.mktime(medition.medition_date.timetuple())), kw1=str(medition.kW), time2=date2, kw2=str(kw2), cont=str(cont)))#date=int(time.mktime(medition.medition_date.timetuple()))
                print medition.kW, kw2
        else:
            for medition in meditions2:
                cont+=1
                kw2 = 0 if cont > len1 else meditions1[cont-1].kW
                date= 0 if cont > len1 else int(time.mktime(meditions1[cont-1].medition_date.timetuple()))
                compared_meditions.append(dict(time1=str(date), kw1=str(kw2), kw2=str(medition.kW), time2=str(time.mktime(medition.medition_date.timetuple())), cont=str(cont)))
                print medition.kW, kw2

        return HttpResponse(content=simplejson.dumps(compared_meditions), content_type="application/json")

    for key in request.GET:
        if re.search('^building\d+', key):
            building = get_object_or_404(Building, pk=int(request.GET[key]))
            buildings.append(building)

    if len(buildings) > 0:
        data=get_KW_json_b(buildings, f1_init, f1_end)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def get_kw_data(request):
    if 'building' in request.GET:
        f1_init, f1_end = get_intervals_1(request.GET)
        building = get_object_or_404(Building, pk=int(request.GET['building']))
        if "f2_init" in request.GET:
            f2_init, f2_end = get_intervals_2(request.GET)
            #esto comparando con otro intervalo de tiempo
            #tengo que sacar los datos de los dos intervalos y homologar las fechas
            #como intervalos regulares de tiempo

            meditions1 = get_medition_in_time(building, f1_init, f1_end)
            meditions2 = get_medition_in_time(building, f2_init, f2_end)
            len1=len(meditions1)
            len2=len(meditions2)
            cont=0
            compared_meditions=[]

            if len1 > len2:
                for medition in meditions1:
                    cont+=1
                    kw2 = 0 if cont > len2 else meditions2[cont-1].kW
                    date2= 0 if cont > len2 else int(time.mktime(meditions2[cont-1].medition_date.timetuple()))
                    compared_meditions.append(dict(time1=int(time.mktime(medition.medition_date.timetuple())), kw1=str(medition.kW), time2=date2, kw2=str(kw2), cont=str(cont)))#date=int(time.mktime(medition.medition_date.timetuple()))
                    print medition.kW, kw2
            else:
                for medition in meditions2:
                    cont+=1
                    kw2 = 0 if cont > len1 else meditions1[cont-1].kW
                    date= 0 if cont > len1 else int(time.mktime(meditions1[cont-1].medition_date.timetuple()))
                    compared_meditions.append(dict(time1=str(date), kw1=str(kw2), kw2=str(medition.kW), time2=str(time.mktime(medition.medition_date.timetuple())), cont=str(cont)))
                    print medition.kW, kw2

            return HttpResponse(content=simplejson.dumps(compared_meditions), content_type="application/json")
        data=get_KW_json(building, f1_init, f1_end)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404


def get_kvar_data(request):
    if 'building' in request.GET:
        f1_init, f1_end = get_intervals_1(request.GET)
        building = get_object_or_404(Building, pk=int(request.GET['building']))
        if "f2_init" in request.GET:
            f2_init, f2_end = get_intervals_2(request.GET)
            #esto comparando con otro intervalo de tiempo
            #tengo que sacar los datos de los dos intervalos y homologar las fechas
            #como intervalos regulares de tiempo

            meditions1 = get_medition_in_time(building, f1_init, f1_end)
            meditions2 = get_medition_in_time(building, f2_init, f2_end)
            len1=len(meditions1)
            len2=len(meditions2)
            cont=0
            compared_meditions=[]

            if len1 > len2:
                for medition in meditions1:
                    cont+=1
                    kvar2 = 0 if cont > len2 else meditions2[cont-1].kvar
                    date2= 0 if cont > len2 else int(time.mktime(meditions2[cont-1].medition_date.timetuple()))
                    compared_meditions.append(dict(time1=int(time.mktime(medition.medition_date.timetuple())), kvar1=str(medition.kvar), time2=date2, kvar2=str(kvar2), cont=str(cont)))#date=int(time.mktime(medition.medition_date.timetuple()))
                    print medition.kvar, kvar2
            else:
                for medition in meditions2:
                    cont+=1
                    kvar2 = 0 if cont > len1 else meditions1[cont-1].kvar
                    date= 0 if cont > len1 else int(time.mktime(meditions1[cont-1].medition_date.timetuple()))
                    compared_meditions.append(dict(time1=str(date), kvar1=str(kvar2), kvar2=str(medition.kvar), time2=str(medition.medition_date), cont=str(cont)))
                    print medition.kvar, kvar2

            return HttpResponse(content=simplejson.dumps(compared_meditions), content_type="application/json")
        data=get_KVar_json(building, f1_init, f1_end)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def get_kvar_data_boris(request):
    f1_init, f1_end = get_intervals_1(request.GET)
    buildings = []
    for key in request.GET:
        if re.search('^building\d+', key):
            building = get_object_or_404(Building, pk=int(request.GET[key]))
            buildings.append(building)

    if len(buildings) > 0:
        data = get_KVar_json_boris(buildings, f1_init, f1_end)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def get_KVar_json_boris(buildings, datetime_from, datetime_to):
    meditions_json = []
    buildings_number = len(buildings)
    if buildings_number < 1:
        return simplejson.dumps(meditions_json)

    buildings_meditions = []
    for building in buildings:
        print "Building"
        buildings_meditions.append(get_medition_in_time(building, datetime_from, datetime_to))

    meditions_number = len(buildings_meditions[0])
    for medition_index in range(0, meditions_number):
        current_medition = None
        meditions_kw = []
        for building_index in range(0, buildings_number):
            #print buildings_meditions[building_index][medition_index]
            current_medition = buildings_meditions[building_index][medition_index]
            meditions_kw.append(str(current_medition.kvar))

        meditions_json.append(dict(meditions = meditions_kw, date = int(time.mktime(current_medition.medition_date.timetuple()))))

    return simplejson.dumps(meditions_json)


def get_pf_data(request):
    if 'building' in request.GET:
        f1_init, f1_end = get_intervals_1(request.GET)
        building = get_object_or_404(Building, pk=int(request.GET['building']))
        if "f2_init" in request.GET:
            f2_init, f2_end = get_intervals_2(request.GET)
            #esto comparando con otro intervalo de tiempo
            #tengo que sacar los datos de los dos intervalos y homologar las fechas
            #como intervalos regulares de tiempo

            meditions1 = get_medition_in_time(building, f1_init, f1_end)
            meditions2 = get_medition_in_time(building, f2_init, f2_end)
            len1=len(meditions1)
            len2=len(meditions2)
            cont=0
            compared_meditions=[]

            if len1 > len2:
                for medition in meditions1:
                    cont+=1
                    pf2 = 0 if cont > len2 else meditions2[cont-1].PF
                    date2= 0 if cont > len2 else int(time.mktime(meditions2[cont-1].medition_date.timetuple()))
                    compared_meditions.append(dict(time1=int(time.mktime(medition.medition_date.timetuple())), pf1=str(medition.PF), time2=date2, pf2=str(pf2), cont=str(cont)))#date=int(time.mktime(medition.medition_date.timetuple()))

            else:
                for medition in meditions2:
                    cont+=1
                    pf2 = 0 if cont > len1 else meditions1[cont-1].PF
                    date= 0 if cont > len1 else int(time.mktime(meditions1[cont-1].medition_date.timetuple()))
                    compared_meditions.append(dict(time1=str(date), pf1=str(pf2), pf2=str(medition.PF), time2=str(medition.medition_date), cont=str(cont)))


            return HttpResponse(content=simplejson.dumps(compared_meditions), content_type="application/json")
        data=get_PF_json(building, f1_init, f1_end)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def get_pf_data_boris(request):
    f1_init, f1_end = get_intervals_1(request.GET)
    buildings = []
    for key in request.GET:
        if re.search('^building\d+', key):
            building = get_object_or_404(Building, pk=int(request.GET[key]))
            buildings.append(building)

    if len(buildings) > 0:
        data = get_PF_json_boris(buildings, f1_init, f1_end)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def get_PF_json_boris(buildings, datetime_from, datetime_to):
    meditions_json = []
    buildings_number = len(buildings)
    if buildings_number < 1:
        return simplejson.dumps(meditions_json)

    buildings_meditions = []
    for building in buildings:
        print "Building"
        buildings_meditions.append(get_medition_in_time(building, datetime_from, datetime_to))

    meditions_number = len(buildings_meditions[0])
    for medition_index in range(0, meditions_number):
        current_medition = None
        meditions_kw = []
        for building_index in range(0, buildings_number):
            #print buildings_meditions[building_index][medition_index]
            current_medition = buildings_meditions[building_index][medition_index]
            meditions_kw.append(str(current_medition.PF))

        meditions_json.append(dict(meditions = meditions_kw, date = int(time.mktime(current_medition.medition_date.timetuple()))))

    return simplejson.dumps(meditions_json)


def get_pp_data(request):
    if 'building' in request.GET:
        building = get_object_or_404(Building, pk=int(request.GET['building']))
        f1_init, f1_end = get_intervals_1(request.GET)
        data=get_power_profile_json(request.session['main_building'], f1_init, f1_end)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404


def potencia_reactiva(request):
    template_vars = {"type":"kvar"}
    #second interval, None by default
    f2_init = None
    f2_end = None

    f1_init, f1_end = get_intervals_1(request.GET)

    if request.GET:

        if "f2_init" in request.GET:
            template_vars['fi'], template_vars['ff'] = f1_init, f1_end
            template_vars['fi2'], template_vars['ff2'] = get_intervals_2(request.GET)
            template_vars['building']=request.session['main_building'].pk
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/graphs/potencia_reactiva.html", template_vars_template)
        else:
            buildings = []
            buildings.append(request.session['main_building'].pk)
            template_vars['building_names'] = []
            template_vars['building_names'].append(get_object_or_404(Building, pk = request.session['main_building'].pk))

            #second interval, None by default
            f2_init = None
            f2_end = None

            f1_init, f1_end = get_intervals_1(request.GET)
            print request.method
            if request.method == "GET":
                if "f2_init" in request.GET:
                    f2_init, f2_end = get_intervals_2(request.GET)

                for key in request.GET:
                    if re.search('^compare_to\d+', key):
                        buildings.append(int(request.GET[key]))
                        template_vars['building_names'].append(get_object_or_404(Building, pk = int(request.GET[key])))

                template_vars['buildings'] = simplejson.dumps(buildings)

            template_vars['fi'], template_vars['ff'] = f1_init, f1_end
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/graphs/potencia_reactiva_b.html", template_vars_template)
    else:
        return HttpResponse(content="", content_type="text/html")

def factor_potencia(request):
    template_vars = {"type":"pf"}
    #second interval, None by default
    f2_init = None
    f2_end = None

    f1_init, f1_end = get_intervals_1(request.GET)

    if request.GET:

        if "f2_init" in request.GET:
            template_vars['fi'], template_vars['ff'] = f1_init, f1_end
            template_vars['fi2'], template_vars['ff2'] = get_intervals_2(request.GET)
            template_vars['building']=request.session['main_building'].pk
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/graphs/factor_potencia.html", template_vars_template)
        else:
            buildings = []
            buildings.append(request.session['main_building'].pk)
            template_vars['building_names'] = []
            template_vars['building_names'].append(get_object_or_404(Building, pk = request.session['main_building'].pk))

            #second interval, None by default
            f2_init = None
            f2_end = None

            f1_init, f1_end = get_intervals_1(request.GET)
            print request.method
            if request.method == "GET":
                if "f2_init" in request.GET:
                    f2_init, f2_end = get_intervals_2(request.GET)

                for key in request.GET:
                    if re.search('^compare_to\d+', key):
                        buildings.append(int(request.GET[key]))
                        template_vars['building_names'].append(get_object_or_404(Building, pk = int(request.GET[key])))

                template_vars['buildings'] = simplejson.dumps(buildings)

            template_vars['fi'], template_vars['ff'] = f1_init, f1_end
            template_vars_template = RequestContext(request, template_vars)
            return render_to_response("consumption_centers/graphs/factor_potencia_b.html", template_vars_template)
    else:
        return HttpResponse(content="", content_type="text/html")


def perfil_carga(request):
    template_vars = {"type":"profile"}
    #second interval, None by default
    f2_init = None
    f2_end = None

    f1_init, f1_end = get_intervals_1(request.GET)

    if request.GET:

        if "f2_init" in request.GET:
            f2_init, f2_end = get_intervals_2(request.GET)
        for key in request.GET:
            if re.search('^compare_to\d+', key):
                # "compare", request.session['main_building'], "with building", key
                building_compare = Building.objects.get(pk=int(key))
                template_vars['compare_interval_pf'] = get_PF(building_compare, f1_init, f1_end)
                template_vars['compare_interval_kvar'] = get_KVar(building_compare, f1_init, f1_end)
                template_vars['compare_interval_kw'] = get_KW(building_compare, f1_init, f1_end)
                if f2_init:
                    template_vars['compare_interval2_pf'] = get_PF(building_compare, f2_init, f2_end)
                    template_vars['compare_interval2_kvar'] = get_KVar(building_compare, f2_init, f2_end)
                    template_vars['compare_interval2_kw'] = get_KW(building_compare, f2_init, f2_end)
    template_vars['building']=request.session['main_building'].pk
    template_vars['fi'], template_vars['ff'] = f1_init, f1_end
    #template_vars['main_interval_kw'], \
    #template_vars['fi'], \
    #template_vars['ff'] = get_KW(request.session['main_building'], f1_init, f1_end)

    if f2_init:
        template_vars['main_interval2_pf'] = get_PF(request.session['main_building'], f2_init, f2_end)
        template_vars['main_interval_kvar_kw2'] = get_power_profile(request.session['main_building'], f2_init, f2_end)

    template_vars_template = RequestContext(request, template_vars)
    return render_to_response("consumption_centers/graphs/perfil_carga.html", template_vars_template)

def set_default_building(request, id_building):
    request.session['main_building'] = Building.objects.get(pk=id_building)
    if 'referer' in request.GET:
        if request.GET['referer'] == "cfe":
            return HttpResponseRedirect("/reportes/cfe/")
    return HttpResponse(status=200)

def recibocfe(request):

    #Obtiene los registros de un medidor en un determinado periodo de tiempo
    start_date, end_date = get_intervals_1(request.GET)
    consumer_unit = ConsumerUnit.objects.get(building=request.session['main_building'])
    pr_powermeter = ProfilePowermeter.objects.get(pk=consumer_unit.profile_powermeter.pk)
    region = request.session['main_building'].region

    vars=dict(tarifa=tarifaHM_total(pr_powermeter, start_date, end_date, region, request.session['main_building'].electric_rate))
    print vars
    variables = RequestContext(request, vars)
    return render_to_response('consumption_centers/cfe.html', variables)

def get_medition_in_time(building, datetime_from, datetime_to):
    """ Gets the meditions registered in a time window

    building = Building model instance
    datetime_from = lower date limit
    datetime_to = upper date limit

    Right now we are assuming that there is only a powermeter(and one consumer unit) per building

    """

    consumer_unit = ConsumerUnit.objects.get(building=building)
    profile_powermeter = ProfilePowermeter.objects.get(pk=consumer_unit.profile_powermeter.pk)
    date_gte = datetime_from.replace(hour=0,minute=0,second=0,tzinfo=timezone.get_current_timezone())
    date_lte = datetime_to.replace(hour=23,minute=59,second=59,tzinfo=timezone.get_current_timezone())
    #date_gte = datetime_from-timedelta(hours=5)
    #date_lte = datetime_to+timedelta(days=1)-timedelta(hours=5)

    meditions = ElectricData.objects.filter(profile_powermeter=profile_powermeter,
        medition_date__range=(date_gte, date_lte)).order_by("medition_date")
    print consumer_unit.building, profile_powermeter.pk, date_gte, date_lte
    return meditions

def get_KW(building, datetime_from, datetime_to):
    """ Gets the KW data in a given interval"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    kw=[]
    fi = None
    for medition in meditions:
        if not fi:
            fi=medition.medition_date
        kw.append(dict(kw=medition.kW, date=medition.medition_date))
    ff = meditions[len(meditions)-1].medition_date
    return kw, fi, ff

def get_KW_json(building, datetime_from, datetime_to):
    """ Gets the KW data in a given interval"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    kw=[]
    for medition in meditions:
        kw.append(dict(kw=str(medition.kW), date=int(time.mktime(medition.medition_date.timetuple()))))

    return simplejson.dumps(kw)

def get_KW_json_b(buildings, datetime_from, datetime_to):
    #pdb.set_trace()

    meditions_json = []
    buildings_number = len(buildings)
    if buildings_number < 1:
        return simplejson.dumps(meditions_json)

    buildings_meditions = []
    for building in buildings:
        buildings_meditions.append(get_medition_in_time(building, datetime_from, datetime_to))

    meditions_number = len(buildings_meditions[0])

    for medition_index in range(0, meditions_number):
        current_medition = None
        meditions_kw = []
        for building_index in range(0, buildings_number):
            #print buildings_meditions[building_index][medition_index]
            current_medition = buildings_meditions[building_index][medition_index]
            meditions_kw.append(str(current_medition.kW))

        meditions_json.append(dict(meditions = meditions_kw, date = int(time.mktime(current_medition.medition_date.timetuple()))))

    return simplejson.dumps(meditions_json)

def get_KVar(building, datetime_from, datetime_to):
    """ Gets the KW data in a given interval"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    kvar=[]
    for medition in meditions:
        kvar.append(dict(kvar=medition.kvar, date=medition.medition_date))

    return kvar

def get_KVar_json(building, datetime_from, datetime_to):
    """ Gets the KVar data in a given interval"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    kvar=[]
    for medition in meditions:
        kvar.append(dict(kvar=str(medition.kvar), date=int(time.mktime(medition.medition_date.timetuple()))))

    return simplejson.dumps(kvar)


def get_PF(building, datetime_from, datetime_to):
    """ Gets the KW data in a given interval"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    pf=[]
    for medition in meditions:
        pf.append(dict(pf=medition.PF, date=medition.medition_date))
    return pf

def get_PF_json(building, datetime_from, datetime_to):
    """ Gets the PF data in a given interval"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    pf=[]
    for medition in meditions:
        pf.append(dict(pf=str(medition.PF), date=int(time.mktime(medition.medition_date.timetuple()))))

    return simplejson.dumps(pf)


def get_power_profile(building, datetime_from, datetime_to):
    """ gets the data from the active and reactive energy for a building in a time window"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    kvar=[]
    kw=[]
    for medition in meditions:
        kw.append(dict(kw=medition.kW, date=medition.medition_date))
        kvar.append(dict(kvar=medition.kvar, date=medition.medition_date))
    return zip(kvar,kw)


def get_power_profile_json(building, datetime_from, datetime_to):
    """ gets the data from the active and reactive energy for a building in a time window"""
    meditions = get_medition_in_time(building, datetime_from, datetime_to)
    #kvar=[]
    kw=[]
    for medition in meditions:
        kw.append(dict(kw=str(medition.kW), kvar=str(medition.kvar), date=int(time.mktime(medition.medition_date.timetuple()))))
        #kvar.append(dict(kvar=str(medition.kvar), date=int(time.mktime(medition.medition_date.timetuple()))))
    return simplejson.dumps(kw)


