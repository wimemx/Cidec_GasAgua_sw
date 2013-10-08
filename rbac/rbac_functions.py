# -*- coding: utf-8 -*-
import re
from datetime import date

from django.db.models.aggregates import Count
from django.core.exceptions import ObjectDoesNotExist
from django.utils import simplejson

from rbac.models import PermissionAsigment, UserRole, DataContextPermission, \
    Operation, Object
from c_center.models import ConsumerUnit, Cluster, CompanyBuilding, Company, \
    ClusterCompany, Building
import variety
from gas_agua.models import WaterGasData

VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")


def check_roles_permission(object_name):
    """ Check the roles that have an allowed operation over an object
    :param object_name: string, the name of the object
    :return an array with a dict with keys: role and operation
    """
    permissions = PermissionAsigment.objects.filter(
        object__object_name=object_name)
    role_operations = []
    for perm in permissions:
        r_o = dict(role=perm.role, operation=perm.operation)
        role_operations.append(r_o)
    return role_operations


def has_permission(user, operation, object_name):
    """ Checks if a user has certain permission over an object

    :param user: django auth user object
    :param operation:  rbac opearion object
    :param object_name: string, the name of the subject
    :return Boolean, true if the user has permission, False if not
    """
    user_role = UserRole.objects.filter(user=user,
                                        role__status=True).exclude(status=False)
    for u_role in user_role:
        permission = PermissionAsigment.objects.filter(
            object__object_name=object_name,
            role=u_role.role, operation=operation)
        if permission:
            return True
    return False


def get_all_clusters_for_operation(operation, permission, user):
    """returns a list of clusters in wich the user has certain permission

    :param operation: Operation instance
    :param permission: Object name
    :param user: django contrib.auth.models.User instance
    :return a list of cluster in which the user has certain permission
    """
    if user.is_superuser:
        return Cluster.objects.filter(cluster_status=1)
    else:
        data_cntx = DataContextPermission.objects.filter(user_role__user=user,
                                                         company=None,
                                                         building=None,
                                                         part_of_building=None)
        clusters = []
        for dc in data_cntx:
            p_a = PermissionAsigment.objects.filter(
                role=dc.user_role.role,
                operation=operation,
                object__object_name=permission)
            if p_a:
                clusters.append(dc.cluster)
        return clusters


def get_all_companies_for_operation(operation, permission, user):
    """returns a list of clusters in which the user has certain permission

    :param operation: Operation instance
    :param permission: Onject name
    :param user: django.contrib.auth.models.User instance
    :return a list of cluster in which the user has certain permission
    """
    if user.is_superuser:
        return Company.objects.filter(company_status=1)
    else:
        data_cntx = DataContextPermission.objects.filter(user_role__user=user,
                                                         building=None,
                                                         part_of_building=None)
        companies = []
        for dc in data_cntx:
            p_a = PermissionAsigment.objects.filter(
                role=dc.user_role.role,
                operation=operation,
                object__object_name=permission)
            if p_a:
                if not dc.company:
                    comp_clus = CompanyCluster.objects.filter(
                        company__company_status=1,
                        cluster=dc.cluster)
                    for c_c in comp_clus:
                        companies.append(c_c.company)
                else:
                    companies.append(dc.company)
        return companies


def is_allowed_operation_for_object(operation, permission, user, _object,
                                    obj_type):
    """Checks if the user has permission for a operation for a object

    :param operation: Operation class instance (ver, crear, modificar, etc)
    :param permission: Object class instance ("crear usuarios",
        "modificar roles", "etc")
    :param user: auth.User instance
    :param _object: Cluster, Company, Building or PartOfBuilding instance
    :param obj_type: string, the type of the object
    :return boolean, true if the user has permission, false if the user don't have permission
    """
    #Get the data context(s) in wich the user has a role
    result = {
        'cluster': lambda: get_data_context_cluster(user,
                                                    _object),
        'company': lambda: get_data_context_company(user,
                                                    _object),
        'building': lambda: get_data_context_building(user,
                                                      _object),
        'part': lambda: get_data_context_part(user, _object)
    }[obj_type]()
    if result:
        for data_context in result:
            rol = data_context.user_role.role
            try:
                PermissionAsigment.objects.get(role=rol,
                                               operation=operation,
                                               object=permission)
            except ObjectDoesNotExist:
                continue
            else:
                return True
        else:
            return False
    else:
        return False


def get_data_context_cluster(user, cluster):
    """
    Obtains all the cluster in which the user has permission

    :param user: auth.User instance
    :param cluster: Cluster class instance
    :return: a query set with the cluster the user has permission
    """
    dc = DataContextPermission.objects.filter(user_role__user=user,
                                              cluster=cluster,
                                              company=None,
                                              building=None,
                                              part_of_building=None)
    return dc


