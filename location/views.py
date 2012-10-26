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
from django.db.models.deletion import ProtectedError
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
        if variety.validate_string(post['estado']):
            valid['estado'] = Estado(estado_name=post['estado'].strip())
            valid['estado'].save()
        else:
            valid['error'] = True
    return valid

def validate_add_municipality(post):
    valid = dict(error=False)
    if not post['state'] or not post['estado'] or not post['municipio']:
        valid['error'] = True
    else:
        valid['estado'] = get_object_or_404(Estado, pk=int(post['state']))
        if variety.validate_string(post['municipio']):
            valid['municipio'] = Municipio(municipio_name=post['municipio'].strip())
            valid['municipio'].save()
        else:
            valid['error'] = True
    return valid

def validate_add_neighboorhood(post):
    valid = dict(error=False)
    if not post['municipality'] or not post['municipio'] or not post['colonia']:
        valid['error'] = True
    else:
        valid['municipio'] = get_object_or_404(Municipio, pk=int(post['municipality']))
        if variety.validate_string(post['colonia']):
            valid['colonia'] = Colonia(colonia_name=post['colonia'].strip())
            valid['colonia'].save()
        else:
            valid['error'] = True
    return valid

def validate_add_street(post):
    valid = dict(error=False)
    if not post['neighboorhood'] or not post['colonia'] or not post['calle']:
        valid['error'] = True
    else:
        valid['colonia'] = get_object_or_404(Colonia, pk=int(post['neighboorhood']))
        if variety.validate_string(post['colonia']):
            valid['calle'] = Calle(calle_name=post['calle'].strip())
            valid['calle'].save()
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
            company=request.session['company'],
            operation="add"
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
                                            "&ntype=success")
            else:
                template_vars['message'] = "ha ocurrido un error al validar el nombre del estado"
                template_vars['type'] = "n_error"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_state.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def edit_state(request, id_state_country):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        pais_estado = get_object_or_404(PaisEstado, pk=id_state_country)
        pais = pais_estado.pais.pais_name
        estado = pais_estado.estado.estado_name
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation = "edit",
            pais = pais,
            estado = estado
        )
        if request.method == "POST":
            estado = request.POST['estado'].strip()
            if variety.validate_string(estado):
                pais_estado.estado.estado_name = estado
                pais_estado.estado.save()
                message = "El estado se ha modificado correctamente"
                ntype = "success"
            else:
                message = "ha ocurrido un error al validar el nombre del estado"
                ntype = "n_error"
            return HttpResponseRedirect("/location/ver_estados?msj=" + message + "&ntype=" +
                                        ntype)
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_state.html", template_vars_template)

    else:
        return render_to_response("generic_error.html", RequestContext(request))

def add_municipality(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation="add"
        )
        if request.method == "POST":
            valid = validate_add_municipality(request.POST)
            if not valid['error']:
                p_e, created = EstadoMunicipio.objects.get_or_create(estado=valid['estado'], municipio=valid['municipio'])
                if created:
                    message = "El Estado-Municipio se ha agregado correctamente"
                else:
                    message = "El Estado-Municipio ya existe, no se aplicó ninguna operación"
                return HttpResponseRedirect("/location/ver_municipios?msj=" +
                                            message +
                                            "&ntype=success")
            else:
                template_vars['message'] = "ha ocurrido un error al validar el nombre del municipio"
                template_vars['type'] = "n_error"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_municipality.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def edit_municipality(request, id_edo_munip):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        estado_municipio = get_object_or_404(EstadoMunicipio, pk=id_edo_munip)
        pais_est = PaisEstado.objects.get(estado=estado_municipio.estado)
        municipio = estado_municipio.municipio.municipio_name
        estado = pais_est.estado.estado_name
        pais =pais_est.pais.pais_name
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation = "edit",
            municipio = municipio,
            estado = estado,
            pais = pais
        )
        if request.method == "POST":
            municipio = request.POST['municipio'].strip()
            if variety.validate_string(municipio):
                estado_municipio.municipio.municipio_name = municipio
                estado_municipio.municipio.save()
                message = "El municipio se ha modificado correctamente"
                ntype = "success"
            else:
                message = "ha ocurrido un error al validar el nombre del municipio"
                ntype = "n_error"
            return HttpResponseRedirect("/location/ver_municipios?msj=" + message + "&ntype=" +
                                        ntype)
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_municipality.html", template_vars_template)

    else:
        return render_to_response("generic_error.html", RequestContext(request))

