# -*- coding: utf-8 -*-
import re
from datetime import date

from django.db.models.aggregates import Count
from django.core.exceptions import ObjectDoesNotExist

from rbac.models import  PermissionAsigment, UserRole, DataContextPermission,\
    Operation, Object
from c_center.models import ConsumerUnit, Cluster, CompanyBuilding, Company,\
    ClusterCompany, Building
import variety

VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")

def check_roles_permission(object):
    """ Check the roles that have an allowed operation over an object

    object = string, the name of the object
    returns an array with a dict with keys: role and operation

    """
    permissions = PermissionAsigment.objects.filter(object__object_name=object)
    role_operations = []
    for perm in permissions:
        r_o = dict(role=perm.role, operation=perm.operation)
        role_operations.append(r_o)
    return role_operations


def has_permission(user, operation, object):
    """ Checks if a user has certain permission over an object

    user.- django auth user object
    operation.- rbac operation object
    object.- string, the name of the subject

    returns True if the user has permission, False if not

    """
    user_role = UserRole.objects.filter(user=user)
    for u_role in user_role:
        permission = PermissionAsigment.objects.filter(
            object__object_name=object,
            role=u_role.role, operation=operation)
        if permission:
            return True
    return False


def get_all_clusters_for_operation(operation, permission, user):
    """returns a list of clusters in wich the user has certain permission
    operation.- Operation instance
    permission.- Object name
    user.- django.contrib.auth.models.User instance
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
            p_a = PermissionAsigment.objects.filter(role=dc.user_role.role,
                                                    operation=operation,
                                                    object__object_name=permission)
            if p_a:
                clusters.append(dc.cluster)
        return clusters


def get_all_companies_for_operation(operation, permission, user):
    """returns a list of clusters in wich the user has certain permission
    operation.- Operation instance
    permission.- Object name
    user.- django.contrib.auth.models.User instance
    """
    if user.is_superuser:
        return Company.objects.filter(company_status=1)
    else:
        data_cntx = DataContextPermission.objects.filter(user_role__user=user,
                                                         building=None,
                                                         part_of_building=None)
        companies = []
        for dc in data_cntx:
            p_a = PermissionAsigment.objects.filter(role=dc.user_role.role,
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


def is_allowed_operation_for_object(operation, permission, user, object, type):
    """returns true or false if the user has permission over the object or
    not
    operation = Operation class instance (ver, crear, modificar, etc)
    permission = Object class instance ("crear usuarios", "modificar roles",
                                        "etc")
    user = auth.User instance
    object = Cluster, Company, Building or PartOfBuilding instance
    type = string, the type of the object
    """
    #Get the data context(s) in wich the user has a role
    result = {
                 'cluster': lambda: get_data_context_cluster(user,
                                                             object),
                 'company': lambda: get_data_context_company(user,
                                                             object),
                 'building': lambda: get_data_context_building(user,
                                                               object),
                 'part': lambda: get_data_context_part(user, object)
             }[type]()
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
    dc = DataContextPermission.objects.filter(user_role__user=user,
                                              cluster=cluster,
                                              company=None,
                                              building=None,
                                              part_of_building=None)
    return dc


def get_data_context_company(user, company):
    dc = DataContextPermission.objects.filter(user_role__user=user,
                                              company=company,
                                              building=None,
                                              part_of_building=None)
    return dc


def get_data_context_building(user, building):
    dc = DataContextPermission.objects.filter(user_role__user=user,
                                              building=building,
                                              part_of_building=None)
    return dc


def get_data_context_part(user, part):
    dc = DataContextPermission.objects.filter(user_role__user=user,
                                              part_of_building=part)
    return dc


def get_buildings_context(user):
    """Gets and return a dict with the different buildings in the
    DataContextPermission
    for the active user
    todo get ordered to show:
    -company
    --building1
    --building2
    -company2
    --building3
    """
    datacontext = DataContextPermission.objects.filter(user_role__user=user)
    buildings = []

    for dcontext in datacontext:
        try:
            if dcontext.building:
                buildings.append(dict(building_pk=dcontext.building.pk,
                                      building_name=dcontext.building.building_name))
            elif dcontext.company:
                building_comp = CompanyBuilding.objects.filter(
                    company=dcontext.company)
                for bc in building_comp:
                    buildings.append(dict(building_pk=bc.building.pk,
                                          building_name=bc.building.building_name))
            else:
                clust_comp = ClusterCompany.objects.filter(
                    cluster=dcontext.cluster)
                for cc in clust_comp:
                    building_comp = CompanyBuilding.objects.filter(
                        company=cc.company)
                    for bc in building_comp:
                        buildings.append(dict(building_pk=bc.building.pk,
                                              building_name=bc.building.building_name))
        except ObjectDoesNotExist:
            continue

        else:
            buildings = variety.unique_from_array(buildings)
    return buildings


def default_consumerUnit(user, building):
    cu = ConsumerUnit.objects.get(building=building,
                                  electric_device_type__electric_device_type_name="Total Edificio")
    return cu

def save_perm(role, objs_ids, operation):
    """Add a PermissionAsigment for a given role
    role = a Role instance
    objs_ids = array with ids of objects
    operation = string ["ver", "Crear", "Eliminar"], if neither, defaults UPDATE
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
                object = Object.objects.get(pk=int(obj_id))
            except ObjectDoesNotExist:
                mensaje = "El privilegio no existe, por favor seleccione"
                mensaje += " nuevamente la operaci&oacute;n y el privilegio"
                return False, mensaje
            else:
                perm = PermissionAsigment(role=role, operation=operation,
                                          object=object)
                perm.save()
    return True, "El registro se completó exitosamente"

