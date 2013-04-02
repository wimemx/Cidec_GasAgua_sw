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
from math import ceil

#local application/library specific imports
from django.shortcuts import HttpResponse, get_object_or_404
from django.http import Http404
from django.utils import simplejson, timezone
from django.db.models import Q
from django.db.models.aggregates import *
from django.core.exceptions import ObjectDoesNotExist
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

from rbac.rbac_functions import is_allowed_operation_for_object,\
    default_consumerUnit
import variety

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
    c_comp = ClusterCompany.objects.filter(cluster=cluster)
    companies_pks = [cc.company.pk for cc in c_comp]
    return Company.objects.filter(pk__in=companies_pks, company_status=1)


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
    c_buildings = CompanyBuilding.objects.filter(company=company)
    buildings_pks = [cb.building.pk for cb in c_buildings]
    return Building.objects.filter(pk__in=buildings_pks, building_status=1)


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
    """Obtains a queryset for all the ConsumerUnits that exists in a
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
        data = simplejson.dumps([dict(all="all")])
    else:
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

def get_pw_profiles(request):
    """ Get all the ProfilePowermeters that are available for use in a
    consumer unit, except for not registered and virtual profile
    """
    used_profiles = ConsumerUnit.objects.all()
    used_pks = [pw.profile_powermeter.powermeter.pk for pw in used_profiles]
    profiles = ProfilePowermeter.objects.all().exclude(
        powermeter__powermeter_anotation="Medidor Virtual").exclude(
        powermeter__powermeter_anotation="No Registrado").exclude(
        powermeter__id__in=used_pks).values("pk",
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


    return True

def get_hierarchy_list(building, user):
    """ Obtains an unordered-nested list representing the building hierarchy

    """
    hierarchy = HierarchyOfPart.objects.filter(
        part_of_building_composite__building=building)
    ids_hierarchy = []
    for hy in hierarchy:
        if hy.part_of_building_leaf:
            ids_hierarchy.append(hy.part_of_building_leaf.pk)

    #sacar el padre(partes de edificios que no son hijos de nadie)
    parents = PartOfBuilding.objects.filter(building=building).exclude(
        pk__in=ids_hierarchy)

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
                electric_device_type__electric_device_type_name="Total Edificio")
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
    context1 = DataContextPermission.objects.filter(user_role__user=user,
                                                    company=company.company,
                                                    building=None,
                                                    part_of_building=None)
    cluster = ClusterCompany.objects.get(company=company.company)
    context2 = DataContextPermission.objects.filter(user_role__user=user,
                                                    cluster=cluster.cluster,
                                                    company=None, building=None,
                                                    part_of_building=None)
    if context1 or context2:
        return True
    if consumerUnit.electric_device_type.electric_device_type_name == "Total Edificio":
        context = DataContextPermission.objects.filter(user_role__user=user,
                                                       building=building,
                                                       part_of_building=None)
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
    """ checks if consumerUnit is part of the part_of_building
    returns True if consumerUnit is inside the part
    consumerUnit = ConsumerUnit instance *without part_of_building*
    part_of_building = PartOfBuilding instance
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
            #if the user has permission over a part of building, and the
            # consumer unit is
            #the cu for the part of building
            if consumer_unit.part_of_building == cntx.part_of_building:
                contextos.append(cntx)
            elif is_in_part_of_building(consumer_unit, cntx.part_of_building):
                contextos.append(cntx)

        else: #if cntx.building == consumer_unit.building:
            contextos.append(cntx)

    user_roles = [cntx.user_role.pk for cntx in contextos]

    user_role = UserRole.objects.filter(user=user, pk__in=user_roles)

    graphs = []
    for u_role in user_role:
        for _object in graphs_type:
            #ob = Object.objects.get(object_name=object)
            permission = PermissionAsigment.objects.filter(object=_object,
                                                           role=u_role.role,
                                                           operation=operation)
            if permission or user.is_superuser:
                graphs.append(_object)
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

    imagefile = cStringIO.StringIO(i.read())
    imagefile.seek(0)
    imageImage = Image.open(imagefile)

    if imageImage.mode != "RGB":
        imageImage = imageImage.convert("RGB")

    (width, height) = imageImage.size
    width, height = variety.scale_dimensions(width, height, longest_side=200)
    resizedImage = imageImage.resize((width, height))

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