def add_neighboorhood(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation="add"
        )
        if request.method == "POST":
            valid = validate_add_neighboorhood(request.POST)
            if not valid['error']:
                p_e, created = MunicipioColonia.objects.get_or_create(municipio=valid['municipio'], colonia=valid['colonia'])
                if created:
                    message = "El Municipio-Colonia se ha agregado correctamente"
                else:
                    message = "El Municipio-Colonia ya existe, no se aplicó ninguna operación"
                return HttpResponseRedirect("/location/ver_colonias?msj=" +
                                            message + "&ntype=success")
            else:
                template_vars['message'] = "ha ocurrido un error al validar el nombre de la colonia"
                template_vars['type'] = "n_error"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_neighboorhood.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def edit_neighboorhood(request, id_munip_col):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        municipio_colonia = get_object_or_404(MunicipioColonia, pk=id_munip_col)
        est_mun = EstadoMunicipio.objects.get(municipio=municipio_colonia.municipio)
        pais_est = PaisEstado.objects.get(estado=est_mun.estado)
        colonia = municipio_colonia.colonia.colonia_name
        municipio = est_mun.municipio.municipio_name
        estado = pais_est.estado.estado_name
        pais =pais_est.pais.pais_name
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation = "edit",
            colonia = colonia,
            municipio = municipio,
            estado = estado,
            pais = pais
        )
        if request.method == "POST":
            colonia = request.POST['colonia'].strip()
            if variety.validate_string(municipio):
                municipio_colonia.colonia.colonia_name = colonia
                municipio_colonia.colonia.save()
                message = "La colonia se ha modificado correctamente"
                ntype = "success"
            else:
                message = "ha ocurrido un error al validar el nombre de la colonia"
                ntype = "n_error"
            return HttpResponseRedirect("/location/ver_colonias?msj=" + message + "&ntype=" +
                                        ntype)
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_neighboorhood.html", template_vars_template)

    else:
        return render_to_response("generic_error.html", RequestContext(request))

