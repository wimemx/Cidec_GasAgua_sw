# -*- coding: utf-8 -*-
__author__ = 'wime'
#standard library imports
from datetime import  timedelta, datetime
from dateutil.relativedelta import relativedelta
import os
import cStringIO
import Image
import hashlib

#local application/library specific imports
from django.shortcuts import HttpResponse, get_object_or_404
from django.utils import simplejson

from cidec_sw import settings
from c_center.models import Cluster, ClusterCompany, Company, CompanyBuilding, Building, PartOfBuilding
from rbac.models import PermissionAsigment, DataContextPermission, Role, UserRole, Object, Operation
from location.models import *

from rbac.rbac_functions import is_allowed_operation_for_object, \
    default_consumerUnit
import variety

VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")

def get_clusters_for_operation(permission, operation, user):
    """Obtains a queryset for all the clusters that exists in a datacontext for a user,
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
        roles_pks = [pa.role.pk for pa in PermissionAsigment.objects.filter(object=permission, operation=operation)]
        #lista de data_context's del usuario donde tiene permiso de crear asignaciones de roles
        data_context = DataContextPermission.objects.filter(user_role__role__pk__in=roles_pks, user_role__user=user)
        clusters_pks = []
        for dc in data_context:
            clusters_pks.append(dc.cluster.pk)

        return Cluster.objects.filter(pk__in=clusters_pks, cluster_status=1)

def get_all_active_companies_for_cluster(cluster):
    c_comp = ClusterCompany.objects.filter(cluster=cluster)
    companies_pks = [cc.company.pk for cc in c_comp]
    return Company.objects.filter(pk__in=companies_pks, company_status=1)

def get_companies_for_operation(permission, operation, user, cluster):
    """Obtains a queryset for all the companies that exists in a datacontext for a user for a
    given cluster, if the user is super_user returns all active companies for the cluster,
    if the user has permission over the entire cluster, returns all active companies for the cluster
    returns a tuple containing the queryset, and a boolean, indicating if returns all the objects

    permission.- string, the name of the permission object
    operation.- operation object, (VIEW, CREATE, etc)
    user.- django.contrib.auth.models.User instance
    cluster.- Cluster instance
    """
    if user.is_superuser:
        return get_all_active_companies_for_cluster(cluster), True
    else:
        permission = Object.objects.get(object_name=permission)
        if is_allowed_operation_for_object(operation, permission, user, cluster, "cluster"):
            return get_all_active_companies_for_cluster(cluster), True
        else:
            #lista de roles que tienen permiso de "operation" "permission"
            roles_pks = [pa.role.pk for pa in PermissionAsigment.objects.filter(object=permission, operation=operation)]
            #lista de data_context's del usuario donde tiene permiso de crear asignaciones de roles
            data_context = DataContextPermission.objects.filter(user_role__role__pk__in=roles_pks, user_role__user=user, cluster=cluster)
            compnies_pks = []
            for data_c in data_context:
                #reviso si tengo un datacontext para el cluster completo
                if not data_c.company:
                    return get_all_active_companies_for_cluster(cluster), True
                else:
                    compnies_pks.append(data_c.company.pk)
            return Company.objects.filter(pk__in=compnies_pks, company_status=1), False

def get_all_companies_for_operation(permission, operation, user):
    clusters = get_clusters_for_operation(permission, operation, user)
    companies_array = []
    for cluster in clusters:
        companies, all = get_companies_for_operation(permission, operation, user, cluster)
        companies_array.extend(companies)
    return companies_array

def get_all_active_buildings_for_company(company):
    c_buildings = CompanyBuilding.objects.filter(company=company)
    buildings_pks = [cb.building.pk for cb in c_buildings]
    return Building.objects.filter(pk__in=buildings_pks, building_status=1)

def get_buildings_for_operation(permission, operation, user, company):
    """Obtains a queryset for all the buildings that exists in a datacontext for a user for a
    given company, if the user is super_user returns all active building for the company,
    if the user has permission over the entire company, returns all active buildings for the company
    returns a tuple containing the queryset, and a boolean, indicating if returns all the objects

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
        if is_allowed_operation_for_object(operation, permission, user, company, "company") or \
           is_allowed_operation_for_object(operation, permission, user, cluster, "cluster"):
            return get_all_active_buildings_for_company(company), True
        else:
            #lista de roles que tienen permiso de "operation" "permission"
            roles_pks = [pa.role.pk for pa in PermissionAsigment.objects.filter(object=permission, operation=operation)]
            #lista de data_context's del usuario donde tiene permiso de crear asignaciones de roles
            data_context = DataContextPermission.objects.filter(user_role__role__pk__in=roles_pks, user_role__user=user, company=company)
            buildings_pks = []
            for data_c in data_context:
                #reviso si tengo un datacontext para el cluster completo
                if not data_c.building:
                    return get_all_active_buildings_for_company(company), True
                else:
                    buildings_pks.append(data_c.building.pk)
            return Building.objects.filter(pk__in=buildings_pks, building_status=1), False