def get_data_context_company(user, company):
    """
    Obtains all the companies in which the user has permission

    :param user: auth.User instance
    :param company: Company class instance
    :return: a query set with the companies the user has permission
    """
    dc = DataContextPermission.objects.filter(user_role__user=user,
                                              company=company,
                                              building=None,
                                              part_of_building=None)
    return dc


def get_data_context_building(user, building):
    """
    Obtains all the buildings in which the user has permission

    :param user: auth.User instance
    :param building: Building class instance
    :return: a query set with the buildings the user has permission
    """
    dc = DataContextPermission.objects.filter(user_role__user=user,
                                              building=building,
                                              part_of_building=None)
    return dc


def get_data_context_part(user, part):
    """
    Obtains all the parts in which the user has permission
    :param user: auth.User instance
    :param part: PartOfBuilding class instance
    :return: a query set with the parts of buildings the user has permission
    """
    dc = DataContextPermission.objects.filter(user_role__user=user,
                                              part_of_building=part)
    return dc

def get_buildings_context_for_gaswater(user,builds):
    """Obtains the buildings the user has permission


    :param user: auth.User instance
    :return JSON with the different buildings the active user has permission,
     and a dictionary with the ids and name of buildings
    """
    datacontext = DataContextPermission.objects.filter(user_role__user=user)
    buildings = []
    for dcontext in datacontext:
        try:
            if dcontext.building:
                if dcontext.building.building_status == 1 and dcontext.building in builds:
                    buildings.append(
                        dict(building_pk=dcontext.building.pk,
                             building_name=dcontext.building.building_name))
            elif dcontext.company:
                building_comp = CompanyBuilding.objects.filter(
                    company=dcontext.company,building__in=builds
                ).exclude(
                    building__building_status=0)
                for bc in building_comp:
                    buildings.append(
                        dict(building_pk=bc.building.pk,
                             building_name=bc.building.building_name))
            else:
                clust_comp = ClusterCompany.objects.filter(
                    cluster=dcontext.cluster)
                for cc in clust_comp:
                    building_comp = CompanyBuilding.objects.filter(
                        company=cc.company, building__in=builds
                    ).exclude(
                        building__building_status=0
                    )
                    for bc in building_comp:
                        buildings.append(
                            dict(building_pk=bc.building.pk,
                                 building_name=bc.building.building_name))
        except ObjectDoesNotExist:
            continue

        else:
            buildings = variety.unique_from_array(buildings)
    companies_list = []
    if buildings:
        edificios_pk = [edif['building_pk'] for edif in buildings]
        buil_comp = CompanyBuilding.objects.filter(
            building__pk__in=edificios_pk
        ).values("company__company_name", "company").annotate(Count("company"))
        for company_building in buil_comp:
            clust_comp = ClusterCompany.objects.filter(
                company__pk=company_building['company']
            ).values("cluster__cluster_name")
            company_detail = dict(
                company_name=company_building['company__company_name'],
                cluster_company=clust_comp[0]['cluster__cluster_name'],
                building_count=company_building['company__count'],
                buildings=[])
            comp_buildings = CompanyBuilding.objects.filter(
                company__pk=company_building['company'],
                building__pk__in=edificios_pk).values(
                "building__building_name",
                "building",
                "building__estado__estado_name")
            for com_buil in comp_buildings:
                buil_detail = dict(
                    building_name=com_buil['building__building_name'],
                    building_city=com_buil[
                        'building__estado__estado_name'],
                    building_id=int(com_buil['building']))
                company_detail['buildings'].append(buil_detail)
            companies_list.append(company_detail)
    # return buildings

    return simplejson.dumps(companies_list), buildings




