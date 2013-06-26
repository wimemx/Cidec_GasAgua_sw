# -*- coding: utf-8 -*-
import variety
import re
import json as simplejson
import datetime
#local application/library specific imports
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.context import RequestContext
from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.db.models.deletion import ProtectedError
from django.contrib.auth.decorators import login_required
from location.models import *
from rbac.models import Operation
from rbac.rbac_functions import  get_buildings_context


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
            pa_es = PaisEstado.objects.filter(pais=valid['pais'],
                                              estado__estado_name=post[
                                                                  'estado'])
            if not pa_es:
                valid['estado'] = Estado(estado_name=post['estado'].strip())
                valid['estado'].save()
            else:
                valid['error'] = True
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
            es_mun = EstadoMunicipio.objects.filter(estado=valid['estado'],
                                                    municipio__municipio_name=
                                                    post['municipio'])
            if not es_mun:
                valid['municipio'] = Municipio(
                    municipio_name=post['municipio'].strip())
                valid['municipio'].save()
            else:
                valid['error'] = True
        else:
            valid['error'] = True
    return valid


def validate_add_neighboorhood(post):
    valid = dict(error=False)
    if not post['municipality'] or not post['municipio'] or not post['colonia']:
        valid['error'] = True
    else:
        valid['municipio'] = get_object_or_404(Municipio,
                                               pk=int(post['municipality']))
        if variety.validate_string(post['colonia']):
            m_col = MunicipioColonia.objects.filter(
                municipio=valid['municipio'],
                colonia__colonia_name=post['colonia'])
            if not m_col:
                valid['colonia'] = Colonia(colonia_name=post['colonia'].strip())
                valid['colonia'].save()
            else:
                valid['error'] = True
        else:
            valid['error'] = True
    return valid


def validate_add_street(post):
    valid = dict(error=False)
    if not post['neighboorhood'] or not post['colonia'] or not post['calle']:
        valid['error'] = True
    else:
        valid['colonia'] = get_object_or_404(Colonia,
                                             pk=int(post['neighboorhood']))
        if variety.validate_string(post['calle']):
            c_col = ColoniaCalle.objects.filter(colonia=valid['colonia'],
                                                calle__calle_name=post['calle'])
            if not c_col:
                valid['calle'] = Calle(calle_name=post['calle'].strip())
                valid['calle'].save()
            else:
                valid['error'] = True
        else:
            valid['error'] = True
    return valid