def get_all_buildings_for_operation(permission, operation, user):
    companies = get_all_companies_for_operation(permission, operation, user)
    buildings_arr = []
    for company in companies:
        building, all = get_buildings_for_operation(permission, operation, user, company)

        buildings_arr.extend(building)
    return buildings_arr

def get_all_active_parts_for_building(building):
    return PartOfBuilding.objects.filter(building=building, part_of_building_status=True)

def get_partsofbuilding_for_operation(permission, operation, user, building):
    """Obtains a queryset for all the partsofbuilding that exists in a datacontext for a user for a
    given building, if the user is super_user returns all active partsofbuilding for the building,
    if the user has permission over the entire building, returns all active partsofbuilding for the building
    returns a tuple containing the queryset, and a boolean, indicating if returns all the objects

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

        if is_allowed_operation_for_object(operation, permission, user, building, "building") or \
                is_allowed_operation_for_object(operation, permission, user, company, "company") or\
                is_allowed_operation_for_object(operation, permission, user, cluster, "cluster"):
            return get_all_active_parts_for_building(building), True
        else:
            #lista de roles que tienen permiso de "operation" "permission"
            roles_pks = [pa.role.pk for pa in PermissionAsigment.objects.filter(object=permission, operation=operation)]
            #lista de data_context's del usuario donde tiene permiso de crear asignaciones de roles
            data_context = DataContextPermission.objects.filter(user_role__role__pk__in=roles_pks, user_role__user=user, building=building)
            parts_pks = []
            for data_c in data_context:
                #reviso si tengo un datacontext para el cluster completo
                if not data_c.part_of_building:
                    return get_all_active_parts_for_building(building), True
                else:
                    parts_pks.append(data_c.part_of_building.pk)
            return PartOfBuilding.objects.filter(pk__in=parts_pks, part_of_building_status=True), False

def get_cluster_companies(request, id_cluster):
    cluster = get_object_or_404(Cluster, pk=id_cluster)
    companies_for_user, all_cluster = get_companies_for_operation("Asignar roles a usuarios", CREATE, request.user, cluster)
    #c_buildings= ClusterCompany.objects.filter(cluster=cluster, company__company_status=1)
    companies = []
    if companies_for_user:
        for company in companies_for_user:
            companies.append(dict(pk=company.pk, company=company.company_name, all=all_cluster))
        data=simplejson.dumps(companies)
    elif all_cluster:
        data=simplejson.dumps([dict(all="all")])
    else:
        data=simplejson.dumps([dict(all="none")])
    return HttpResponse(content=data,content_type="application/json")

def get_company_buildings(request, id_company):
    company = get_object_or_404(Company, pk=id_company)
    buildings_for_user, all_company = get_buildings_for_operation("Asignar roles a usuarios", CREATE, request.user, company)
    #c_buildings= CompanyBuilding.objects.filter(company=company, building__building_status=1)
    buildings = []
    if buildings_for_user:
        for building in buildings_for_user:
            buildings.append(dict(pk=building.pk, building=building.building_name, all=all_company))
        data=simplejson.dumps(buildings)
    elif all_company:
        data=simplejson.dumps([dict(all="all")])
    else:
        data=simplejson.dumps([dict(all="none")])
    return HttpResponse(content=data,content_type="application/json")

def get_parts_of_building(request, id_building):
    building = get_object_or_404(Building, pk=id_building)
    parts_for_user, all_building = get_partsofbuilding_for_operation("Asignar roles a usuarios", CREATE, request.user, building)
    #p_buildings= PartOfBuilding.objects.filter(building=building)
    parts = []
    if parts_for_user:
        for part in parts_for_user:
            parts.append(dict(pk=part.pk, part=part.part_of_building_name, all=all_building))
        data=simplejson.dumps(parts)
    elif all_building:
        data=simplejson.dumps([dict(all="all")])
    else:
        data=simplejson.dumps([dict(all="none")])
    return HttpResponse(content=data,content_type="application/json")

def get_all_profiles_for_user(user):
    """ returns an array of consumer_units in wich the user has access
    """
    contexts = DataContextPermission.objects.filter(user_role__user=user)
    c_us = []
    for context in contexts:
        consumer_units = ConsumerUnit.objects.filter(building=context.building)
        #cu, user, building
        for consumerUnit in consumer_units:
            if consumerUnit.profile_powermeter.powermeter.powermeter_anotation != "Medidor Virtual":
                if context.part_of_building:
                    #if the user has permission over a part of building, and the consumer unit is
                    #the cu for the part of building
                    if consumerUnit.part_of_building == context.part_of_building:
                        c_us.append(consumerUnit)
                    elif is_in_part_of_building(consumerUnit, context.part_of_building):
                        c_us.append(consumerUnit)
                elif context.building == consumerUnit.building:
                    c_us.append(consumerUnit)

    return c_us

def get_intervals_1(get):
    """get the interval for the graphs
    by default we get the data from the last month
    returns f1_init, f1_end as datetime objects
    """
    f1_init = datetime.datetime.today() - relativedelta( months = 1 )
    f1_end = datetime.datetime.today()

    if "f1_init" in get:
        if get["f1_init"] != '':
            f1_init = time.strptime(get['f1_init'], "%d/%m/%Y")
            f1_init = datetime.datetime(f1_init.tm_year, f1_init.tm_mon, f1_init.tm_mday)
        if get["f1_end"] != '':
            f1_end = time.strptime(get['f1_end'], "%d/%m/%Y")
            f1_end = datetime.datetime(f1_end.tm_year, f1_end.tm_mon, f1_end.tm_mday)

    return f1_init, f1_end

def get_intervals_fecha(get):
    """get the interval for the graphs
    by default we get the data from the last month
    returns f1_init, f1_end as formated strings
    """
    f1_init = datetime.datetime.today() - relativedelta( months = 1 )
    f1_init = str(f1_init.year)+"-"+str(f1_init.month)+"-"+str(f1_init.day)+" 00:00:00"
    f1_end = datetime.datetime.today()
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
    """gets the second date interval """
    get2=dict(f1_init=get['f2_init'], f1_end=get['f2_end'])
    return get_intervals_1(get2)

def set_default_session_vars(request, datacontext):
    """Sets the default building and consumer unit """
    #todo: revisar bien estos callbacks, seguramente cambiaran cuando haya un landing page
    if not datacontext:
        request.session['main_building'] = None
        request.session['company']= None
        request.session['consumer_unit'] = None

    if 'main_building' not in request.session:
        #print "144"
        #sets the default building (the first in DataContextPermission)
        try:
            building=Building.objects.get(pk=datacontext[0]['building_pk'])
            request.session['main_building'] = building
        except ObjectDoesNotExist:
            request.session['main_building'] = None
        except IndexError:
            request.session['main_building'] = None
    if "company" not in request.session and request.session['main_building']:
        c_b = CompanyBuilding.objects.get(building=request.session['main_building'])
        request.session['company'] = c_b.company
    elif request.session['company'] and request.session['main_building']:
        c_b = CompanyBuilding.objects.get(building=request.session['main_building'])
        request.session['company'] = c_b.company
    else:
        #print "177"
        request.session['company']= None
    if ('consumer_unit' not in request.session and request.session['main_building']) or\
       (not request.session['consumer_unit'] and request.session['main_building']):
        #print "181"
        #sets the default ConsumerUnit (the first in ConsumerUnit for the main building)
        request.session['consumer_unit'] = default_consumerUnit(request.user, request.session['main_building'])
    else:
        if not request.session['consumer_unit'] or 'consumer_unit' not in request.session:
            #print "186"
            request.session['consumer_unit'] = None
            #try:
            #    c_unit = ConsumerUnit.objects.filter(building=request.session['main_building'])
            #    request.session['consumer_unit'] = c_unit[0]
            #except ObjectDoesNotExist:
            #    request.session['main_building'] = None
            #except IndexError:
            #    request.session['main_building'] = None

    return True

def get_sons(parent, part, user, building):
    """ Gets a list of the direct sons of a given part, or consumer unit
    parent = instance of PartOfBuilding, or ConsumerUnit
    part = string, is the type of the parent
    """
    if part == "part":
        sons_of_parent = HierarchyOfPart.objects.filter(part_of_building_composite=parent)
    else:
        sons_of_parent = HierarchyOfPart.objects.filter(consumer_unit_composite=parent)

    if sons_of_parent:
        list = '<ul>'
        for son in sons_of_parent:
            if son.part_of_building_leaf:
                tag = son.part_of_building_leaf.part_of_building_name
                sons = get_sons(son.part_of_building_leaf, "part", user, building)
                cu = ConsumerUnit.objects.get(part_of_building=son.part_of_building_leaf)
                _class = "part_of_building"
            else:
                tag = son.consumer_unit_leaf.electric_device_type.electric_device_type_name
                sons = get_sons(son.consumer_unit_leaf, "consumer", user, building)
                cu = son.consumer_unit_leaf
                _class = "consumer_unit"
            if allowed_cu(cu, user, building):
                list += '<li><a href="#" rel="' + str(cu.pk) + '" class="' + _class + '">'
                list +=  tag + '</a>' + sons
            else:
                list += '<li>'
                list +=  tag + sons
            list += '</li>'
        list += '</ul>'
        return list
    else:
        return ""

def get_total_consumer_unit(consumerUnit, total):
    """gets the (physical)sons of a cu"""
    c_units = []
    if not total:

        if consumerUnit.part_of_building:
            #es el consumer_unit de una parte de un edificio, saco sus hijos
            leafs = HierarchyOfPart.objects.filter(part_of_building_composite =
            consumerUnit.part_of_building)

        else:
            #es un consumer unit de algún electric device, saco sus hijos
            leafs = HierarchyOfPart.objects.filter(consumer_unit_composite = consumerUnit)


        for leaf in leafs:
            if leaf.part_of_building_leaf:
                leaf_cu = ConsumerUnit.objects.get(part_of_building=leaf.part_of_building_leaf)
            else:
                leaf_cu = leaf.consumer_unit_leaf
            if leaf.ExistsPowermeter:
                c_units.append(leaf_cu)
            else:
                c_units_leaf=get_total_consumer_unit(leaf_cu, False)
                c_units.extend(c_units_leaf)
        return c_units
    else:
        hierarchy = HierarchyOfPart.objects.filter(Q(part_of_building_composite__building=
        consumerUnit.building)
                                                   |Q(consumer_unit_composite__building=
        consumerUnit.building))
        ids_hierarchy = [] #arreglo donde guardo los hijos
        ids_hierarchy_cu = [] #arreglo donde guardo los hijos (consumerunits)
        for hy in hierarchy:
            if hy.part_of_building_leaf:
                ids_hierarchy.append(hy.part_of_building_leaf.pk)
            if hy.consumer_unit_leaf:
                ids_hierarchy_cu.append(hy.consumer_unit_leaf.pk)

        #sacar los padres(partes de edificios y consumerUnits que no son hijos de nadie)
        parents = PartOfBuilding.objects.filter(building=consumerUnit.building).exclude(
            pk__in=ids_hierarchy)

        for parent in parents:
            par_cu=ConsumerUnit.objects.get(part_of_building=parent)
            if par_cu.profile_powermeter.powermeter.powermeter_anotation == "Medidor Virtual":
                c_units_leaf=get_total_consumer_unit(par_cu, False)
                c_units.extend(c_units_leaf)
            else:
                c_units.append(par_cu)
    return c_units



def get_consumer_units(consumerUnit):
    """ Gets an array of consumer units which sum equals the given consumerUnit"""
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
    """returns true or false if the user has permission over the consumerUnit or not
    consumerUnit = ConsumerUnit instance
    user = auth.User instance
    building = Building instance
    """
    if user.is_superuser:
        return True
    company = CompanyBuilding.objects.get(building=building)
    context1 = DataContextPermission.objects.filter(user_role__user=user, company=company.company, building=None, part_of_building=None)
    cluster = ClusterCompany.objects.get(company=company.company)
    context2 = DataContextPermission.objects.filter(user_role__user=user, cluster=cluster.cluster, company=None, building=None, part_of_building=None)
    if context1 or context2:
        return True
    if consumerUnit.electric_device_type.electric_device_type_name == "Total Edificio":
        context = DataContextPermission.objects.filter(user_role__user=user, building=building, part_of_building=None)
        if context:
            return True
        else:
            return False
    else:
        context = DataContextPermission.objects.filter(user_role__user=user, building=building)
        for cntx in context:
            if cntx.part_of_building:
                #if the user has permission over a part of building, and the consumer unit is
                #the cu for the part of building
                if consumerUnit.part_of_building == cntx.part_of_building:
                    return True
                elif is_in_part_of_building(consumerUnit, cntx.part_of_building):
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
    part_parent = HierarchyOfPart.objects.filter(part_of_building_composite=part_of_building)
    if part_parent:
        for parent_part in part_parent:
            if parent_part.consumer_unit_leaf:
                if parent_part.consumer_unit_leaf == consumerUnit:
                    return True
                else:
                    if is_in_consumer_unit(consumerUnit, parent_part.consumer_unit_leaf):
                        return True
            else:
                if parent_part.part_of_building_leaf == consumerUnit.part_of_building:
                    return True
                elif is_in_part_of_building(consumerUnit, parent_part.part_of_building_leaf):
                    return True
        return False
    else:
        return False

def is_in_consumer_unit(cunit, cuParent):
    """ checks if consumerUnit is part of an electric system (another consumer unit)
    returns True if consumerUnit is inside the system
    cunit = ConsumerUnit instance *without part_of_building*
    cuParent = ConsumerUnit instance
    """
    part_parent = HierarchyOfPart.objects.filter(consumer_unit_composite=cuParent)
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

    returns an array of objects of permission, False if user is not allowed to see graphs

    """

    operation = VIEW
    company = CompanyBuilding.objects.get(building=consumer_unit.building)
    cluster = ClusterCompany.objects.get(company=company.company)
    context = DataContextPermission.objects.filter(user_role__user=user,
        cluster=cluster.cluster)
    contextos = []
    for cntx in context:
        if cntx.part_of_building:
            #if the user has permission over a part of building, and the consumer unit is
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
        for object in graphs_type:

            #ob = Object.objects.get(object_name=object)
            permission = PermissionAsigment.objects.filter(object=object, role=u_role.role,
                operation=operation)
            if permission or user.is_superuser:
                graphs.append(object)
    if graphs:
        return graphs
    else:
        return False