def add_street(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation="add"
        )
        if request.method == "POST":
            valid = validate_add_street(request.POST)
            if not valid['error']:
                p_e, created = ColoniaCalle.objects.get_or_create(colonia=valid['colonia'], calle=valid['calle'])
                if created:
                    message = "La calle-colonia se ha agregado correctamente"
                else:
                    message = "La calle-colonia ya existe, no se aplicó ninguna operación"
                return HttpResponseRedirect("/location/ver_calles?msj=" +
                                            message +
                                            "&ntype=success")
            else:
                template_vars['message'] = "ha ocurrido un error al validar el nombre de la calle"
                template_vars['type'] = "n_error"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_street.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def edit_street(request, id_col_calle):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if request.user.is_superuser:
        calle_colonia = get_object_or_404(ColoniaCalle, pk=id_col_calle)
        mun_col = MunicipioColonia.objects.get(colonia=calle_colonia.colonia)
        est_mun = EstadoMunicipio.objects.get(municipio=mun_col.municipio)
        pais_est = PaisEstado.objects.get(estado=est_mun.estado)
        calle = calle_colonia.calle.calle_name
        colonia = mun_col.colonia.colonia_name
        municipio = est_mun.municipio.municipio_name
        estado = pais_est.estado.estado_name
        pais =pais_est.pais.pais_name
        template_vars = dict(
            datacontext=get_buildings_context(request.user),
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation = "edit",
            calle = calle,
            colonia = colonia,
            municipio = municipio,
            estado = estado,
            pais = pais
        )
        if request.method == "POST":
            calle = request.POST['calle'].strip()
            if variety.validate_string(calle):
                calle_colonia.calle.calle_name = calle
                calle_colonia.calle.save()
                message = "La calle se ha modificado correctamente"
                ntype = "success"
            else:
                message = "ha ocurrido un error al validar el nombre de la calle"
                ntype = "n_error"
            return HttpResponseRedirect("/location/ver_calles?msj=" + message + "&ntype=" +
                                        ntype)
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_street.html", template_vars_template)
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

        if "search" in request.GET:
            search = request.GET["search"]
            search=search.strip()
        else:
            search = ''

        order = "estado" #default order
        order_desc = False
        order_pais = "asc"
        order_estado = "asc"
        if "order_pais" in request.GET:
            order = "pais"
            if request.GET["order_pais"] == "desc":
                order_desc = True
            else:
                order_pais = "asc"
        elif "order_estado" in request.GET:
            order = "estado"
            if request.GET["order_estado"] == "asc":
                order_estado = "desc"
            else:
                order_desc = True
        if search:
            e_p = PaisEstado.objects.filter(Q(estado__estado_name__icontains=search)|Q(pais__pais_name__icontains=search))

        else:
            e_p = PaisEstado.objects.all()

        lista=[]
        for e_ in e_p:
            lista.append(dict(id_pais_estado=e_.pk, estado=e_.estado.estado_name,
                              pais=e_.pais.pais_name)
            )
        lista = sorted(lista, key=lambda k: k[order], reverse=order_desc)
        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars['order_pais'] = order_pais
        template_vars['order_estado'] = order_estado


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
        return render_to_response("location/states_list.html", template_vars_template)
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

        if "search" in request.GET:
            search = request.GET["search"]
            search=search.strip()
        else:
            search = ''

        order = "municipio" #default order
        order_desc = False
        order_municipio = "asc"
        order_estado = "asc"
        if "order_municipio" in request.GET:
            order = "municipio"
            if request.GET["order_municipio"] == "asc":
                order_municipio = "desc"
            else:
                order_desc = True
        elif "order_estado" in request.GET:
            order = "estado"
            if request.GET["order_estado"] == "asc":
                order_estado = "desc"
            else:
                order_desc = True
        if search:
            estados_m = EstadoMunicipio.objects.filter(Q(estado__estado_name__icontains=search)|Q(municipio__municipio_name__icontains=search))
        else:
            estados_m = EstadoMunicipio.objects.all()

        lista=[]
        for estados_ in estados_m:
            lista.append(dict(id_est_mun=estados_.pk,
                municipio=estados_.municipio.municipio_name,
                estado=estados_.estado.estado_name)
            )
        lista = sorted(lista, key=lambda k: k[order], reverse=order_desc)
        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars['order_municipio'] = order_municipio
        template_vars['order_estado'] = order_estado


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
        return render_to_response("location/municipalities_list.html", template_vars_template)
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

        if "search" in request.GET:
            search = request.GET["search"]
            search=search.strip()
        else:
            search = ''

        order = "colonia" #default order
        order_desc = False
        order_colonia = "asc"
        order_municipio = "asc"
        order_estado = "asc"
        if "order_colonia" in request.GET:
            order = "colonia"
            if request.GET["order_colonia"] == "asc":
                order_colonia = "desc"
            else:
                order_desc = True
        elif "order_municipio" in request.GET:
            order = "municipio"
            if request.GET["order_municipio"] == "asc":
                order_municipio = "desc"
            else:
                order_desc = True
        elif "order_estado" in request.GET:
            order = "estado"
            if request.GET["order_estado"] == "asc":
                order_estado = "desc"
            else:
                order_desc = True
        if search:
            estados_m = EstadoMunicipio.objects.filter(Q(estado__estado_name__icontains=search)|Q(municipio__municipio_name__icontains=search))
            muns = [em.municipio.pk for em in estados_m]
            muns_col = MunicipioColonia.objects.filter(Q(municipio__pk__in=muns)|Q(colonia__colonia_name__icontains=search))

        else:
            muns_col = MunicipioColonia.objects.all()

        lista=[]
        for muns_ in muns_col:
            col_mun = MunicipioColonia.objects.get(colonia=muns_.colonia)
            estado_m = EstadoMunicipio.objects.get(municipio=col_mun.municipio)
            lista.append(dict(id_mun_col=muns_.pk,
                colonia=muns_.colonia.colonia_name,
                municipio=estado_m.municipio.municipio_name,
                estado=estado_m.estado.estado_name)
            )
        lista = sorted(lista, key=lambda k: k[order], reverse=order_desc)
        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars['order_colonia'] = order_colonia
        template_vars['order_municipio'] = order_municipio
        template_vars['order_estado'] = order_estado


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
        return render_to_response("location/neighboorhood_list.html", template_vars_template)
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

        order = "calle" #default order
        order_desc = False
        order_calle = "asc"
        order_colonia = "asc"
        order_municipio = "asc"
        order_estado = "asc"
        if "order_calle" in request.GET:

            if request.GET["order_calle"] == "desc":
                order_desc = True
        elif "order_colonia" in request.GET:
            order = "colonia"
            if request.GET["order_colonia"] == "asc":
                order_colonia = "desc"
            else:
                order_desc = True
        elif "order_municipio" in request.GET:
            order = "municipio"
            if request.GET["order_municipio"] == "asc":
                order_municipio = "desc"
            else:
                order_desc = True
        elif "order_estado" in request.GET:
            order = "estado"
            if request.GET["order_estado"] == "asc":
                order_estado = "desc"
            else:
                order_desc = True
        if search:
            estados_m = EstadoMunicipio.objects.filter(
                                                Q(estado__estado_name__icontains=search)|
                                                Q(municipio__municipio_name__icontains=search))
            muns = [em.municipio.pk for em in estados_m]
            muns_col = MunicipioColonia.objects.filter(
                                                    Q(municipio__pk__in=muns)|
                                                    Q(colonia__colonia_name__icontains=search))
            cols = [mc.colonia.pk for mc in muns_col]
            c_calles = ColoniaCalle.objects.filter(
                                                Q(colonia__pk__in=cols)|
                                                Q(calle__callename__icontains=search))

        else:
            c_calles = ColoniaCalle.objects.all()

        lista=[]
        for calle in c_calles:
            col_mun = MunicipioColonia.objects.get(colonia=calle.colonia)
            estado_m = EstadoMunicipio.objects.get(municipio=col_mun.municipio)
            lista.append(dict(id_c_calle=calle.pk, calle=calle.calle.calle_name,
                colonia=calle.colonia.colonia_name,
                municipio=estado_m.municipio.municipio_name,
                estado=estado_m.estado.estado_name)
            )
        lista = sorted(lista, key=lambda k: k[order], reverse=order_desc)
        paginator = Paginator(lista, 10) # muestra 10 resultados por pagina
        template_vars['order_calle'] = order_calle
        template_vars['order_colonia'] = order_colonia
        template_vars['order_municipio'] = order_municipio
        template_vars['order_estado'] = order_estado


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
        return render_to_response("location/streets_list.html", template_vars_template)
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
    """get a list of states wich contains 'term' and are in a certain 'country'"""
    if "term" in request.GET and "country" in request.GET:
        term = request.GET['term']
        pais_est = PaisEstado.objects.filter(pais__pk=int(request.GET['country']),
                                             estado__estado_name__icontains=term)
        states = []
        for estado in pais_est:
            label = estado.pais.pais_name + "-" + estado.estado.estado_name
            states.append(dict(value=estado.estado.estado_name, pk=estado.estado.pk,
                               label=label))
        data=simplejson.dumps(states)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def search_municipality(request):
    """get a list of municipalities wich contains 'term' and are in a certain 'state'"""
    if "term" in request.GET and "state" in request.GET:
        term = request.GET['term']
        e_munip = EstadoMunicipio.objects.filter(estado__pk=int(request.GET['state']),
                                                 municipio__municipio_name__icontains=term)

        municipalities = []
        for municipio in e_munip:
            label = municipio.estado.estado_name + " - " + municipio.municipio.municipio_name
            municipalities.append(dict(value=municipio.municipio.municipio_name,
                                       pk=municipio.municipio.pk, label=label))
        data=simplejson.dumps(municipalities)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def search_neighboorhood(request):
    """get a list of neighboorhoods wich contains 'term' and are in a certain 'municipality'"""
    if "term" in request.GET and "municipality" in request.GET:
        term = request.GET['term']

        mun_cols=MunicipioColonia.objects.filter(municipio__pk=int(request.GET['municipality'])
                                                 , colonia__colonia_name__icontains=term)
        neighboorhoods = []
        for colonia in mun_cols:
            label = colonia.municipio.municipio_name + " - " + colonia.colonia.colonia_name
            neighboorhoods.append(dict(value=colonia.colonia.colonia_name,
                                       pk=colonia.colonia.pk, label=label))
        data=simplejson.dumps(neighboorhoods)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def search_street(request):
    """get a list of streets wich contains 'term' and are in a certain 'neighboorhood'"""
    if "term" in request.GET and "neighboorhood" in request.GET:
        term = request.GET['term']

        calle_col = ColoniaCalle.objects.filter(colonia__pk=int(request.GET['neighboorhood']),
                                                calle__calle_name__icontains=term)
        streets = []
        for calle in calle_col:
            label = calle.colonia.colonia_name + " - " + calle.calle.calle_name
            streets.append(dict(value=calle.calle.calle_name, pk=calle.calle.pk, label=label))
        data=simplejson.dumps(streets)
        return HttpResponse(content=data,content_type="application/json")
    else:
        raise Http404

