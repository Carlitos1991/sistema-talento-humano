# apps/person/forms.py
from datetime import date

from django import forms
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError

from apps.core.forms import BaseFormMixin
from apps.core.models import User, CatalogItem, Location
from .models import Person


def validar_cedula_ecuatoriana(cedula):
    if not cedula or len(cedula) != 10 or not cedula.isdigit():
        return False
    provincia = int(cedula[0:2])
    if provincia < 1 or provincia > 24:
        return False
    digito_tres = int(cedula[2])
    if digito_tres >= 6:
        return False
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    suma = 0
    for i in range(9):
        valor = int(cedula[i]) * coeficientes[i]
        if valor >= 10: valor -= 9
        suma += valor
    digito_verificador = int(cedula[9])
    residuo = suma % 10
    resultado = 10 - residuo if residuo != 0 else 0
    return resultado == digito_verificador


class PersonForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Person
        fields = '__all__'
        exclude = ['user', 'created_at', 'updated_at']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'address_reference': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['has_disability'].widget.attrs.update({'v-model': 'form.has_disability'})
        self.fields['has_catastrophic_illness'].widget.attrs.update({'v-model': 'form.has_catastrophic_illness'})
        self.fields['is_substitute'].widget.attrs.update({'v-model': 'form.is_substitute'})
        self.fields['birth_date'].input_formats = ['%Y-%m-%d']

        # 1. LOGICA: Preseleccionar "CEDULA" solo al Crear (sin PK)
        if not self.instance.pk:
            try:
                # Buscamos coincidencias en el catálogo DOCUMENT_TYPES (nombre exacto del modelo)
                cedula_type = CatalogItem.objects.filter(
                    catalog__code='DOCUMENT_TYPES',
                    name__icontains='CEDULA'
                ).first()

                if cedula_type:
                    self.fields['document_type'].initial = cedula_type
            except Exception:
                pass  # Fallo silencioso si no existe el catálogo aún

        # 2. LOGICA: Clases CSS y Atributos (Manejo especial para Email)
        for name, field in self.fields.items():
            attrs = {}

            # --- CASO ESPECIAL: EMAIL (Sin mayúsculas) ---
            if name == 'email':
                attrs['class'] = 'input-field'  # Clase limpia (sin uppercase-input)
                attrs['placeholder'] = 'ejemplo@correo.com'

            # --- CASO SELECTS (Para Select2) ---
            elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                attrs['class'] = 'input-field select2-field'

            # --- CASO CHECKBOX ---
            elif isinstance(field.widget, forms.CheckboxInput):
                attrs['class'] = 'form-checkbox'

            # --- RESTO DE CAMPOS (Mayúsculas visuales) ---
            else:
                attrs['class'] = 'input-field uppercase-input'

            # Aplicamos los atributos al widget
            field.widget.attrs.update(attrs)

        # 3. LOGICA: Campos Obligatorios Manuales
        mandatory = [
            'document_type', 'document_number', 'first_name', 'last_name',
            'email', 'birth_date', 'gender', 'marital_status',
            'blood_type', 'country', 'province', 'canton', 'parish', 'address_reference'
        ]
        for field in mandatory:
            if field in self.fields:
                self.fields[field].required = True

        # 4. LOGICA: Cascada de Ubicaciones
        # Inicializar todos los querysets vacíos (incluyendo country)
        self.fields['country'].queryset = Location.objects.filter(level=1, is_active=True).order_by('name')
        self.fields['country'].empty_label = "-- Seleccione --"  # Texto del placeholder
        self.fields['province'].queryset = self.fields['province'].queryset.none()
        self.fields['province'].empty_label = "-- Seleccione --"
        self.fields['canton'].queryset = self.fields['canton'].queryset.none()
        self.fields['canton'].empty_label = "-- Seleccione --"
        self.fields['parish'].queryset = self.fields['parish'].queryset.none()
        self.fields['parish'].empty_label = "-- Seleccione --"

        # Cargar Provincia según País
        if 'country' in self.data:
            try:
                country_id = int(self.data.get('country'))
                self.fields['province'].queryset = Location.objects.filter(parent_id=country_id).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.country:
            self.fields['province'].queryset = self.instance.country.children.order_by('name')

        # Cargar Cantón según Provincia
        if 'province' in self.data:
            try:
                province_id = int(self.data.get('province'))
                self.fields['canton'].queryset = Location.objects.filter(parent_id=province_id).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.province:
            self.fields['canton'].queryset = self.instance.province.children.order_by('name')

        # Cargar Parroquia según Cantón
        if 'canton' in self.data:
            try:
                canton_id = int(self.data.get('canton'))
                self.fields['parish'].queryset = Location.objects.filter(parent_id=canton_id).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.canton:
            self.fields['parish'].queryset = self.instance.canton.children.order_by('name')

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            if hasattr(photo, 'size'):
                if photo.size > 1 * 1024 * 1024:  # 1MB
                    raise ValidationError("La imagen es muy pesada. Máximo 1MB.")
        return photo

    def clean_birth_date(self):
        dob = self.cleaned_data.get('birth_date')
        if dob:
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 16:
                raise ValidationError("La persona debe ser mayor de 16 años.")
            if age > 120:
                raise ValidationError("La fecha de nacimiento no es válida. La persona tendría más de 120 años.")
        return dob

    def clean(self):
        cleaned_data = super().clean()

        # 1. Conversión a Mayúsculas (EXCLUYENDO EMAIL)
        for field, val in cleaned_data.items():
            # Si es texto y NO es email, convertir a mayúsculas
            if isinstance(val, str) and field != 'email':
                cleaned_data[field] = val.upper()

        # 2. Conversión forzosa a Minúsculas para Email
        email = cleaned_data.get('email')
        if email:
            cleaned_data['email'] = email.lower()

        # 3. Validación de Cédula
        doc_type = cleaned_data.get('document_type')
        doc_num = cleaned_data.get('document_number')

        if doc_type and doc_num:
            type_name = str(doc_type).upper()

            if 'CEDULA' in type_name or 'CÉDULA' in type_name:
                if not doc_num.isdigit():
                    self.add_error('document_number', "La cédula solo debe contener números.")
                if len(doc_num) != 10:
                    self.add_error('document_number', "La cédula debe tener 10 dígitos.")
                if not validar_cedula_ecuatoriana(doc_num):
                    self.add_error('document_number', "El número de cédula no es válido.")

                # Unicidad (excluyendo al propio usuario si es edición)
                qs = Person.objects.filter(document_number=doc_num)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    self.add_error('document_number', "Ya existe una persona con esta cédula.")

        return cleaned_data