def validate_role(post):
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
    role = a Role instance
    objs_ids = array with ids of objects
    operation = string ["Cer", "Crear", "Eliminar"], if neither, defaults UPDATE
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
    for object in objs_arr:
        perm = PermissionAsigment(role=role, operation=operation, object=object)
        perm.save()
    return True, "El rol se modificó exitosamente"

def validate_user(post):
    """ Validates the post info for the add user form
    returns cleaned data if the user is valid
    else, returns false
    """
    data = {}
    if variety.validate_string(post['username']):
        data['username'] = post['username'].strip()
    else:
        return False

    if variety.validate_string(post['name']):
        if not re.search("\d", post['name']):
            data['name'] = post['name'].strip()
        else:
            return False
    else:
        return False

    if variety.validate_string(post['last_name']):
        if not re.search("\d", post['last_name']):
            data['last_name'] = post['last_name'].strip()
        else:
            return False
    else:
        return False

    if post['surname']:
        if variety.validate_string(post['surname']):
            if not re.search("\d", post['surname']):
                data['surname'] = post['surname'].strip()
            else:
                return False
        else:
            return False
    else:
        data['surname'] = ''

    if variety.is_valid_email(post['mail']):
        data['mail'] = post['mail']
    else:
        return False

    if post['dob']:
        try:
            fnac = post['dob'].split("-")
            data['fnac'] = date(int(fnac[2]), int(fnac[1]), int(fnac[0]))
        except IndexError, ValueError:
            return False
    else:
        return False

    if post['pass1']:
        if post['pass1'] == post['pass2']:
            data['pass'] = post['pass1']
        else:
            return False
    else:
        data['pass'] = False

    return data

def add_permission_to_parts(usuario, rol, cluster, company, building):
    """Asigns the role 'rol' for all the parts in the building 'building'
     usuario = django UserAuth object
     cluster =  Cluster object
     company = Company object
     building = Building object
     only returns messages
    """
    user_role, created = UserRole.objects.get_or_create(user=usuario,
                                                        role=rol)
    data_context, created = DataContextPermission.objects.get_or_create(
        user_role=user_role,
        cluster=cluster,
        company=company,
        building=building
    )
    message = "El rol, sus permisos y su asignación al edificio, se"\
              " ha guardado correctamente"
    type = "n_success"
    return message, type


def add_permission_to_buildings(usuario, rol, cluster, company_pk):
    """Asigns the role 'rol' for all the buildings in 'company_pk'
     usuario = django UserAuth object
     cluster =  Cluster object
     company = Company object
     only returns messages
    """
    try:
        company = Company.objects.get(pk=int(company_pk))
    except ObjectDoesNotExist:
        message = "Ha ocurrido un error al seleccionar la empresa, por favor "\
                  "verifique e intente de nuevo"
        type = "n_error"
    else:
        user_role, created = UserRole.objects.get_or_create(user=usuario,
                                                            role=rol)

        data_context, created = DataContextPermission.objects.get_or_create(
            user_role=user_role,
            cluster=cluster,
            company=company
        )

        message = "El rol, sus permisos y su asignación a los edificios"\
                  "de la empresa se han guardado correctamente"
        type = "n_success"
    return message, type


def add_permission_to_companies(usuario, rol, cluster):
    """Asigns the role 'rol' for all the companies in the cluster 'cluster'
     usuario = django UserAuth object
     cluster =  Cluster object
     company = Company object
     only returns messages
    """
    user_role, created = UserRole.objects.get_or_create(user=usuario,
                                                        role=rol)
    data_context, created = DataContextPermission.objects.get_or_create(
        user_role=user_role,
        cluster=cluster
    )
    message = "El rol, sus permisos y asignaciones al cluster y "\
              "sus empresas, se ha guardado correctamente"
    type = "n_success"

    return message, type