@login_required(login_url='/')
def add_state(request):
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation="add",
            sidebar=request.session['sidebar']
        )
        if request.method == "POST":
            valid = validate_add_state(request.POST)
            if not valid['error']:
                p_e, created = PaisEstado.objects.get_or_create(
                    pais=valid['pais'], estado=valid['estado'])
                if created:
                    message = "El País-Estado se ha agregado correctamente"
                else:
                    message = "El país estado ya existe, " \
                              "no se aplicó ninguna operación"
                return HttpResponseRedirect("/location/ver_estados?msj=" +
                                            message +
                                            "&ntype=success")
            else:
                template_vars[
                'message'] = "ha ocurrido un error al validar el nombre del " \
                             "estado"
                template_vars['type'] = "n_error"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_state.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def edit_state(request, id_state_country):
    if request.user.is_superuser:
        pais_estado = get_object_or_404(PaisEstado, pk=id_state_country)
        pais = pais_estado.pais.pais_name
        estado = pais_estado.estado.estado_name
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation="edit",
            pais=pais,
            estado=estado,
            sidebar=request.session['sidebar']
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
            return HttpResponseRedirect(
                "/location/ver_estados?msj=" + message + "&ntype=" +
                ntype)
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_state.html",
                                  template_vars_template)

    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def add_municipality(request):
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation="add",
            sidebar=request.session['sidebar']
        )
        if request.method == "POST":
            valid = validate_add_municipality(request.POST)
            if not valid['error']:
                p_e, created = EstadoMunicipio.objects.get_or_create(
                    estado=valid['estado'], municipio=valid['municipio'])
                if created:
                    message = "El Estado-Municipio se ha agregado correctamente"
                else:
                    message = "El Estado-Municipio ya existe, " \
                              "no se aplicó ninguna operación"
                return HttpResponseRedirect("/location/ver_municipios?msj=" +
                                            message +
                                            "&ntype=success")
            else:
                template_vars[
                'message'] = "ha ocurrido un error al validar el nombre del " \
                             "municipio"
                template_vars['type'] = "n_error"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_municipality.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def edit_municipality(request, id_edo_munip):
    if request.user.is_superuser:
        estado_municipio = get_object_or_404(EstadoMunicipio, pk=id_edo_munip)
        pais_est = PaisEstado.objects.get(estado=estado_municipio.estado)
        municipio = estado_municipio.municipio.municipio_name
        estado = pais_est.estado.estado_name
        pais = pais_est.pais.pais_name
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation="edit",
            municipio=municipio,
            estado=estado,
            pais=pais,
            sidebar=request.session['sidebar']
        )
        if request.method == "POST":
            municipio = request.POST['municipio'].strip()
            if variety.validate_string(municipio):
                estado_municipio.municipio.municipio_name = municipio
                estado_municipio.municipio.save()
                message = "El municipio se ha modificado correctamente"
                ntype = "success"
            else:
                message = "ha ocurrido un error al validar el nombre del " \
                          "municipio"
                ntype = "n_error"
            return HttpResponseRedirect(
                "/location/ver_municipios?msj=" + message + "&ntype=" +
                ntype)
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_municipality.html",
                                  template_vars_template)

    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def add_neighboorhood(request):
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation="add",
            sidebar=request.session['sidebar']
        )
        if request.method == "POST":
            valid = validate_add_neighboorhood(request.POST)
            if not valid['error']:
                p_e, created = MunicipioColonia.objects.get_or_create(
                    municipio=valid['municipio'], colonia=valid['colonia'])
                if created:
                    message = "El Municipio-Colonia se ha agregado " \
                              "correctamente"
                else:
                    message = "El Municipio-Colonia ya existe, " \
                              "no se aplicó ninguna operación"
                return HttpResponseRedirect("/location/ver_colonias?msj=" +
                                            message + "&ntype=success")
            else:
                template_vars[
                'message'] = "ha ocurrido un error al validar el nombre de la" \
                             " colonia"
                template_vars['type'] = "n_error"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_neighboorhood.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def edit_neighboorhood(request, id_munip_col):
    if request.user.is_superuser:
        municipio_colonia = get_object_or_404(MunicipioColonia, pk=id_munip_col)
        est_mun = EstadoMunicipio.objects.get(
            municipio=municipio_colonia.municipio)
        pais_est = PaisEstado.objects.get(estado=est_mun.estado)
        colonia = municipio_colonia.colonia.colonia_name
        municipio = est_mun.municipio.municipio_name
        estado = pais_est.estado.estado_name
        pais = pais_est.pais.pais_name
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation="edit",
            colonia=colonia,
            municipio=municipio,
            estado=estado,
            pais=pais,
            sidebar=request.session['sidebar']
        )
        if request.method == "POST":
            colonia = request.POST['colonia'].strip()
            if variety.validate_string(municipio):
                municipio_colonia.colonia.colonia_name = colonia
                municipio_colonia.colonia.save()
                message = "La colonia se ha modificado correctamente"
                ntype = "success"
            else:
                message = "ha ocurrido un error al validar el nombre de la " \
                          "colonia"
                ntype = "n_error"
            return HttpResponseRedirect(
                "/location/ver_colonias?msj=" + message + "&ntype=" +
                ntype)
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_neighboorhood.html",
                                  template_vars_template)

    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def add_street(request):
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation="add",
            sidebar=request.session['sidebar']
        )
        if request.method == "POST":
            valid = validate_add_street(request.POST)
            if not valid['error']:
                p_e, created = ColoniaCalle.objects.get_or_create(
                    colonia=valid['colonia'], calle=valid['calle'])
                if created:
                    message = "La calle-colonia se ha agregado correctamente"
                else:
                    message = "La calle-colonia ya existe, " \
                              "no se aplicó ninguna operación"
                return HttpResponseRedirect("/location/ver_calles?msj=" +
                                            message +
                                            "&ntype=success")
            else:
                template_vars[
                'message'] = "ha ocurrido un error al validar el nombre de la" \
                             " calle"
                template_vars['type'] = "n_error"

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_street.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def edit_street(request, id_col_calle):
    if request.user.is_superuser:
        calle_colonia = get_object_or_404(ColoniaCalle, pk=id_col_calle)
        mun_col = MunicipioColonia.objects.get(colonia=calle_colonia.colonia)
        est_mun = EstadoMunicipio.objects.get(municipio=mun_col.municipio)
        pais_est = PaisEstado.objects.get(estado=est_mun.estado)
        calle = calle_colonia.calle.calle_name
        colonia = mun_col.colonia.colonia_name
        municipio = est_mun.municipio.municipio_name
        estado = pais_est.estado.estado_name
        pais = pais_est.pais.pais_name
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            operation="edit",
            calle=calle,
            colonia=colonia,
            municipio=municipio,
            estado=estado,
            pais=pais,
            sidebar=request.session['sidebar']
        )
        if request.method == "POST":
            calle = request.POST['calle'].strip()
            if variety.validate_string(calle):
                calle_colonia.calle.calle_name = calle
                calle_colonia.calle.save()
                message = "La calle se ha modificado correctamente"
                ntype = "success"
            else:
                message = "ha ocurrido un error al validar el nombre de la " \
                          "calle"
                ntype = "n_error"
            return HttpResponseRedirect(
                "/location/ver_calles?msj=" + message + "&ntype=" +
                ntype)
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_street.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def state_list(request):
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            sidebar=request.session['sidebar']
        )

        if "search" in request.GET:
            search = request.GET["search"]
            search = search.strip()
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
            e_p = PaisEstado.objects.filter(
                Q(estado__estado_name__icontains=search) | Q(
                    pais__pais_name__icontains=search))

        else:
            e_p = PaisEstado.objects.all()

        lista = []
        for e_ in e_p:
            lista.append(
                dict(id_pais_estado=e_.pk, estado=e_.estado.estado_name,
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

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/states_list.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def municipality_list(request):
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            sidebar=request.session['sidebar']
        )

        if "search" in request.GET:
            search = request.GET["search"]
            search = search.strip()
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
            estados_m = EstadoMunicipio.objects.filter(
                Q(estado__estado_name__icontains=search) | Q(
                    municipio__municipio_name__icontains=search))
        else:
            estados_m = EstadoMunicipio.objects.all()

        lista = []
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

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/municipalities_list.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def neighboorhood_list(request):
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            sidebar=request.session['sidebar']
        )

        if "search" in request.GET:
            search = request.GET["search"]
            search = search.strip()
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
            estados_m = EstadoMunicipio.objects.filter(
                Q(estado__estado_name__icontains=search) | Q(
                    municipio__municipio_name__icontains=search))
            muns = [em.municipio.pk for em in estados_m]
            muns_col = MunicipioColonia.objects.filter(
                Q(municipio__pk__in=muns) | Q(
                    colonia__colonia_name__icontains=search))

        else:
            muns_col = MunicipioColonia.objects.all()

        lista = []
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

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/neighboorhood_list.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def street_list(request):
    if request.user.is_superuser:
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            sidebar=request.session['sidebar']
        )

        if "search" in request.GET:
            search = request.GET["search"]
            search = search.strip()
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
                Q(estado__estado_name__icontains=search) |
                Q(municipio__municipio_name__icontains=search))
            muns = [em.municipio.pk for em in estados_m]
            muns_col = MunicipioColonia.objects.filter(
                Q(municipio__pk__in=muns) |
                Q(colonia__colonia_name__icontains=search))
            cols = [mc.colonia.pk for mc in muns_col]
            c_calles = ColoniaCalle.objects.filter(
                Q(colonia__pk__in=cols) |
                Q(calle__callename__icontains=search))

        else:
            c_calles = ColoniaCalle.objects.all()

        lista = []
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

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/streets_list.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def search_country(request):
    if "term" in request.GET:
        term = request.GET['term']
        countries = Pais.objects.filter(Q(pais_name__icontains=term))
        countries_arr = []
        for country in countries:
            countries_arr.append(dict(value=country.pais_name, pk=country.pk,
                                      label=country.pais_name))
        data = simplejson.dumps(countries_arr)
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404


