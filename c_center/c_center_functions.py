# -*- coding: utf-8 -*-
__author__ = 'wime'
#standard library imports
import datetime
from dateutil.relativedelta import relativedelta
import time
import os
import cStringIO
import Image
import hashlib
import pytz
import threading
from math import ceil
import urllib2
import csv

#local application/library specific imports
from django.shortcuts import HttpResponse, get_object_or_404
from django.http import Http404
from django.utils import simplejson, timezone
from django.db.models import Q
from django.db.models.aggregates import *
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.views.decorators.csrf import csrf_exempt

from calendar import monthrange

from cidec_sw import settings
from c_center.calculations import *
from c_center.models import Cluster, ClusterCompany, Company, CompanyBuilding, \
    Building, PartOfBuilding, HierarchyOfPart, ConsumerUnit, \
    ProfilePowermeter, ElectricDataTemp, DailyData, DacHistoricData, \
    HMHistoricData, T3HistoricData, ElectricRateForElectricData
from rbac.models import PermissionAsigment, DataContextPermission, Role,\
    UserRole, Object, Operation
from location.models import *
from electric_rates.models import ElectricRatesDetail
from data_warehouse_extended.views import get_electrical_parameter, \
    get_instant_delta, get_instants_list, get_consumer_unit_profile, \
    get_consumer_unit_electrical_parameter_data_list
from data_warehouse_extended.models import ConsumerUnitInstantElectricalData,\
    data_warehouse_extended

from rbac.rbac_functions import is_allowed_operation_for_object,\
    default_consumerUnit

from bs4 import BeautifulSoup

import variety

import pdb

VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")

def get_clusters_for_operation(permission, operation, user):
    """Obtains a queryset for all the clusters that exists in a datacontext
    for a user,
     if the user is super_user returns all active clusters
     returns a the queryset

     permission.- string, the name of the permission object
     operation.- operation object, (VIEW, CREATE, etc)
     user.- django.contrib.auth.models.User instance
    """
    if user.is_superuser:
        return Cluster.objects.filter(cluster_status=1)
    else:
        permission = Object.objects.get(object_name=permission)
        #lista de roles que tienen permiso de "operation" "permission"
        roles_pks = [pa.role.pk for pa in
                     PermissionAsigment.objects.filter(object=permission,
                                                       operation=operation)]
        #lista de data_context's del usuario donde tiene permiso de crear
        # asignaciones de roles
        data_context = DataContextPermission.objects.filter(
            user_role__role__pk__in=roles_pks, user_role__user=user)
        clusters_pks = []
        for dc in data_context:
            clusters_pks.append(dc.cluster.pk)

        return Cluster.objects.filter(pk__in=clusters_pks, cluster_status=1)


def get_all_active_companies_for_cluster(cluster):
    c_comp = ClusterCompany.objects.filter(
        cluster=cluster).values_list("company__pk", flat=True)
    return Company.objects.filter(pk__in=c_comp, company_status=1)


def get_companies_for_operation(permission, operation, user, cluster):
    """Obtains a queryset for all the companies that exists in a datacontext
    for a user for a
    given cluster, if the user is super_user returns all active companies for
     the cluster,
    if the user has permission over the entire cluster,
    returns all active companies for the cluster
    returns a tuple containing the queryset, and a boolean,
    indicating if returns all the objects

    :param permission:string, the name of the permission object
    :param operation:operation object, (VIEW, CREATE, etc)
    :param user:django.contrib.auth.models.User instance
    :param cluster: Cluster instance
    """
    if user.is_superuser:
        return get_all_active_companies_for_cluster(cluster), True
    else:
        permission = Object.objects.get(object_name=permission)
        if is_allowed_operation_for_object(operation, permission, user, cluster,
                                           "cluster"):
            return get_all_active_companies_for_cluster(cluster), True
        else:
            #lista de roles que tienen permiso de "operation" "permission"
            roles_pks = [pa.role.pk for pa in
                         PermissionAsigment.objects.filter(object=permission,
                                                           operation=operation)]
            #lista de data_context's del usuario donde tiene permiso de crear
            # asignaciones de roles
            data_context = DataContextPermission.objects.filter(
                user_role__role__pk__in=roles_pks, user_role__user=user,
                cluster=cluster)
            compnies_pks = []
            for data_c in data_context:
                #reviso si tengo un datacontext para el cluster completo
                if not data_c.company:
                    return get_all_active_companies_for_cluster(cluster), True
                else:
                    compnies_pks.append(data_c.company.pk)
            return Company.objects.filter(pk__in=compnies_pks,
                                          company_status=1), False


def get_all_companies_for_operation(permission, operation, user):
    clusters = get_clusters_for_operation(permission, operation, user)
    companies_array = []
    for cluster in clusters:
        companies, all_companies = get_companies_for_operation(permission,
                                                               operation,
                                                               user, cluster)
        companies_array.extend(companies)
    return companies_array


def get_all_active_buildings_for_company(company):
    c_buildings = CompanyBuilding.objects.filter(
        company=company).values_list("building__pk", flat=True)
    return Building.objects.filter(pk__in=c_buildings, building_status=1)


def get_buildings_for_operation(permission, operation, user, company):
    """Obtains a queryset for all the buildings that exists in a datacontext
    for a user for a
    given company, if the user is super_user returns all active building for
    the company,
    if the user has permission over the entire company,
    returns all active buildings for the company
    returns a tuple containing the queryset, and a boolean,
    indicating if returns all the objects

    permission.- string, the name of the permission object
    operation.- operation object, (VIEW, CREATE, etc)
    user.- django.contrib.auth.models.User instance
    company.- Company instance
    """
    if user.is_superuser:
        return get_all_active_buildings_for_company(company), True
    else:
        permission = Object.objects.get(object_name=permission)
        cluster = ClusterCompany.objects.get(company=company).cluster
        if is_allowed_operation_for_object(operation, permission, user, company,
                                           "company") or\
           is_allowed_operation_for_object(operation, permission, user, cluster,
                                           "cluster"):
            return get_all_active_buildings_for_company(company), True
        else:
            #lista de roles que tienen permiso de "operation" "permission"
            roles_pks = [pa.role.pk for pa in
                         PermissionAsigment.objects.filter(object=permission,
                                                           operation=operation)]
            #lista de data_context's del usuario donde tiene permiso de crear
            # asignaciones de roles
            data_context = DataContextPermission.objects.filter(
                user_role__role__pk__in=roles_pks, user_role__user=user,
                company=company)
            buildings_pks = []
            for data_c in data_context:
                #reviso si tengo un datacontext para el cluster completo
                if not data_c.building:
                    return get_all_active_buildings_for_company(company), True
                else:
                    buildings_pks.append(data_c.building.pk)
            return Building.objects.filter(pk__in=buildings_pks,
                                           building_status=1), False


def get_all_buildings_for_operation(permission, operation, user):
    """ Gets an array of all the buildings in wich a user can do 'x' operation
    :param permission: String, the name of the object
    :param operation: Object, VIEW, CREATE, or UPDATE object
    :param user: User object
    """
    companies = get_all_companies_for_operation(permission, operation, user)
    buildings_arr = []
    for company in companies:
        building, all_buildings = get_buildings_for_operation(permission,
                                                              operation,
                                                              user,
                                                              company)

        buildings_arr.extend(building)
    return buildings_arr


def get_all_active_parts_for_building(building):
    return PartOfBuilding.objects.filter(building=building,
                                         part_of_building_status=True)


def get_partsofbuilding_for_operation(permission, operation, user, building):
    """Obtains a queryset for all the partsofbuilding that exists in a
    datacontext for a user for a given building, if the user is super_user
    returns all active partsofbuilding for the building,
    if the user has permission over the entire building,
    returns all active partsofbuilding for the building
    returns a tuple containing the queryset, and a boolean,
    indicating if returns all the objects

    permission.- string, the name of the permission object
    operation.- operation object, (VIEW, CREATE, etc)
    user.- django.contrib.auth.models.User instance
    building.- Building instance
    """
    if user.is_superuser:
        return get_all_active_parts_for_building(building), True
    else:
        permission = Object.objects.get(object_name=permission)

        company = CompanyBuilding.objects.get(building=building).company
        cluster = ClusterCompany.objects.get(company=company).cluster

        if is_allowed_operation_for_object(operation, permission, user,
                                           building, "building") or\
           is_allowed_operation_for_object(operation, permission, user, company,
                                           "company") or\
           is_allowed_operation_for_object(operation, permission, user, cluster,
                                           "cluster"):
            return get_all_active_parts_for_building(building), True
        else:
            #lista de roles que tienen permiso de "operation" "permission"
            roles_pks = [pa.role.pk for pa in
                         PermissionAsigment.objects.filter(object=permission,
                                                           operation=operation)]
            #lista de data_context's del usuario donde tiene permiso de crear
            # asignaciones de roles
            data_context = DataContextPermission.objects.filter(
                user_role__role__pk__in=roles_pks, user_role__user=user,
                building=building)
            parts_pks = []
            for data_c in data_context:
                #reviso si tengo un datacontext para el cluster completo
                if not data_c.part_of_building:
                    return get_all_active_parts_for_building(building), True
                else:
                    parts_pks.append(data_c.part_of_building.pk)
            return PartOfBuilding.objects.filter(
                pk__in=parts_pks, part_of_building_status=True), False


def get_all_consumer_units_for_building(building):
    """ Returns all the non virtual consumer units
     :param building: Object Building instance
    """
    return ConsumerUnit.objects.filter(building=building).exclude(
        profile_powermeter__powermeter__powermeter_anotation="Medidor Virtual"
    ).exclude(profile_powermeter__powermeter__status=0)


def get_c_unitsforbuilding_for_operation(permission, operation, user, building):
    """Obtains a queryset for all the physical ConsumerUnits that exists in a
    datacontext for a user for a given building, if the user is super_user
    returns all active ConsumerUnits for the building,
    if the user has permission over the entire building,
    returns all active ConsumerUnits for the building
    returns a tuple containing the queryset, and a boolean,
    indicating if returns all the objects

    :param permission: string, the name of the permission object
    :param operation: operation object, (VIEW, CREATE, etc)
    :param user: django.contrib.auth.models.User instance
    :param building: Building instance
    """
    if user.is_superuser:
        return get_all_consumer_units_for_building(building), True
    else:
        permission = Object.objects.get(object_name=permission)

        company = CompanyBuilding.objects.get(building=building).company
        cluster = ClusterCompany.objects.get(company=company).cluster

        if is_allowed_operation_for_object(operation, permission, user,
                                           building, "building") or \
                is_allowed_operation_for_object(operation, permission, user, company,
                                                "company") or \
                is_allowed_operation_for_object(operation, permission, user, cluster,
                                                "cluster"):
            return get_all_consumer_units_for_building(building), True
        else:
            #lista de roles que tienen permiso de "operation" "permission"
            roles_pks = PermissionAsigment.objects.filter(
                object=permission,
                operation=operation).values_list("role__pk", flat=True)
            #lista de data_context's del usuario donde tiene permiso de crear
            # asignaciones de roles
            data_context = DataContextPermission.objects.filter(
                user_role__role__pk__in=roles_pks, user_role__user=user,
                building=building)
            parts_pks = []
            for data_c in data_context:
                #reviso si tengo un datacontext para el cluster completo
                if not data_c.part_of_building:
                    return get_all_consumer_units_for_building(building), True
                else:
                    parts_pks.append(data_c.part_of_building.pk)
            return ConsumerUnit.objects.filter(
                part_of_building__pk__in=parts_pks,
                part_of_building__part_of_building_status=True
            ).exclude(
                profile_powermeter__powermeter__powermeter_anotation="Medidor Virtual"
            ).exclude(profile_powermeter__powermeter__status=0), False

def get_cluster_companies(request, id_cluster):
    """
    returns a json with all the comanies in the cluster with id = id_cluster,

    """
    if "op" in request.GET:
        operation = Object.objects.get(id=request.GET['op'])
        operation = operation.object_name
    else:
        operation="Asignar roles a usuarios"
    cluster = get_object_or_404(Cluster, pk=id_cluster)
    companies_for_user, all_cluster = get_companies_for_operation(
        operation, CREATE, request.user, cluster)
    companies = []
    if companies_for_user:
        for company in companies_for_user:
            companies.append(dict(pk=company.pk, company=company.company_name,
                                  all=all_cluster))
        data = simplejson.dumps(companies)
    elif all_cluster:
        #has permission, but the custer has no companies
        data = simplejson.dumps([dict(all="all")])
    else:
        #user don't have permission
        data = simplejson.dumps([dict(all="none")])
    return HttpResponse(content=data, content_type="application/json")


def get_company_buildings(request, id_company):
    company = get_object_or_404(Company, pk=id_company)
    if "op" in request.GET:
        operation = Object.objects.get(id=request.GET['op'])
        operation = operation.object_name
    else:
        operation="Asignar roles a usuarios"
    buildings_for_user, all_company = get_buildings_for_operation(
        operation, CREATE, request.user, company)
    buildings = []
    if buildings_for_user:
        for building in buildings_for_user:
            buildings.append(
                dict(pk=building.pk, building=building.building_name,
                     all=all_company))
        data = simplejson.dumps(buildings)
    elif all_company:
        data = simplejson.dumps([dict(all="all")])
    else:
        data = simplejson.dumps([dict(all="none")])
    return HttpResponse(content=data, content_type="application/json")


def get_parts_of_building(request, id_building):
    """ Get all the parts of a building in wich the user has permission to do
    something

    """
    building = get_object_or_404(Building, pk=id_building)
    if "op" in request.GET:
        operation = Object.objects.get(id=request.GET['op'])
        operation = operation.object_name
    else:
        operation="Asignar roles a usuarios"
    parts_for_user, all_building = get_partsofbuilding_for_operation(
        operation, CREATE, request.user, building)
    #p_buildings= PartOfBuilding.objects.filter(building=building)
    parts = []
    if parts_for_user:
        for part in parts_for_user:
            parts.append(dict(pk=part.pk, part=part.part_of_building_name,
                              all=all_building))
        data = simplejson.dumps(parts)
    elif all_building:
        data = simplejson.dumps([dict(all="all")])
    else:
        data = simplejson.dumps([dict(all="none")])
    return HttpResponse(content=data, content_type="application/json")


def get_cus_of_building(request, id_building):
    """ Get all the consumer units of a building in wich the user has
    permission to do something

    """
    building = get_object_or_404(Building, pk=id_building)
    if "op" in request.GET:
        operation = Object.objects.get(id=request.GET['op'])
        operation = operation.object_name
    else:
        operation="Asignar roles a usuarios"
    cus_for_user, all_building = get_c_unitsforbuilding_for_operation(
        operation, CREATE, request.user, building)
    #p_buildings= PartOfBuilding.objects.filter(building=building)
    consumer_units = []
    if cus_for_user:
        for cu in cus_for_user:
            consumer_units.append(
                dict(
                    pk=cu.pk,
                    annotation=cu.profile_powermeter.powermeter.powermeter_anotation,
                    all=all_building))
        data = simplejson.dumps(consumer_units)
    elif all_building:
        data = simplejson.dumps([dict(all="all")])
    else:
        data = simplejson.dumps([dict(all="none")])
    return HttpResponse(content=data, content_type="application/json")


