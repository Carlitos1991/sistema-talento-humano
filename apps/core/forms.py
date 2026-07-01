from django import forms
from .models import User, Catalog, CatalogItem, Location, SystemConfiguration


class BaseFormMixin:
    """
    Mixin para inyectar clases CSS modernas a todos los formularios automáticamente.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            # Clase base para todos los inputs
            attrs = {'class': 'form-control'}

            # Si es un Checkbox, usamos una clase distinta si quisieramos
            if isinstance(field.widget, forms.CheckboxInput):
                attrs = {'class': 'form-check-input'}

            # Si es un Select, agregamos soporte para Select2
            elif isinstance(field.widget, forms.Select):
                attrs = {'class': 'form-control select2'}

            field.widget.attrs.update(attrs)


class UserProfileForm(BaseFormMixin, forms.ModelForm):
    photo = forms.ImageField(required=False,
                             widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}))
    document_number = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        # Definimos etiquetas en español si el modelo no las tiene (el tuyo ya las tiene)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si el usuario tiene una Person vinculada, cargar sus datos iniciales
        if self.instance and hasattr(self.instance, 'person') and self.instance.person:
            self.fields['document_number'].initial = self.instance.person.document_number
            self.fields['photo'].initial = self.instance.person.photo

    def save(self, *args, **kwargs):
        # Guardamos el usuario primero
        user = super().save(*args, **kwargs)

        # Ahora manejamos la foto y el document_number de Person si fueron proporcionados
        if self.cleaned_data.get('photo') or self.cleaned_data.get('document_number'):
            from person.models import Person
            person, created = Person.objects.get_or_create(user=user)

            if self.cleaned_data.get('photo'):
                person.photo = self.cleaned_data['photo']

            if self.cleaned_data.get('document_number'):
                person.document_number = self.cleaned_data['document_number']

            person.save()

        return user


class CatalogForm(forms.ModelForm):
    """
    Formulario para creación y edición de Catálogos.
    Mantiene el control total de los campos y validaciones backend.
    """

    class Meta:
        model = Catalog
        fields = ['name', 'code']  # Ajusta según tu modelo real
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'v-model': 'form.name'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'v-model': 'form.code'}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            return code.upper()
        return code

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            return name.upper()
        return name


class CatalogItemForm(forms.ModelForm):
    """
    Formulario para creación y edición de Items.
    Mantiene el control total de los campos y validaciones backend.
    """

    class Meta:
        model = CatalogItem
        fields = ['name', 'code']  # Ajusta según tu modelo real
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'v-model': 'form.name'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'v-model': 'form.code'}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            return code.upper()
        return code

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            return name.upper()
        return name


class LocationForm(forms.ModelForm):
    """
    Formulario para creación y edición de Catálogos.
    Mantiene el control total de los campos y validaciones backend.
    """

    class Meta:
        model = Location
        fields = ['name', 'level', 'parent']  # Ajusta según tu modelo real
        widgets = {
            'name': forms.TextInput(
                attrs={'class': 'input-field', 'v-model': 'form.name', 'placeholder': 'Nombre de la ubicación'}),
            'level': forms.NumberInput(attrs={
                'class': 'input-field', 'v-model': 'form.level', 'min': '1', 'max': '4'}),
            'parent': forms.Select(attrs={'class': 'input-field', 'v-model': 'form.parent'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = Location.objects.filter(is_active=True).order_by('level', 'name')
        self.fields['parent'].empty_label = "--------- (Raíz) ---------"

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            return name.upper()
        return name


class SystemLetterheadForm(forms.ModelForm):
    class Meta:
        model = SystemConfiguration
        fields = ['letterhead']
        widgets = {
            'letterhead': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.png,.jpg,.jpeg,.webp',
            }),
        }


class SystemConfigurationSetupForm(forms.ModelForm):
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
                attrs={'class': 'form-control', 'placeholder': 'Nombre de la institución'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ciudad'}),
            'institution_ruc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RUC institucional'}),
            'institution_address': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Dirección institucional'}),
            'institution_phone': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Teléfono institucional'}),
            'institution_email': forms.EmailInput(
                attrs={'class': 'form-control', 'placeholder': 'Correo institucional'}),
            'max_authority_name': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Nombre de máxima autoridad'}),
            'max_authority_position': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Cargo de máxima autoridad'}),
            'talento_humano_authority_name': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Nombre autoridad TTHH (opcional)'}),
            'talento_humano_authority_position': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Cargo autoridad TTHH (opcional)'}),
            'effective_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': '.png,.jpg,.jpeg,.webp'}),
            'sanction_green_days': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Días semáforo verde'}),
            'sanction_yellow_days': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Días semáforo amarillo'}),
        }