def all_dailyreportAll():
    buildings = Building.objects.all()
    initial_d = datetime.datetime(2013,3,9)
    datos = DailyData.objects.filter(data_day__gte=initial_d)
    datos.delete()
    dia = datetime.timedelta(days=1)
    while initial_d < datetime.datetime.today():
        for buil in buildings:
            try:
                main_cu = ConsumerUnit.objects.get(
                    building=buil,
                    electric_device_type__electric_device_type_name="Total Edificio"
                )
            except ObjectDoesNotExist:
                continue
            else:
                dailyReport(buil, main_cu, initial_d)
        initial_d += dia
    print "Done AlldailyReportAll"

def dailyReportAll():
    buildings = Building.objects.all()
    for buil in buildings:
        try:
            main_cu = ConsumerUnit.objects.get(
                building=buil,
                electric_device_type__electric_device_type_name="Total Edificio"
            )
        except ObjectDoesNotExist:
            continue
        else:
            dia = datetime.timedelta(days=1)
            dailyReport(buil, main_cu, datetime.datetime.today()-dia)
        # ----- iterative daily report for all consumer units
        #cus = ConsumerUnit.objects.filter(building=buil)
        #for cu in cus:
        #    dia = datetime.timedelta(days=1)
        #    eq_cu = get_consumer_units(cu)
        #    if len(eq_cu) > 1:
        #        #suma(eq_cu)
        #        pass
        #    else:
        #        dailyReport(buil, cu, datetime.datetime.today()-dia)
    print "Done dailyReportAll"