def get_cu_siblings(consumerUnit):
    """ Returns a queryset of all the active physical consumer units in a
     consumerUnit building

    :param consumerUnit: Object - ConsumerUnit instance.
    """
    return ConsumerUnit.objects.filter(
        building=consumerUnit.building,
        profile_powermeter__profile_powermeter_status=1).exclude(
        profile_powermeter__powermeter__powermeter_anotation="Medidor Virtual")


def get_building_siblings(building):
    """ Returns a queryset of the CompanyBuildings in wich the building is part

    :param building: Object - Building instance.
    """
    company = CompanyBuilding.objects.get(building=building)

    return CompanyBuilding.objects.filter(
        company=company.company,
        building__building_status=1)

def get_company_siblings(company):
    """ Returns a queryset of the ClusterCompany in wich the company is part

    :param company: Object - Company instance.
    """
    cluster = ClusterCompany.objects.get(company=company)

    return ClusterCompany.objects.filter(
        cluster=cluster.cluster,
        company__company_status=1)

def get_pw_profiles(request):
    """ Get all the ProfilePowermeters that are available for use in a
    consumer unit, except for not registered and virtual profile
    """
    used_profiles = ConsumerUnit.objects.all().values_list(
        "profile_powermeter__powermeter__pk", flat=True)
    profiles = ProfilePowermeter.objects.all().exclude(
        powermeter__powermeter_anotation="Medidor Virtual").exclude(
        powermeter__powermeter_anotation="No Registrado").exclude(
        powermeter__id__in=used_profiles).values("pk",
                                            "powermeter__powermeter_anotation")
    data = []
    for profile in profiles:
        data.append(dict(pk=profile['pk'],
                    powermeter=profile['powermeter__powermeter_anotation']))
    data = simplejson.dumps(data)
    return HttpResponse(content=data, content_type="application/json")


def get_all_profiles_for_user(user, permission, operation):
    """ returns an array of consumer_units in wich the user has access
    :param user: user object instance
    :param permission: String the name of the object
    :param operation: object operation instance (VIEW, CREATE, etc)
    :rtype : bytearray
    """
    contexts = DataContextPermission.objects.filter(user_role__user=user)
    c_us = []
    for context in contexts:
        consumer_units = ConsumerUnit.objects.filter(building=context.building)
        #cu, user, building
        for consumerUnit in consumer_units:
            if consumerUnit.profile_powermeter\
                .powermeter.powermeter_anotation != "Medidor Virtual" and \
                            consumerUnit.profile_powermeter\
                                .powermeter\
                                .powermeter_anotation != "No Registrado":
                if context.part_of_building:
                    #if the user has permission over a part of building,
                    # and the consumer unit is
                    #the cu for the part of building
                    if consumerUnit.part_of_building == context.part_of_building:
                        c_us.append(consumerUnit)
                    elif is_in_part_of_building(consumerUnit,
                                                context.part_of_building):
                        c_us.append(consumerUnit)
                elif context.building == consumerUnit.building:
                    c_us.append(consumerUnit)
    c_us = variety.unique_from_array(c_us)
    return c_us


def get_intervals_1(get):
    """get the interval for the graphs
    by default we get the data from the last month
    returns f1_init, f1_end as datetime objects
    """
    f1_init = datetime.datetime.today() - relativedelta(months=1)
    f1_end = datetime.datetime.today()

    if "f1_init" in get:
        if get["f1_init"] != '':
            f1_init = time.strptime(get['f1_init'], "%d/%m/%Y")
            f1_init = datetime.datetime(f1_init.tm_year, f1_init.tm_mon,
                                        f1_init.tm_mday)
        if get["f1_end"] != '':
            f1_end = time.strptime(get['f1_end'], "%d/%m/%Y")
            f1_end = datetime.datetime(f1_end.tm_year, f1_end.tm_mon,
                                       f1_end.tm_mday)

    return f1_init, f1_end


def get_intervals_fecha(get):
    """get the interval for the graphs
    by default we get the data from the last month
    returns f1_init, f1_end as formated strings
    """
    f1_init = datetime.datetime.today() - relativedelta(months=1)
    f1_init = str(f1_init.year) + "-" + str(f1_init.month) + "-" + str(
        f1_init.day) + " 00:00:00"
    f1_end = datetime.datetime.today()
    f1_end = str(f1_end.year) + "-" + str(f1_end.month) + "-" + str(
        f1_end.day) + " 23:59:59"

    if "f1_init" in get:
        f1_init = get['f1_init']
        f1_init = str.split(str(f1_init), "/")
        f1_init = str(f1_init[2]) + "-" + str(f1_init[1]) + "-" + str(
            f1_init[0]) + " 00:00:00"
        f1_end = get['f1_end']
        f1_end = str.split(str(f1_end), "/")
        f1_end = str(f1_end[2]) + "-" + str(f1_end[1]) + "-" + str(
            f1_end[0]) + " 23:59:59"
    return f1_init, f1_end


def get_intervals_2(get):
    """gets the second date interval """
    get2 = dict(f1_init=get['f2_init'], f1_end=get['f2_end'])
    return get_intervals_1(get2)


def set_default_session_vars(request, datacontext):
    """Sets the default building and consumer unit """
    #todo: revisar bien estos callbacks, seguramente cambiaran cuando haya un landing page
    if not datacontext:
        request.session['main_building'] = None
        request.session['company'] = None
        request.session['consumer_unit'] = None

    if 'main_building' not in request.session:
        #print "144"
        #sets the default building (the first in DataContextPermission)
        try:
            building = Building.objects.get(pk=datacontext[0]['building_pk'])
            request.session['main_building'] = building
        except ObjectDoesNotExist:
            request.session['main_building'] = None
        except IndexError:
            request.session['main_building'] = None
    if "company" not in request.session and request.session['main_building']:
        c_b = CompanyBuilding.objects.get(
            building=request.session['main_building'])
        request.session['company'] = c_b.company
    elif request.session['company'] and request.session['main_building']:
        c_b = CompanyBuilding.objects.get(
            building=request.session['main_building'])
        request.session['company'] = c_b.company
    else:
        #print "177"
        request.session['company'] = None
    if ('consumer_unit' not in request.session and request.session[
                                                   'main_building']) or\
       (not request.session['consumer_unit'] and request.session[
                                                 'main_building']):
        #print "181"
        #sets the default ConsumerUnit
        # (the first in ConsumerUnit for the main building)
        request.session['consumer_unit'] = default_consumerUnit(
            request.session['main_building'])
    else:
        if not request.session[
               'consumer_unit'] or 'consumer_unit' not in request.session:
            #print "186"
            request.session['consumer_unit'] = None

    request.session['timezone']= get_google_timezone(
        request.session['main_building'])[0]
    tz = pytz.timezone(request.session.get('timezone'))
    if tz:
        timezone.activate(tz)
    return True

def get_hierarchy_list(building, user):
    """ Obtains an unordered-nested list representing the building hierarchy

    """
    hierarchy = HierarchyOfPart.objects.filter(
        part_of_building_composite__building=building).exclude(
        part_of_building_composite__part_of_building_status=False,
        part_of_building_leaf__part_of_building_status=False,
        consumer_unit_composite__profile_powermeter__powermeter__status=False,
        consumer_unit_leaf__profile_powermeter__powermeter__status=False)
    ids_hierarchy = []
    for hy in hierarchy:
        if hy.part_of_building_leaf:
            ids_hierarchy.append(hy.part_of_building_leaf.pk)

    #sacar el padre(partes de edificios que no son hijos de nadie)
    parents = PartOfBuilding.objects.filter(building=building).exclude(
        pk__in=ids_hierarchy, part_of_building_status=False)
    main_cu = ConsumerUnit.objects.get(
        building=building,
        electric_device_type__electric_device_type_name="Total Edificio")
    clase_parent = "class='raiz"
    if main_cu.profile_powermeter.powermeter.powermeter_anotation == "Medidor Virtual":
        clase_parent += " virtual"
    clase_parent += "'"
    hierarchy_list = "<ul id='org'>"\
                     "<li " + clase_parent + ">"
    if allowed_cu(main_cu, user, building):
        hierarchy_list += "<a href='#' rel='" + str(main_cu.pk) + "'>" +\
                          building.building_name +\
                          "<br/>(Total)</a>"
    else:
        hierarchy_list += building.building_name + "<br/>(Total)"
    node_cont = 1
    hierarchy_list += "<ul>"
    try:
        parents[0]
    except IndexError:
        #No tiene partes, paso para revisar sus sistemas y dispositiovos
        pass
    else:
        for parent in parents:
            c_unit_parent = ConsumerUnit.objects.filter(
                building=building, part_of_building=parent).exclude(
                electric_device_type__electric_device_type_name="Total Edificio",
                profile_powermeter__powermeter__status=False)
            clase = "class='part_of_building "
            clase += "disabled" if not parent.part_of_building_status else ""
            cu_part = ConsumerUnit.objects.get(part_of_building=parent)
            if cu_part.profile_powermeter.powermeter.powermeter_anotation == "Medidor Virtual":
                clase += " " + str(node_cont) + " virtual'"
            else:
                clase += " " + str(node_cont) + "'"
            if allowed_cu(c_unit_parent[0], user, building):
                hierarchy_list += "<li " + clase + "> <a href='#' rel='" +\
                                  str(c_unit_parent[0].pk) + "'>" +\
                                  parent.part_of_building_name + "</a>"
            else:
                hierarchy_list += "<li " + clase + ">" +\
                                  parent.part_of_building_name
                #obtengo la jerarquia de cada rama del arbol
            hierarchy_list += get_sons(parent,
                                       "part",
                                       user,
                                       building,
                                       node_cont)
            hierarchy_list += "</li>"
            node_cont += 1


    #revisa por dispositivos en el primer nivel
    #(dispositivos que no estén como hojas en el arbol de jerarquía)
    hierarchy = HierarchyOfPart.objects.filter(
        consumer_unit_leaf__building=building
    ).exclude(
        consumer_unit_leaf__profile_powermeter__powermeter__status=False
    )
    ids_hierarchy = []
    for hy in hierarchy:
        if hy.consumer_unit_leaf:
            ids_hierarchy.append(hy.consumer_unit_leaf.pk)
    #sacar el padre(ConsumerUnits que no son hijos de nadie)
    parents = ConsumerUnit.objects.filter(
        building=building, part_of_building=None).exclude(
        Q(pk__in=ids_hierarchy) |
        Q(electric_device_type__electric_device_type_name="Total Edificio")
        ).exclude(
        profile_powermeter__profile_powermeter_status=False
    )
    try:
        parents[0]
    except IndexError:
        #si no hay ninguno, es un edificio sin partes, o sin partes anidadas
        pass
    else:

        for parent in parents:
            clase = "class='consumer_unit "
            if not parent.profile_powermeter.profile_powermeter_status:
                clase += 'disabled'
            else:
                clase += ""
            if parent.profile_powermeter.powermeter.powermeter_anotation == "Medidor Virtual":
                clase += " " + str(node_cont) + " virtual'"
            else:
                clase += " " + str(node_cont) + "'"
            if allowed_cu(parent, user, building):
                hierarchy_list += "<li " + clase + "> <a href='#' rel='" +\
                                  str(parent.pk) + "'>" +\
                                  parent.electric_device_type\
                                  .electric_device_type_name +\
                                  "</a>"
            else:
                hierarchy_list += "<li " + clase + ">" +\
                                  parent.electric_device_type.\
                                  electric_device_type_name
                #obtengo la jerarquia de cada rama del arbol
            hierarchy_list += get_sons(parent, "consumer", user,
                                       building, node_cont)
            hierarchy_list += "</li>"
            node_cont += 1

    hierarchy_list += "</ul>"


    hierarchy_list += "</li></ul>"
    return hierarchy_list

def get_sons(parent, part, user, building, node_index):
    """ Gets a list of the direct sons of a given part, or consumer unit
    parent = instance of PartOfBuilding, or ConsumerUnit
    part = string, is the type of the parent
    """
    node_index = str(node_index)
    node_number = 1
    if part == "part":
        sons_of_parent = HierarchyOfPart.objects.filter(
            part_of_building_composite=parent)
    else:
        sons_of_parent = HierarchyOfPart.objects.filter(
            consumer_unit_composite=parent)

    if sons_of_parent:
        _list = '<ul>'
        for son in sons_of_parent:
            if son.part_of_building_leaf:
                tag = son.part_of_building_leaf.part_of_building_name
                sons = get_sons(son.part_of_building_leaf, "part", user,
                                building, node_number)
                cu = ConsumerUnit.objects.get(
                    part_of_building=son.part_of_building_leaf)
                _class = "part_of_building"
                if cu.profile_powermeter.powermeter.powermeter_anotation == "Medidor Virtual":
                    _class += " virtual"

            else:
                tag = son.consumer_unit_leaf.electric_device_type.electric_device_type_name
                sons = get_sons(son.consumer_unit_leaf, "consumer", user,
                                building, node_number)
                cu = son.consumer_unit_leaf
                _class = "consumer_unit"
                if cu.profile_powermeter.powermeter.powermeter_anotation == "Medidor Virtual":
                    _class += " virtual"
            if allowed_cu(cu, user, building):
                _list += '<li class="' + _class + ' ' + node_index + "_" + \
                        str(node_number) + '"><a href="#" rel="' + str(
                    cu.pk) + '">'
                _list += tag + '</a>' + sons
            else:
                _list += '<li>'
                _list += tag + sons
            _list += '</li>'
            node_number += 1
        _list += '</ul>'
        return _list
    else:
        return ""


def get_total_consumer_unit(consumerUnit, total):
    """gets the (physical)sons of a cu"""
    c_units = []
    if not total:
        if consumerUnit.part_of_building:
            #es el consumer_unit de una parte de un edificio, saco sus hijos
            leafs = HierarchyOfPart.objects.filter(part_of_building_composite=
            consumerUnit.part_of_building)

        else:
            #es un consumer unit de algún electric device, saco sus hijos
            leafs = HierarchyOfPart.objects.filter(
                consumer_unit_composite=consumerUnit)

        for leaf in leafs:
            if leaf.part_of_building_leaf:
                leaf_cu = ConsumerUnit.objects.get(
                    part_of_building=leaf.part_of_building_leaf)
            else:
                leaf_cu = leaf.consumer_unit_leaf
            if leaf.ExistsPowermeter:
                c_units.append(leaf_cu)
            else:
                c_units_leaf = get_total_consumer_unit(leaf_cu, False)
                c_units.extend(c_units_leaf)
        return c_units
    else:
        hierarchy = HierarchyOfPart.objects.filter(
            Q(part_of_building_composite__building=
            consumerUnit.building)
            | Q(consumer_unit_composite__building=
            consumerUnit.building))
        ids_hierarchy = [] #arreglo donde guardo los hijos
        ids_hierarchy_cu = [] #arreglo donde guardo los hijos (consumerunits)
        if not hierarchy:
            cus = ConsumerUnit.objects.filter(
                building=consumerUnit.building).exclude(
                electric_device_type__electric_device_type_name="Total Edificio"
            )
            c_units = [cu for cu in cus]
        else:
            for hy in hierarchy:
                if hy.part_of_building_leaf:
                    ids_hierarchy.append(hy.part_of_building_leaf.pk)
                if hy.consumer_unit_leaf:
                    ids_hierarchy_cu.append(hy.consumer_unit_leaf.pk)

            #sacar los padres(partes de edificios y consumerUnits que no son
            # hijos de nadie)
            parents = PartOfBuilding.objects.filter(
                building=consumerUnit.building).exclude(
                pk__in=ids_hierarchy)

            for parent in parents:
                par_cu = ConsumerUnit.objects.get(part_of_building=parent)
                if par_cu.profile_powermeter.powermeter.powermeter_anotation == "Medidor Virtual":
                    c_units_leaf = get_total_consumer_unit(par_cu, False)
                    c_units.extend(c_units_leaf)
                else:
                    c_units.append(par_cu)
    return c_units


