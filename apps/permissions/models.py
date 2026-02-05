import datetime

from django.db import models
from employee.models import Employee
from core.models import CatalogItem


class TypeOfPermit(models.Model):
    type_of_permit = models.CharField(verbose_name='Tipo de permiso', max_length=100)
    is_active = models.BooleanField(verbose_name='Estado', default=True)
    parent_id = models.IntegerField(verbose_name='Dependiente de: *', blank=True, null=True, default=0)
    justifying = models.BooleanField(verbose_name='Necesita justificar?', default=True)
    discount = models.BooleanField(verbose_name='Descuento a vacaciones?', default=False)
    unexpected = models.BooleanField(verbose_name='Adjuntar PDF?', default=False)

    class Meta:
        ordering = ['type_of_permit']
        verbose_name = 'Tipo de permiso'
        verbose_name_plural = 'Tipos de permiso'

    def __str__(self):
        return u'{0}'.format(self.type_of_permit)

    def __unicode__(self):
        return u'{0}'.format(self.type_of_permit)


class Permission(models.Model):
    employee = models.ForeignKey(Employee, verbose_name='Empleado', on_delete=models.PROTECT, blank=True, null=True)
    type_of_permit = models.ForeignKey('TypeOfPermit', verbose_name='Tipo de Permiso', on_delete=models.PROTECT,
                                       blank=True, null=True, limit_choices_to={'status': True, 'parent_id': 0})
    registration_date = models.DateTimeField(verbose_name='Fecha de registro', default=datetime.datetime.now,
                                             blank=True, null=True)
    date_permission_start = models.DateField(verbose_name='Fecha de permiso:*',
                                             blank=True, null=True)
    date_permission_end = models.DateField(verbose_name='Fecha Fin de permiso', blank=True, null=True)
    start_time = models.TimeField(verbose_name='Hora de inicio:*', blank=True, null=True)
    end_time = models.TimeField(verbose_name='Hora de fin', blank=True, null=True)
    num_dias = models.IntegerField(blank=True, null=True, verbose_name='Días:', default=0)
    num_horas = models.IntegerField(blank=True, null=True, verbose_name='Horas:', default=0)
    num_minutos = models.IntegerField(blank=True, null=True, verbose_name='Minutos:', default=0)
    status = models.CharField(verbose_name='Estado', blank=True, null=True, max_length=50)
    registered_by = models.CharField(verbose_name='Registrado por', max_length=100, blank=True, null=True)
    edit_by = models.CharField(verbose_name='Modificado por', max_length=100, blank=True, null=True)
    edit_date = models.DateTimeField(verbose_name='Fecha de registro', blank=True, null=True)
    file_pdf = models.FileField(upload_to='documents/permisos/', verbose_name='Permisos',
                                blank=True, null=True)

    class Meta:
        ordering = ['date_permission_start']
        verbose_name = 'Permiso'
        verbose_name_plural = 'permisos'

    def __str__(self):
        return u'{0}-{1}'.format(self.employee, self.type_of_permit)

    def __unicode__(self):
        return u'{0}-{1}'.format(self.employee, self.type_of_permit)