class UserAccountForm(forms.Form):
    username = forms.CharField(
        label="Nombre de Usuario",
        widget=forms.TextInput(attrs={'class': 'input-field lowercase-input', 'autocomplete': 'off'})
    )
    # Password es opcional en edición, obligatorio en creación (lo manejamos en __init__)
    password = forms.CharField(
        label="Contraseña",
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'input-field', 'autocomplete': 'new-password'})
    )
    is_active = forms.BooleanField(
        label="Acceso al Sistema Activo",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )
    # Si usas Grupos/Roles de Django
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        label="Roles / Perfiles",
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'input-field select2-field'})
    )

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)  # El objeto User (si existe)
        super().__init__(*args, **kwargs)

        if self.instance:
            self.fields['username'].initial = self.instance.username
            self.fields['username'].widget.attrs['readonly'] = True
            self.fields['username'].widget.attrs['class'] += ' bg-gray-100 cursor-not-allowed'
            self.fields['is_active'].initial = self.instance.is_active
            self.fields['groups'].initial = self.instance.groups.all()

            # CAMBIO: Placeholder de asteriscos para indicar que ya existe pass
            self.fields['password'].widget.attrs['placeholder'] = '******'
            self.fields['password'].help_text = "Deje en blanco para mantener la contraseña actual."
        else:
            # MODO CREACIÓN
            self.fields['password'].required = True
            self.fields['is_active'].initial = True
            # En creación no ponemos placeholder o ponemos uno genérico
            self.fields['password'].widget.attrs['placeholder'] = 'Ingrese contraseña segura'

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        # Validar unicidad solo si es creación
        if not self.instance:
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("Este nombre de usuario ya está en uso.")
        return username

    def save(self, person):
        data = self.cleaned_data

        if self.instance:
            # Actualizar
            user = self.instance
            user.is_active = data['is_active']
            if data['password']:
                user.set_password(data['password'])
            user.save()
        else:
            # Crear
            user = User.objects.create_user(
                username=data['username'],
                password=data['password'],
                email=person.email  # Vinculamos el email de la persona
            )
            user.is_active = data['is_active']
            user.save()
            # Vincular a la persona
            person.user = user
            person.save()

        # Asignar grupos
        if 'groups' in data:
            user.groups.set(data['groups'])

        return user
