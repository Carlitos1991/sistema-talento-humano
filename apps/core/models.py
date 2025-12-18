# apps/core/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


class BaseModel(models.Model):
    """
    Abstract model for audit fields.
    Code in English, Verbose names in Spanish.
    """
    is_active = models.BooleanField(default=True, verbose_name="Estado")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")

    # User references
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_created",
        null=True, blank=True,
        verbose_name="Creado por"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_updated",
        null=True, blank=True,
        verbose_name="Actualizado por"
    )

    class Meta:
        abstract = True

    def toggle_status(self):
        """
        Alterna el estado de activo a inactivo y viceversa.
        Reemplaza la eliminación física.
        """
        self.is_active = not self.is_active
        self.save()


class User(AbstractUser):
    """
    Modelo de Usuario técnico.
    Se encarga SOLO de la autenticación (username, password, permisos).
    """

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return self.username


# --- MODELOS DE NEGOCIO ---

class Catalog(BaseModel):
    """
    Representa una colección de items, como "Tipos de Documento" o "Géneros".
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre",
        error_messages={'unique': 'Ya existe un catálogo con este nombre.'}
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Código",
        error_messages={'unique': 'Ya existe un catálogo con este código.'}
    )

    class Meta:
        verbose_name = "Catálogo"
        verbose_name_plural = "Catálogos"

    def __str__(self):
        return self.name


class CatalogItem(BaseModel):
    """
    Representa un item individual dentro de un Catálogo.
    """
    catalog = models.ForeignKey(
        Catalog,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Catálogo"
    )
    name = models.CharField(max_length=100, verbose_name="Nombre")
    code = models.CharField(max_length=50, verbose_name="Código")

    class Meta:
        verbose_name = "Item de Catálogo"
        verbose_name_plural = "Items de Catálogo"
        unique_together = ('catalog', 'code')

    def __str__(self):
        return f" {self.name}"


class Location(BaseModel):
    """
    Representa una ubicación jerárquica (País, Provincia, Cantón, Parroquia).
    """
    name = models.CharField(max_length=100, verbose_name="Nombre")
    level = models.PositiveIntegerField(verbose_name="Nivel")  # 1=País, 2=Provincia, etc.

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Ubicación Padre"
    )

    @property
    def level_label(self):
        labels = {
            1: 'País',
            2: 'Provincia',
            3: 'Ciudad',
            4: 'Parroquia'
        }
        return labels.get(self.level, f'Nivel {self.level}')

    class Meta:
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"
        unique_together = ('parent', 'name')

    def __str__(self):
        full_path = [self.name]
        p = self.parent
        while p is not None:
            full_path.append(p.name)
            p = p.parent
        return ' > '.join(full_path[::-1])

    def toggle_status(self):
        """
        Alterna estado propio y propaga el MISMO estado a todos los descendientes.
        """
        new_status = not self.is_active
        self.is_active = new_status
        self.save()

        # Propagación recursiva a los hijos
        self._propagate_status(self, new_status)

    def _propagate_status(self, location, status):
        # Obtenemos los hijos directos
        children = location.children.all()
        for child in children:
            child.is_active = status
            child.save()
            # Llamada recursiva para los hijos de los hijos
            self._propagate_status(child, status)


class SystemConfiguration(BaseModel):
    """
    Configuración del sistema para documentos oficiales.
    Almacena información institucional, autoridades y membretes.
    """
    # Información institucional
    institution_name = models.CharField(
        max_length=255,
        verbose_name="Nombre de la Institución"
    )
    city = models.CharField(
        max_length=100,
        verbose_name="Ciudad",
        default="Loja",
        help_text="Ciudad donde se encuentra la institución"
    )
    institution_ruc = models.CharField(
        max_length=13,
        verbose_name="RUC Institucional",
        blank=True,
        null=True
    )
    institution_address = models.CharField(
        max_length=255,
        verbose_name="Dirección Institucional",
        blank=True,
        null=True
    )
    institution_phone = models.CharField(
        max_length=20,
        verbose_name="Teléfono Institucional",
        blank=True,
        null=True
    )
    institution_email = models.EmailField(
        verbose_name="Email Institucional",
        blank=True,
        null=True
    )

    # Autoridades
    max_authority_name = models.CharField(
        max_length=255,
        verbose_name="Nombre de Máxima Autoridad"
    )
    max_authority_position = models.CharField(
        max_length=255,
        verbose_name="Cargo de Máxima Autoridad"
    )
    talento_humano_authority_name = models.CharField(
        max_length=255,
        verbose_name="Nombre de Autoridad de TTHH",
        blank=True,
        null=True
    )
    talento_humano_authority_position = models.CharField(
        max_length=255,
        verbose_name="Cargo de Autoridad de TTHH",
        blank=True,
        null=True
    )

    # Membretes y Logo
    letterhead = models.ImageField(
        upload_to='letterheads/',
        verbose_name="Hoja Membretada",
        blank=True,
        null=True,
        help_text="Imagen de fondo para todos los documentos PDF (A4, 300 DPI)"
    )
    logo = models.ImageField(
        upload_to='logos/',
        verbose_name="Logo Institucional",
        blank=True,
        null=True,
        help_text="Logo de la institución para reportes"
    )

    # Control de vigencia
    effective_date = models.DateField(
        verbose_name="Fecha de Vigencia",
        help_text="Fecha desde la cual esta configuración es válida"
    )

    class Meta:
        verbose_name = "Configuración del Sistema"
        verbose_name_plural = "Configuraciones del Sistema"
        ordering = ['-effective_date']

    def __str__(self):
        return f"{self.institution_name} - Vigente desde {self.effective_date}"

    @classmethod
    def get_current(cls):
        """
        Obtiene la configuración activa vigente.
        Retorna la configuración más reciente que esté activa.
        """
        from django.utils import timezone
        return cls.objects.filter(
            is_active=True,
            effective_date__lte=timezone.now().date()
        ).first()
