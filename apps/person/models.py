from django.db import models
from django.conf import settings  # IMPORTANTE: Usar settings, no el User model directo
from core.models import BaseModel, CatalogItem, Location
from datetime import date


class Person(models.Model):
    """
    Este modelo representa a una persona en el sistema.
    Una persona puede o no tener una cuenta de usuario asociada.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='person'
                                )

    # --- Identificación ---
    document_type = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, null=True, blank=True,
                                      limit_choices_to={'catalog__code': 'DOCUMENT_TYPES'},
                                      related_name='people_by_document_type')
    document_number = models.CharField(max_length=15, unique=True, null=True, blank=True)

    # --- Nombres y Correo (Datos propios de la persona) ---
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    photo = models.ImageField(upload_to='employee/photos/', null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True, verbose_name="Correo Personal")

    # --- Información Personal Básica ---
    birth_date = models.DateField(null=True, blank=True, verbose_name="Fecha de Nacimiento")
    gender = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, null=True, blank=True,
                               limit_choices_to={'catalog__code': 'GENDERS'},
                               related_name='people_by_gender', verbose_name="Género")
    marital_status = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, null=True, blank=True,
                                       limit_choices_to={'catalog__code': 'MARITAL_STATUSES'},
                                       related_name='people_by_marital_status', verbose_name="Estado Civil")
    blood_type = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, null=True, blank=True,
                                   limit_choices_to={'catalog__code': 'BLOOD_TYPES'},
                                   related_name='people_by_blood_type', verbose_name="Tipo de Sangre")

    # --- Ubicación y Contacto ---
    country = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True,
                                limit_choices_to={'level': 1}, related_name='people_by_country')
    province = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True,
                                 limit_choices_to={'level': 2}, related_name='people_by_province')
    canton = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True,
                               limit_choices_to={'level': 3}, related_name='people_by_canton')
    parish = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True,
                               limit_choices_to={'level': 4}, related_name='people_by_parish')
    address_reference = models.TextField(blank=True, null=True, verbose_name="Dirección")
    phone_number = models.CharField(max_length=20, blank=True, null=True,  verbose_name="Teléfono")

    # --- Información de Salud ---
    has_disability = models.BooleanField(default=False)
    disability_type = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, null=True, blank=True,
                                        limit_choices_to={'catalog__code': 'DISABILITY_TYPES'},
                                        related_name='people_by_disability')
    disability_percentage = models.PositiveIntegerField(null=True, blank=True)
    has_catastrophic_illness = models.BooleanField(default=False)
    catastrophic_illness_description = models.CharField(max_length=255, blank=True, null=True)

    # --- Información de Sustituto ---
    is_substitute = models.BooleanField(default=False)
    substitute_family_member_id = models.CharField(max_length=50, blank=True, null=True)
    substitute_family_member_name = models.CharField(max_length=255, blank=True, null=True)
    substitute_family_member_relationship = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, null=True,
                                                              blank=True,
                                                              limit_choices_to={
                                                                  'catalog__code': 'RELATIONSHIPS'},
                                                              related_name='substitutes_by_relationship')
    substitute_family_member_disability_type = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, null=True,
                                                                 blank=True,
                                                                 limit_choices_to={
                                                                     'catalog__code': 'DISABILITY_TYPES'},
                                                                 related_name='substitutes_by_disability')
    substitute_family_member_disability_percentage = models.PositiveIntegerField(null=True, blank=True)

    # --- Contacto de Emergencia ---
    emergency_contact_name = models.CharField(max_length=255, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact_relationship = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, null=True, blank=True,
                                                       limit_choices_to={'catalog__code': 'RELATIONSHIPS'},
                                                       related_name='emergency_contacts_by_relationship')

    # --- Estado de la Persona ---
    person_status = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, null=True, blank=True,
                                      limit_choices_to={'catalog__code': 'PERSON_STATUS'},
                                      related_name='people_by_status',
                                      verbose_name='Estado')

    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Persona"
        verbose_name_plural = "Personas"
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def location_text(self):
        """Retorna la ubicación más específica disponible string"""
        locs = [self.parish, self.canton, self.province, self.country]
        for loc in locs:
            if loc: return loc.name
        return "Sin ubicación"

    @property
    def age(self):
        """
        Calcula la edad de la persona a partir de su fecha de nacimiento.
        """
        if self.birth_date:
            today = date.today()
            return today.year - self.birth_date.year - (
                    (today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        return None