def delete_state_country(request, id_state_country):
    if request.user.is_superuser:
        state_country = get_object_or_404(PaisEstado, pk=id_state_country)
        estado = state_country.estado
        pais = state_country.pais
        state_country.delete()
        try:
            delete_municipalities(estado)
        except ProtectedError:
            PaisEstado(pais=pais, estado=estado).save()
            mensaje = "Ha ocurrido un error de integridad de datos, por favor revisa que no " \
                      "haya ningún dato asociado al estado ni a sus municipios, colonias o " \
                      "calles"
            type = "error"
        else:
            mensaje = "Se ha eliminado correctamente la asociación entre el país y el estado"
            type = "success"
        return HttpResponseRedirect("/location/ver_estados/?msj=" + mensaje +
                                    "&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def delete_municipality_state(request, id_edo_munip):
    if request.user.is_superuser:
        edo_munip = get_object_or_404(EstadoMunicipio, pk=id_edo_munip)
        munip = edo_munip.municipio
        edo = edo_munip.estado
        edo_munip.delete()
        try:
            delete_neigboorhoods(munip)
        except ProtectedError:
            EstadoMunicipio(estado=edo, municipio=munip).save()
            mensaje = "Ha ocurrido un error de integridad de datos, por favor revisa que no " \
                      "haya ningún dato asociado al municipio ni a sus colonias o calles"
            type = "error"
        else:
            mensaje = "Se ha eliminado correctamente la asociación entre el estado y el " \
                      "municipio"
            type = "success"
        return HttpResponseRedirect("/location/ver_municipios?msj=" + mensaje +"&ntype="+type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_neighboorhood_municipality(request, id_munip_col):
    if request.user.is_superuser:
        munip_col = get_object_or_404(MunicipioColonia, pk=id_munip_col)
        colonia = munip_col.colonia
        municipio = munip_col.municipio
        munip_col.delete()
        try:
            delete_streets(colonia)
        except ProtectedError:
            MunicipioColonia(municipio=municipio, colonia=colonia).save()
            mensaje = "Ha ocurrido un error de integridad de datos, por favor revisa que no "\
                      "haya ningún dato asociado a la colonia ni a sus calles"
            type = "error"
        else:
            mensaje = "Se ha eliminado correctamente la asociación entre el municipio y la " \
                      "colonia"
            type = "success"
        return HttpResponseRedirect("/location/ver_colonias?msj=" + mensaje + "&ntype=" + type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_street_neighboor(request, id_col_calle):
    if request.user.is_superuser:
        col_calle = get_object_or_404(ColoniaCalle, pk=id_col_calle)
        calle = col_calle.calle
        colonia = col_calle
        col_calle.delete()
        try:
            calle.delete()
        except ProtectedError:
            ColoniaCalle(colonia=colonia, calle=calle).save()
            mensaje = "Ha ocurrido un error de integridad de datos, por favor revisa que no "\
                      "haya ningún dato asociado a la calle"
            type = "error"
        else:
            mensaje = "Se ha eliminado correctamente la asociación entre el colonia y la "\
                      "calle"
            type = "success"

        return HttpResponseRedirect("/location/ver_municipios?msj=" + mensaje + "&ntype="+type)
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
                if re.search('^estado_\w+', key):
                    r_id = int(key.replace("estado_",""))
                    object = get_object_or_404(PaisEstado, pk=r_id)
                    estado = object.estado
                    pais = object.pais
                    object.delete()
                    try:
                        delete_municipalities(estado)
                    except ProtectedError:
                        PaisEstado(estado=estado, pais=pais).save()
                        mensaje = "Ha ocurrido un error de integridad de datos, por favor " \
                                  "revisa que no haya ningún dato asociado al estado ni a " \
                                  "sus municipios, colonias o calles"
                        return HttpResponseRedirect("/location/ver_estados/?msj=" + mensaje +
                                                    "&ntype=error")
            mensaje = "Las relaciones País-Estado han sido eliminadas"
            return HttpResponseRedirect("/location/ver_estados/?msj=" + mensaje +
                                        "&ntype=success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/location/ver_estados/?msj=" + mensaje +
                                        "&ntype=success")
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
                if re.search('^municipio_\w+', key):
                    r_id = int(key.replace("municipio_",""))
                    object = get_object_or_404(EstadoMunicipio, pk=r_id)
                    mun = object.municipio
                    est = object.estado
                    object.delete()
                    try:
                        delete_neigboorhoods(mun)
                    except ProtectedError:
                        EstadoMunicipio(estado=est, municipio=mun).save()
                        mensaje = "Ha ocurrido un error de integridad de datos, por favor "\
                                  "revisa que no haya ningún dato asociado al municipio, " \
                                  "colonias o calles"
                        return HttpResponseRedirect("/location/ver_municipios/?msj=" +
                                                    mensaje + "&ntype=error")
            mensaje = "Las relaciones Estado-Municipio han sido eliminadas"
            return HttpResponseRedirect("/location/ver_municipios/?msj=" + mensaje +
                                        "&ntype=success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/location/ver_municipios/?msj=" + mensaje +
                                        "&ntype=success")
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
                if re.search('^colonia_\w+', key):
                    r_id = int(key.replace("colonia_",""))
                    object = get_object_or_404(MunicipioColonia, pk=r_id)
                    colonia = object.colonia
                    municipio = object.municipio
                    object.delete()
                    try:
                        delete_streets(colonia)
                    except ProtectedError:
                        MunicipioColonia(municipio=municipio, colonia=colonia).save()
                        mensaje = "Ha ocurrido un error de integridad de datos, por favor "\
                                  "revisa que no haya ningún dato asociado a la colonia, "\
                                  "o sus calles"
                        return HttpResponseRedirect("/location/ver_colonias/?msj=" +
                                                    mensaje + "&ntype=error")
            mensaje = "Las relaciones Municipio-Colonia han sido eliminadas"
            return HttpResponseRedirect("/location/ver_colonias/?msj=" + mensaje +
                                        "&ntype=success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/location/ver_colonias/?msj=" + mensaje +
                                        "&ntype=success")
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
                if re.search('^calle_\w+', key):
                    r_id = int(key.replace("calle_",""))
                    object = get_object_or_404(ColoniaCalle, pk=r_id)
                    calle=object.calle
                    object.delete()#borro la relación
                    calle.delete()#borro la calle
            mensaje = "Las relaciones Colonia-calle han sido eliminadas"
            return HttpResponseRedirect("/location/ver_calles/?msj=" + mensaje +
                                        "&ntype=success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect("/location/ver_calles/?msj=" + mensaje +
                                        "&ntype=success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))

def delete_streets(neighboorhood):
    """Deletes all the streets in a given neighboorhood, then
    deletes itself
    """
    calles = ColoniaCalle.objects.filter(colonia=neighboorhood)
    for c_c in calles:
        calle = c_c.calle
        c_c.delete()
        calle.delete()
    neighboorhood.delete()
    return True

def delete_neigboorhoods(municipality):
    """Deletes all the neighboorhoods and streets in a given municipality, then
    deletes itself
    """
    mun_cols = MunicipioColonia.objects.filter(municipio=municipality)
    for m_c in mun_cols:
        colonia=m_c.colonia
        m_c.delete()
        delete_streets(colonia)
    municipality.delete()
    return True

def delete_municipalities(state):
    """Deletes all the municipalities and neighboorhoods and streets in a given state, then
    deletes itself
    """
    est_muns = EstadoMunicipio.objects.filter(estado=state)
    for e_m in est_muns:
        mun = e_m.municipio
        e_m.delete()
        delete_neigboorhoods(mun)
    state.delete()
    return True