def get_consumer_units(consumerUnit):
    """ Gets an array of consumer units which sum equals the given
    consumerUnit
    :param consumerUnit: ConsumerUnit object
    """
    if consumerUnit.profile_powermeter.powermeter.powermeter_anotation == "Medidor Virtual":
        if consumerUnit.electric_device_type.electric_device_type_name == "Total Edificio":
            total = True
        else:
            total = False
        c_units = get_total_consumer_unit(consumerUnit, total)
    else:
        c_units = [consumerUnit]
    return c_units


def allowed_cu(consumerUnit, user, building):
    """returns true or false if the user has permission over the
    consumerUnit or not
    consumerUnit = ConsumerUnit instance
    user = auth.User instance
    building = Building instance
    """
    if user.is_superuser:
        return True
    company = CompanyBuilding.objects.get(building=building)
    context1 = DataContextPermission.objects.filter(
        user_role__user=user,
        company=company.company,
        building=None,
        part_of_building=None).count()
    cluster = ClusterCompany.objects.get(company=company.company)
    context2 = DataContextPermission.objects.filter(
        user_role__user=user,
        cluster=cluster.cluster,
        company=None, building=None,
        part_of_building=None).count()
    if context1 or context2:
        return True
    if consumerUnit.electric_device_type.electric_device_type_name == "Total Edificio":
        context = DataContextPermission.objects.filter(
            user_role__user=user,
            building=building,
            part_of_building=None).count()
        if context:
            return True
        else:
            return False
    else:
        context = DataContextPermission.objects.filter(user_role__user=user,
                                                       building=building)
        for cntx in context:
            if cntx.part_of_building:
                #if the user has permission over a part of building, and the
                # consumer unit is
                #the cu for the part of building
                if consumerUnit.part_of_building == cntx.part_of_building:
                    return True
                elif is_in_part_of_building(consumerUnit,
                                            cntx.part_of_building):
                    return True
            elif cntx.building == consumerUnit.building:
                return True
        return False


def is_in_part_of_building(consumerUnit, part_of_building):
    """checks if consumerUnit is part of the part_of_building
    returns True if consumerUnit is inside the part
    :param consumerUnit: ConsumerUnit instance *without part_of_building*
    :param part_of_building: PartOfBuilding instance
    """
    part_parent = HierarchyOfPart.objects.filter(
        part_of_building_composite=part_of_building)
    if part_parent:
        for parent_part in part_parent:
            if parent_part.consumer_unit_leaf:
                if parent_part.consumer_unit_leaf == consumerUnit:
                    return True
                else:
                    if is_in_consumer_unit(consumerUnit,
                                           parent_part.consumer_unit_leaf):
                        return True
            else:
                if parent_part.part_of_building_leaf == consumerUnit.part_of_building:
                    return True
                elif is_in_part_of_building(consumerUnit,
                                            parent_part.part_of_building_leaf):
                    return True
        return False
    else:
        return False


def is_in_consumer_unit(cunit, cuParent):
    """ checks if consumerUnit is part of an electric system (another consumer
    unit)
    returns True if consumerUnit is inside the system
    cunit = ConsumerUnit instance *without part_of_building*
    cuParent = ConsumerUnit instance
    """
    part_parent = HierarchyOfPart.objects.filter(
        consumer_unit_composite=cuParent)
    if part_parent:
        for parent_part in part_parent:
            if parent_part.consumer_unit_leaf == cunit:
                return True
            else:
                if is_in_consumer_unit(cunit, parent_part.consumer_unit_leaf):
                    return True
        return False
    else:
        return False


def graphs_permission(user, consumer_unit, graphs_type):
    """ Checks what kind of graphs can a user see for a consumer_unit
    user.- django auth user object
    consumer_unit.- ConsumerUnit object

    returns an array of objects of permission, False if user is not allowed
    to see graphs

    """

    operation = VIEW
    company = CompanyBuilding.objects.get(building=consumer_unit.building)
    cluster = ClusterCompany.objects.get(company=company.company)
    context = DataContextPermission.objects.filter(user_role__user=user,
                                                   cluster=cluster.cluster)
    contextos = []
    for cntx in context:
        if cntx.part_of_building:
            part = cntx.part_of_building
            #if the user has permission over a part of building, and the
            # consumer unit is
            #the cu for the part of building
            if consumer_unit.part_of_building == part:
                contextos.append(cntx)
            elif is_in_part_of_building(consumer_unit, part):
                contextos.append(cntx)

        else: #if cntx.building == consumer_unit.building:
            contextos.append(cntx)

    user_roles = context.values_list("user_role__pk", flat=True)

    ur = UserRole.objects.filter(
        user=user, pk__in=user_roles).values_list(
        "role__pk", flat=True)
    graphs = []
    for _object in graphs_type:
        if user.is_superuser:
            graph_obj = Object.objects.get(pk=_object)
            graphs.append(graph_obj)
        else:
            permission = PermissionAsigment.objects.filter(
                object__pk=_object, role__in=ur, operation=operation).count()
            if permission:
                graph_obj = Object.objects.get(pk=_object)
                graphs.append(graph_obj)
    if graphs:
        return graphs
    else:
        return False


def handle_company_logo(i, company, is_new):
    dir_fd = os.open(os.path.join(settings.PROJECT_PATH,
                                  "templates/static/media/logotipos/"),
                     os.O_RDONLY)
    os.fchdir(dir_fd)
    #Revisa si la carpeta de la empresa existe.
    if not is_new:
        dir_path = os.path.join(settings.PROJECT_PATH,
                                'templates/static/media/logotipos/')
        files = os.listdir(dir_path)
        dir_fd = os.open(dir_path, os.O_RDONLY)
        os.fchdir(dir_fd)
        for _file in files:
            if _file == company.company_logo:
                os.remove(_file)
        os.close(dir_fd)

    dir_fd = os.open(os.path.join(settings.PROJECT_PATH,
                                  "templates/static/media/logotipos/"),
                     os.O_RDONLY)
    os.fchdir(dir_fd)
    try:
        imagefile = cStringIO.StringIO(i.read())
        imagefile.seek(0)
        imageImage = Image.open(imagefile)
    except IOError:
        print "could not load image"
        return False

    if imageImage.mode != "RGB":
        imageImage = imageImage.convert("RGB")

    (width, height) = imageImage.size
    width, height = variety.scale_dimensions(width, height, longest_side=200)
    resizedImage = imageImage.resize((width, height), Image.ANTIALIAS)

    imagefile = cStringIO.StringIO()
    resizedImage.save(imagefile, 'JPEG', quality=100)
    filename = hashlib.md5(imagefile.getvalue()).hexdigest() + '.jpg'

    # #save to disk
    imagefile = open(os.path.join('', filename), 'w')
    resizedImage.save(imagefile, 'JPEG', quality=100)
    company.company_logo = "logotipos/" + filename
    company.save()
    os.close(dir_fd)
    return True


def location_objects(country_id, country_name, state_id, state_name,
                     municipality_id, municipality_name, neighborhood_id,
                     neighborhood_name, street_id, street_name):
    #Se obtiene el objeto de Pais, sino esta Pais, se da de alta un pais nuevo.
    if country_id:
        countryObj = get_object_or_404(Pais, pk=country_id)
    else:
        countryObj = Pais(
            pais_name=country_name
        )
        countryObj.save()

    #Se obtiene el objeto de Estado, sino esta Estado, se da de alta un estado
    # nuevo.
    if state_id:
        stateObj = get_object_or_404(Estado, pk=state_id)
    else:
        stateObj = Estado(
            estado_name=state_name
        )
        stateObj.save()

        #Se crea la relación Pais - Estado
        country_stateObj = PaisEstado(
            pais=countryObj,
            estado=stateObj,
        )
        country_stateObj.save()

    #Se obtiene el objeto de Municipio, sino esta Municipio, se da de alta un
    # municipio nuevo.
    if municipality_id:
        municipalityObj = get_object_or_404(Municipio, pk=municipality_id)
    else:
        municipalityObj = Municipio(
            municipio_name=municipality_name
        )
        municipalityObj.save()

        #Se crea la relación Estado - Municipio
        state_munObj = EstadoMunicipio(
            estado=stateObj,
            municipio=municipalityObj,
        )
        state_munObj.save()

    #Se obtiene el objeto de Colonia, sino esta Colonia, se da de alta una
    # Colonia nueva.
    if neighborhood_id:
        neighborhoodObj = get_object_or_404(Colonia, pk=neighborhood_id)
    else:
        neighborhoodObj = Colonia(
            colonia_name=neighborhood_name
        )
        neighborhoodObj.save()

        #Se crea la relación Municipio - Colonia
        mun_neighObj = MunicipioColonia(
            municipio=municipalityObj,
            colonia=neighborhoodObj,
        )
        mun_neighObj.save()

    #Se obtiene el objeto de Calle, sino esta Calle, se da de alta una
    # Calle nueva.
    if street_id:
        streetObj = get_object_or_404(Calle, pk=street_id)
    else:
        streetObj = Calle(
            calle_name=street_name
        )
        streetObj.save()

        #Se crea la relación Calle - Colonia
        neigh_streetObj = ColoniaCalle(
            colonia=neighborhoodObj,
            calle=streetObj,
        )
        neigh_streetObj.save()

    return countryObj, stateObj, municipalityObj, neighborhoodObj, streetObj

@csrf_exempt
def get_profile(request):
    if request.method == 'POST':
        if "serials" in request.POST:
            serials = request.POST['serials'].split("-")
            srls = []
            for serial in serials:
                profile = ProfilePowermeter.objects.get(
                    powermeter__powermeter_serial=serial
                )
                consumer = ConsumerUnit.objects.get(
                    profile_powermeter = profile
                )
                srls.append(dict(profile=profile.pk,
                                 consumer=consumer.pk,
                                 serial=serial))
            data = simplejson.dumps(srls)
            return HttpResponse(content=data, content_type="application/json")
        else:
            raise Http404
    else:
        raise Http404

def all_dailyreportAll(from_date):
    """Calculate the daily report for all the consumer units in all the buildings
    It starts from a given date to today
    :param from_date: Datetime, the start date
    """
    buildings = Building.objects.all()
    initial_d = from_date
    #datos = DailyData.objects.filter(data_day__gte=initial_d)
    #datos.delete()
    dia = datetime.timedelta(days=1)
    while initial_d < datetime.datetime.now():
        for buil in buildings:
            cus = ConsumerUnit.objects.filter(building=buil)
            if cus:
                for cu in cus:
                    dailyReport(buil, cu, initial_d)
            else:
                continue
        initial_d += dia
    print "Done AlldailyReportAll"


def dailyReportAll_Period(start_date, end_date):
    """Calculate the daily report for all the consumer units in all the buildings
    for a given period
    :param start_date: Datetime, the start date
    :param end_date: Datetime, the end date
    """
    buildings = Building.objects.all()
    for buil in buildings:

        # ----- iterative daily report for all consumer units
        cus = ConsumerUnit.objects.filter(building=buil)

        for cu in cus:
            dailyReportPeriodofTime(buil, cu, start_date, end_date)

    print "Done dailyReportAll"


def dailyReportPeriodofTime(building, consumer_unit, start_date, end_date):
    """Calculate the daily report for a consumer unit in a building for a
    given period
    :param building: Building Object
    :param consumer_unit: Consumer Unit Object
    :param start_date: Datetime, the start date
    :param end_date: Datetime, the end date
    """
    actual_date = start_date
    dia = datetime.timedelta(days=1)
    while actual_date <= end_date:
        dailyReport(building, consumer_unit, actual_date)
        actual_date += dia

    print "Done dailyReportPeriodofTime"

def dailyReportAll():
    """Calculate the daily report for all the consumer units in all the buildings
    for the day before
    """
    buildings = Building.objects.all()
    for buil in buildings:

        # ----- iterative daily report for all consumer units
        cus = ConsumerUnit.objects.filter(building=buil)
        #19 - kW - Instant
        #24 - kWhIMPORT
        #26 - kvarhIMPORT
        #paramters_pks = [19, 24, 26]

        for cu in cus:
            dia = datetime.timedelta(days=1)
            dailyReport(buil, cu, datetime.datetime.today()-dia)

    print "Done dailyReportAll"


