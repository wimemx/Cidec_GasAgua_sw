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
                PaisEstado(pais=valid['pais'], estado=valid['estado']).save()
                message = "El Pais-Estado se ha agregado correctamente"
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
    pass
def delete_municipality_state(request, id_edo_munip):
    pass
def delete_neighboorhood_municipality(request, id_munip_col):
    pass
def delete_street_neighboor(request, id_col_calle):
    pass