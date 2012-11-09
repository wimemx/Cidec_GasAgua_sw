__author__ = 'wime'
from django.shortcuts import HttpResponse, get_object_or_404
from django.utils import simplejson

from c_center.models import Cluster, ClusterCompany, Company, CompanyBuilding, Building, PartOfBuilding
from rbac.models import PermissionAsigment, DataContextPermission, Role, UserRole, Object, Operation

from rbac.rbac_functions import is_allowed_operation_for_object


VIEW = Operation.objects.get(operation_name="Ver")
CREATE = Operation.objects.get(operation_name="Crear")
DELETE = Operation.objects.get(operation_name="Eliminar")
UPDATE = Operation.objects.get(operation_name="Modificar")

def get_clusters_for_operation(permission, operation, user):
    """Obtains a queryset for all the clusters that exists in a datacontext for a user,
     if the user is super_user returns all active clusters
     returns a tuple containing the queryset, and a boolean, indicating if returns all the objects

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
