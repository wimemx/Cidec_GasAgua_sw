# -*- coding: utf-8 -*-
import variety
import json as simplejson
#local application/library specific imports
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.context import RequestContext
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, InvalidPage

from location.models import *
from rbac.models import Operation
from rbac.rbac_functions import  has_permission, get_buildings_context, graphs_permission

VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")

def validate_add_state(post):
    valid = dict(error=False)
    if not post['country'] or not post['pais'] or not post['estado']:
        valid['error'] = True
    else:
        valid['pais'] = get_object_or_404(Pais, pk=int(post['country']))
        if validate_string(post['estado']):
            valid['estado'], created = Estado.objects.get_or_create(estado_name=post['estado'].strip())
        else:
            valid['error'] = True
    return valid

def add_state(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )
        if request.method == "POST":
            valid = validate_add_state(request.POST)
            if not valid['error']:
                p_e, created = PaisEstado.objects.get_or_create(pais=valid['pais'], estado=valid['estado'])
                if created:
                    message = "El País-Estado se ha agregado correctamente"
                else:
                    message = "El país estado ya existe, no se aplicó ninguna operación"
                return HttpResponseRedirect("/location/ver_estados?msj=" +
                                            message +
                                            "&ntype=n_success")

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_state.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def edit_state(request, id_state_country):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        pais_estado = get_object_or_404(PaisEstado, pk=id_state_country)
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )

    else:
        return render_to_response("generic_error.html", RequestContext(request))

def add_municipality(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )
        pass
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def edit_municipality(request, id_edo_munip):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )
        pass
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def add_neighboorhood(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )
        pass
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def edit_neighboorhood(request, id_munip_col):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )
        pass
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def add_street(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )
        pass
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def edit_street(request, id_col_calle):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )
        pass
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def state_list(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )
        pass
    else:
        return render_to_response("generic_error.html", RequestContext(request))
def municipality_list(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )
        pass
    else:
        return render_to_response("generic_error.html", RequestContext(request))