@login_required(login_url='/')
def search_state(request):
    """get a list of states wich contains 'term' and are in a certain
    'country'"""
    if "term" in request.GET:
        term = request.GET['term']

        ctry_id = request.GET['country']
        try:
            ctry_id = int(ctry_id)
        except ValueError:
            states_arr = []
        else:
            #Se obtiene el país
            country = get_object_or_404(Pais, pk=ctry_id)

            states = PaisEstado.objects.filter(pais=country).filter(
                Q(estado__estado_name__icontains=term))
            states_arr = []
            for sts in states:
                states_arr.append(
                    dict(value=sts.estado.estado_name, pk=sts.estado.pk,
                         label=sts.estado.estado_name))
        data = simplejson.dumps(states_arr)
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404


@login_required(login_url='/')
def search_municipality(request):
    """get a list of municipalities wich contains 'term' and are in a certain
     'state'"""
    if "term" in request.GET:
        term = request.GET['term']

        state_id = request.GET['state']
        try:
            state_id = int(state_id)
        except ValueError:
            mun_arr = []
        else:
            #Se obtiene el país
            state = get_object_or_404(Estado, pk=state_id)

            municipalities = EstadoMunicipio.objects.filter(
                estado=state).filter(
                Q(municipio__municipio_name__icontains=term))
            mun_arr = []

            for mnp in municipalities:
                mun_arr.append(dict(value=mnp.municipio.municipio_name,
                                    pk=mnp.municipio.pk,
                                    label=mnp.municipio.municipio_name))

        data = simplejson.dumps(mun_arr)
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404