def dailyReport(building, consumer_unit, today):
    """Calculate the daily report for a consumer unit in a building for a given
    day
    :param building: Building Object
    :param consumer_unit: Consumer Unit Object
    :param today: Datetime
    """

    #Inicializacion de variables
    kwh_totales = 0
    kwh_punta = 0
    kwh_intermedio = 0
    kwh_base = 0
    demanda_max = 0
    dem_max_time = '00:00:00'
    demanda_min = 0
    dem_min_time = '00:00:00'
    kvarh_totales = 0
    kvarhs_anterior = False

    tarifa_kwh = 0
    tarifa_kwh_base = 0
    tarifa_kwh_intermedio = 0
    tarifa_kwh_punta = 0

    costo_energia_total = 0

    day_delta = datetime.timedelta(days=1)

    #Se borra el día si existe
    try:
        day_data = DailyData.objects.get(consumer_unit=consumer_unit,
                                         data_day=today)
    except ObjectDoesNotExist:
        pass
    else:
        day_data.delete()

    #Se agregan las horas (Formato UTC)

    today_s_utc = today
    today_e_utc = today_s_utc + day_delta

    #Se obtiene la región
    region = building.region

    #Se obtiene la tarifa del edificio
    electric_rate = building.electric_rate

    consumer_units = get_consumer_units(consumer_unit)
    if consumer_units:
        if len(consumer_units) > 1:
            virtual_cu =\
            c_functions_get_consumer_unit_electrical_parameter_data_clustered(
                consumer_unit,
                today_s_utc,
                today_e_utc,
                'kW',
                300
            )

            for vcu in virtual_cu:
                if vcu['value']:
                    if vcu['value'] > demanda_max:
                        demanda_max = vcu['value']
                        dem_max_time = datetime.datetime.\
                        utcfromtimestamp(vcu['datetime']).\
                        replace(tzinfo=pytz.utc).\
                        astimezone(timezone.get_current_timezone()).time()


                if not demanda_min:
                    if vcu['value']:
                        demanda_min = vcu['value']
                        dem_min_time = datetime.datetime.\
                        utcfromtimestamp(vcu['datetime']).\
                        replace(tzinfo=pytz.utc).\
                        astimezone(timezone.get_current_timezone()).time()
                else:
                    if vcu['value']:
                        if vcu['value'] < demanda_min:
                            demanda_min = vcu['value']
                            dem_min_time = datetime.datetime.\
                            utcfromtimestamp(vcu['datetime']).\
                            replace(tzinfo=pytz.utc).\
                            astimezone(timezone.get_current_timezone()).time()
        else:
            #Se obtiene la demanda max
            demanda_max_obj = ElectricDataTemp.objects.\
            filter(profile_powermeter = consumer_units[0].profile_powermeter).\
            filter(medition_date__gte=today_s_utc).\
            filter(medition_date__lte=today_e_utc).\
            order_by('-kW_import_sliding_window_demand')

            if demanda_max_obj:
                demanda_max_temp = demanda_max_obj[0].\
                kW_import_sliding_window_demand
                if demanda_max_temp > demanda_max:
                    demanda_max = demanda_max_temp
                    dem_max_time = demanda_max_obj[0].medition_date.\
                    astimezone(timezone.get_current_timezone()).time()

            #Se obtiene la demanda min
            demanda_min_obj = ElectricDataTemp.objects.\
            filter(profile_powermeter = consumer_units[0].profile_powermeter).\
            filter(medition_date__gte=today_s_utc).\
            filter(medition_date__lte=today_e_utc).\
            order_by('kW')
            if demanda_min_obj:
                demanda_min_temp = demanda_min_obj[0].kW
                if not demanda_min:
                    demanda_min = demanda_min_temp
                    dem_min_time = demanda_min_obj[0].medition_date.\
                    astimezone(timezone.get_current_timezone()).time()
                if demanda_min_temp < demanda_min:
                    demanda_min = demanda_min_temp
                    dem_min_time = demanda_min_obj[0].medition_date.\
                    astimezone(timezone.get_current_timezone()).time()

        for c_unit in consumer_units:
            #print c_unit
            profile_powermeter =  c_unit.profile_powermeter
            #print "Profile Powermeter:", profile_powermeter.pk

            kwh_dia_dic = getKWHperDay(today_s_utc, today_e_utc, profile_powermeter)

            kwh_base += kwh_dia_dic['base']
            kwh_intermedio += kwh_dia_dic['intermedio']
            kwh_punta += kwh_dia_dic['punta']
            kwh_totales += kwh_dia_dic['base'] + \
                           kwh_dia_dic['intermedio'] + \
                           kwh_dia_dic['punta']

            #Se obtienen los kvarhs por medidor
            kvarh_totales += obtenerKVARH(profile_powermeter,
                         today_s_utc,
                         today_e_utc)
            """
            kvarh_totales += obtenerKVARH_dia(profile_powermeter,
                                              today_s_utc,
                                              today_e_utc,
                                              kvarhs_anterior)
            """
    #Si es tarifa HM
    if electric_rate.pk == 1:
        #Obtiene el id de la tarifa correspondiente para el mes en cuestion
        tarifasObj = ElectricRatesDetail.objects.filter(electric_rate=1).filter(
            region=region).filter(date_init__lte=today).filter(
            date_end__gte=today)

        if tarifasObj:
            tarifa_kwh_base = tarifasObj[0].KWHB
            tarifa_kwh_intermedio = tarifasObj[0].KWHI
            tarifa_kwh_punta = tarifasObj[0].KWHP


        #Se obtiene costo de energía
        costo_energia_total = costoenergia(kwh_base, kwh_intermedio,
                                           kwh_punta, tarifa_kwh_base,
                                           tarifa_kwh_intermedio,
                                           tarifa_kwh_punta)

    elif electric_rate.pk == 2:#Si es tarifa Dac
        #Para las regiones BC y BCS es necesario obtener revisar si se aplica
        # Tarifa de Verano o de Invierno

        if region.pk == 1 or region.pk == 2:
            tf_ver_inv = obtenerHorarioVeranoInvierno(today, 2)
            tarifasObj = DACElectricRateDetail.objects.filter(
                region=region.pk).filter(date_interval=tf_ver_inv).filter(
                date_init__lte=today).filter(date_end__gte=today)
            if tarifasObj:
                tarifa_kwh = tarifasObj[0].kwh_rate

        else:
            tarifasObj = DACElectricRateDetail.objects.filter(
                region=region.pk).filter(date_interval=None).filter(
                date_init__lte=today).filter(date_end__gte=today)
            if tarifasObj:
                tarifa_kwh = tarifasObj[0].kwh_rate

        costo_energia_total = kwh_totales * tarifa_kwh

    elif electric_rate.pk == 3:#Si es tarifa 3
        tarifasObj = ThreeElectricRateDetail.objects.filter(
            date_init__lte=today).filter(date_end__gte=today)
        if tarifasObj:
            tarifa_kwh = tarifasObj[0].kwh_rate

        costo_energia_total = kwh_totales * tarifa_kwh

    #Se obtiene Factor de Potencia
    factor_potencia_total = factorpotencia(kwh_totales, kvarh_totales)

    #Se guarda en la BD
    new_daily = DailyData(
        consumer_unit = consumer_unit,
        data_day = today,
        KWH_total = kwh_totales,
        KWH_base = kwh_base,
        KWH_intermedio = kwh_intermedio,
        KWH_punta = kwh_punta,
        max_demand = int(ceil(demanda_max)),
        max_demand_time = dem_max_time,
        min_demand = int(ceil(demanda_min)),
        min_demand_time = dem_min_time,
        KWH_cost = str(costo_energia_total),
        power_factor = str(factor_potencia_total),
        KVARH = str(kvarh_totales)
    )
    new_daily.save()

    return 'OK'

def getDailyReports(consumer, month, year, days_offset=None):
    """ Returns an array of dicts with the daily data for the year-month

    :param consumer: ConsumerUnit object
    :param month: number 1-12 number of the month
    :param year: number 4 digits number of the year
    :param days_offset: number negative days offset (for week starting in mon)
    """

    #Se obtienen los dias del mes
    month_days = variety.getMonthDays(month, year)

    #Se crea un arreglo para almacenar los datos
    dailyreport_arr = []

    for day in month_days:
        if days_offset:
            day = day + datetime.timedelta(days=days_offset)

        ddata_obj = DailyData.objects.filter(
            consumer_unit=consumer,
            data_day=day).values("max_demand", "KWH_total")[:1]
        if not ddata_obj:
            dailyreport_arr.append(dict(fecha=str(day),
                                        empty="true"))
        else:
            ddata_obj = ddata_obj[0]
            data = dict(fecha=str(day),
                        max_demand=ddata_obj['max_demand'],
                        KWH_total=ddata_obj['KWH_total'],
                        empty="false"
            )
            dailyreport_arr.append(data)

    return dailyreport_arr

def getWeeklyReport(consumer, month, year, days_offset=None):
    """ Returns an array of dicts with the weekly data for the year-month

    :param consumer: ConsumerUnit object
    :param month: number 1-12 number of the month
    :param year: number 4 digits number of the year
    :param days_offset: number negative days offset (for week starting in mon)
    """
    semanas = []
    #Se obtienen los dias del mes
    month_days = variety.getMonthDays(month, year)

    while len(month_days) > 0:

        semana_array = []
        no_days = 0

        while no_days < 7:
            semana_array.append(month_days.pop(0))
            no_days += 1

        fecha_inicial = semana_array[0]
        fecha_final = semana_array[6]

        if days_offset:
            fecha_inicial = fecha_inicial + datetime.timedelta(days=days_offset)
            fecha_final = fecha_final - datetime.timedelta(days=days_offset)

        no_semana = {
        'demanda_max': demandaMaxima(consumer, fecha_inicial, fecha_final),
        'demanda_min': demandaMinima(consumer, fecha_inicial, fecha_final),
        'consumo_acumulado': consumoAcumuladoKWH(consumer, fecha_inicial,
                                                 fecha_final),
        'consumo_promedio': promedioKWH(consumer, fecha_inicial, fecha_final),
        'consumo_desviacion': desviacionStandardKWH(consumer, fecha_inicial,
                                                    fecha_final),
        'consumo_mediana': medianaKWH(consumer, fecha_inicial, fecha_final)}

        semanas.append(no_semana)

    return semanas


def getMonthlyReport(consumer_u, month, year):
    """ Returns a dictionary with the monthly report.
    If the requested report is of the current month, it is calculated so far and
    returned. (IT IS NOT SAVED).
    If the report is of a previous month, checks if the monthly report exists,
    the object is returned. If not, the report is calculated, saved and returned.

    :param consumer_u: ConsumerUnit object
    :param month: number 1-12 number of the month
    :param year: number 4 digits number of the year
    """
    if month < datetime.datetime.today().month and \
            year <= datetime.datetime.today().year:
        try:
            mes = MonthlyData.objects.get(consumer_unit=consumer_u,
                                          month=month, year=year)
        except ObjectDoesNotExist:
            mes_new = calculateMonthlyReport(consumer_u, month, year)
            mes = MonthlyData(consumer_unit=consumer_u,
                              month=month,
                              year=year,
                              KWH_total=mes_new['consumo_acumulado'],
                              max_demand=mes_new['demanda_max'],
                              max_cons=mes_new['consumo_maximo'],
                              carbon_emitions=mes_new['emisiones'],
                              power_factor=str(mes_new['factor_potencia']),
                              min_demand=mes_new['demanda_min'],
                              average_demand=str(mes_new['demanda_promedio']),
                              min_cons=mes_new['consumo_minimo'],
                              average_cons=str(mes_new['consumo_promedio']),
                              median_cons=str(mes_new['consumo_mediana']),
                              deviation_cons=str(mes_new['consumo_desviacion']))
            mes.save()
        return dict(consumo_acumulado=mes.KWH_total,
                    demanda_max=mes.max_demand,
                    consumo_maximo=mes.max_cons,
                    emisiones=mes.carbon_emitions,
                    factor_potencia=float(mes.power_factor),
                    demanda_min=float(mes.min_demand),
                    demanda_promedio=float(mes.average_demand),
                    consumo_minimo=float(mes.min_cons),
                    consumo_promedio=float(mes.average_cons),
                    consumo_mediana=float(mes.median_cons),
                    consumo_desviacion=float(mes.deviation_cons))
    else:
        return calculateMonthlyReport(consumer_u, month, year)


def calculateMonthlyReport_all(month, year):
    """ Calculate the Monthly report for all the Consumer units and save it.
    If the month given is the current month, it is not calculated.

    :param month: number 1-12 number of the month
    :param year: number 4 digits number of the year
    """
    consumer_units = ConsumerUnit.objects.all()
    today = datetime.date.today()
    for consumer_u in consumer_units:
        if year == today.year and month >= today.month:
            #si el mes aún no concluye
            continue
        else:
            mes_new = calculateMonthlyReport(consumer_u, month, year)
            try:
                mes, created = \
                    MonthlyData.objects.get_or_create(
                        consumer_unit=consumer_u,
                        month=month,
                        year=year)
            except MultipleObjectsReturned:
                MonthlyData.objects.filter(
                    consumer_unit=consumer_u,
                    month=month,
                    year=year).delete()
                mes = MonthlyData(consumer_unit=consumer_u,  month=month,
                                  year=year)
                mes.save()
            mes.KWH_total = mes_new['consumo_acumulado']
            mes.max_demand = mes_new['demanda_max']
            mes.max_cons = mes_new['consumo_maximo']
            mes.carbon_emitions = mes_new['emisiones']
            mes.power_factor = str(mes_new['factor_potencia'])
            mes.min_demand = mes_new['demanda_min']
            mes.average_demand = mes_new['demanda_promedio']
            mes.min_cons = mes_new['consumo_minimo']
            mes.average_cons = str(mes_new['consumo_promedio'])
            mes.median_cons = str(mes_new['consumo_mediana'])
            mes.deviation_cons = str(mes_new['consumo_desviacion'])
            mes.save()
    return "done calculateMonthlyReport_all"


def calculateMonthlyReport(consumer_u, month, year):
    """Calculate the month report for the consumer_unit

    :param consumer_u: ConsumerUnit object
    :param month: int month number
    :param year: int year umber
    :return mes: dictionary
    """
    mes = {}

    #Se obtiene el tipo de tarifa del edificio.
    tipo_tarifa = consumer_u.building.electric_rate

    #Se obtienen las fechas de inicio y de fin
    diasmes_arr = monthrange(year, month)

    #Se agregan las horas
    fecha_inicio = datetime.datetime(year,month, 1)
    fecha_final = datetime.datetime(year, month, diasmes_arr[1])

    #Se obtiene el profile_powermeter
    try:
        profile_powermeter = consumer_u.profile_powermeter

    except ObjectDoesNotExist:
        #Si no hay consumer unit, regresa todos los valores en 0
        mes['consumo_acumulado'] = 0
        mes['demanda_max'] = 0
        mes['demanda_min'] = 0
        mes['factor_potencia'] = 0
        mes['consumo_promedio'] = 0
        mes['consumo_mediana'] = 0
        mes['consumo_desviacion'] = 0
        mes['emisiones'] = 0
    else:

        #Obtener consumo acumulado
        mes['consumo_acumulado'] = consumoAcumuladoKWH(consumer_u,
                                                       fecha_inicio,
                                                       fecha_final)

        if not mes['consumo_acumulado']:
            mes['consumo_acumulado'] = 0

        #Obtener demanda maxima
        mes['demanda_max'] = float(
            demandaMaxima(consumer_u, fecha_inicio, fecha_final))

        #Obtener demanda minima
        mes['demanda_min'] = float(demandaMinima(consumer_u,
                                                 fecha_inicio,
                                                 fecha_final))

        #Obtener factor de potencia.
        #Para obtener el factor potencia son necesarios los KWH Totales
        # (consumo acumulado) y los KVARH

        kvarh = kvarhDiariosPeriodo(consumer_u, fecha_inicio, fecha_final)

        print "Kvarh", kvarh

        mes['factor_potencia'] = float(
            factorpotencia(float(mes['consumo_acumulado']),kvarh))

        #Consumo minimo
        mes['consumo_minimo'] = float(max_minKWH(consumer_u, fecha_inicio,
                                              fecha_final, "min"))

        #Consumo maximo
        mes['consumo_maximo'] = float(max_minKWH(consumer_u, fecha_inicio,
                                           fecha_final, "max"))

        #demanda promedio
        mes['demanda_promedio'] = float(promedioKW(consumer_u, fecha_inicio,
                                                   fecha_final))

        #Consumo promedio
        mes['consumo_promedio'] = float(promedioKWH(consumer_u, fecha_inicio,
                                                    fecha_final))

        #Consumo desviación
        mes['consumo_desviacion'] = float(desviacionStandardKWH(consumer_u,
                                                                fecha_inicio,
                                                                fecha_final))

        #Consumo mediana
        mes['consumo_mediana'] = float(medianaKWH(consumer_u,
                                                  fecha_inicio,
                                                  fecha_final))

        #emisiones de carbon
        mes['emisiones'] = mes['consumo_acumulado'] * .55842

    return mes


