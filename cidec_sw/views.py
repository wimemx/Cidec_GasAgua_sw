# -*- coding: utf-8 -*-
#standard library imports
#for timezone support
import pytz

#related third party imports
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, HttpResponse, Http404
from django.template.context import RequestContext
from django.contrib.auth.decorators import login_required

#local application/library specific imports
from c_center.models import ElectricDataTemp
from c_center.views import main_page, week_report_kwh
from c_center.c_center_functions import set_default_session_vars
from rbac.models import GroupObject, MenuCategs, MenuHierarchy
from rbac.rbac_functions import get_buildings_context
from gas_agua.models import WaterGasData

from django.shortcuts import redirect, render
GRAPHS = ['Potencia Activa (kW)', 'Potencia Reactiva (KVar)',
          'Factor de Potencia (PF)',
          'kW Hora', 'kWh/h Consumido', 'kVAR Hora', 'kVAR Hora Consumido']
GRAPHS_ENERGY = [ob.object.object_name for ob in GroupObject.objects.filter(
    group__group_name="Energía")]
GRAPHS_I = [ob.object.object_name for ob in GroupObject.objects.filter(
    group__group_name="Corriente")]
GRAPHS_V = [ob.object.object_name for ob in GroupObject.objects.filter(
    group__group_name="Voltaje")]
GRAPHS_PF = [ob.object.object_name for ob in GroupObject.objects.filter(
    group__group_name="Factor de Potencia")]
GRAPHS.extend(GRAPHS_ENERGY)
GRAPHS.extend(GRAPHS_I)
GRAPHS.extend(GRAPHS_V)
GRAPHS.extend(GRAPHS_PF)


def set_timezone(request):
    if request.method == 'POST':
        request.session['django_timezone'] = pytz.timezone(
            request.POST['timezone'])
        return redirect('/')
    else:
        return render(request, 'set_timezone.html',
                      {'timezones': pytz.common_timezones})


def _login(request):
    error = username = password = ''
    if request.user.is_authenticated():
        return HttpResponseRedirect("/main/")
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                request.session.set_expiry(1900)
                #valid years for reporting
                request.session['years'] = [__date.year for __date in
                                            ElectricDataTemp.objects.all().
                                            dates('medition_date', 'year')]
                url = "/medition_type_menu/"
                try:
                    ur_get = request.META['HTTP_REFERER']
                except KeyError:
                    pass
                else:
                    ur_get = ur_get.split("next=")
                    if len(ur_get) > 1:
                        url += "?next=" + ur_get[1]
                return HttpResponseRedirect(url)
            else:
                error = "Tu cuenta ha sido desactivada, por favor ponte en " \
                        "contacto con tu administrador"
        else:
            error = "Tu nombre de usuario o contrase&ntilde;a son incorrectos."
    variables = dict(username=username, password=password, error=error)
    variables_template = RequestContext(request, variables)
    return render_to_response("login.html", variables_template)


@login_required(login_url='/')
def index(request):
    if 'main_building' in request.session:
        if WaterGasData.objects.filter(industrial_equipment__building=request.session['main_building']):
            del request.session['main_building']
    menu_option_str = "<ul id='main_menu' class='fr'>"
    #------------------------------------------------------------
    categories = MenuCategs.objects.filter(main=True).order_by("order")
    for category in categories:
        if category.added_class:
            clase = category.added_class
        else:
            clase = ''
        menu_option_str += "<li class='first_level " + clase + "'>"
        if category.categ_access_point:
            menu_option_str += "<a href='" + category.categ_access_point + "'>"
            menu_option_str += category.categ_name
            menu_option_str += "</a>"
        else:
            menu_option_str += category.categ_name
            menu_option_str += get_sub_categs_items(category)
        menu_option_str += "</li>"
    menu_option_str += "</ul>"
    request.session['sidebar'] = menu_option_str

    if 'next' in request.GET:
        datacontext, b_list = get_buildings_context(request.user)
        if not datacontext:
            request.session['consumer_unit'] = None
        set_default_session_vars(request, b_list)
        return HttpResponseRedirect(request.GET['next'])
    elif 'g_type' in request.GET:
        return main_page(request)
    else:
        return week_report_kwh(request)

@login_required(login_url='/')
def medition_type_menu(request):
    return render_to_response("medition_type_menu.html")


def get_sub_categs_items(parent):
    sub_cat = MenuHierarchy.objects.filter(
        parent_cat=parent).order_by("child_cat__order")
    sub_menu = ''
    if sub_cat:
        sub_menu = "<ul class='sub_list hidden'>"
        for sub_c in sub_cat:
            if sub_c.child_cat.added_class:
                clase = sub_c.child_cat.added_class
            else:
                clase = ''
            sub_menu += "<li class='sub_level " + clase + "'>"
            if sub_c.child_cat.categ_access_point:
                sub_menu += "<a href='" + \
                            sub_c.child_cat.categ_access_point + "'>"
                sub_menu += sub_c.child_cat.categ_name
                sub_menu += "</a>"
            elif sub_c.child_cat:
                sub_menu += sub_c.child_cat.categ_name
                sub_menu += get_sub_categs_items(sub_c.child_cat)
            sub_menu += "</li>"
        sub_menu += "</ul>"

    return sub_menu


def logout_page(request):
    logout(request)
    return HttpResponseRedirect('/main/?logout')


@login_required(login_url="/")
def serve_data(request):
    link = "<a href='/static/data.zip'>Descargar informaci&oacute;n del " \
           "proyecto</a>"
    return HttpResponse(content=link, status=200)