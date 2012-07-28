from django.db import models
from c_center.models import Cluster, Company, Building, PartOfBuilding

import django.contrib.auth.models

class ExtendedUser(models.Model):
    """ Informacion adicional del usuario

    Almacena la informacion adicional basica de los usuarios del sistema que les permite tener acceso al sistema
    """
    user = models.OneToOneField(django.contrib.auth.models.User, on_delete=models.PROTECT)
    user_activation_key = models.CharField(max_length=128)
    user_first_visit = models.DateTimeField(null=True, blank=True)

    def __unicode__(self):
        return self.user.username + " - " + str(self.user_first_visit)

class UserProfile(models.Model):
    """ Informacion de perfil que no es guardada por django

    Almacena la informacion del perfil de un usuario del sistema.

    """
    SEXO = (
        ('M','Masculino'),
        ('F','Femenino')
        )
    user = models.OneToOneField(django.contrib.auth.models.User, on_delete=models.PROTECT)
    user_profile_surname_mother = models.CharField(max_length=80, blank=True, null=True)
    user_profile_birth_dates = models.DateField()
    user_profile_sex = models.CharField(choices=SEXO, default='M', max_length=1)
    user_profile_image = models.CharField(max_length=256, null=True, blank=True)
    user_profile_office_phone1 = models.CharField(max_length="40", null=True, blank=True)
    user_profile_office_phone2 = models.CharField(max_length="40", null=True, blank=True)
    user_profile_mobile_phone = models.CharField(max_length="40", null=True, blank=True)
    user_profile_idnext = models.CharField(max_length="40", null=True, blank=True)
    user_profile_contact_email = models.EmailField(max_length=254)
    user_profile_contact_phone = models.CharField(max_length="40", null=True, blank=True)

    def __unicode__(self):
        return self.user.first_name + " " + self.user.last_name

class Operation(models.Model):
    """Catalogo de operaciones

    Registro de las diferentes acciones que pueden hacer sobre un objeto
    (view, create, delete, update, otros)

    """
    operation_name = models.CharField(max_length=128)
    operation_description = models.TextField(max_length=256, null=True, blank=True)

    def __unicode__(self):
        return self.operation_name

class Object(models.Model):
    """ Catalogo de objetos

    Contiene el registro de todos los servicios/funciones que se pueden
    realizar en el sistema.

    """
    object_name = models.CharField(max_length=128)
    object_description = models.TextField(max_length=256, null=True, blank=True)
    object_access_point = models.CharField(max_length=256)
    def __unicode__(self):
        return self.object_name

class Role(models.Model):
    """Catalogo de roles

    Almacena los diferentes roles que seran usados en el sistema
    (admin, usuario, agente, entre otros).

    """
    role_name = models.CharField(max_length=128)
    role_description = models.TextField(max_length=256, null=True, blank=True)
    role_importance = models.CharField(max_length=200)
    def __unicode__(self):
        return self.role_name

class PermissionAsigment(models.Model):
    """ Asignacion de Permisos a Roles

    Un rol puede tener diversos permisos para realizar operaciones sobre
    las funciones del sistema

    """
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    operation = models.ForeignKey(Operation, on_delete=models.PROTECT)
    object = models.ForeignKey(Object, on_delete=models.PROTECT)

    def __unicode__(self):
        return self.role.role_name + " - " + self.operation.operation_name \
               + " - " + self.object.object_name

class UserRole(models.Model):
    user = models.ForeignKey(django.contrib.auth.models.User, on_delete=models.PROTECT)
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    def __unicode__(self):
        return self.user.username + " - " + self.role.role_name
    class Meta:
        unique_together = ('user', 'role')

class DataContextPermission(models.Model):
    """ contexto de asignacion de permisos

    Asignacion de contexto de datos sobre los que
    se aplican los permisos asignados a un usuario.

    """
    user_role = models.ForeignKey(UserRole, on_delete=models.PROTECT)
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    building = models.ForeignKey(Building, on_delete=models.PROTECT)
    part_of_building = models.ForeignKey(PartOfBuilding, on_delete=models.PROTECT, blank=True, null=True)

    def __unicode__(self):
        return self.user_role.user.username + " - " + \
               self.part_of_building.building.building_name