def save_historic(monthly_cutdate, building):
    """ Calculate the CFE bill for a given building. The calculations depend
    on the building's electric type bill (HM, DAC, 3)

    :param monthly_cutdate: MonthlyCutDate Object
    :param building: Building Object
    """

    if building.electric_rate.pk == 1:
        exist_historic = HMHistoricData.objects.filter(
            monthly_cut_dates=monthly_cutdate)
    elif building.electric_rate.pk == 2:
        exist_historic = DacHistoricData.objects.filter(
            monthly_cut_dates=monthly_cutdate)
    else:#if building.electric_rate.pk == 3:
        exist_historic = T3HistoricData.objects.filter(
            monthly_cut_dates=monthly_cutdate)
    if exist_historic:
        exist_historic.delete()

    month = monthly_cutdate.billing_month.month
    year = monthly_cutdate.billing_month.year

    #Se obtiene el tipo de tarifa del edificio (HM o DAC)
    print "tarifa", building.electric_rate.pk
    if building.electric_rate.pk == 1: #Tarifa HM
        resultado_mensual = tarifaHM_2(building,
            monthly_cutdate.date_init,
            monthly_cutdate.date_end, month, year)

        if resultado_mensual['kwh_totales'] == 0:
            aver_rate = 0
        else:
            aver_rate = resultado_mensual['subtotal'] / resultado_mensual[
                                                        'kwh_totales']
        aver_rate = str(aver_rate)
        resultado_mensual['factor_carga'] = str(
            resultado_mensual['factor_carga'])
        resultado_mensual['costo_fpotencia'] = str(
            resultado_mensual['costo_fpotencia'])
        resultado_mensual['subtotal'] = str(resultado_mensual['subtotal'])
        resultado_mensual['iva'] = str(resultado_mensual['iva'])
        resultado_mensual['total'] = str(resultado_mensual['total'])
        newHistoric = HMHistoricData(
            monthly_cut_dates=monthly_cutdate,
            KWH_total=resultado_mensual['kwh_totales'],
            KWH_base=resultado_mensual['kwh_base'],
            KWH_intermedio=resultado_mensual['kwh_intermedio'],
            KWH_punta=resultado_mensual['kwh_punta'],
            KW_base=resultado_mensual['kw_base'],
            KW_punta=resultado_mensual['kw_punta'],
            KW_intermedio=resultado_mensual['kw_intermedio'],
            KVARH=resultado_mensual['kvarh_totales'],
            power_factor=str(resultado_mensual['factor_potencia']),
            charge_factor=str(resultado_mensual['factor_carga']),
            billable_demand=resultado_mensual['demanda_facturable'],
            KWH_base_rate=str(resultado_mensual['tarifa_kwhb']),
            KWH_intermedio_rate=str(resultado_mensual['tarifa_kwhi']),
            KWH_punta_rate=str(resultado_mensual['tarifa_kwhp']),
            billable_demand_rate=str(resultado_mensual['tarifa_df']),
            average_rate=str(aver_rate),
            energy_cost=str(resultado_mensual['costo_energia']),
            billable_demand_cost=str(resultado_mensual['costo_dfacturable']),
            power_factor_bonification=str(resultado_mensual['costo_fpotencia']),
            subtotal=str(resultado_mensual['subtotal']),
            iva=str(resultado_mensual['iva']),
            total=str(resultado_mensual['total'])
        )
        newHistoric.save()

    elif building.electric_rate.pk == 2:#Tarifa DAC
        resultado_mensual = tarifaDAC_2(building,
            monthly_cutdate.date_init,
            monthly_cutdate.date_end, month, year)

        if resultado_mensual['kwh_totales'] == 0:
            aver_rate = 0
        else:
            aver_rate = resultado_mensual['costo_energia'] / resultado_mensual[
                                                             'kwh_totales']
        aver_rate = str(aver_rate)

        resultado_mensual['costo_energia'] = str(resultado_mensual['costo_energia'])
        resultado_mensual['costo_energia'] = str(resultado_mensual[
                                                 'costo_energia'])
        resultado_mensual['iva'] = str(resultado_mensual['iva'])
        resultado_mensual['total'] = str(resultado_mensual['total'])
        newHistoric = DacHistoricData(
            monthly_cut_dates=monthly_cutdate,
            KWH_total=resultado_mensual['kwh_totales'],
            KWH_rate=resultado_mensual['tarifa_kwh'],
            monthly_rate=resultado_mensual['tarifa_mes'],
            energy_cost=resultado_mensual['importe'],
            average_rate=aver_rate,
            subtotal=resultado_mensual['costo_energia'],
            iva=resultado_mensual['iva'],
            total=resultado_mensual['total']
        )
        newHistoric.save()

    elif building.electric_rate.pk == 3:#Tarifa 3
        resultado_mensual = tarifa_3(building,
            monthly_cutdate.date_init,
            monthly_cutdate.date_end, month, year)

        if resultado_mensual['kwh_totales'] == 0:
            aver_rate = 0
        else:
            aver_rate = resultado_mensual['subtotal'] / resultado_mensual[
                                                        'kwh_totales']

        aver_rate = str(aver_rate)
        resultado_mensual['factor_carga'] = str(
            resultado_mensual['factor_carga'])
        resultado_mensual['costo_fpotencia'] = str(
            resultado_mensual['costo_fpotencia'])
        resultado_mensual['subtotal'] = str(resultado_mensual['subtotal'])
        resultado_mensual['iva'] = str(resultado_mensual['iva'])
        resultado_mensual['total'] = str(resultado_mensual['total'])
        newHistoric = T3HistoricData(
            monthly_cut_dates=monthly_cutdate,
            KWH_total=resultado_mensual['kwh_totales'],
            KVARH=resultado_mensual['kvarh_totales'],
            power_factor=resultado_mensual['factor_potencia'],
            charge_factor=resultado_mensual['factor_carga'],
            max_demand=resultado_mensual['kw_totales'],
            KWH_rate=resultado_mensual['tarifa_kwh'],
            demand_rate=resultado_mensual['tarifa_kw'],
            average_rate=aver_rate,
            energy_cost=resultado_mensual['costo_energia'],
            demand_cost=resultado_mensual['costo_demanda'],
            power_factor_bonification=resultado_mensual['costo_fpotencia'],
            subtotal=resultado_mensual['subtotal'],
            iva=resultado_mensual['iva'],
            total=resultado_mensual['total']
        )
        newHistoric.save()

def tarifaHM_2(building, s_date, e_date, month, year):
    """ Calculates the Electric Bill HM

    :param building: Building object
    :param s_date: Datetime - Beginning date
    :param e_date: Datetime - Ending date
    :param month: Number - Billing month
    :param year: Number - Year of the billing month
    """
    status = 'OK'
    diccionario_final_cfe = dict(status=status)
    #Variables que almacenan todos los campos
    tarifa_kwh_base = 0
    tarifa_kwh_intermedio = 0
    tarifa_kwh_punta = 0
    tarifa_fri = 0
    tarifa_frb = 0
    tarifa_demanda_facturable = 0
    diccionario_final_cfe["kw_base"] = 0
    diccionario_final_cfe["kw_intermedio"] = 0
    diccionario_final_cfe["kw_punta"] = 0
    diccionario_final_cfe["kwh_base"] = 0
    diccionario_final_cfe["kwh_intermedio"] = 0
    diccionario_final_cfe["kwh_punta"] = 0
    diccionario_final_cfe["kwh_totales"] = 0
    diccionario_final_cfe['kvarh_totales'] = 0

    #Se obtiene la región
    region = building.region
    #Se obtiene el tipo de tarifa (HM)
    hm_id = building.electric_rate

    billing_mrates = datetime.date(year=year, month=month, day=1)

    periodo = s_date.astimezone(timezone.get_current_timezone()).strftime(
        '%d/%m/%Y %I:%M %p') +\
              " - " + e_date.astimezone(
        timezone.get_current_timezone()).strftime('%d/%m/%Y %I:%M %p')
    periodo_dias = (e_date - s_date).days
    periodo_horas = periodo_dias * 24

    demanda_max = 0

    #Se obtiene el medidor padre del edificio
    main_cu = ConsumerUnit.objects.get(
        building=building,
        electric_device_type__electric_device_type_name="Total Edificio")
    #Se obtienen todos los medidores necesarios
    consumer_units = get_consumer_units(main_cu)

    #Se obtienen las tuplas Dia Inicio - Dia Fin
    tupleDays_global = getTupleDays(s_date, e_date)

    if consumer_units:

        if len(consumer_units) > 1:

            virtual_cu =\
            c_functions_get_consumer_unit_electrical_parameter_data_clustered(
                main_cu,
                s_date,
                e_date,
                'kW',
                300
            )

            arr_kw_base = []
            arr_kw_int = []
            arr_kw_punta = []

            for vcu in virtual_cu:
                if vcu['value']:
                    kw_date =  datetime.datetime.utcfromtimestamp(vcu['datetime']).\
                    replace(tzinfo=pytz.utc).\
                    astimezone(timezone.get_current_timezone())

                    periodo_mv = obtenerTipoPeriodoObj(kw_date, region)
                    if periodo_mv['period_type'] == 'base':
                        arr_kw_base.append(vcu['value'])
                    elif periodo_mv['period_type'] == 'intermedio':
                        arr_kw_int.append(vcu['value'])
                    elif periodo_mv['period_type'] == 'punta':
                        arr_kw_punta.append(vcu['value'])

            diccionario_final_cfe["kw_base"] =\
            obtenerDemanda_kw_valores(arr_kw_base)

            diccionario_final_cfe["kw_intermedio"] =\
            obtenerDemanda_kw_valores(arr_kw_int)

            diccionario_final_cfe["kw_punta"] =\
            obtenerDemanda_kw_valores(arr_kw_punta)

        else:

            tupleDays_arr = tupleDays_global

            for tupleDay in tupleDays_arr:
                kw_dia_dic = getKWperDay(tupleDay[0], tupleDay[1], consumer_units[0].profile_powermeter)
                if kw_dia_dic['base'] > diccionario_final_cfe["kw_base"]:
                    diccionario_final_cfe["kw_base"] = kw_dia_dic['base']
                if kw_dia_dic['intermedio'] > diccionario_final_cfe["kw_intermedio"]:
                    diccionario_final_cfe["kw_intermedio"] = kw_dia_dic['intermedio']
                if kw_dia_dic['punta'] > diccionario_final_cfe["kw_punta"]:
                    diccionario_final_cfe["kw_punta"] = kw_dia_dic['punta']

        if diccionario_final_cfe["kw_base"] > demanda_max:
            demanda_max = diccionario_final_cfe["kw_base"]
        if diccionario_final_cfe["kw_intermedio"] > demanda_max:
            demanda_max = diccionario_final_cfe["kw_intermedio"]
        if diccionario_final_cfe["kw_punta"] > demanda_max:
            demanda_max = diccionario_final_cfe["kw_punta"]

        for c_unit in consumer_units:
            #Se obtienen directamente los kw Base, Intermedio y Punta.

            profile_powermeter = c_unit.profile_powermeter

            tupleDays_arr = tupleDays_global
            #Se obtiene y calcula el día de inicio
            tuple_first = tupleDays_arr[0]
            kwh_dia_dic = getKWHperDay(tuple_first[0], tuple_first[1], profile_powermeter)
            diccionario_final_cfe["kwh_base"] += kwh_dia_dic['base']
            diccionario_final_cfe["kwh_intermedio"] += kwh_dia_dic['intermedio']
            diccionario_final_cfe["kwh_punta"] += kwh_dia_dic['punta']
            diccionario_final_cfe["kwh_totales"] += kwh_dia_dic['base'] + kwh_dia_dic['intermedio'] + kwh_dia_dic['punta']


            #Se obtiene y calcula el día final
            tuple_last = tupleDays_arr[len(tupleDays_arr)-1]
            kwh_dia_dic = getKWHperDay(tuple_last[0], tuple_last[1], profile_powermeter)
            diccionario_final_cfe["kwh_base"] += kwh_dia_dic['base']
            diccionario_final_cfe["kwh_intermedio"] += kwh_dia_dic['intermedio']
            diccionario_final_cfe["kwh_punta"] += kwh_dia_dic['punta']
            diccionario_final_cfe["kwh_totales"] += kwh_dia_dic['base'] + kwh_dia_dic['intermedio'] + kwh_dia_dic['punta']


            tupleDays_arr = tupleDays_arr[1:-1]

            for tupleDay in tupleDays_arr:

                try:
                    a_day = datetime.date(tupleDay[0].year,tupleDay[0].month,tupleDay[0].day)
                    daily_info = DailyData.objects.get(consumer_unit = c_unit, data_day = a_day)
                except ObjectDoesNotExist:
                    kwh_dia_dic = getKWHperDay(tupleDay[0], tupleDay[1], profile_powermeter)
                    diccionario_final_cfe["kwh_base"] += kwh_dia_dic['base']
                    diccionario_final_cfe["kwh_intermedio"] += kwh_dia_dic['intermedio']
                    diccionario_final_cfe["kwh_punta"] += kwh_dia_dic['punta']
                    diccionario_final_cfe["kwh_totales"] += kwh_dia_dic['base'] + kwh_dia_dic['intermedio'] + kwh_dia_dic['punta']
                else:
                    diccionario_final_cfe["kwh_base"] += daily_info.KWH_base
                    diccionario_final_cfe["kwh_intermedio"] += daily_info.KWH_intermedio
                    diccionario_final_cfe["kwh_punta"] += daily_info.KWH_punta
                    diccionario_final_cfe["kwh_totales"] += daily_info.KWH_base + daily_info.KWH_intermedio + daily_info.KWH_punta


            #Se obtienen los kvarhs por medidor
            diccionario_final_cfe['kvarh_totales'] += obtenerKVARH(
                profile_powermeter, s_date, e_date)

    #Obtiene el id de la tarifa correspondiente para el mes en cuestion
    tarifasObj = ElectricRatesDetail.objects.filter(electric_rate=hm_id).filter(
        region=region).filter(date_init__lte=billing_mrates).filter(
        date_end__gte=billing_mrates)

    if tarifasObj:
        tarifa_kwh_base = tarifasObj[0].KWHB
        tarifa_kwh_intermedio = tarifasObj[0].KWHI
        tarifa_kwh_punta = tarifasObj[0].KWHP
        tarifa_fri = tarifasObj[0].FRI
        tarifa_frb = tarifasObj[0].FRB
        tarifa_demanda_facturable = tarifasObj[0].KDF

    #Demanda Facturable
    df_t = demandafacturable(diccionario_final_cfe["kw_base"],
                             diccionario_final_cfe["kw_intermedio"],
                             diccionario_final_cfe["kw_punta"], tarifa_fri,
                             tarifa_frb)

    #Factor de Potencia
    factor_potencia_total = factorpotencia(diccionario_final_cfe["kwh_totales"],
                                           diccionario_final_cfe[
                                           'kvarh_totales'])

    #Costo Energía
    costo_energia_total = costoenergia(diccionario_final_cfe["kwh_base"],
                                       diccionario_final_cfe["kwh_intermedio"],
                                       diccionario_final_cfe["kwh_punta"],
                                       tarifa_kwh_base, tarifa_kwh_intermedio,
                                       tarifa_kwh_punta)

    #Costo Demanda Facturable
    costo_demanda_facturable = costodemandafacturable(df_t,
                                                      tarifa_demanda_facturable)

    #Costo Factor Potencia
    costo_factor_potencia = costofactorpotencia(factor_potencia_total,
                                                costo_energia_total,
                                                costo_demanda_facturable)

    #Subtotal
    subtotal_final = obtenerSubtotal(costo_energia_total,
                                     costo_demanda_facturable,
                                     costo_factor_potencia)

    #Total
    total_final = obtenerTotal(subtotal_final, 16)

    if demanda_max == 0:
        factor_carga = 0
    else:
        factor_carga = (float(diccionario_final_cfe["kwh_totales"]) / float(
            demanda_max * periodo_horas)) * 100

    diccionario_final_cfe['periodo'] = periodo
    diccionario_final_cfe['demanda_facturable'] = df_t
    diccionario_final_cfe['factor_potencia'] = factor_potencia_total
    diccionario_final_cfe['factor_carga'] = factor_carga
    diccionario_final_cfe['tarifa_kwhb'] = tarifa_kwh_base
    diccionario_final_cfe['tarifa_kwhi'] = tarifa_kwh_intermedio
    diccionario_final_cfe['tarifa_kwhp'] = tarifa_kwh_punta
    diccionario_final_cfe['tarifa_df'] = tarifa_demanda_facturable
    diccionario_final_cfe['costo_energia'] = costo_energia_total
    diccionario_final_cfe['costo_dfacturable'] = costo_demanda_facturable
    diccionario_final_cfe['costo_fpotencia'] = costo_factor_potencia
    diccionario_final_cfe['subtotal'] = subtotal_final
    diccionario_final_cfe['iva'] = obtenerIva(subtotal_final, 16)
    diccionario_final_cfe['total'] = total_final

    return diccionario_final_cfe