@login_required(login_url='/')
def search_neighboorhood(request):
    """get a list of neighboorhoods wich contains 'term' and are in a certain
     'municipality'"""
    if "term" in request.GET:
        term = request.GET['term']

        mun_id = request.GET['municipality']
        try:
            mun_id = int(mun_id)
        except ValueError:
            ngh_arr = []
        else:
            #Se obtiene el municipio
            municipality = get_object_or_404(Municipio, pk=mun_id)

            neighborhoods = MunicipioColonia.objects.filter(
                municipio=municipality).filter(
                Q(colonia__colonia_name__icontains=term))
            ngh_arr = []

            for ng in neighborhoods:
                ngh_arr.append(
                    dict(value=ng.colonia.colonia_name, pk=ng.colonia.pk,
                         label=ng.colonia.colonia_name))

        data = simplejson.dumps(ngh_arr)
        return HttpResponse(content=data, content_type="application/json")
    else:
        raise Http404


@login_required(login_url='/')
def search_street(request):
    """get a list of streets wich contains 'term' and are in a certain
    'neighboorhood'"""
    if "term" in request.GET:
        term = request.GET['term']

        neigh_id = request.GET['neighborhood']
        try:
            neigh_id = int(neigh_id)
        except ValueError:
            street_arr = []
        else:
            #Se obtiene la colonia

            neighborhood = get_object_or_404(Colonia, pk=neigh_id)
            streets = ColoniaCalle.objects.filter(colonia=neighborhood).filter(
                Q(calle__calle_name__icontains=term))

            street_arr = []

            for st in streets:
                street_arr.append(
                    dict(value=st.calle.calle_name, pk=st.calle.pk,
                         label=st.calle.calle_name))

        data = simplejson.dumps(street_arr)
        return HttpResponse(content=data, content_type="application/json")
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
            mensaje = "Ha ocurrido un error de integridad de datos, " \
                      "por favor revisa que no "\
                      "haya ningún dato asociado al estado ni a sus " \
                      "municipios, colonias o "\
                      "calles"
            type = "error"
        else:
            mensaje = "Se ha eliminado correctamente la asociación entre el " \
                      "país y el estado"
            type = "success"
        return HttpResponseRedirect("/location/ver_estados/?msj=" + mensaje +
                                    "&ntype=" + type)
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
            mensaje = "Ha ocurrido un error de integridad de datos, " \
                      "por favor revisa que no "\
                      "haya ningún dato asociado al municipio ni a sus " \
                      "colonias o calles"
            type = "error"
        else:
            mensaje = "Se ha eliminado correctamente la asociación entre el " \
                      "estado y el "\
                      "municipio"
            type = "success"
        return HttpResponseRedirect(
            "/location/ver_municipios?msj=" + mensaje + "&ntype=" + type)
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
            mensaje = "Ha ocurrido un error de integridad de datos, " \
                      "por favor revisa que no "\
                      "haya ningún dato asociado a la colonia ni a sus calles"
            type = "error"
        else:
            mensaje = "Se ha eliminado correctamente la asociación entre el " \
                      "municipio y la "\
                      "colonia"
            type = "success"
        return HttpResponseRedirect(
            "/location/ver_colonias?msj=" + mensaje + "&ntype=" + type)
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
            mensaje = "Ha ocurrido un error de integridad de datos, " \
                      "por favor revisa que no "\
                      "haya ningún dato asociado a la calle"
            type = "error"
        else:
            mensaje = "Se ha eliminado correctamente la asociación entre el " \
                      "colonia y la "\
                      "calle"
            type = "success"

        return HttpResponseRedirect(
            "/location/ver_calles?msj=" + mensaje + "&ntype=" + type)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def delete_state_country_batch(request):
    if request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^estado_\w+', key):
                    r_id = int(key.replace("estado_", ""))
                    object = get_object_or_404(PaisEstado, pk=r_id)
                    estado = object.estado
                    pais = object.pais
                    object.delete()
                    try:
                        delete_municipalities(estado)
                    except ProtectedError:
                        PaisEstado(estado=estado, pais=pais).save()
                        mensaje = "Ha ocurrido un error de integridad de " \
                                  "datos, por favor "\
                                  "revisa que no haya ningún dato asociado al" \
                                  " estado ni a "\
                                  "sus municipios, colonias o calles"
                        return HttpResponseRedirect(
                            "/location/ver_estados/?msj=" + mensaje +
                            "&ntype=error")
            mensaje = "Las relaciones País-Estado han sido eliminadas"
            return HttpResponseRedirect(
                "/location/ver_estados/?msj=" + mensaje +
                "&ntype=success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/location/ver_estados/?msj=" + mensaje +
                "&ntype=success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def delete_municipality_state_batch(request):
    if request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^municipio_\w+', key):
                    r_id = int(key.replace("municipio_", ""))
                    object = get_object_or_404(EstadoMunicipio, pk=r_id)
                    mun = object.municipio
                    est = object.estado
                    object.delete()
                    try:
                        delete_neigboorhoods(mun)
                    except ProtectedError:
                        EstadoMunicipio(estado=est, municipio=mun).save()
                        mensaje = "Ha ocurrido un error de integridad de " \
                                  "datos, por favor "\
                                  "revisa que no haya ningún dato asociado al" \
                                  " municipio, "\
                                  "colonias o calles"
                        return HttpResponseRedirect(
                            "/location/ver_municipios/?msj=" +
                            mensaje + "&ntype=error")
            mensaje = "Las relaciones Estado-Municipio han sido eliminadas"
            return HttpResponseRedirect(
                "/location/ver_municipios/?msj=" + mensaje +
                "&ntype=success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/location/ver_municipios/?msj=" + mensaje +
                "&ntype=success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def delete_neighboorhood_municipality_batch(request):
    if request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^colonia_\w+', key):
                    r_id = int(key.replace("colonia_", ""))
                    object = get_object_or_404(MunicipioColonia, pk=r_id)
                    colonia = object.colonia
                    municipio = object.municipio
                    object.delete()
                    try:
                        delete_streets(colonia)
                    except ProtectedError:
                        MunicipioColonia(municipio=municipio,
                                         colonia=colonia).save()
                        mensaje = "Ha ocurrido un error de integridad de " \
                                  "datos, por favor "\
                                  "revisa que no haya ningún dato asociado a " \
                                  "la colonia, "\
                                  "o sus calles"
                        return HttpResponseRedirect(
                            "/location/ver_colonias/?msj=" +
                            mensaje + "&ntype=error")
            mensaje = "Las relaciones Municipio-Colonia han sido eliminadas"
            return HttpResponseRedirect(
                "/location/ver_colonias/?msj=" + mensaje +
                "&ntype=success")
        else:
            mensaje = "No se ha seleccionado una acción"
            return HttpResponseRedirect(
                "/location/ver_colonias/?msj=" + mensaje +
                "&ntype=success")
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def delete_street_neighboor_batch(request):
    if request.user.is_superuser:
        if request.method == "GET":
            raise Http404
        if request.POST['actions'] == 'delete':
            for key in request.POST:
                if re.search('^calle_\w+', key):
                    r_id = int(key.replace("calle_", ""))
                    object = get_object_or_404(ColoniaCalle, pk=r_id)
                    calle = object.calle
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
        colonia = m_c.colonia
        m_c.delete()
        delete_streets(colonia)
    municipality.delete()
    return True


def delete_municipalities(state):
    """Deletes all the municipalities and neighboorhoods and streets in a
    given state, then
    deletes itself
    """
    est_muns = EstadoMunicipio.objects.filter(estado=state)
    for e_m in est_muns:
        mun = e_m.municipio
        e_m.delete()
        delete_neigboorhoods(mun)
    state.delete()
    return True

#"""
#Regiones
#"""
@login_required(login_url='/')
def add_region(request):
    if request.user.is_superuser:
        #Se obtienen los estados que ya estan completamente ocupados
        #Primero obtengo todos los e
        #estados_exc = [regiones_estados.estado_id for regiones_estados in
        # RegionEstado.objects.filter(municipio = None)]
        estados_exc = []

        #Se obtienen todos los estados de la tabla RegionEstado
        r_states = RegionEstado.objects.values('estado').annotate(
            dstates=Count('estado'))
        for rs in r_states:
            region_states = RegionEstado.objects.filter(
                estado__pk=rs['estado']).filter(municipio=None)
            #Significa que es un estado con todos sus municipios y se agrega
            # por completo a la lista de excepcion de estados
            if region_states:
                estados_exc.append(rs['estado'])
            else:
                region_states = RegionEstado.objects.filter(
                    estado__pk=rs['estado']).filter(~Q(municipio=None))
                #Se cuentan cuantos municipios ya estan registrados dentro de
                # la tabla RegionEstado
                reg_mun = len(region_states)

                #Se obtienen el numero total de municipios de un estado
                mun_estate = EstadoMunicipio.objects.filter(
                    estado__pk=rs['estado'])
                est_mun = len(mun_estate)

                #Si ambos numeros son iguales indica que ya todos los
                # municipios de ese estado estan registrado y por lo tanto no
                # debe aparecer en la lista
                if reg_mun == est_mun:
                    estados_exc.append(rs['estado'])

        estados = Estado.objects.all().exclude(pk__in=estados_exc).order_by(
            'estado_name')
        type = ''
        message = ''
        template_vars = dict(
            datacontext=get_buildings_context(request.user)[0],
            empresa=request.session['main_building'],
            company=request.session['company'],
            sidebar=request.session['sidebar'],
            operation="add",
            estados=estados,
        )

        post = {'region_id': 0}

        if request.method == "POST":
            template_vars["post"] = request.POST
            region_name = request.POST.get('region_name').strip()
            region_description = request.POST.get('region_description').strip()

            continuar = True
            if region_name == '':
                message = "El nombre de la Región no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(region_name):
                message = "El nombre de la Región contiene caracteres inválidos"
                type = "n_notif"
                region_name = ""
                continuar = False


            #Valida por si le da muchos clics al boton
            regionValidate = Region.objects.filter(region_name=region_name)
            if regionValidate:
                message = "Ya existe una Región con ese nombre"
                type = "n_notif"
                continuar = False

            post = {'region_name': region_name,
                    'region_description': region_description}
            template_vars['post'] = post

            if continuar:
                newRegion = Region(
                    region_name=region_name,
                    region_description=region_description
                )
                newRegion.save()

                for state_id in request.POST:
                    if re.search('^r_state_\w+', state_id):
                        s_id = int(state_id.replace("r_state_", ""))
                        atr_value_complete = request.POST.get(state_id)
                        atr_value_arr = atr_value_complete.split(',')

                        #Se obtiene el objeto de estado
                        state_obj = get_object_or_404(Estado, pk=s_id)

                        #Se obtienen el número de municipios que tiene el estado
                        state_mun = EstadoMunicipio.objects.filter(
                            estado__pk=s_id)

                        if len(state_mun) != len(atr_value_arr):
                            for id_mun in atr_value_arr:
                                #Se obtiene el objeto de municipio
                                mun_obj = get_object_or_404(Municipio,
                                                            pk=id_mun)

                                newRegionEstado = RegionEstado(
                                    region=newRegion,
                                    estado=state_obj,
                                    municipio=mun_obj,
                                )
                                newRegionEstado.save()
                        else:
                            newRegionEstado = RegionEstado(
                                region=newRegion,
                                estado=state_obj,
                            )
                            newRegionEstado.save()

                template_vars["message"] = "Región creada exitosamente"
                template_vars["type"] = "n_success"

                if request.user.is_superuser:
                    return HttpResponseRedirect("/location/ver_regiones?msj=" +
                                                template_vars["message"] +
                                                "&ntype=n_success")

            template_vars["message"] = message
            template_vars["type"] = type
        template_vars["post"] = post
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_region.html",
                                  template_vars_template)

    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def edit_region(request, id_region):
    if request.user.is_superuser:
        regionObj = get_object_or_404(Region, pk=id_region)

        #Se obtienen los estados que ya tienen todos sus municipios registrados
        estados_exc = [regiones_estados.estado_id for regiones_estados in
                       RegionEstado.objects.filter(municipio=None).exclude(
                           region=regionObj)]

        estados = Estado.objects.all().exclude(id__in=estados_exc).order_by(
            'estado_name')

        html_string_inputs = ''
        html_string_tags = ''
        string_municipios = ''

        r_states = RegionEstado.objects.filter(region=regionObj).values(
            'estado').annotate(dstates=Count('estado'))
        for rs in r_states:
            region_states = RegionEstado.objects.filter(
                region=regionObj).filter(estado__pk=rs['estado']).filter(
                municipio=None)
            if region_states:
                estados_municipios = EstadoMunicipio.objects.filter(
                    estado__pk=rs['estado'])
                if estados_municipios:
                    for emun in estados_municipios:
                        string_municipios += str(emun.municipio.pk) + ","

                html_string_tags += "<div class='tag'><span " \
                                    "class='delete_icon'><a href='#eliminar' " \
                                    "rel='" + str(
                    estados_municipios[
                    0].estado_id) + "' class='del del_icn' title='Eliminar " \
                                    "Estado'></a></span><span " \
                                    "class='tag_label'><a href='#' " \
                                    "id='s_tag_" + str(
                    estados_municipios[
                    0].estado_id) + "' onclick='getMun(" + str(
                    estados_municipios[
                    0].estado_id) + ");' class='state_tag'>" + \
                                    estados_municipios[
                                    0].estado.estado_name + " (" + str(
                    len(estados_municipios)) + ")" + "</a></span></div>"
                html_string_inputs += "<div><input type='hidden' " \
                                      "name='r_state_" + str(
                    estados_municipios[0].estado_id) + "' id='r_state_" + str(
                    estados_municipios[0].estado_id) + "' value='" + \
                                      string_municipios[:-1] + "'/></div>"
                string_municipios = ''
            else:
                region_states = RegionEstado.objects.filter(
                    region=regionObj).filter(estado__pk=rs['estado']).filter(
                    ~Q(municipio=None))
                for rst in region_states:
                    string_municipios += str(rst.municipio.pk) + ','

                html_string_tags += "<div class='tag'><span " \
                                    "class='delete_icon'><a href='#eliminar' " \
                                    "rel='" + str(
                    rst.estado_id) + "' class='del del_icn' title='Eliminar " \
                                     "Estado'></a></span><span " \
                                     "class='tag_label'><a href='#' " \
                                     "id='s_tag_" + str(
                    rst.estado_id) + "' onclick='getMun(" + str(
                    rst.estado_id) + ");' class='state_tag'>" + rst.estado\
                .estado_name + " (" + str(
                    len(region_states)) + ")" + "</a></span></div>"
                html_string_inputs += "<div><input type='hidden' " \
                                      "name='r_state_" + str(
                    rst.estado_id) + "' id='r_state_" + str(
                    rst.estado_id) + "' value='" + string_municipios[
                                                   :-1] + "'/></div>"
                string_municipios = ''

        post = {'region_id': regionObj.pk, 'region_name': regionObj.region_name,
                'region_description': regionObj.region_description,
                'region_tags': html_string_tags,
                'region_inputs': html_string_inputs}

        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        message = ''
        type = ''

        if request.method == "POST":
            region_name = request.POST.get('region_name').strip()
            region_description = request.POST.get('region_description').strip()

            continuar = True
            if region_name == '':
                message = "El nombre de la Región no puede quedar vacío"
                type = "n_notif"
                continuar = False
            elif not variety.validate_string(region_name):
                message = "El nombre de la Región contiene caracteres inválidos"
                type = "n_notif"
                region_name = ""
                continuar = False

            #Valida por si le da muchos clics al boton
            if regionObj.region_name != region_name:
                regionValidate = Region.objects.filter(region_name=region_name)
                if regionValidate:
                    message = "Ya existe una Región con ese nombre"
                    type = "n_notif"
                    continuar = False

            if continuar:
                regionObj.region_name = region_name
                regionObj.region_description = region_description
                regionObj.save()

                #Borrar todos los estados-municipios para esta region
                region_mun_delete = RegionEstado.objects.filter(
                    region=regionObj)
                region_mun_delete.delete()

                for state_id in request.POST:
                    if re.search('^r_state_\w+', state_id):
                        s_id = int(state_id.replace("r_state_", ""))
                        atr_value_complete = request.POST.get(state_id)
                        atr_value_arr = atr_value_complete.split(',')

                        #Se obtiene el objeto de estado
                        state_obj = get_object_or_404(Estado, pk=s_id)

                        #Se obtienen el número de municipios que tiene el estado
                        state_mun = EstadoMunicipio.objects.filter(
                            estado__pk=s_id)

                        if len(state_mun) != len(atr_value_arr):
                            for id_mun in atr_value_arr:
                                #Se obtiene el objeto de municipio
                                mun_obj = get_object_or_404(Municipio,
                                                            pk=id_mun)

                                newRegionEstado = RegionEstado(
                                    region=regionObj,
                                    estado=state_obj,
                                    municipio=mun_obj,
                                )
                                newRegionEstado.save()
                        else:
                            newRegionEstado = RegionEstado(
                                region=regionObj,
                                estado=state_obj,
                            )
                            newRegionEstado.save()

                message = "Región editada exitosamente"
                type = "n_success"

                if request.user.is_superuser:
                    return HttpResponseRedirect("/location/ver_regiones?msj=" +
                                                message +
                                                "&ntype=n_success")

        template_vars = dict(datacontext=datacontext,
                             empresa=empresa,
                             estados=estados,
                             post=post,
                             sidebar=request.session['sidebar'],
                             operation="edit",
                             message=message,
                             type=type,
                             company=request.session['company']
        )
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/add_region.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def view_regions(request):
    if request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']
        company = request.session['company']
        if "search" in request.GET:
            search = request.GET["search"]
        else:
            search = ''

        order_name = 'asc'
        order_description = 'asc'
        order = "region_name" #default order
        if "order_name" in request.GET:
            if request.GET["order_name"] == "desc":
                order = "-region_name"
                order_name = "asc"
            else:
                order_name = "desc"
        else:
            if "order_description" in request.GET:
                if request.GET["order_description"] == "asc":
                    order = "region_description"
                    order_description = "desc"
                else:
                    order = "-region_description"
                    order_description = "asc"
        if search:
            lista = Region.objects.filter(
                Q(region_name__icontains=request.GET['search']) | Q(
                    region_description__icontains=request.GET[
                                                  'search'])).order_by(order)

        else:
            lista = Region.objects.all().order_by(order)
        paginator = Paginator(lista, 6) # muestra 10 resultados por pagina
        template_vars = dict(order_name=order_name,
                             order_description=order_description,
                             datacontext=datacontext, empresa=empresa,
                             company=company,
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

        template_vars['paginacion'] = pag_user

        if 'msj' in request.GET:
            template_vars['message'] = request.GET['msj']
            template_vars['msg_type'] = request.GET['ntype']

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/regions.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


@login_required(login_url='/')
def see_region(request, id_region):
    if request.user.is_superuser:
        datacontext = get_buildings_context(request.user)[0]
        empresa = request.session['main_building']

        region = get_object_or_404(Region, pk=id_region)

        lista_estados = []

        r_states = RegionEstado.objects.filter(region=region).values(
            'estado').annotate(dstates=Count('estado'))
        for rs in r_states:
            region_states = RegionEstado.objects.filter(region=region).filter(
                estado__pk=rs['estado']).filter(municipio=None)
            estados_municipios = EstadoMunicipio.objects.filter(
                estado__pk=rs['estado'])
            if region_states:
                if estados_municipios:
                    lista_estados.append(
                        "<a class='fbox' data-fancybox-type='iframe'  href='/location/municipios_estado/" + str(
                            region_states[0].region_id) + "/" + str(
                            rs['estado']) + "/'>" + estados_municipios[
                                                    0].estado.estado_name + ' (' + str(
                            len(estados_municipios)) + ')' + "</a>")
            else:
                region_states = RegionEstado.objects.filter(
                    region=region).filter(estado__pk=rs['estado']).filter(
                    ~Q(municipio=None))
                if region_states:
                    lista_estados.append(
                        "<a class='fbox' data-fancybox-type='iframe'  href='/location/municipios_estado/" + str(
                            region_states[0].region_id) + "/" + str(
                            rs['estado']) + "/'>" + region_states[
                                                    0].estado.estado_name + ' (' + str(
                            len(estados_municipios)) + ')' + "</a>")

        template_vars = dict(
            datacontext=datacontext,
            region=region,
            region_estados=lista_estados,
            empresa=empresa,
            sidebar=request.session['sidebar'],
            company=request.session['company']
        )

        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("location/see_region.html",
                                  template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))


def region_municipalities(request, id_region, id_state):
    municipios = []
    r_states = RegionEstado.objects.filter(region__pk=id_region).filter(
        estado__pk=id_state)

    region_name = r_states[0].region.region_name
    estado_name = r_states[0].estado.estado_name

    for rs in r_states:
        if not rs.municipio:
            estados_municipios = EstadoMunicipio.objects.filter(
                estado__pk=id_state)
            for mn in estados_municipios:
                municipios.append(mn.municipio.municipio_name)
        else:
            municipios.append(rs.municipio.municipio_name)

    template_vars = dict(
        region_name=region_name,
        estado_name=estado_name,
        municipios=municipios,
    )

    template_vars_template = RequestContext(request, template_vars)
    return render_to_response("location/region_municipalities.html",
                              template_vars_template)

def regions_list(request):
    return render_to_response("location/regions_list.html")


@login_required(login_url='/')
def get_select_municipalities(request, id_state, id_region):
    """Obtiene los municipios de ese estado que ya estan asignados a una region
    """
    reg_est_exc = RegionEstado.objects.filter(estado__pk=id_state).exclude(
        region__pk=id_region)
    list_exception = []
    if reg_est_exc:
        for rg_ex in reg_est_exc:
            list_exception.append(rg_ex.municipio.pk)

    municipalities = EstadoMunicipio.objects.filter(
        estado__pk=id_state).exclude(municipio__pk__in=list_exception).order_by(
        'municipio__municipio_name')

    string_to_return = ''
    if municipalities:
        for mun in municipalities:
            string_to_return += """<option value="%s">
                                    %s
                                    </option>""" % (
            mun.municipio.pk, mun.municipio.municipio_name)

    return HttpResponse(content=string_to_return, content_type="text/html")


def get_datetime_type(request, date_capture, c_unit):
    """Regresa un offset y  un datetime con el ajuste de hora realizado
    dependiendo la fecha

    :param request:
    :param date_capture: naive datetime
    :param c_unit: ConsumerUnit object
    :return:
    """
    isborder= c_unit.building.municipio.border

    if isborder:
        periodos = DateSavingTimes.objects.filter(
            date_start__gte= date_capture,
            date_end__lte=date_capture,
            identifier__contains='frontera')
    else:
        periodos = DateSavingTimes.objects.filter(
            date_start__gte= date_capture,
            date_end__lte=date_capture).exclude(
            identifier__contains='frontera')

    if periodos:
        periodos = periodos[0]
        if periodos.period == 'Verano':
            offset = c_unit.building.municipio.dst_offset
        else:
            offset = c_unit.building.municipio.raw_offset

        date_capture = date_capture +  datetime.timedelta(hours=offset)

        return offset, date_capture




