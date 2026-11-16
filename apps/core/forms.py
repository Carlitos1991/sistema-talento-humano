"""
Módulo de Formularios Centrales y Utilidades Base (Core).
Provee el mixin fundamental `BaseFormMixin` para estandarizar clases CSS corporativas
y los formularios de validación del lado del servidor para el módulo Core.
"""
from django import forms
from .models import Catalog, CatalogItem, Location, SystemConfiguration, User


# ==============================================================================
# 1. MIXIN BASE UNIVERSAL PARA FORMULARIOS
# ==============================================================================
class BaseFormMixin:
    """
    Mixin central que inyecta las clases CSS estándar de SIGETH en los widgets
    sin sobrescribir atributos previamente definidos.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing_classes = field.widget.attrs.get('class', '').split()

            if isinstance(field.widget, forms.CheckboxInput):
                if 'form-check-input' not in existing_classes:
                    existing_classes.append('form-check-input')
            elif isinstance(field.widget, forms.Select):
                if 'form-control' not in existing_classes:
                    existing_classes.append('form-control')
                if 'select2' not in existing_classes:
                    existing_classes.append('select2')
            else:
                if 'input-field' not in existing_classes:
                    existing_classes.append('input-field')

            field.widget.attrs['class'] = ' '.join(existing_classes).strip()


# ==============================================================================
# 2. PERFIL DE USUARIO
# ==============================================================================
class UserProfileForm(BaseFormMixin, forms.ModelForm):
    """Formulario para actualizar datos básicos del usuario y su ficha Person."""

    photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
    )
    document_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número de cédula o pasaporte'}),
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo Electrónico',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'person') and self.instance.person:
            self.fields['document_number'].initial = self.instance.person.document_number
            self.fields['photo'].initial = self.instance.person.photo

    def save(self, *args, **kwargs):
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
class CatalogForm(BaseFormMixin, forms.ModelForm):
    """Formulario de validación para cabeceras de catálogos paramétricos."""

    class Meta:
        model = Catalog
        fields = ['name', 'code', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ej: ESTADO CIVIL'}),
            'code': forms.TextInput(attrs={'placeholder': 'Ej: CAT_ESTADO_CIVIL'}),
        }
        labels = {
            'name': 'Nombre del Catálogo',
            'code': 'Código Único',
            'is_active': 'Activo',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['code'].required = False

    def clean_code(self):
        if self.instance and self.instance.pk:
            return self.instance.code
        code = (self.cleaned_data.get('code') or '').strip().upper()
        if not code:
            raise forms.ValidationError('El código es obligatorio.')
        if Catalog.objects.filter(code=code).exists():
            raise forms.ValidationError('Ya existe un catálogo con este código.')
        return code

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip().upper()
        if not name:
            raise forms.ValidationError('El nombre es obligatorio.')
        qs = Catalog.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Ya existe un catálogo con este nombre.')
        return name


class CatalogItemForm(BaseFormMixin, forms.ModelForm):
    """Formulario de validación para elementos individuales dentro de un catálogo."""

    class Meta:
        model = CatalogItem
        fields = ['name', 'code', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ej: SOLTERO/A'}),
            'code': forms.TextInput(attrs={'placeholder': 'Ej: SOL'}),
        }
        labels = {
            'name': 'Nombre del Ítem',
            'code': 'Código',
            'is_active': 'Activo',
        }

    def __init__(self, *args, catalog=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.catalog = catalog or getattr(self.instance, 'catalog', None)
        if self.instance and self.instance.pk:
            self.fields['code'].required = False

    def clean_code(self):
        if self.instance and self.instance.pk:
            return self.instance.code
        code = (self.cleaned_data.get('code') or '').strip().upper()
        if not code:
            raise forms.ValidationError('El código del ítem es obligatorio.')
        if self.catalog and CatalogItem.objects.filter(catalog=self.catalog, code=code).exists():
            raise forms.ValidationError('Ya existe un ítem con este código dentro del catálogo.')
        return code

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip().upper()
        if not name:
            raise forms.ValidationError('El nombre es obligatorio.')
        return name


# ==============================================================================
# 4. UBICACIONES GEOGRÁFICAS (DPA)
# ==============================================================================
class LocationForm(BaseFormMixin, forms.ModelForm):
    """Formulario de validación para jerarquías geográficas (País, Provincia, Ciudad, Parroquia)."""

    class Meta:
        model = Location
        fields = ['name', 'level', 'parent', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Nombre de la localidad geográfica'}),
            'level': forms.NumberInput(attrs={'min': '1', 'max': '4', 'placeholder': 'Nivel (1 a 4)'}),
            'parent': forms.Select(),
        }
        labels = {
            'name': 'Nombre',
            'level': 'Nivel Jerárquico',
            'parent': 'Ubicación Padre',
            'is_active': 'Activo',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = Location.objects.filter(is_active=True).order_by('level', 'name')
        self.fields['parent'].empty_label = '--------- (Nivel Raíz / País) ---------'
        if self.instance and self.instance.pk:
            self.fields['level'].required = False
            self.fields['parent'].required = False

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip().title()
        if not name:
            raise forms.ValidationError('El nombre de la ubicación es obligatorio.')
        return name

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        if self.instance and self.instance.pk:
            level = self.instance.level
            parent = self.instance.parent
            cleaned_data['level'] = level
            cleaned_data['parent'] = parent
        else:
            level = cleaned_data.get('level') or 1
            parent = cleaned_data.get('parent')

        if name:
            qs_dup = Location.objects.filter(name__iexact=name, level=level, parent=parent)
            if self.instance and self.instance.pk:
                qs_dup = qs_dup.exclude(pk=self.instance.pk)
            if qs_dup.exists():
                self.add_error('name', f'Ya existe una ubicación con el nombre "{name}" en este nivel.')
        return cleaned_data


# ==============================================================================
# 5. CONFIGURACIÓN INSTITUCIONAL Y MEMBRETES
# ==============================================================================
class SystemLetterheadForm(BaseFormMixin, forms.ModelForm):
    """Carga de membrete institucional para documentos oficiales y exportaciones PDF."""

    class Meta:
        model = SystemConfiguration
        fields = ['letterhead']
        widgets = {
            'letterhead': forms.FileInput(attrs={'class': 'form-control', 'accept': '.png,.jpg,.jpeg,.webp'}),
        }
        labels = {
            'letterhead': 'Membrete Oficial (Encabezado)',
        }


class SystemConfigurationSetupForm(BaseFormMixin, forms.ModelForm):
    """Formulario de configuración general de datos institucionales y autoridades."""

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
            'institution_name': forms.TextInput(
                attrs={'placeholder': 'Ej: GOBIERNO AUTÓNOMO DESCENTRALIZADO MUNICIPAL'}),
            'city': forms.TextInput(attrs={'placeholder': 'Ej: Loja'}),
            'institution_ruc': forms.TextInput(attrs={'placeholder': '1160000240001'}),
            'institution_address': forms.TextInput(attrs={'placeholder': 'Dirección física principal'}),
            'institution_phone': forms.TextInput(attrs={'placeholder': 'PBX / Conmutador'}),
            'institution_email': forms.EmailInput(attrs={'placeholder': 'contacto@municipiodeloja.gob.ec'}),
            'max_authority_name': forms.TextInput(attrs={'placeholder': 'Nombres y Apellidos de la Máxima Autoridad'}),
            'max_authority_position': forms.TextInput(attrs={'placeholder': 'Ej: ALCALDE DEL CANTÓN'}),
            'talento_humano_authority_name': forms.TextInput(attrs={'placeholder': 'Director/a de Talento Humano'}),
            'talento_humano_authority_position': forms.TextInput(
                attrs={'placeholder': 'Ej: DIRECTOR DE TALENTO HUMANO'}),
            'effective_date': forms.DateInput(attrs={'type': 'date'}),
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': '.png,.jpg,.jpeg,.webp'}),
            'sanction_green_days': forms.NumberInput(attrs={'min': '0', 'placeholder': 'Días límite alerta verde'}),
            'sanction_yellow_days': forms.NumberInput(attrs={'min': '0', 'placeholder': 'Días límite alerta amarilla'}),
        }