# noinspection PyArgumentList
def tarifaDAC_2(building, s_date, e_date, month, year):
    """ Calculates the Electric Bill DAC

    :param building: Building object
    :param s_date: Datetime - Beginning date
    :param e_date: Datetime - Ending date
    :param month: Number - Billing month
    :param year: Number - Year of the billing month
    """
    status = 'OK'
    diccionario_final_cfe = {'status': status}

    tarifa_kwh = 0
    tarifa_mes = 0

    #Se obtiene la region
    region = building.region

    billing_mrates = datetime.date(year=year, month=month, day=1)

    periodo = s_date.astimezone(timezone.get_current_timezone()).strftime(
        '%d/%m/%Y %I:%M %p') +\
              " - " + e_date.astimezone(
        timezone.get_current_timezone()).strftime('%d/%m/%Y %I:%M %p')

    #Para las regiones BC y BCS es necesario obtener revisar si se aplica
    # Tarifa de Verano o de Invierno
    if region.pk == 1 or region.pk == 2:
        tf_ver_inv = obtenerHorarioVeranoInvierno(billing_mrates, 2)
        tarifasObj = DACElectricRateDetail.objects.filter(
            region=region.pk).filter(date_interval=tf_ver_inv).filter(
            date_init__lte=billing_mrates).filter(date_end__gte=billing_mrates)
        if tarifasObj:
            tarifa_kwh = tarifasObj[0].kwh_rate
            tarifa_mes = tarifasObj[0].month_rate

    else:
        tarifasObj = DACElectricRateDetail.objects.filter(
            region=region.pk).filter(date_interval=None).filter(
            date_init__lte=billing_mrates).filter(date_end__gte=billing_mrates)
        if tarifasObj:
            tarifa_kwh = tarifasObj[0].kwh_rate
            tarifa_mes = tarifasObj[0].month_rate


    #Se obtiene el medidor padre del edificio
    main_cu = ConsumerUnit.objects.get(
        building=building,
        electric_device_type__electric_device_type_name="Total Edificio")
    #Se obtienen todos los medidores necesarios
    consumer_units = get_consumer_units(main_cu)

    kwh_netos = 0

    #Se obtienen las tuplas Dia Inicio - Dia Fin
    tupleDays_arr = getTupleDays(s_date, e_date)

    if consumer_units:
        for c_unit in consumer_units:
            profile_powermeter = c_unit.profile_powermeter
            """
            #Se obtiene y calcula el día de inicio
            tuple_first = tupleDays_arr[0]
            kwh_netos += getKWHSimplePerDay(tuple_first[0], tuple_first[1], profile_powermeter)

            #Se obtiene y calcula el día final
            tuple_last = tupleDays_arr[len(tupleDays_arr)-1]
            kwh_netos += getKWHSimplePerDay(tuple_last[0], tuple_last[1], profile_powermeter)

            tupleDays_arr = tupleDays_arr[1:-1]

            for tupleDay in tupleDays_arr:
                try:
                    a_day = datetime.date(tupleDay[0].year,tupleDay[0].month,tupleDay[0].day)
                    daily_info = DailyData.objects.get(consumer_unit = c_unit, data_day = a_day)
                except ObjectDoesNotExist:
                    kwh_netos += getKWHSimplePerDay(tupleDay[0], tupleDay[1], profile_powermeter)
                else:
                    kwh_netos += daily_info.KWH_total
            """

            #Se obtienen los kwh de ese periodo de tiempo.
            kwh_lecturas = ElectricDataTemp.objects.filter(
                profile_powermeter=profile_powermeter).\
            filter(medition_date__gte=s_date).filter(
                medition_date__lt=e_date).\
            order_by('medition_date')
            total_lecturas = kwh_lecturas.count()

            if kwh_lecturas:
                kwh_inicial = kwh_lecturas[0].TotalkWhIMPORT
                kwh_final = kwh_lecturas[total_lecturas - 1].TotalkWhIMPORT

                kwh_netos += int(ceil(kwh_final - kwh_inicial))


    importe = kwh_netos * tarifa_kwh
    costo_energia = importe + tarifa_mes
    iva = costo_energia * Decimal(str(.16))
    total = costo_energia + iva

    diccionario_final_cfe['periodo'] = periodo
    diccionario_final_cfe['kwh_totales'] = kwh_netos
    diccionario_final_cfe['tarifa_kwh'] = tarifa_kwh
    diccionario_final_cfe['tarifa_mes'] = tarifa_mes
    diccionario_final_cfe['importe'] = importe
    diccionario_final_cfe['costo_energia'] = float(costo_energia)
    diccionario_final_cfe['iva'] = float(iva)
    diccionario_final_cfe['total'] = float(total)

    return diccionario_final_cfe


def tarifa_3(building, s_date, e_date, month, year):
    """ Calculates the Electric Bill 3

    :param building: Building object
    :param s_date: Datetime - Beginning date
    :param e_date: Datetime - Ending date
    :param month: Number - Billing month
    :param year: Number - Year of the billing month
    """
    status = 'OK'
    diccionario_final_cfe = dict(status=status)

    tarifa_kwh = 0
    tarifa_kw = 0
    demanda_max = 0
    kwh_netos = 0
    kvarh_netos = 0

    # Se obtiene la region
    # region = building.region

    billing_mrates = datetime.date(year=year, month=month, day=1)

    periodo = s_date.astimezone(timezone.get_current_timezone()).strftime(
        '%d/%m/%Y %I:%M %p') +\
              " - " + e_date.astimezone(
        timezone.get_current_timezone()).strftime('%d/%m/%Y %I:%M %p')
    periodo_dias = (e_date - s_date).days
    periodo_horas = periodo_dias * 24

    tarifasObj = ThreeElectricRateDetail.objects.filter(
        date_init__lte=billing_mrates).filter(date_end__gte=billing_mrates)
    if tarifasObj:
        tarifa_kwh = tarifasObj[0].kwh_rate
        tarifa_kw = tarifasObj[0].kw_rate

    #Se obtiene el medidor padre del edificio
    main_cu = ConsumerUnit.objects.get(
        building=building,
        electric_device_type__electric_device_type_name="Total Edificio")
    #Se obtienen todos los medidores necesarios
    consumer_units = get_consumer_units(main_cu)

    #Se obtienen las tuplas Dia Inicio - Dia Fin
    tupleDays_arr = getTupleDays(s_date, e_date)

    if consumer_units:
        if len(consumer_units) > 1:

            virtual_cu =\
            c_functions_get_consumer_unit_electrical_parameter_data_clustered(
                main_cu,
                s_date.astimezone(timezone.get_current_timezone()),
                e_date.astimezone(timezone.get_current_timezone()),
                'kW',
                300
            )

            arr_kw = []

            for vcu in virtual_cu:
                arr_kw.append(vcu['value'])

            demanda_max = obtenerDemanda_kw_valores(arr_kw)

        else:

            profile_powermeter = consumer_units[0].profile_powermeter

            lectura_max = ElectricDataTemp.objects.filter(
                profile_powermeter=profile_powermeter,
                medition_date__gte=s_date,
                medition_date__lt=e_date).\
            aggregate(Max('kW_import_sliding_window_demand'))

            demanda_max = lectura_max['kW_import_sliding_window_demand__max']


        for c_unit in consumer_units:
            profile_powermeter = c_unit.profile_powermeter

            """
            #Se obtiene y calcula el día de inicio
            tuple_first = tupleDays_arr[0]
            kwh_netos += getKWHSimplePerDay(tuple_first[0], tuple_first[1], profile_powermeter)

            #Se obtiene y calcula el día final
            tuple_last = tupleDays_arr[len(tupleDays_arr)-1]
            kwh_netos += getKWHSimplePerDay(tuple_last[0], tuple_last[1], profile_powermeter)

            tupleDays_arr = tupleDays_arr[1:-1]

            for tupleDay in tupleDays_arr:
                try:
                    a_day = datetime.date(tupleDay[0].year,tupleDay[0].month,tupleDay[0].day)
                    daily_info = DailyData.objects.get(consumer_unit = c_unit, data_day = a_day)
                except ObjectDoesNotExist:
                    kwh_netos += getKWHSimplePerDay(tupleDay[0], tupleDay[1], profile_powermeter)
                else:
                    kwh_netos += daily_info.KWH_total
            """

            #Se obtienen los kwh de ese periodo de tiempo.
            kwh_lecturas = ElectricDataTemp.objects.filter(
                profile_powermeter=profile_powermeter).\
            filter(medition_date__gte=s_date).filter(
                medition_date__lt=e_date).\
            order_by('pk')
            total_lecturas = kwh_lecturas.count()

            if kwh_lecturas:
                kwh_inicial = kwh_lecturas[0].TotalkWhIMPORT
                kwh_final = kwh_lecturas[total_lecturas - 1].TotalkWhIMPORT

                kwh_netos += int(ceil(kwh_final - kwh_inicial))

            #Se obtienen los kvarhs por medidor
            kvarh_netos += obtenerKVARH(profile_powermeter, s_date, e_date)

    #Factor de Potencia
    factor_potencia_total = factorpotencia(kwh_netos, kvarh_netos)

    #Factor de Carga
    if demanda_max == 0:
        factor_carga = 0
    else:
        factor_carga = (float(kwh_netos) / float(
            demanda_max * periodo_horas)) * 100

    costo_energia = kwh_netos * tarifa_kwh
    costo_demanda = demanda_max * tarifa_kw
    costo_factor_potencia = costofactorpotencia(factor_potencia_total,
                                                costo_energia, costo_demanda)

    subtotal = obtenerSubtotal(costo_energia, costo_demanda,
                               costo_factor_potencia)
    iva = obtenerIva(subtotal, 16)
    total = obtenerTotal(subtotal, 16)

    diccionario_final_cfe['periodo'] = periodo
    diccionario_final_cfe['kwh_totales'] = kwh_netos
    diccionario_final_cfe['kw_totales'] = demanda_max
    diccionario_final_cfe['kvarh_totales'] = kvarh_netos
    diccionario_final_cfe['tarifa_kwh'] = tarifa_kwh
    diccionario_final_cfe['tarifa_kw'] = tarifa_kw
    diccionario_final_cfe['factor_potencia'] = factor_potencia_total
    diccionario_final_cfe['factor_carga'] = factor_carga
    diccionario_final_cfe['costo_energia'] = costo_energia
    diccionario_final_cfe['costo_demanda'] = costo_demanda
    diccionario_final_cfe['costo_fpotencia'] = costo_factor_potencia
    diccionario_final_cfe['subtotal'] = float(subtotal)
    diccionario_final_cfe['iva'] = float(iva)
    diccionario_final_cfe['total'] = float(total)

    return diccionario_final_cfe

def asign_electric_data_to_pw(serials):
    """ change the profile_powermeter of all the meditions with an specific
    power_meter_serial and unregistered powermeter
    serials: an array containing strings: powermeter_serials
    """
    for serial in serials:
        profile = ProfilePowermeter.objects.get(
            powermeter__powermeter_serial=serial)
        ed = ElectricDataTemp.objects.filter(
            powermeter_serial=serial,
            profile_powermeter__powermeter__powermeter_anotation="No Registrado")
        if ed:
            for e in ed:
                e.profile_powermeter = profile
                e.save()

    return "done"


def c_functions_get_consumer_unit_electrical_parameter_data_clustered(
        consumer_unit,
        datetime_from,
        datetime_to,
        electrical_parameter_name,
        granularity_seconds=None
):
    """
        Description:
            To-Do

        Arguments:
            consumer_unit - A Consumer Unit object.

            datetime_from - A Datetime object.

            datetime_to - A Datetime object.

            electrical_parameter - A String that represents the name of the
                electrical parameter.

            granularity_seconds - An Integer that represents the number of
                seconds between the points to be retrieved.

        Return:
            A list of dictionaries.
    """
    #
    # Localize datetimes (if neccesary) and convert to UTC
    #
    timezone_current = timezone.get_current_timezone()
    datetime_from_local = datetime_from
    if datetime_from_local.tzinfo is None:
        datetime_from_local = timezone_current.localize(datetime_from)

    datetime_from_utc =\
    datetime_from_local.astimezone(timezone.utc)

    datetime_to_local = datetime_to
    if datetime_to_local.tzinfo is None:
        datetime_to_local = timezone_current.localize(datetime_to)

    datetime_to_utc = datetime_to_local.astimezone(timezone.utc)

    # Get the Electrical Parameter
    #
    electrical_parameter =\
    get_electrical_parameter(
        electrical_parameter_name=electrical_parameter_name)

    if electrical_parameter is None:
        return None

    #
    # Get the Instants between the from and to datetime according to the Instant
    # Delta and create a dictionary with them.
    #
    instant_delta =\
    get_instant_delta(
        delta_seconds=granularity_seconds)


    if instant_delta is None:
        return None

    instants =\
    get_instants_list(
        datetime_from_utc,
        datetime_to_utc,
        instant_delta)

    instants_dictionary = dict()
    instant_dictionary_generic_value = {
        'certainty' : True,
        'value' :None
    }

    for instant in instants:
        key_current = instant['instant_datetime'].strftime(
            "%Y/%m/%d-%H:%M:%S")
        instants_dictionary[key_current] =\
        instant_dictionary_generic_value.copy()

    #
    # Get the dependent Consumer Units List and retrieve their data.
    #
    consumer_units_list = get_consumer_units(consumer_unit)

    for consumer_unit_item in consumer_units_list:
        #
        # Get a Consumer Unit Profile (from the app Data Warehouse Extended)
        #
        consumer_unit_profile =\
        get_consumer_unit_profile(
            consumer_unit_item.pk)

        if consumer_unit_profile is None:
            return None

        consumer_unit_data_list =\
        get_consumer_unit_electrical_parameter_data_list(
            consumer_unit_profile,
            datetime_from_utc,
            datetime_to_utc,
            electrical_parameter,
            instant_delta)

        #
        # Update the information in the Instants dictionary
        #
        for consumer_unit_data in consumer_unit_data_list:
            instant_key_current =\
            consumer_unit_data['instant__instant_datetime'].strftime(
                "%Y/%m/%d-%H:%M:%S")

            try:
                instant_dictionary_current =\
                instants_dictionary[instant_key_current]

            except KeyError:
                instant_dictionary_current = instant_dictionary_generic_value

            certainty_current = instant_dictionary_current['certainty']
            certainty_current =\
            certainty_current and consumer_unit_data['value'] is not None

            instant_dictionary_current['certainty'] = certainty_current

            if certainty_current:
                value_current = instant_dictionary_current['value']
                if value_current is None:
                    value_current = consumer_unit_data['value']

                else:
                    value_current += consumer_unit_data['value']

                instant_dictionary_current['value'] = value_current

            instants_dictionary[instant_key_current] =\
            instant_dictionary_current.copy()

    #
    # Build the list of dictionaries that is to be retrieved.
    #
    consumer_units_data_dictionaries_list = []
    for instant in instants:
        key_current = instant['instant_datetime'].strftime(
            "%Y/%m/%d-%H:%M:%S")

        try:
            instant_dictionary_current = instants_dictionary[key_current]

        except KeyError:
            instant_dictionary_current = instant_dictionary_generic_value

        data_dictionary_current = instant_dictionary_current

        datetime_localtime_timetuple =\
        timezone.localtime(
            instant['instant_datetime']
        ).timetuple()

        data_dictionary_current['datetime'] =\
        int(time.mktime(datetime_localtime_timetuple))

        consumer_units_data_dictionaries_list.append(
            data_dictionary_current.copy())

    return consumer_units_data_dictionaries_list