def dailyReport(building, consumer_unit, today):

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

    tarifa_kwh_base = 0
    tarifa_kwh_intermedio = 0
    tarifa_kwh_punta = 0

    #Se agregan las horas
    today_s_str = str(today.year) + "-" + str(today.month) + "-" + \
                  str(today.day)+" 00:00:00"
    today_s_str = time.strptime(today_s_str, "%Y-%m-%d  %H:%M:%S")
    today_s_tuple = time.gmtime(time.mktime(today_s_str))
    today_s_utc = datetime.datetime(year= today_s_tuple[0],
                                    month=today_s_tuple[1],
                                    day=today_s_tuple[2],
                                    hour=today_s_tuple[3],
                                    minute=today_s_tuple[4],
                                    second=today_s_tuple[5],
                                    tzinfo = pytz.utc)

    today_e_str = str(today.year) + "-" + str(today.month) + "-" + \
                  str(today.day)+" 23:59:59"
    today_e_str = time.strptime(today_e_str, "%Y-%m-%d  %H:%M:%S")
    today_e_tuple = time.gmtime(time.mktime(today_e_str))
    today_e_utc = datetime.datetime(year= today_e_tuple[0],
                                    month=today_e_tuple[1],
                                    day=today_e_tuple[2],
                                    hour=today_e_tuple[3],
                                    minute=today_e_tuple[4],
                                    second=today_e_tuple[5],
                                    tzinfo = pytz.utc)

    #print "Today s_utc", today_s_utc
    #print "Today e_utc", today_e_utc

    #Se obtiene la región
    region = building.region

    consumer_units = get_consumer_units(consumer_unit)
    if consumer_units:
        for c_unit in consumer_units:
            pr_powermeter = c_unit.profile_powermeter.powermeter
            profile_powermeter =  c_unit.profile_powermeter

            #Se obtiene la demanda max
            demanda_max_obj = ElectricDataTemp.objects. \
                filter(profile_powermeter__powermeter__pk=pr_powermeter.pk). \
                filter(medition_date__gte=today_s_utc).filter(medition_date__lte=today_e_utc). \
                order_by('-kW_import_sliding_window_demand')
            if demanda_max_obj:
                demanda_max = demanda_max_obj[0].kW_import_sliding_window_demand
                dem_max_time = demanda_max_obj[0].medition_date.time()

            #Se obtiene la demanda min
            demanda_min_obj = ElectricDataTemp.objects.\
                filter(profile_powermeter__powermeter__pk=pr_powermeter.pk).\
                filter(medition_date__gte=today_s_utc).filter(medition_date__lte=today_e_utc).\
                order_by('kW')
            if demanda_min_obj:
                demanda_min = demanda_min_obj[0].kW
                dem_min_time = demanda_min_obj[0].medition_date.time()

            #KWH
            #Se obtienen todos los identificadores para los KWH
            lecturas_identificadores = ElectricRateForElectricData.objects \
                .filter(
                electric_data__profile_powermeter__powermeter__pk
                =pr_powermeter.pk). \
                filter(electric_data__medition_date__gte=today_s_utc).filter(
                electric_data__medition_date__lte=today_e_utc). \
                order_by("electric_data__medition_date").values(
                "identifier").annotate(Count("identifier"))

            if lecturas_identificadores:
                ultima_lectura = 0
                ultimo_id = None
                kwh_por_periodo = []


                for lectura in lecturas_identificadores:

                    electric_info = ElectricRateForElectricData.objects.filter(
                        identifier=lectura["identifier"]). \
                        filter(
                        electric_data__profile_powermeter__powermeter__pk
                        =pr_powermeter.pk). \
                        filter(
                        electric_data__medition_date__gte=today_s_utc
                    ).filter(electric_data__medition_date__lte=today_e_utc). \
                        order_by("electric_data__medition_date")

                    num_lecturas = len(electric_info)
                    ultimo_id = electric_info[num_lecturas-1].electric_data.pk
                    #print "Ultimo ID", ultimo_id
                    primer_lectura = electric_info[0].electric_data.TotalkWhIMPORT
                    ultima_lectura = electric_info[
                        num_lecturas - 1].electric_data.TotalkWhIMPORT
                    #print electric_info[0].electric_data.pk,"Primer Lectura:",
                    # primer_lectura,"-",
                    # electric_info[num_lecturas-1].electric_data.pk,
                    # " Ultima Lectura:",ultima_lectura

                    #Obtener el tipo de periodo: Base, punta, intermedio
                    tipo_periodo = electric_info[
                        0].electric_rates_periods.period_type
                    t = primer_lectura, tipo_periodo
                    kwh_por_periodo.append(t)

                kwh_periodo_long = len(kwh_por_periodo)

                kwh_base_t = 0
                kwh_intermedio_t = 0
                kwh_punta_t = 0

                #Se obtiene la primer lectura del dia siguiente para que
                # concuerde la suma de los KWH
                #Si el dia actual es igual al ultimo dia del mes, no se hace
                # nada.
                diasmes_arr = monthrange(today.year, today.month)
                if not today.day is diasmes_arr[1]:
                    nextReading = ElectricDataTemp.objects.filter(
                        profile_powermeter__powermeter__pk=pr_powermeter.pk). \
                        filter(pk__gt = ultimo_id)
                    if nextReading:
                        ultima_lectura = nextReading[0].TotalkWhIMPORT

                    #sirve para los kvarh
                    kvarhs_anterior = True


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
                        kwh_base_t += kwh_netos
                    elif periodo_t == 'intermedio':
                        kwh_intermedio_t += kwh_netos
                    elif periodo_t == 'punta':
                        kwh_punta_t += kwh_netos

                kwh_base_t = int(ceil(kwh_base_t))
                kwh_base += kwh_base_t

                kwh_intermedio_t = int(ceil(kwh_intermedio_t))
                kwh_intermedio += kwh_intermedio_t

                kwh_punta_t = int(ceil(ceil(kwh_punta_t)))
                kwh_punta += kwh_punta_t

                kwh_t = kwh_base_t + kwh_intermedio_t + kwh_punta_t
                kwh_totales += kwh_t

            #Se obtienen los kvarhs por medidor
            kvarh_totales += obtenerKVARH_dia(profile_powermeter,
                                              today_s_utc,
                                              today_e_utc,
                                              kvarhs_anterior)

    #Obtiene el id de la tarifa correspondiente para el mes en cuestion
    tarifasObj = ElectricRatesDetail.objects.filter(electric_rate=1).filter(
        region=region).filter(date_init__lte=today).filter(
        date_end__gte=today)

    if tarifasObj:
        tarifa_kwh_base = tarifasObj[0].KWHB
        tarifa_kwh_intermedio = tarifasObj[0].KWHI
        tarifa_kwh_punta = tarifasObj[0].KWHP

    #Se obtiene Factor de Potencia
    factor_potencia_total = factorpotencia(kwh_totales, kvarh_totales)

    #Se obtiene costo de energía
    costo_energia_total = costoenergia(kwh_base, kwh_intermedio,
                                       kwh_punta, tarifa_kwh_base,
                                       tarifa_kwh_intermedio,
                                       tarifa_kwh_punta)

    #Se guarda en la BD
    new_daily = DailyData(
        building = building,
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


def getDailyReports(building, month, year):

    #Se obtienen los dias del mes
    month_days = getMonthDaysForDailyReport(month, year)

    #Se crea un arreglo para almacenar los datos
    dailyreport_arr = []

    for day in month_days:
        try:
            ddata_obj = DailyData.objects.get(building=building,
                                              data_day=day)
        except DailyData.DoesNotExist:
            dailyreport_arr.append(dict(fecha=str(day),
                                        empty="true"))
        else:
            data = dict(fecha=str(day),
                        max_demand=ddata_obj.max_demand,
                        KWH_total=ddata_obj.KWH_total,
                        empty="false"
            )
            dailyreport_arr.append(data)

    return dailyreport_arr

def getWeeklyReport(building, month, year):

    semanas = []
    #Se obtienen los dias del mes
    month_days = getMonthDaysForDailyReport(month, year)

    while len(month_days) > 0:

        semana_array = []
        no_days = 0

        while no_days < 7:
            semana_array.append(month_days.pop(0))
            no_days += 1

        fecha_inicial = semana_array[0]
        fecha_final = semana_array[6]

        no_semana = {
        'demanda_max': demandaMaxima(building, fecha_inicial, fecha_final),
        'demanda_min': demandaMinima(building, fecha_inicial, fecha_final),
        'consumo_acumulado': consumoAcumuladoKWH(building, fecha_inicial,
                                                 fecha_final),
        'consumo_promedio': promedioKWH(building, fecha_inicial, fecha_final),
        'consumo_desviacion': desviacionStandardKWH(building, fecha_inicial,
                                                    fecha_final),
        'consumo_mediana': medianaKWH(building, fecha_inicial, fecha_final)}

        semanas.append(no_semana)

    return semanas

def getMonthlyReport(building, month, year):
    mes = {}

    #Se obtiene el tipo de tarifa del edificio.
    tipo_tarifa = building.electric_rate

    #Se obtienen las fechas de inicio y de fin
    diasmes_arr = monthrange(year, month)

    #Se agregan las horas
    fecha_inicio = datetime.datetime(year,month, 1)
    fecha_final = datetime.datetime(year, month, diasmes_arr[1])

    #Se obtiene el profile_powermeter
    try:
        main_cu = ConsumerUnit.objects.get(
            building=building,
            electric_device_type__electric_device_type_name="Total Edificio"
        )
        profile_powermeter = main_cu.profile_powermeter

    except ObjectDoesNotExist:
        #Si no hay consumer unit, regresa todos los valores en 0
        mes['consumo_acumulado'] = 0
        mes['demanda_max'] = 0
        mes['demanda_min'] = 0
        mes['factor_potencia'] = 0
        mes['consumo_promedio'] = 0
        mes['consumo_mediana'] = 0
        mes['consumo_desviacion'] = 0
    else:
        #Obtener consumo acumulado
        mes['consumo_acumulado'] = consumoAcumuladoKWH(building,
                                                       fecha_inicio,
                                                       fecha_final)

        if not mes['consumo_acumulado']:
            mes['consumo_acumulado'] = 0

        #Obtener demanda maxima
        mes['demanda_max'] = demandaMaxima(building, fecha_inicio, fecha_final)

        #Obtener demanda minima
        mes['demanda_min'] = demandaMinima(building, fecha_inicio, fecha_final)

        #Obtener factor de potencia.
        #Para obtener el factor potencia son necesarios los KWH Totales
        # (consumo acumulado) y los KVARH
        kvarh = obtenerKVARH_total(profile_powermeter.powermeter, fecha_inicio,
                                   fecha_final)
        print "kvarh", kvarh
        mes['factor_potencia'] = factorpotencia(float(mes['consumo_acumulado']),
                                                kvarh)

        #Consumo promedio
        mes['consumo_promedio'] = promedioKWH(building, fecha_inicio,
                                              fecha_final)

        #Consumo mediana
        mes['consumo_desviacion'] = desviacionStandardKWH(building,
                                                          fecha_inicio,
                                                          fecha_final)

        #Consumo desviación
        mes['consumo_mediana'] = medianaKWH(building, fecha_inicio, fecha_final)

    return mes

def getMonthDaysForDailyReport(month, year):
    actual_day = datetime.date(year=year, month=month, day=1)
    weekday = actual_day.weekday()

    notSunday = False
    if not weekday is 6:
        notSunday = True

    #Si el primer dia del mes es domingo
    while notSunday:

        actual_day = actual_day + relativedelta(days=-1)
        #Se obtiene el dia de la semana del dia anterior
        weekday = actual_day.weekday()
        if weekday is 6:
            notSunday = False

    #Se crea el arreglo que almacenara los dias del mes
    month_days = []

    no_dia =  0
    while no_dia < 42:
        month_days.append(actual_day)
        actual_day = actual_day + relativedelta(days=+1)
        no_dia += 1

    return month_days


def save_historic(monthly_cutdate, building):
    try:
        if building.electric_rate.pk == 1:
            exist_historic = HMHistoricData.objects.get(
                monthly_cut_dates=monthly_cutdate)
        elif building.electric_rate.pk == 2:
            exist_historic = DacHistoricData.objects.get(
                monthly_cut_dates=monthly_cutdate)
        else:#if building.electric_rate.pk == 3:
            exist_historic = T3HistoricData.objects.get(
                monthly_cut_dates=monthly_cutdate)
    except ObjectDoesNotExist:
        pass
    else:
        exist_historic.delete()

    month = monthly_cutdate.billing_month.month
    year = monthly_cutdate.billing_month.year

    #Se obtiene el tipo de tarifa del edificio (HM o DAC)
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
            power_factor=resultado_mensual['factor_potencia'],
            charge_factor=resultado_mensual['factor_carga'],
            billable_demand=resultado_mensual['demanda_facturable'],
            KWH_base_rate=resultado_mensual['tarifa_kwhb'],
            KWH_intermedio_rate=resultado_mensual['tarifa_kwhi'],
            KWH_punta_rate=resultado_mensual['tarifa_kwhp'],
            billable_demand_rate=resultado_mensual['tarifa_df'],
            average_rate=aver_rate,
            energy_cost=resultado_mensual['costo_energia'],
            billable_demand_cost=resultado_mensual['costo_dfacturable'],
            power_factor_bonification=resultado_mensual['costo_fpotencia'],
            subtotal=resultado_mensual['subtotal'],
            iva=resultado_mensual['iva'],
            total=resultado_mensual['total']
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

        resultado_mensual['subtotal'] = str(resultado_mensual['subtotal'])
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
        resultado_mensual = tarifa_3_v2(building,
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


# noinspection PyArgumentList
def tarifaHM_2(building, s_date, e_date, month, year):
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

    #Se convierten las fechas a zona horaria

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

    if consumer_units:
        for c_unit in consumer_units:
            #Se obtienen directamente los kw Base, Intermedio y Punta.

            profile_powermeter = c_unit.profile_powermeter

            #lecturas_totales = ElectricRateForElectricData.objects.filter(
            #electric_data__profile_powermeter = profile_powermeter).\
            #filter(electric_data__medition_date__gte=s_date).filter(
            # electric_data__medition_date__lte=e_date).\
            #order_by('electric_data__medition_date')
            #kw_t = obtenerDemanda_kw(lecturas_totales)


            lecturas_base = ElectricRateForElectricData.objects.filter(
                electric_data__profile_powermeter=profile_powermeter).\
            filter(electric_data__medition_date__gte=s_date).filter(
                electric_data__medition_date__lt=e_date).\
            filter(electric_rates_periods__period_type='base').order_by(
                'electric_data__medition_date')
            kw_base_t = obtenerDemanda_kw(lecturas_base)
            if kw_base_t > diccionario_final_cfe["kw_base"]:
                diccionario_final_cfe["kw_base"] = kw_base_t

            lecturas_intermedio = ElectricRateForElectricData.objects.filter(
                electric_data__profile_powermeter=profile_powermeter).\
            filter(electric_data__medition_date__gte=s_date).filter(
                electric_data__medition_date__lt=e_date).\
            filter(
                electric_rates_periods__period_type='intermedio').order_by(
                'electric_data__medition_date')
            kw_intermedio_t = obtenerDemanda_kw(lecturas_intermedio)
            if kw_intermedio_t > diccionario_final_cfe["kw_intermedio"]:
                diccionario_final_cfe["kw_intermedio"] = kw_intermedio_t

            lecturas_punta = ElectricRateForElectricData.objects.filter(
                electric_data__profile_powermeter=profile_powermeter).\
            filter(electric_data__medition_date__gte=s_date).filter(
                electric_data__medition_date__lt=e_date).\
            filter(electric_rates_periods__period_type='punta').order_by(
                'electric_data__medition_date')
            kw_punta_t = obtenerDemanda_kw(lecturas_punta)
            if kw_punta_t > diccionario_final_cfe["kw_punta"]:
                diccionario_final_cfe["kw_punta"] = kw_punta_t

            if kw_base_t > demanda_max:
                demanda_max = kw_base_t
            elif kw_intermedio_t > demanda_max:
                demanda_max = kw_intermedio_t
            elif kw_punta_t > demanda_max:
                demanda_max = kw_punta_t

            #KWH
            #Se obtienen todos los identificadores para los KWH
            lecturas_identificadores = ElectricRateForElectricData.objects\
            .filter(
                electric_data__profile_powermeter
                =profile_powermeter).\
            filter(electric_data__medition_date__gte=s_date).filter(
                electric_data__medition_date__lt=e_date).\
            order_by("electric_data__medition_date").values(
                "identifier").annotate(Count("identifier"))

            ultima_lectura = 0
            kwh_por_periodo = []

            for lectura in lecturas_identificadores:
                electric_info = ElectricRateForElectricData.objects.filter(
                    identifier=lectura["identifier"]).\
                filter(
                    electric_data__profile_powermeter
                    =profile_powermeter).\
                filter(electric_data__medition_date__gte=s_date).filter(
                    electric_data__medition_date__lt=e_date).\
                order_by("electric_data__medition_date")

                num_lecturas = len(electric_info)
                primer_lectura = electric_info[0].electric_data.TotalkWhIMPORT
                ultima_lectura = electric_info[
                                 num_lecturas - 1].electric_data.TotalkWhIMPORT

                #Obtener el tipo de periodo: Base, punta, intermedio
                tipo_periodo = electric_info[
                               0].electric_rates_periods.period_type
                t = primer_lectura, tipo_periodo
                kwh_por_periodo.append(t)

            kwh_periodo_long = len(kwh_por_periodo)

            kwh_base_t = 0
            kwh_intermedio_t = 0
            kwh_punta_t = 0

            for idx, kwh_p in enumerate(kwh_por_periodo):
                print "Lectura:", kwh_p[0], "-:", kwh_p[1]
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
                    kwh_base_t += kwh_netos
                elif periodo_t == 'intermedio':
                    kwh_intermedio_t += kwh_netos
                elif periodo_t == 'punta':
                    kwh_punta_t += kwh_netos

            kwh_base_t = int(ceil(kwh_base_t))
            diccionario_final_cfe["kwh_base"] += kwh_base_t

            kwh_intermedio_t = int(ceil(kwh_intermedio_t))
            diccionario_final_cfe["kwh_intermedio"] += kwh_intermedio_t

            kwh_punta_t = int(ceil(ceil(kwh_punta_t)))
            diccionario_final_cfe["kwh_punta"] += kwh_punta_t

            kwh_totales = kwh_base_t + kwh_intermedio_t + kwh_punta_t
            diccionario_final_cfe["kwh_totales"] += kwh_totales

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

    if consumer_units:
        for c_unit in consumer_units:
            profile_powermeter = c_unit.profile_powermeter

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


# noinspection PyArgumentList
def tarifa_3_v2(building, s_date, e_date, month, year):
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

    if consumer_units:
        for c_unit in consumer_units:
            profile_powermeter = c_unit.profile_powermeter

            #Se obtienen los KW, para obtener la demanda maxima
            lecturas_totales = ElectricRateForElectricData.objects.filter(
                electric_data__profile_powermeter=profile_powermeter).\
            filter(electric_data__medition_date__gte=s_date).filter(
                electric_data__medition_date__lt=e_date).\
            order_by('electric_data__medition_date')
            kw_t = obtenerDemanda_kw(lecturas_totales)

            if kw_t > demanda_max:
                demanda_max = kw_t

            #Se obtienen los kwh de ese periodo de tiempo.
            kwh_lecturas = ElectricDataTemp.objects.filter(
                profile_powermeter=profile_powermeter).\
            filter(medition_date__gte=s_date).filter(
                medition_date__lt=e_date).\
            order_by('medition_date')
            total_lecturas = len(kwh_lecturas)

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
    power_meter_serial
    serials: an array containing strings: powermeter_serials
    """
    for serial in serials:
        profile = ProfilePowermeter.objects.get(
            powermeter__powermeter_serial=serial)
        ed = ElectricDataTemp.objects.filter(powermeter_serial=serial)
        for e in ed:
            e.profile_powermeter = profile
            e.save()

    return "done"