def handle_company_logo(i, company, is_new):
    dir_fd=os.open(os.path.join(settings.PROJECT_PATH, "templates/static/media/logotipos/"),os.O_RDONLY)
    os.fchdir(dir_fd)
    #Revisa si la carpeta de la empresa existe.
    if not is_new:
        dir_path = os.path.join(settings.PROJECT_PATH, 'templates/static/media/logotipos/')
        files = os.listdir(dir_path)
        dir_fd = os.open(dir_path, os.O_RDONLY)
        os.fchdir(dir_fd)
        for file in files:
            if file==company.company_logo:
                os.remove(file)
        os.close(dir_fd)

    dir_fd=os.open(os.path.join(settings.PROJECT_PATH, "templates/static/media/logotipos/"),os.O_RDONLY)
    os.fchdir(dir_fd)

    imagefile  = cStringIO.StringIO(i.read())
    imagefile.seek(0)
    imageImage = Image.open(imagefile)

    if imageImage.mode != "RGB":
        imageImage = imageImage.convert("RGB")

    (width, height) = imageImage.size
    width, height = variety.scale_dimensions(width, height, longest_side=200)
    resizedImage = imageImage.resize((width, height))

    imagefile = cStringIO.StringIO()
    resizedImage.save(imagefile,'JPEG', quality=100)
    filename = hashlib.md5(imagefile.getvalue()).hexdigest()+'.jpg'

    # #save to disk
    imagefile = open(os.path.join('',filename), 'w')
    resizedImage.save(imagefile,'JPEG', quality=100)
    company.company_logo="logotipos/"+filename
    company.save()
    os.close(dir_fd)
    return True