def crawler_hm_rate(year, month):
    """HM - Gets the rates for the given month and year from the CFE website.
    If the rate already exists in the DB, the object is updated. If not, the rate
    is created.

    :param year: Number - Year of the billing month
    :param month: Number - Billing month
    """
    regiones_dict = dict()
    regiones_fri = dict()

    last_day = monthrange(int(year),int(month))
    date_init = datetime.date(year,month,1)
    date_end = datetime.date(year,month,last_day[1])
    HM_erate = ElectricRates.objects.get(pk = 1)

    try:
        page = urllib2.urlopen("http://app.cfe.gob.mx/Aplicaciones/CCFE/"
                               "Tarifas/Tarifas/tarifas_negocio.asp?Tarifa="
                               "HM&Anio="+str(year)+"&mes="+str(month))
    except IOError:
        print "URL Error. No Connection"
        return False
    else:
        soup = BeautifulSoup(page.read())

        tablasTarifa = soup.find_all('table',{"class" : "tablaTarifa"})
        for tabla in tablasTarifa:
            header_t = tabla.find('tr').find_all('th')

            if str(header_t[1].find(text=True)).replace(
                    '\n','').replace('\t','') == \
                        'Cargo por kilowatt de demanda facturable':
                renglones_tarifa = tabla.find_all('tr')
                for chld in renglones_tarifa:
                    arreglo_tarifas = []
                    tds = chld.find_all('td')
                    if len(tds) > 0:
                        try:
                            region = str(tds[0].find(text=True)).strip()
                            demanda_f = str(tds[1].find(text=True))
                            kwhp = str(tds[2].find(text=True))
                            kwhi = str(tds[3].find(text=True))
                            kwhb = str(tds[4].find(text=True))
                        except IndexError:
                            continue

                        arreglo_tarifas.append(demanda_f.replace('$ ',''))
                        arreglo_tarifas.append(kwhp.replace('$ ',''))
                        arreglo_tarifas.append(kwhi.replace('$ ',''))
                        arreglo_tarifas.append(kwhb.replace('$ ',''))

                        regiones_dict[region] = arreglo_tarifas


            elif str(header_t[1].find(text=True)).strip() == 'FRI':
                renglones_fri = tabla.find_all('tr')
                for r_fri in renglones_fri:
                    arreglo_fri = []
                    tds = r_fri.find_all('td')
                    if len(tds) > 0:
                        try:
                            region = str(tds[0].find(text=True)).strip()
                            fri = str(tds[1].find(text=True))
                            frb = str(tds[2].find(text=True))
                        except IndexError:
                            print "Error: Error al parsear tabla FRI - FRB - " \
                                  "Index Error"
                            continue

                        arreglo_fri.append(fri)
                        arreglo_fri.append(frb)

                        regiones_fri[region] = arreglo_fri

        for region in regiones_dict.keys():
            ar_tarifas = regiones_dict[region]
            ar_fri = regiones_fri[region]

            region_obj = None

            if region == 'Baja California':
                region_obj = Region.objects.get(region_name = 'Baja California')
            elif region == 'Baja California Sur':
                region_obj = Region.objects.get(
                    region_name = 'Baja California Sur')
            elif region == 'Central':
                region_obj = Region.objects.get(region_name = 'Central')
            elif region == 'Noreste':
                region_obj = Region.objects.get(region_name = 'Noreste')
            elif region == 'Noroeste':
                region_obj = Region.objects.get(region_name = 'Noroeste')
            elif region == 'Norte':
                region_obj = Region.objects.get(region_name = 'Norte')
            elif region == 'Peninsular':
                region_obj = Region.objects.get(region_name = 'Peninsular')
            elif region == 'Sur':
                region_obj = Region.objects.get(region_name = 'Sur')

            #Se da de alta la nueva cuota
            try:
                #Se verifica que no haya una tarifa ya registrada para ese mes
                bmonth_exists = ElectricRatesDetail.objects.\
                filter(date_init = date_init).\
                filter(region = region_obj)

                #Si ya existe se actualiza
                if bmonth_exists:

                    bmonth_exists[0].KDF = ar_tarifas[0]
                    bmonth_exists[0].KWHP = ar_tarifas[1]
                    bmonth_exists[0].KWHI = ar_tarifas[2]
                    bmonth_exists[0].KWHB = ar_tarifas[3]
                    bmonth_exists[0].FRI = ar_fri[0]
                    bmonth_exists[0].FRB = ar_fri[1]
                    bmonth_exists[0].KWDMM = 0
                    bmonth_exists[0].KWHEC = 0
                    bmonth_exists[0].date_init = date_init
                    bmonth_exists[0].date_end = date_end
                    bmonth_exists[0].save()

                else: #Si no existe, se inserta la tarifa
                    newHM = ElectricRatesDetail(
                        electric_rate = HM_erate,
                        KDF = ar_tarifas[0],
                        KWHP = ar_tarifas[1],
                        KWHI = ar_tarifas[2],
                        KWHB = ar_tarifas[3],
                        FRI = ar_fri[0],
                        FRB = ar_fri[1],
                        KWDMM = 0,
                        KWHEC = 0,
                        date_init = date_init,
                        date_end = date_end,
                        region = region_obj
                    )
                    newHM.save()
            except IndexError:
                print "Error: No se pudo insertar objeto de Tarifa HM - " \
                      "Index Error"
                continue

        print "HM crawler for "+str(month)+"/"+str(year)+" - Done"
        return True


def crawler_DAC_rate(year, month):
    """DAC - Gets the rates for the given month and year from the CFE website.
    If the rate already exists in the DB, the object is updated. If not, the rate
    is created.

    :param year: Number - Year of the billing month
    :param month: Number - Billing month
    """
    region_obj = None
    last_day = monthrange(int(year),int(month))
    date_init = datetime.date(year,month,1)
    date_end = datetime.date(year,month,last_day[1])

    try:
        page = urllib2.urlopen("http://app.cfe.gob.mx/Aplicaciones/CCFE/"
                               "Tarifas/Tarifas/tarifas_casa.asp?Tarifa="
                               "DAC2003&Anio="+str(year)+"&mes="+str(month))
    except IOError:
        print "URL Error. No Connection"
        return False
    else:
        soup = BeautifulSoup(page.read())
        tablasTarifa = soup.find_all('table', {"class" : "tablaTarifa"})

        #La primer tabla es para tarifas de BC y BC Sur
        # (que tienen Verano e Invierno)
        if len(tablasTarifa) > 0:
            bc_bcs_tarifas = tablasTarifa[0].find_all('tr')
            for bc_t in bc_bcs_tarifas:

                tds = bc_t.find_all('td')
                if len(tds) > 0:
                    try:
                        region = str(tds[0].find(text=True)).strip()
                        cargo_fijo = str(tds[1].find(text=True)).replace('$ ',
                                                                         '')
                        kwh_verano = str(tds[2].find(text=True)).replace('$ ',
                                                                         '')
                        kwh_invierno = str(tds[3].find(text=True)).replace('$ ',
                                                                           '')
                    except IndexError:
                        continue
                    else:
                        region_obj = None

                        if region == 'Baja California':
                            region_obj = Region.objects.\
                            get(region_name = 'Baja California')
                        elif region == 'Baja California Sur':
                            region_obj = Region.objects.\
                            get(region_name = 'Baja California Sur')

                        #Se revisa si el mes cae en verano o invierno
                        tf_ver_inv = obtenerHorarioVeranoInvierno(date_init, 2)
                        #Si el periodo es Verano
                        if tf_ver_inv.interval_period == 1:
                            kwh_t = kwh_verano
                        else: #Si el periodo es Invierno
                            kwh_t = kwh_invierno

                        #Se verifica que no haya una tarifa
                        # ya registrada para ese mes
                        bmonth_exists = DACElectricRateDetail.objects.\
                        filter(date_init = date_init).\
                        filter(region=region_obj)
                        if bmonth_exists:
                            #Actualiza la tarifa
                            bmonth_exists[0].region = region_obj
                            bmonth_exists[0].month_rate = cargo_fijo
                            bmonth_exists[0].kwh_rate = kwh_t
                            bmonth_exists[0].date_interval = tf_ver_inv
                            bmonth_exists[0].date_init = date_init
                            bmonth_exists[0].date_end = date_end
                            bmonth_exists[0].save()

                        else:
                            #Se crea la tarifa
                            newDac = DACElectricRateDetail(
                                region = region_obj,
                                month_rate = cargo_fijo,
                                date_interval = tf_ver_inv,
                                kwh_rate = kwh_t,
                                date_init = date_init,
                                date_end = date_end,
                                )
                            newDac.save()

            resto_tarifas = tablasTarifa[1].find_all('tr')
            for resto_t in resto_tarifas:
                tds = resto_t.find_all('td')
                if len(tds) > 0:
                    try:
                        region = str(tds[0].find(text=True)).strip()
                        cargo_fijo = str(tds[1].find(text=True)).replace('$ ',
                                                                         '')
                        kwh_t= str(tds[2].find(text=True)).replace('$ ','')
                    except IndexError:
                        continue
                    else:
                        if region == 'Norte y Noreste':
                            region_obj = Region.objects.get(
                                region_name = 'Norte')

                            #Se verifica que si la tarifa para la region norte
                            # ya esta registrada
                            bmonth_exists = DACElectricRateDetail.objects.\
                            filter(date_init = date_init).\
                            filter(region=region_obj)

                            if bmonth_exists:
                                #Actualiza la tarifa
                                bmonth_exists[0].region = region_obj
                                bmonth_exists[0].month_rate = cargo_fijo
                                bmonth_exists[0].kwh_rate = kwh_t
                                bmonth_exists[0].date_init = date_init
                                bmonth_exists[0].date_end = date_end
                                bmonth_exists[0].save()
                            else:
                                #Se da de alta la nueva tarifa
                                newDac = DACElectricRateDetail(
                                    region = region_obj,
                                    month_rate = cargo_fijo,
                                    kwh_rate = kwh_t,
                                    date_init = date_init,
                                    date_end = date_end,
                                    )
                                newDac.save()

                            region_obj = Region.objects.get(region_name =
                            'Noreste')

                            #Se verifica que si la tarifa para la region
                            # noreste ya esta registrada
                            bmonth_exists = DACElectricRateDetail.objects.\
                            filter(date_init = date_init).\
                            filter(region=region_obj)

                            if bmonth_exists:
                                #Actualiza la tarifa
                                bmonth_exists[0].region = region_obj
                                bmonth_exists[0].month_rate = cargo_fijo
                                bmonth_exists[0].kwh_rate = kwh_t
                                bmonth_exists[0].date_init = date_init
                                bmonth_exists[0].date_end = date_end
                                bmonth_exists[0].save()
                            else:
                                #Se da de alta la nueva cuota
                                newDac = DACElectricRateDetail(
                                    region = region_obj,
                                    month_rate = cargo_fijo,
                                    kwh_rate = kwh_t,
                                    date_init = date_init,
                                    date_end = date_end,
                                    )
                                newDac.save()

                        elif region == 'Sur y Peninsular':
                            region_obj = Region.objects.get(region_name = 'Sur')

                            #Se verifica que si la tarifa para la region
                            # Sur ya esta registrada
                            bmonth_exists = DACElectricRateDetail.objects.\
                            filter(date_init = date_init).\
                            filter(region=region_obj)

                            if bmonth_exists:
                                #Actualiza la tarifa
                                bmonth_exists[0].region = region_obj
                                bmonth_exists[0].month_rate = cargo_fijo
                                bmonth_exists[0].kwh_rate = kwh_t
                                bmonth_exists[0].date_init = date_init
                                bmonth_exists[0].date_end = date_end
                                bmonth_exists[0].save()
                            else:
                                #Se da de alta la nueva cuota
                                newDac = DACElectricRateDetail(
                                    region = region_obj,
                                    month_rate = cargo_fijo,
                                    kwh_rate = kwh_t,
                                    date_init = date_init,
                                    date_end = date_end,
                                    )
                                newDac.save()

                            region_obj = Region.objects.get(
                                region_name = 'Peninsular')

                            #Se verifica que si la tarifa para la region
                            # Peninsular ya esta registrada
                            bmonth_exists = DACElectricRateDetail.objects.\
                            filter(date_init = date_init).\
                            filter(region=region_obj)

                            if bmonth_exists:
                                #Actualiza la tarifa
                                bmonth_exists[0].region = region_obj
                                bmonth_exists[0].month_rate = cargo_fijo
                                bmonth_exists[0].kwh_rate = kwh_t
                                bmonth_exists[0].date_init = date_init
                                bmonth_exists[0].date_end = date_end
                                bmonth_exists[0].save()
                            else:
                                #Se da de alta la nueva cuota
                                newDac = DACElectricRateDetail(
                                    region = region_obj,
                                    month_rate = cargo_fijo,
                                    kwh_rate = kwh_t,
                                    date_init = date_init,
                                    date_end = date_end,
                                    )
                                newDac.save()

                        else:

                            if region == 'Central':
                                region_obj = Region.objects.\
                                get(region_name = 'Central')

                            elif region == 'Noroeste':
                                region_obj = Region.objects.\
                                get(region_name = 'Noroeste')

                            #Se verifica que si la tarifa para las regiones
                            # central y noroeste ya esta registrada
                            bmonth_exists = DACElectricRateDetail.objects.\
                            filter(date_init = date_init).\
                            filter(region=region_obj)

                            if bmonth_exists:
                                #Actualiza la tarifa
                                bmonth_exists[0].region = region_obj
                                bmonth_exists[0].month_rate = cargo_fijo
                                bmonth_exists[0].kwh_rate = kwh_t
                                bmonth_exists[0].date_init = date_init
                                bmonth_exists[0].date_end = date_end
                                bmonth_exists[0].save()
                            else:
                                #Se da de alta la nueva cuota
                                newDac = DACElectricRateDetail(
                                    region = region_obj,
                                    month_rate = cargo_fijo,
                                    kwh_rate = kwh_t,
                                    date_init = date_init,
                                    date_end = date_end,
                                    )
                                newDac.save()

        print "DAC crawler for "+str(month)+"/"+str(year)+" - Done"
        return True



