"""
Módulo de Formularios Centrales y Utilidades Base (Core).
Provee el mixin fundamental `BaseFormMixin` para estandarizar estilos e inyección de clases CSS
en todos los formularios del sistema, junto con los formularios de perfil, catálogos y configuración.
"""

from django import forms
from .models import User, Catalog, CatalogItem, Location, SystemConfiguration


# ==============================================================================
# 1. MIXIN BASE UNIVERSAL PARA FORMULARIOS
# ==============================================================================
class BaseFormMixin:
    """
    Mixin central que recorre los campos de cualquier ModelForm/Form e inyecta
    las clases CSS corporativas de SIGETH sin destruir atributos previos
    (como placeholders, rows, maxlength, autofocus, autocomplete, etc.).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            # Obtiene las clases ya asignadas en Meta.widgets o en el campo
            existing_classes = field.widget.attrs.get('class', '').split()

            # Caso A: Casillas de verificación (Checkboxes)
            if isinstance(field.widget, forms.CheckboxInput):
                if 'form-check-input' not in existing_classes:
                    existing_classes.append('form-check-input')

            # Caso B: Menús desplegables (Selects convencionales y Select2)
            elif isinstance(field.widget, forms.Select):
                if 'form-control' not in existing_classes:
                    existing_classes.append('form-control')
                if 'select2' not in existing_classes:
                    existing_classes.append('select2')

            # Caso C: Entradas de texto, números, fechas y áreas de texto
            else:
                target_class = 'input-field'
                if target_class not in existing_classes:
                    existing_classes.append(target_class)

            # Reensambla la cadena de clases respetando las anteriores
            field.widget.attrs['class'] = ' '.join(existing_classes).strip()


# ==============================================================================
# 2. PERFIL DE USUARIO
# ==============================================================================
class UserProfileForm(BaseFormMixin, forms.ModelForm):
    """
    Formulario para actualizar datos personales básicos y credenciales de acceso.
    Sincroniza bidireccionalmente la foto y número de documento con el modelo Person.
    """
    photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )
    document_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Número de cédula o pasaporte'
        })
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo Electrónico'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Precarga los valores de la entidad Person si existe el vínculo
        if self.instance and hasattr(self.instance, 'person') and self.instance.person:
            self.fields['document_number'].initial = self.instance.person.document_number
            self.fields['photo'].initial = self.instance.person.photo

    def save(self, *args, **kwargs):
        """Persiste el modelo User y actualiza atómicamente la entidad Person asociada."""
        user = super().save(*args, **kwargs)

        if self.cleaned_data.get('photo') or self.cleaned_data.get('document_number'):
            from person.models import Person
            person, _ = Person.objects.get_or_create(user=user)

            if self.cleaned_data.get('photo'):
                person.photo = self.cleaned_data['photo']

            if self.cleaned_data.get('document_number'):
                person.document_number = self.cleaned_data['document_number']

            person.save()

        return user


# ==============================================================================
# 3. CATÁLOGOS DEL SISTEMA
# ==============================================================================
class CatalogForm(forms.ModelForm):
    """Formulario para la cabecera de catálogos paramétricos del sistema."""

    class Meta:
        model = Catalog
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: ESTADO CIVIL',
                'v-model': 'form.name'
            }),
            'code': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: CAT_ESTADO_CIVIL',
                'v-model': 'form.code'
            }),
        }
        labels = {
            'name': 'Nombre del Catálogo',
            'code': 'Código Único'
        }

    def clean_code(self):
        """Garantiza códigos de catálogo normalizados en mayúsculas."""
        code = self.cleaned_data.get('code')
        return code.strip().upper() if code else code

    def clean_name(self):
        """Garantiza nombres de catálogo legibles en mayúsculas."""
        name = self.cleaned_data.get('name')
        return name.strip().upper() if name else name


class CatalogItemForm(forms.ModelForm):
    """Formulario para los elementos u opciones hijas de un catálogo."""

    class Meta:
        model = CatalogItem
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: SOLTERO/A',
                'v-model': 'form.name'
            }),
            'code': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: SOL',
                'v-model': 'form.code'
            }),
        }
        labels = {
            'name': 'Nombre del Item',
            'code': 'Código'
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        return code.strip().upper() if code else code

    def clean_name(self):
        name = self.cleaned_data.get('name')
        return name.strip().upper() if name else name


# ==============================================================================
# 4. DIVISIONES POLÍTICO-ADMINISTRATIVAS (DPA / UBICACIONES)
# ==============================================================================
class LocationForm(forms.ModelForm):
    """Formulario de estructura geográfica (País, Provincia, Cantón, Parroquia)."""

    class Meta:
        model = Location
        fields = ['name', 'level', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Nombre de la localidad geográfica',
                'v-model': 'form.name'
            }),
            'level': forms.NumberInput(attrs={
                'class': 'input-field',
                'min': '1',
                'max': '4',
                'placeholder': 'Nivel (1 a 4)',
                'v-model': 'form.level'
            }),
            'parent': forms.Select(attrs={
                'class': 'form-control select2',
                'v-model': 'form.parent'
            }),
        }
        labels = {
            'name': 'Nombre',
            'level': 'Nivel Jerárquico',
            'parent': 'Ubicación Padre'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optimiza la lista de padres ordenados por jerarquía
        self.fields['parent'].queryset = Location.objects.filter(is_active=True).order_by('level', 'name')
        self.fields['parent'].empty_label = "--------- (Nivel Raíz / País) ---------"

    def clean_name(self):
        name = self.cleaned_data.get('name')
        return name.strip().upper() if name else name


# ==============================================================================
# 5. CONFIGURACIÓN INSTITUCIONAL Y MEMBRETES
# ==============================================================================
class SystemLetterheadForm(forms.ModelForm):
    """Carga de membrete institucional para reportes impresos y exportaciones PDF."""

    class Meta:
        model = SystemConfiguration
        fields = ['letterhead']
        widgets = {
            'letterhead': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.png,.jpg,.jpeg,.webp',
            }),
        }
        labels = {
            'letterhead': 'Membrete Oficial (Encabezado)'
        }


class SystemConfigurationSetupForm(forms.ModelForm):
    """Formulario integral de configuración de datos generales de la institución."""

    class Meta:
        model = SystemConfiguration
        fields = [
            'institution_name',
            'city',
            'institution_ruc',
            'institution_address',
            'institution_phone',
            'institution_email',
            'max_authority_name',
            'max_authority_position',
            'talento_humano_authority_name',
            'talento_humano_authority_position',
            'sanction_green_days',
            'sanction_yellow_days',
            'effective_date',
            'logo',
        ]
        widgets = {
            'institution_name': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: GOBIERNO AUTÓNOMO DESCENTRALIZADO MUNICIPAL'
            }),
            'city': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: Loja'
            }),
            'institution_ruc': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': '1160000240001'
            }),
            'institution_address': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Dirección física principal'
            }),
            'institution_phone': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'PBX / Conmutador'
            }),
            'institution_email': forms.EmailInput(attrs={
                'class': 'input-field',
                'placeholder': 'contacto@municipiodeloja.gob.ec'
            }),
            'max_authority_name': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Nombres y Apellidos del Alcalde/Máxima Autoridad'
            }),
            'max_authority_position': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: ALCALDE DEL CANTÓN'
            }),
            'talento_humano_authority_name': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Director/a de Talento Humano'
            }),
            'talento_humano_authority_position': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: DIRECTOR DE TALENTO HUMANO'
            }),
            'effective_date': forms.DateInput(attrs={
                'class': 'input-field',
                'type': 'date'
            }),
            'logo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.png,.jpg,.jpeg,.webp'
            }),
            'sanction_green_days': forms.NumberInput(attrs={
                'class': 'input-field',
                'min': '0',
                'placeholder': 'Días límite alerta verde'
            }),
            'sanction_yellow_days': forms.NumberInput(attrs={
                'class': 'input-field',
                'min': '0',
                'placeholder': 'Días límite alerta amarilla'
            }),
        }
