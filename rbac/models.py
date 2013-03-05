from django.db import models
from c_center.models import Cluster, Company, Building, PartOfBuilding

import django.contrib.auth.models

class ExtendedUser(models.Model):
    """ Informacion adicional del usuario

    Almacena la informacion adicional basica de los usuarios del sistema que
    les permite tener acceso al sistema
    """
    user = models.OneToOneField(django.contrib.auth.models.User,
                                on_delete=models.PROTECT)
    user_activation_key = models.CharField(max_length=128)
    user_first_visit = models.DateTimeField(null=True, blank=True)

    def __unicode__(self):
        return self.user.username + " - " + str(self.user_first_visit)


class UserProfile(models.Model):
    """ Informacion de perfil que no es guardada por django

    Almacena la informacion del perfil de un usuario del sistema.

    """
    SEXO = (
        ('M', 'Masculino'),
        ('F', 'Femenino')
        )
    user = models.OneToOneField(django.contrib.auth.models.User,
                                on_delete=models.PROTECT)
    user_profile_surname_mother = models.CharField(max_length=80, blank=True,
                                                   null=True)
    user_profile_birth_dates = models.DateField()
    user_profile_sex = models.CharField(choices=SEXO, default='M', max_length=1)
    user_profile_image = models.CharField(max_length=256, null=True, blank=True)
    user_profile_office_phone1 = models.CharField(max_length="40", null=True,
                                                  blank=True)
    user_profile_office_phone2 = models.CharField(max_length="40", null=True,
                                                  blank=True)
    user_profile_mobile_phone = models.CharField(max_length="40", null=True,
                                                 blank=True)
    user_profile_idnext = models.CharField(max_length="40", null=True,
                                           blank=True)
    user_profile_contact_email = models.EmailField(max_length=254)
    user_profile_contact_phone = models.CharField(max_length="40", null=True,
                                                  blank=True)

    def __unicode__(self):
        return self.user.username + "-" + self.user.first_name + " " + self\
        .user.last_name


class Operation(models.Model):
    """Catalogo de operaciones

    Registro de las diferentes acciones que pueden hacer sobre un objeto
    (view, create, delete, update, otros)

    """
    operation_name = models.CharField(max_length=128)
    operation_description = models.TextField(max_length=256, null=True,
                                             blank=True)

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
    status = models.BooleanField(default=True)

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
        return self.role.role_name + " - " + self.operation.operation_name\
               + " - " + self.object.object_name


class UserRole(models.Model):
    user = models.ForeignKey(django.contrib.auth.models.User,
                             on_delete=models.PROTECT)
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    status = models.BooleanField(default=True)

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
    company = models.ForeignKey(Company, on_delete=models.PROTECT, blank=True,
                                null=True, default=None)
    building = models.ForeignKey(Building, on_delete=models.PROTECT, blank=True,
                                 null=True, default=None)
    part_of_building = models.ForeignKey(PartOfBuilding,
                                         on_delete=models.PROTECT, blank=True,
                                         null=True, default=None)

    def __unicode__(self):
        s = self.user_role.user.username
        if self.cluster:
            s += " - " + self.cluster.cluster_name
        if self.company:
            s += " - " + self.company.company_name
        if self.building:
            s += " - " + self.building.building_name
        if self.part_of_building:
            s += " - " + self.part_of_building.part_of_building_name
        return  s

# ! ! ! NOTA: Los siguientes modelos solo son de referencia para el llenado
# de formularios,
# para gestion de permisos se usaran los modelos especificados originalmente
# (arriba de esta
# nota)

class Group(models.Model):
    """ Agrupacion de objetos de permisos
    almacena las categorias en que se agrupan logicamente los objetos sobre
    los que se
    aplicaran las operaciones. Ejemplo: Reportes, Usuarios y permisos, Empresas
    """
    group_name = models.CharField(max_length=256)

    def __unicode__(self):
        return self.group_name


class GroupObject(models.Model):
    """Agrupacion de objetos
    almacena la relacion entre categorias y los objetos sobre los que se
    aplicaran las
    operaciones. Ejemplo: Reportes-kwh, Usuarios y permisos-asignacion de roles,
    Empresas - alta edificios
    """
    object = models.ForeignKey(Object, on_delete=models.PROTECT)
    group = models.ForeignKey(Group, on_delete=models.PROTECT)

    def __unicode__(self):
        return self.object.object_name + " - " + self.group.group_name

    class Meta:
        unique_together = ('object', 'group')


class OperationForGroup(models.Model):
    """Agrupacion de objetos por grupo
    Almacena la relacion de la(s) operacion(es) que pueden aplicar para
    cierto grupo.
    Ejemplo: Reportes-Lectura, Edificios-Lectura, Edificios-Crear,
    Edificios-Actualizar
    """
    operation = models.ForeignKey(Operation, on_delete=models.PROTECT)
    group = models.ForeignKey(Group, on_delete=models.PROTECT)

    def __unicode__(self):
        return self.operation.operation_name + " - " + self.group.group_name

    class Meta:
        unique_together = ('operation', 'group')


class OperationForGroupObjects(models.Model):
    """

    Agrupa los tipos de operaciones que se pueden realizar
    para cada objeto

    """
    operation = models.ForeignKey(Operation, on_delete=models.PROTECT)
    group_object = models.ForeignKey(GroupObject, on_delete=models.PROTECT)

    def __unicode__(self):
        return self.operation.operation_name + " - " + \
               self.group_object.object.object_name

    class Meta:
        unique_together = ('operation', 'group_object')


class MenuCategs(models.Model):
    categ_name = models.CharField(max_length=32)
    main = models.BooleanField(default=False)
    categ_access_point = models.CharField(max_length=256, blank=True, null=True)
    added_class = models.CharField(max_length=64, blank=True, null=True)
    order = models.IntegerField()

    def __unicode__(self):
        return self.categ_name


class MenuHierarchy(models.Model):
    parent_cat = models.ForeignKey(MenuCategs,
        related_name="parent_cat_composite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        default=None)
    child_cat = models.ForeignKey(MenuCategs,
        related_name="parent_cat_leaf",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        default=None)

    def __unicode__(self):
        s = ""
        t = ""
        if self.parent_cat:
            s = self.parent_cat.categ_name
        if self.child_cat:
            t = self.child_cat.categ_name
        return s + " > " + t