def get_buildings_context(user):
    """Obtains the buildings the user has permission


    :param user: auth.User instance
    :return JSON with the different buildings the active user has permission,
     and a dictionary with the ids and name of buildings
    """
    datacontext = DataContextPermission.objects.filter(user_role__user=user)
    buildings = []
    gw_builds = WaterGasData.objects.values('industrial_equipment__building').distinct()

    for dcontext in datacontext:
        try:
            if dcontext.building:
                ie = {'industrial_equipment__building':dcontext.building.pk}
                if dcontext.building.building_status == 1 and ie not in gw_builds :
                    buildings.append(
                        dict(building_pk=dcontext.building.pk,
                             building_name=dcontext.building.building_name))
                ie = {}
            elif dcontext.company:
                building_comp = CompanyBuilding.objects.filter(
                    company=dcontext.company
                ).exclude(
                    building__building_status=0)
                for bc in building_comp:
                    ie = {'industrial_equipment__building':bc.building.pk}
                    if ie not in gw_builds:
                        buildings.append(
                            dict(building_pk=bc.building.pk,
                                 building_name=bc.building.building_name))
                    ie = {}
            else:
                clust_comp = ClusterCompany.objects.filter(
                    cluster=dcontext.cluster)
                for cc in clust_comp:
                    building_comp = CompanyBuilding.objects.filter(
                        company=cc.company
                    ).exclude(
                        building__building_status=0
                    )
                    for bc in building_comp:
                        ie = {'industrial_equipment__building':bc.building.pk}
                        if ie not in gw_builds:
                            buildings.append(
                                dict(building_pk=bc.building.pk,
                                     building_name=bc.building.building_name))
                        ie = {}
        except ObjectDoesNotExist:
            continue

        else:
            buildings = variety.unique_from_array(buildings)
    companies_list = []
    if buildings:
        edificios_pk = [edif['building_pk'] for edif in buildings]
        buil_comp = CompanyBuilding.objects.filter(
            building__pk__in=edificios_pk
        ).values("company__company_name", "company").annotate(Count("company"))
        for company_building in buil_comp:
            clust_comp = ClusterCompany.objects.filter(
                company__pk=company_building['company']
            ).values("cluster__cluster_name")
            company_detail = dict(
                company_name=company_building['company__company_name'],
                cluster_company=clust_comp[0]['cluster__cluster_name'],
                building_count=company_building['company__count'],
                buildings=[])
            comp_buildings = CompanyBuilding.objects.filter(
                company__pk=company_building['company'],
                building__pk__in=edificios_pk).values(
                "building__building_name",
                "building",
                "building__estado__estado_name")
            for com_buil in comp_buildings:
                buil_detail = dict(
                    building_name=com_buil['building__building_name'],
                    building_city=com_buil[
                        'building__estado__estado_name'],
                    building_id=int(com_buil['building']))
                company_detail['buildings'].append(buil_detail)
            companies_list.append(company_detail)

    return simplejson.dumps(companies_list), buildings


def default_consumerUnit(building):
    """
    Set's the consumer unit

    :param building: Building class instance
    :return: a query set with the consumer unit of the building name Total Edificio
    """
    cu = ConsumerUnit.objects.get(
        building=building,
        electric_device_type__electric_device_type_name="Total Edificio")
    return cu


def save_perm(role, objs_ids, operation):
    """Add a PermissionAsigment for a given role

    :param role: a Role instance
    :param objs_ids: array with he ids of objects
    :param operation: string ["ver", "Crear", "Eliminar"], if neither, defaults UPDATE
    :return boolean, True if the permission is save correctly, False if not
    """
    if operation == "Ver":
        operation = VIEW
    elif operation == "Crear":
        operation = CREATE
    elif operation == "Eliminar":
        operation = DELETE
    else:
        operation = UPDATE

    for obj_id in objs_ids:
        if obj_id != "all" and obj_id != "_":
            try:
                _object = Object.objects.get(pk=int(obj_id))
            except ObjectDoesNotExist:
                mensaje = "El privilegio no existe, por favor seleccione"
                mensaje += " nuevamente la operaci&oacute;n y el privilegio"
                return False, mensaje
            else:
                perm = PermissionAsigment(role=role, operation=operation,
                                          object=_object)
                perm.save()
    return True, "El registro se completó exitosamente"


def validate_role(post):
    """
    Validate the role validating the string

    :param post: a post with the id role or role_desc
    :return: a diccionary name data with the string validated or
    false if it`s not a valid string
    """
    data = {}

    if variety.validate_string(post["role"]):
        data["role"] = post["role"].strip()
    else:
        return False
    if post['role_desc'] != '':
        if variety.validate_string(post["role_desc"]):
            data["role_desc"] = post["role_desc"].strip()
        else:
            return False
    return data


def update_role_privs(role, objs_ids, operation):
    """Update a  list of PermissionAsigments for a given role

    :param role: a Role instance
    :param objs_ids: array with ids of objects
    :param operation: string ["Ver", "Crear", "Eliminar"], if neither, defaults UPDATE
    :return a boolean , True if the rol is modify correctly or false if not
    """
    if operation == "Ver":
        operation = VIEW
    elif operation == "Crear":
        operation = CREATE
    elif operation == "Eliminar":
        operation = DELETE
    else:
        operation = UPDATE

    objs_arr = []
    for obj_id in objs_ids:
        if obj_id != "all" and obj_id != "_":
            try:
                objs_arr.append(Object.objects.get(pk=int(obj_id)))
            except ObjectDoesNotExist:
                mensaje = "El privilegio no existe, por favor seleccione "
                mensaje += "nuevamente la operaci&oacute;n y el privilegio"
                return False, mensaje
    for _object in objs_arr:
        perm = PermissionAsigment(role=role,
                                  operation=operation,
                                  object=_object)
        perm.save()
    return True, "El rol se modificó exitosamente"