def crawler_t3_rate(year, month):
    """ Tarifa 3 - Gets the rates for the given month and year from the CFE website.
    If the rate already exists in the DB, the object is updated. If not, the rate
    is created.

    :param year: Number - Year of the billing month
    :param month: Number - Billing month
    """
    tarifa_demanda = None
    tarifa_kwh = None

    last_day = monthrange(int(year),int(month))
    date_init = datetime.date(year,month,1)
    date_end = datetime.date(year,month,last_day[1])

    try:
        page = urllib2.urlopen("http://app.cfe.gob.mx/Aplicaciones/CCFE/Tarifas/Tarifas/tarifas_negocio.asp?Tarifa=3&Anio="+str(year)+"&mes="+str(month))
    except IOError:
        print "URL Error. No Connection"
        return False
    else:
        soup = BeautifulSoup(page.read())

        form_tabla = soup.find('form')

        tablasTarifa = form_tabla.find_all('table')
        for tablaTarifa in tablasTarifa:
            rows = tablaTarifa.find_all('tr')
            for idx, tds in enumerate(rows):
                if tds.td:
                    renglon = tds.td.find('span')
                    if renglon:
                        try:
                            if renglon.string == u'2.1 Cargo por demanda máxima':
                                tarifa_demanda = rows[idx+1].td.b.string.replace('$ ','')
                            elif renglon.string == u'2.2 Cargo adicional por la energía consumida':
                                tarifa_kwh = rows[idx+1].td.b.string.replace('$ ','')
                        except IndexError:
                            print "Error: Error al parsear tabla - Index Error"
                            continue

        if not tarifa_demanda and not tarifa_kwh:
            print "Error: No se encontraron las tarifas dentro del documento"
        else:
            #Se verifica que no haya una tarifa ya registrada para ese mes
            bmonth_exists = ThreeElectricRateDetail.objects.\
            filter(date_init__lte = date_init).\
            filter(date_end__gte = date_init)

            if bmonth_exists:
                bmonth_exists[0].kw_rate = tarifa_demanda
                bmonth_exists[0].kwh_rate = tarifa_kwh
                bmonth_exists[0].date_init = date_init
                bmonth_exists[0].date_end = date_end
                bmonth_exists[0].save()
            else:
                #Se guarda la nueva tarifa
                newT3 = ThreeElectricRateDetail(
                    kw_rate = tarifa_demanda,
                    kwh_rate = tarifa_kwh,
                    date_init = date_init,
                    date_end = date_end
                )
                newT3.save()

        print "T3 crawler for "+str(month)+"/"+str(year)+" - Done"
        return True


def getRatesCurrentMonth():

    now = datetime.datetime.now()

    crawler_hm_rate(now.year, now.month)
    crawler_DAC_rate(now.year, now.month)
    crawler_t3_rate(now.year, now.month)

    print "Current Month Crawlers - Done"

def getAllRates():

    crawler_hm_rate(2012, 1)
    crawler_DAC_rate(2012, 1)
    crawler_t3_rate(2012, 1)

    print "All Rates Crawlers - Done"

def getPlainDays(s_date_utc, e_date_utc):
    arr_b_days = []
    s_date = s_date_utc.astimezone(timezone.get_current_timezone())
    e_date = e_date_utc.astimezone(timezone.get_current_timezone())

    day_delta = datetime.timedelta(days=1)

    s_date_end = s_date + day_delta
    s_date_end = s_date_end.replace(hour = 0, minute = 0)

    actual_date_begin = s_date_end
    arr_b_days.append(s_date.astimezone(timezone.utc))

    while actual_date_begin < (e_date - day_delta):
        actual_date_begin = actual_date_begin
        actual_date_begin = actual_date_begin + day_delta

        arr_b_days.append(actual_date_begin.astimezone(timezone.utc))

    e_date_begin = actual_date_begin
    arr_b_days.append(e_date_begin.astimezone(timezone.utc))

    return arr_b_days


def getTupleDays(s_date_utc, e_date_utc):
    arr_b_days = []
    arr_e_days = []

    #Recibe fechas en formato UTC
    #Se convierten a fechas locales
    s_date = s_date_utc.astimezone(timezone.get_current_timezone())
    e_date = e_date_utc.astimezone(timezone.get_current_timezone())

    day_delta = datetime.timedelta(days=1)

    s_date_end = s_date + day_delta
    s_date_end = s_date_end.replace(hour = 0, minute = 0)

    actual_date_end = s_date_end
    arr_b_days.append(s_date.astimezone(timezone.utc))
    arr_e_days.append(s_date_end.astimezone(timezone.utc))

    while actual_date_end < (e_date - day_delta):
        actual_date_begin = actual_date_end
        actual_date_end = actual_date_begin + day_delta

        arr_b_days.append(actual_date_begin.astimezone(timezone.utc))
        arr_e_days.append(actual_date_end.astimezone(timezone.utc))

    e_date_begin = actual_date_end
    arr_b_days.append(e_date_begin.astimezone(timezone.utc))
    arr_e_days.append(e_date.astimezone(timezone.utc))

    return zip(arr_b_days,arr_e_days)

def regenerate_ie_config(ie_id, user):
    ie = IndustrialEquipment.objects.get(pk=ie_id)
    json_dic = dict(eDevicesConfigList=[])
    ie_pm = PowermeterForIndustrialEquipment.objects.filter(
        industrial_equipment=ie)
    if ie_pm:
        for pm in ie_pm:
            consumer = ConsumerUnit.objects.get(
                profile_powermeter__powermeter=pm.powermeter)
            pm_annotation = consumer.profile_powermeter.powermeter\
                .powermeter_anotation
            pm_dict = dict(IdMedidorESN=pm.powermeter.powermeter_serial,
                           EDeviceModel=pm.powermeter.powermeter_model \
                               .powermeter_model,
                           ProfileIndex=consumer.profile_powermeter.pk,
                           ProfileConsumerUnit=consumer.pk,
                           PowermeterAnnotation=pm_annotation,
                           ModbusAddress=pm.powermeter.modbus_address,
                           ReadTimeRate=consumer.profile_powermeter \
                               .read_time_rate,
                           SendTimeRate=consumer.profile_powermeter \
                               .send_time_rate,
                           status=pm.powermeter.status)
            json_dic['eDevicesConfigList'].append(pm_dict)
    ie.has_new_config = True
    ie.new_config = simplejson.dumps(json_dic)
    ie.modified_by = user
    ie.save()
    return


def parse_file(_file):
    """ Parses a csv file and stores it in DB
    IMPORTANT change dir before call this function
    :param _file: The file name
    """
    if _file.startswith('.'):
        return -1
    data = csv.reader(open(_file, "U"))
    # Read the column names from the first line of the file
    fields = data.next()
    consumer_units = []
    dates_arr = []
    for row in data:
    # Zip together the field names and values
        #if row:
        items = zip(fields, row)
        item = {}
        # Add the value to our dictionary
        for (name, value) in items:
            item[name.strip()] = value.strip()
        fecha = item['Fecha']
        medition_date = datetime.datetime.strptime(
            fecha, "%a %b %d %H:%M:%S %Z %Y")
        try:
            powerp = ProfilePowermeter.objects.get(
                powermeter__powermeter_serial=item["Id medidor"])
        except ObjectDoesNotExist:
            powerp = ProfilePowermeter.objects.get(
                powermeter__powermeter_anotation="No Registrado"
            )
            timezone_ = pytz.timezone("US/Central")
            medition_date.replace(tzinfo=timezone_)
        else:
            cu = ConsumerUnit.objects.get(profile_powermeter=powerp)
            consumer_units.append(cu)

            time_zone, offset = get_google_timezone(cu.building)
            timezone_ = pytz.timezone(time_zone)
            medition_date.replace(tzinfo=timezone_)
            medition_date = medition_date - datetime.timedelta(seconds=offset)

        dates_arr.append(medition_date)
        elec_data = ElectricDataTemp.objects.filter(
            profile_powermeter=powerp,
            medition_date=medition_date
        )
        if elec_data:
            elec_pks = [elec.pk for elec in elec_data]
            tags = ElectricDataTags.objects.filter(
                electric_data__pk__in=elec_pks)
            tags.delete()
            elec_data.delete()

        elec_data = ElectricDataTemp(
            profile_powermeter=powerp,
            medition_date=medition_date,
            V1=item['Voltaje Fase 1'],
            V2=item['Voltaje Fase 2'],
            V3=item['Voltaje Fase 3'],
            I1=item['Corriente Fase 1'],
            I2=item['Corriente Fase 2'],
            I3=item['Corriente Fase 3'],
            kWL1=item['KiloWatts Fase 1'],
            kWL2=item['KiloWatts Fase 2'],
            kWL3=item['KiloWatts Fase 3'],
            kvarL1=item['KiloVoltAmpereReactivo Fase 1'],
            kvarL2=item['KiloVoltAmpereReactivo Fase 2'],
            kvarL3=item['KiloVoltAmpereReactivo Fase 3'],
            kVAL1=item['KiloVoltAmpere Fase 1'],
            kVAL2=item['KiloVoltAmpere Fase 2'],
            kVAL3=item['KiloVoltAmpere Fase 3'],
            PFL1=item['Factor de Potencia Fase 1'],
            PFL2=item['Factor de Potencia Fase 2'],
            PFL3=item['Factor de Potencia Fase 3'],
            kW=item['KiloWatts Totales'],
            kvar=item['KiloVoltAmperesReactivo Totales'],
            TotalkVA=item['KiloVoltAmpere Totales'],
            PF=item['Factor de Potencia Total'],
            FREQ=item['Frecuencia Fase'],
            TotalkWhIMPORT=item['KiloWattHora Totales'],
            powermeter_serial=powerp.powermeter.powermeter_serial,
            TotalkvarhIMPORT=item['KiloVoltAmpereReactivoHora Totales'],
            kWhL1=item['KiloWattHora Fase 1'],
            kWhL2=item['KiloWattHora Fase 2'],
            kwhL3=item['KiloWattHora Fase 3'],
            kvarhL1=item['KiloVoltAmpereReactivoHora Fase 1'],
            kvarhL2=item['KiloVoltAmpereReactivoHora Fase 2'],
            kvarhL3=item['KiloVoltAmpereReactivoHora Fase 3'],
            kVAhL1=item['KiloVoltAmpereHora Fase 1'],
            kVAhL2=item['KiloVoltAmpereHora Fase 2'],
            kVAhL3=item['KiloVoltAmpereHora Fase 3'],
            kW_import_sliding_window_demand=
            item['kW import sliding window demand'],
            kvar_import_sliding_window_demand=
            item['kvar impor sliding window demand'],
            kVA_sliding_window_demand=item['kVA sliding window demand'],
            kvahTOTAL=item['KiloVoltAmpereHora Totales'],
        )

        elec_data.save()

    dates_arr.sort()
    consumer_units = variety.unique_from_array(consumer_units)
    return dates_arr[0], dates_arr[-1], consumer_units


def get_google_timezone(building):
    #Se obtienen las coordenadas del edificio
    bld_lat = building.building_lat_address
    bld_long = building.building_long_address

    #Se obtiene el Timezone del edificio
    try:
        bld_timezone = TimezonesBuildings.objects.get(building=building)
    except ObjectDoesNotExist:
        print "Building with no Timezone"
        return "America/Mexico_City"
    else:
        #Si el edificio no tiene coordenadas.
        # Se toman las coordenadas por default
        if not bld_lat and not bld_long:
            #Obtener las coordenadas por default
            bld_lat = bld_timezone.time_zone.latitude
            bld_long = bld_timezone.time_zone.longitude

        now_timestamp = int(time.time())
        try:
            timezone_json = urllib2.urlopen(
                'https://maps.googleapis.com/maps/api/'
                'timezone/json?location=' + str(bld_lat) +
                ',' + str(bld_long) + '&timestamp=' +
                str(now_timestamp)+'&sensor=false')
        except IOError:
            print "URL Error. No Connection"
            return False
        else:
            json_t = simplejson.load(timezone_json)
            return json_t['timeZoneId'], int(json_t['dstOffset'])




def replace_accents(with_accents):

    accents = {
        'á':'a',
        'é':'e',
        'í':'i',
        'ó':'o',
        'ú':'u',
        'Á':'A',
        'É':'E',
        'Í':'I',
        'Ó':'O',
        'Ú':'U'
    }

    for key in accents.keys():
        with_accents = with_accents.replace(key,accents[key])


    return with_accents


def crawler_get_municipalities():
    states = Estado.objects.all()
    cont_total = 0
    for state in states:
        safe_name = replace_accents(state.estado_name.lower().replace(" ","-").encode('UTF-8'))
        if safe_name == 'estado-de-mexico':
            safe_name = 'mexico'
        try:
            page = urllib2.urlopen("http://municipios.com.mx/"+safe_name+"/")
        except IOError:
            print "URL Error. No Connection"
            return False
        else:
            soup = BeautifulSoup(page.read())

            tablasTarifa = soup.find_all('table', {'width':'381'})

            for tabla in tablasTarifa:
                header_t = tabla.find('tr').find_all('td')
                if len(header_t) > 1:
                    if str(header_t[1].find(text=True)).replace(
                        '\n','').replace('\t','').strip() == 'Nombre del Municipio':
                        renglones_tarifa = tabla.find_all('tr')
                        del renglones_tarifa[0]
                        print "Estado:",safe_name
                        print len(renglones_tarifa)
                        cont_total += len(renglones_tarifa)
                        for chld in renglones_tarifa:
                            tds = chld.find_all('td')
                            print tds[1].find(text=True).encode('UTF-8')

                            mun = Municipio(
                                municipio_name = tds[1].find(text=True).encode('UTF-8'),
                                border = False
                            )
                            mun.save()

                            estado_mun = EstadoMunicipio(
                                estado = state,
                                municipio = mun
                            )
                            estado_mun.save()

                        print "------------------"
                    else:
                        continue
    print "Total: ", cont_total

    print "Finished"
    return True

def setBuildingDST(border):
    """

    :param - Border: Booleano para indicar si modifica los fronterizos o no.
    """
    bld_timezones = TimezonesBuildings.objects.\
                    filter(building__municipio__border = border)
    if bld_timezones:
        for bld_tz in bld_timezones:
            next_dst = DaySavingDates.objects.filter(
                summer_date__gt = bld_tz.day_saving_date.summer_date,
                border = border).order_by("summer_date")[:1]

            if next_dst:
                bld_tz.day_saving_date = next_dst[0]
                bld_tz.save()

            #Se actualiza el JSON del Equipo Industrial para cada edificio
            try:
                industrial_equip = IndustrialEquipment.objects.get(building =
                bld_tz.building)
            except ObjectDoesNotExist:
                print "setBuildingDST - No Industrial Equipment for building: "+\
                      str(bld_tz.building.building_name)
            except MultipleObjectsReturned:
                print "setBuildingDST - Multiple Industrial Equipments: "+\
                      str(bld_tz.building.building_name)
            else:
                json_dic = {"raw_offset":bld_tz.time_zone.raw_offset,
                            "dst_offset":bld_tz.time_zone.dst_offset,
                            "daysaving_id":next_dst[0].pk}

                industrial_equip.timezone_dst = json.dumps(json_dic)
                industrial_equip.save()

    print "setBuildingDST Done"





3