def neighboorhood_list(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )
        pass
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def street_list(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )

        if "search" in request.GET:
            search = request.GET["search"]
            search=search.strip()
        else:
            search = ''

        order_by = "calle" #default order
        order_desc = False
        if "order_calle" in request.GET:

            if request.GET["order_calle"] == "desc":
                order_desc = True
        elif "order_colonia" in request.GET:

            if request.GET["order_colonia"] == "asc":
                order = "colonia"
            else:
                order = "colonia"
                order_desc = True
        elif "order_municipio" in request.GET:

            if request.GET["order_municipio"] == "asc":
                order = "municipio"
            else:
                order_desc = True
        elif "order_estado" in request.GET:

            if request.GET["order_estado"] == "asc":
                order = "estado"
            else:
                order_desc = True
        if search:
            estados_m = EstadoMunicipio.objects.filter(Q(estado__estado_name__icontains=search)|Q(municipio_municipio_name__icontains=search))
            muns = [em.municipio.pk for em in estados_m]
            muns_col = MunicipioColonia.objects.filter(Q(municipio__pk__in=muns)|Q(colonia__colonia_name__icontains=search))
            cols = [mc.colonia.pk for mc in muns_col]
            c_calles = ColoniaCalle.objects.filter(Q(colonia__pk__in=cols)|Q(calle__callename__icontains="search"))

        else:
            c_calles = ColoniaCalle.objects.all()

        lista=[]
        for calle in c_calles:
            col_mun = MunicipioColonia.objects.get(colonia=calle.colonia)
            estado_m = EstadoMunicipio.objects.get(municipio=col_mun.municipio)
            lista.append(dict(id_c_calle=calle.pk, calle=calle.calle.calle_name,
                colonia=calle.colonia,
                municipio=estado_m.municipio.municipio_name,
                estado=estado_m.estado.estado_name)
            )
        lista = sorted(lista, key=lambda k: k['name'], reverse=order_desc)
        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name, order_username=order_username,
            order_email=order_email, datacontext=datacontext, empresa=empresa, company=company)
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
        return render_to_response("rbac/user_list.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def add_street(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company']
        )
        pass
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def search_country(request):
    if "term" in request.GET:
        term = request.GET['term']
        paises = Pais.objects.filter(pais_name__icontains=term)
        countries = []
        for pais in paises:
            countries.append(dict(value=pais.pais_name, pk=pais.pk, label=pais.pais_name))
        data=simplejson.dumps(countries)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def search_state(request):
    if "term" in request.GET:
        term = request.GET['term']
        estados = Estado.objects.filter(estado_name__icontains=term)
        states = []
        for estado in estados:
            states.append(dict(value=estado.estado_name, pk=estado.pk,
                               label=estado.estado_name))
        data=simplejson.dumps(states)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def search_municipality(request):
    if "term" in request.GET:
        term = request.GET['term']
        municipios = Municipio.objects.filter(municipio_name__icontains=term)
        municipalities = []
        for municipio in municipios:
            municipalities.append(dict(value=municipio.municipio_name, pk=municipio.pk,
                                       label=municipio.municipio_name))
        data=simplejson.dumps(municipalities)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def search_neighboorhood(request):
    if "term" in request.GET:
        term = request.GET['term']
        colonias = Colonia.objects.filter(colonia_name__icontains=term)
        neighboorhoods = []
        for colonia in colonias:
            neighboorhoods.append(dict(value=colonia.colonia_name, pk=colonia.pk,
                                       label=colonia.colonia_name))
        data=simplejson.dumps(neighboorhoods)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def search_street(request):
    if "term" in request.GET:
        term = request.GET['term']
        calles = Calle.objects.filter(calle_name__icontains=term)
        streets = []
        for calle in calles:
            streets.append(dict(value=calle.calle_name, pk=calle.pk, label=calle.calle_name))
        data=simplejson.dumps(streets)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def delete_state_country(request, id_state_country):
    if request.user.is_superuser:
        state_country = get_object_or_404(PaisEstado, pk=id_state_country)
        state_country.delete()
        mensaje = "Se ha eliminado correctamente la asociación entre el país y el estado"
        return HttpResponseRedirect("/location/ver_estados/?msj=" + mensaje +
                                    "&ntype=success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def delete_municipality_state(request, id_edo_munip):
    if request.user.is_superuser:
        edo_munip = get_object_or_404(EstadoMunicipio, pk=id_edo_munip)
        edo_munip.delete()
        mensaje = "Se ha eliminado correctamente la asociación entre el estado y el municipio"
        return HttpResponseRedirect("/location/ver_municipios?msj=" + mensaje +
                                    "&ntype=success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_neighboorhood_municipality(request, id_munip_col):
    if request.user.is_superuser:
        munip_col = get_object_or_404(MunicipioColonia, pk=id_munip_col)
        munip_col.delete()
        mensaje = "Se ha eliminado correctamente la asociación entre el municipio y la colonia"
        return HttpResponseRedirect("/location/ver_municipios?msj=" + mensaje +
                                    "&ntype=success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_street_neighboor(request, id_col_calle):
    if request.user.is_superuser:
        col_calle = get_object_or_404(ColoniaCalle, pk=id_col_calle)
        col_calle.delete()
        mensaje = "Se ha eliminado correctamente la asociación entre la colonia y la calle"
        return HttpResponseRedirect("/location/ver_municipios?msj=" + mensaje +
                                    "&ntype=success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_state_country_batch(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^p_estado_\w+', key):
                    r_id = int(key.replace("p_estado_",""))
                    object = get_object_or_404(PaisEstado, pk=r_id)
                    object.delete()
            mensaje = "Las relaciones País-Estado han sido eliminadas"
            return HttpResponseRedirect("/location/ver_estados/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/location/ver_estados/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def delete_municipality_state_batch(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^e_municip_\w+', key):
                    r_id = int(key.replace("e_municip_",""))
                    object = get_object_or_404(EstadoMunicipio, pk=r_id)
                    object.delete()
            mensaje = "Las relaciones Estado-Municipio han sido eliminadas"
            return HttpResponseRedirect("/location/ver_municipios/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/location/ver_municipios/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def delete_neighboorhood_municipality_batch(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^m_col_\w+', key):
                    r_id = int(key.replace("m_col_",""))
                    object = get_object_or_404(MunicipioColonia, pk=r_id)
                    object.delete()
            mensaje = "Las relaciones Municipio-Colonia han sido eliminadas"
            return HttpResponseRedirect("/location/ver_colonias/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/location/ver_colonias/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def delete_street_neighboor_batch(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^c_calle_\w+', key):
                    r_id = int(key.replace("c_calle_",""))
                    object = get_object_or_404(ColoniaCalle, pk=r_id)
                    object.delete()
            mensaje = "Las relaciones Colonia-calle han sido eliminadas"
            return HttpResponseRedirect("/location/ver_calles/?msj=" + mensaje +
                                        "&ntype=n_success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/location/ver_calles/?msj=" + mensaje +
                                        "&ntype=n_success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))