def location_objects(country_id, country_name, state_id, state_name, municipality_id,municipality_name,neighborhood_id,neighborhood_name,street_id,street_name):
    #Se obtiene el objeto de Pais, sino esta Pais, se da de alta un pais nuevo.
    if country_id:
        countryObj = get_object_or_404(Pais, pk=country_id)
    else:
        countryObj = Pais(
            pais_name = country_name
        )
        countryObj.save()

    #Se obtiene el objeto de Estado, sino esta Estado, se da de alta un estado nuevo.
    if state_id:
        stateObj = get_object_or_404(Estado, pk=state_id)
    else:
        stateObj = Estado(
            estado_name = state_name
        )
        stateObj.save()

        #Se crea la relación Pais - Estado
        country_stateObj = PaisEstado(
            pais = countryObj,
            estado = stateObj,
        )
        country_stateObj.save()

    #Se obtiene el objeto de Municipio, sino esta Municipio, se da de alta un municipio nuevo.
    if municipality_id:
        municipalityObj = get_object_or_404(Municipio, pk=municipality_id)
    else:
        municipalityObj = Municipio(
            municipio_name = municipality_name
        )
        municipalityObj.save()

        #Se crea la relación Estado - Municipio
        state_munObj = EstadoMunicipio(
            estado = stateObj,
            municipio = municipalityObj,
        )
        state_munObj.save()

    #Se obtiene el objeto de Colonia, sino esta Colonia, se da de alta una Colonia nueva.
    if neighborhood_id:
        neighborhoodObj = get_object_or_404(Colonia, pk=neighborhood_id)
    else:
        neighborhoodObj = Colonia(
            colonia_name = neighborhood_name
        )
        neighborhoodObj.save()

        #Se crea la relación Municipio - Colonia
        mun_neighObj = MunicipioColonia(
            municipio = municipalityObj,
            colonia = neighborhoodObj,
        )
        mun_neighObj.save()

    #Se obtiene el objeto de Calle, sino esta Calle, se da de alta una Calle nueva.
    if street_id:
        streetObj = get_object_or_404(Calle, pk=street_id)
    else:
        streetObj = Calle(
            calle_name = street_name
        )
        streetObj.save()

        #Se crea la relación Calle - Colonia
        neigh_streetObj = ColoniaCalle(
            colonia = neighborhoodObj,
            calle = streetObj,
        )
        neigh_streetObj.save()

    return countryObj, stateObj, municipalityObj, neighborhoodObj, streetObj