def validate_user(post):
    """
     Validates the post info for the add user form
    returns cleaned data if the user is valid
    else, returns false

    :param post: a post dictionary with the info of the user
    :return: a dictionary with the info if its validate correctly,
    a boolean with false if not.
    """
    data = {}
    if variety.validate_string(post['username']):
        data['username'] = post['username'].strip()
    else:
        print "bad username"
        return False

    if variety.validate_string(post['name']):
        if not re.search("\d", post['name']):
            data['name'] = post['name'].strip()
        else:
            print "bad name"
            return False
    else:
        return False

    if variety.validate_string(post['last_name']):
        if not re.search("\d", post['last_name']):
            data['last_name'] = post['last_name'].strip()
        else:
            print "bad last name"
            return False
    else:
        return False

    if post['surname']:
        if variety.validate_string(post['surname']):
            if not re.search("\d", post['surname']):
                data['surname'] = post['surname'].strip()
            else:
                print "bad surname"
                return False
    else:
        data['surname'] = ''

    if variety.is_valid_email(post['mail']):
        data['mail'] = post['mail']
    else:
        print "bad mail"
        return False

    if post['dob']:
        try:
            fnac = post['dob'].split("-")
            data['fnac'] = date(int(fnac[2]), int(fnac[1]), int(fnac[0]))
        except IndexError:
            print "bad dob index"
            return False
        except ValueError:
            print "bad dob value"
            return False
    else:
        return False

    if post['pass1']:
        if post['pass1'] == post['pass2']:
            data['pass'] = post['pass1']
        else:
            print "bad password"
            return False
    else:
        data['pass'] = False

    return data


def add_permission_to_parts(usuario, rol, cluster, company, building):
    """Asigns the role 'rol' for all the parts in the building 'building'

    :param usuario: django UserAuth object
    :param rol: Rol class instance
    :param cluster: Cluster class instance
    :param company: Company class instance
    :param building: Building class instance
    :return a message and the type of the message
    """
    user_role, created = UserRole.objects.get_or_create(user=usuario,
                                                        role=rol)
    # noinspection PyUnusedLocal
    data_context, created = DataContextPermission.objects.get_or_create(
        user_role=user_role,
        cluster=cluster,
        company=company,
        building=building
    )
    message = "El rol, sus permisos y su asignación al edificio, se" \
              " ha guardado correctamente"
    type_ = "n_success"
    return message, type_


def add_permission_to_buildings(usuario, rol, cluster, company_pk):
    """Asigns the role 'rol' for all the buildings in 'company_pk'

    :param usuario: django UserAuth object
    :param rol:  Rol class instance
    :param cluster: Cluster class instance
    :param company_pk: int of the company id
    :return a message and the type o the message
    """
    try:
        company = Company.objects.get(pk=int(company_pk))
    except ObjectDoesNotExist:
        message = "Ha ocurrido un error al seleccionar la empresa, por favor " \
                  "verifique e intente de nuevo"
        type_ = "n_error"
    else:
        user_role, created = UserRole.objects.get_or_create(user=usuario,
                                                            role=rol)
        # noinspection PyUnusedLocal
        data_context, created = DataContextPermission.objects.get_or_create(
            user_role=user_role,
            cluster=cluster,
            company=company
        )

        message = "El rol, sus permisos y su asignación a los edificios" \
                  "de la empresa se han guardado correctamente"
        type_ = "n_success"
    return message, type_


def add_permission_to_companies(usuario, rol, cluster):
    """Asigns the role 'rol' for all the companies in the cluster 'cluster'

    :param usuario: django UserAuth object
    :param rol: Rol class instance
    :param cluster: Cluster class instance
    :return a message and the type of the message
    """
    user_role, created = UserRole.objects.get_or_create(user=usuario,
                                                        role=rol)
    # noinspection PyUnusedLocal
    data_context, created = DataContextPermission.objects.get_or_create(
        user_role=user_role,
        cluster=cluster
    )
    message = "El rol, sus permisos y asignaciones al cluster y " \
              "sus empresas, se ha guardado correctamente"
    type_ = "n_success"

    return message, type_