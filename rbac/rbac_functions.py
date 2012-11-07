from django.db.models.aggregates import Count
from django.core.exceptions import ObjectDoesNotExist
from rbac.models import  PermissionAsigment, UserRole, DataContextPermission, Operation, Object
from c_center.models import ConsumerUnit

def check_roles_permission(object):
    """ Check the roles that have an allowed operation over an object

    object = string, the name of the object
    returns an array with a dict with keys: role and operation

    """
    permissions=PermissionAsigment.objects.filter(object__object_name=object)
    role_operations=[]
    for perm in permissions:
        r_o=dict(role=perm.role, operation=perm.operation)
        role_operations.append(r_o)
    return role_operations

def has_permission(user, operation, object):
    """ Checks if a user has certain permission over an object

    user.- django auth user object
    operation.- rbac operation object
    object.- string, the name of the subject

    returns True if the user has permission, False if not

    """
    user_role=UserRole.objects.filter(user=user)
    for u_role in user_role:
        permission = PermissionAsigment.objects.filter(object__object_name=object,
            role=u_role.role, operation=operation)
        if permission:
            return True
    return False

def get_allowed_clusters_for_operation(operation, permission, user):
    """returns a list of clusters in wich the user has certain permission
    operation.- Operation instance
    permission.- Object name
    user.- django.contrib.auth.models.User instance
    """
    if user.is_superuser:
        return Cluster.objects.all()
    else:
        data_cntx = DataContextPermission.objects.filter(user_role__user=user, company=None, building=None, part_of_building=None)
        roles_pks = [urol.role for urol in data_cntx]
        clusters = []
        for dc in data_cntx:
            p_a = PermissionAsigment.objects.filter(role__pk__in=roles_pks, operation=operation, object__object_name=permission)
            if p_a:
                clusters.append(dc.cluster)
        return clusters


def is_allowed_operation_for_object(operation, permission, user, object, type):
        """returns true or false if the user has permission over the object or not
        operation = Operation class instance (ver, crear, modificar, etc)
        permission = Object class instance ("crear usuarios", "modificar roles", "etc")
        user = auth.User instance
        object = Cluster, Company, Building or PartOfBuilding instance
        type = string, the type of the object
        """
        #Get the data context(s) in wich the user has a role
        result = {
                     'cluster': lambda : get_data_context_cluster(user, object),
                     'company': lambda : get_data_context_company(user, object),
                     'building': lambda : get_data_context_building(user, object),
                     'part': lambda : get_data_context_part(user, object)
                 }[type]()
        if result:
            for data_context in result:
                rol = data_context.user_role.role
                try:
                    PermissionAsigment.objects.get(role=rol, operation=operation, object=permission)
                except ObjectDoesNotExist:
                    continue
                else:
                    return True
            else:
                return False
        else:
            return False

def get_data_context_cluster(user, cluster):
    dc = DataContextPermission.objects.filter(user_role__user=user, cluster=cluster,
                                    company=None, building=None, part_of_building=None)
    return dc

def get_data_context_company(user, company):
    dc = DataContextPermission.objects.filter(user_role__user=user, company=company,
                                               building=None, part_of_building=None)
    return dc

def get_data_context_building(user, building):
    dc = DataContextPermission.objects.filter(user_role__user=user, building=building,
                                               part_of_building=None)
    return dc

def get_data_context_part(user, part):
    dc = DataContextPermission.objects.filter(user_role__user=user, part_of_building=part)
    return dc


def get_buildings_context(user):
    """Gets and return a dict with the different buildings in the DataContextPermission
    for the active user
    """
    datacontext = DataContextPermission.objects.filter(user_role__user=user).values(
        "building__building_name", "building").annotate(Count("building"))
    buildings=[]
    for building in datacontext:
        buildings.append(dict(building_pk=building['building'],
            building_name=building['building__building_name']))
    return buildings

def default_consumerUnit(user, building):
    context = DataContextPermission.objects.filter(user_role__user=user, building=building)
    context = context[0]
    if not context.part_of_building:
        cu = ConsumerUnit.objects.get(building=building, electric_device_type__electric_device_type_name="Total Edificio")
        return cu
    else:
        cu = ConsumerUnit.objects.get(part_of_building=context.part_of_building)
        return cu