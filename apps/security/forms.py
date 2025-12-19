# apps/security/forms.py
from django import forms
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from apps.core.forms import BaseFormMixin
from apps.core.models import User
from apps.person.models import Person


class RoleForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field uppercase-input',
                'placeholder': 'Ej: ANALISTA_TTHH'
            })
        }
        labels = {'name': 'Nombre del Rol'}

    def get_grouped_permissions(self):
        """
        Organiza los permisos por 'Aplicación' o 'Módulo' para pintar la tabla.
        Retorna un diccionario: { 'Nombre Módulo': [ {modelo: 'Persona', perms: {view, add, change, delete}} ] }
        """
        # 1. Definimos qué apps queremos gestionar (para no traer basura de Django interno)
        # Ajusta esto a los nombres reales de tus apps en settings
        target_apps = {
            'person': 'Gestión de Personal',
            'core': 'Sistema y Usuarios',  # Aquí están User, Catalog, Location
            'auth': 'Seguridad (Roles)',  # Aquí está el modelo Group
        }

        grouped_data = {}

        for app_label, verbose_name in target_apps.items():
            # Obtener ContentTypes de esa app
            content_types = ContentType.objects.filter(app_label=app_label)

            module_models = []

            for ct in content_types:
                # Obtener permisos para este modelo
                perms = Permission.objects.filter(content_type=ct)
                if not perms.exists():
                    continue

                # Estructura para la fila de la tabla
                model_data = {
                    'name': ct.model_class()._meta.verbose_name_plural.title(),
                    'perms': {
                        'view': perms.filter(codename__startswith='view_').first(),
                        'add': perms.filter(codename__startswith='add_').first(),
                        'change': perms.filter(codename__startswith='change_').first(),
                        'delete': perms.filter(codename__startswith='delete_').first(),
                    }
                }
                module_models.append(model_data)

            if module_models:
                grouped_data[verbose_name] = module_models

        return grouped_data


class CredentialCreationForm(BaseFormMixin, forms.Form):
    username = forms.CharField(
        label="Nombre de Usuario",
        widget=forms.TextInput(attrs={
            'class': 'input-field lowercase-input',
            'placeholder': 'ej: juan.perez',
            'autocomplete': 'off',
            'style': 'display: block; width: 100%;'  # FORZAR ESTILO EN LÍNEA POR SI ACASO
        }),
        error_messages={'required': 'El nombre de usuario es obligatorio.'}
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'input-field',
            'placeholder': '******'
        }),
        error_messages={'required': 'La contraseña es obligatoria.'}
    )
    confirm_password = forms.CharField(
        label="Repetir Contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'input-field',
            'placeholder': '******'
        }),
        error_messages={'required': 'Debes confirmar la contraseña.'}
    )
    role = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        label="Rol / Perfil",
        empty_label="-- Seleccione Rol --",
        widget=forms.Select(attrs={'class': 'input-field select2-field'}),
        error_messages={'required': 'Debes seleccionar un rol.'}
    )
    is_active = forms.BooleanField(
        label="Usuario Activo",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    is_staff = forms.BooleanField(
        label="Acceso al Admin",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, person_id=None, *args, **kwargs):
        self.person_id = person_id
        super().__init__(*args, **kwargs)

        # Opcional: Si es edición y el usuario ya existe, poblar datos (lo haremos después si es necesario)

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        # Validar si existe (solo si estamos creando uno nuevo)
        # Nota: Si es update, la validación cambia. Por ahora asumimos creación.
        if not self.person_id:  # Caso raro sin persona
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("Este nombre de usuario ya está en uso.")
        else:
            # Verificar si OTRO usuario ya tiene este username
            person = Person.objects.get(pk=self.person_id)
            if person.user and person.user.username == username:
                return username  # Es el mismo usuario, todo bien

            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("Este nombre de usuario ya está en uso.")

        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Las contraseñas no coinciden.")

        return cleaned_data

    def save(self):
        data = self.cleaned_data
        person = Person.objects.get(pk=self.person_id)

        # Lógica Upsert (Crear o Actualizar)
        if person.user:
            user = person.user
            user.username = data['username']
            if data['password']:  # Solo cambiamos si escribió algo
                user.set_password(data['password'])
            user.is_active = data['is_active']
            user.is_staff = data['is_staff']
            user.email = person.email  # Sincronizar email
            user.save()

            # Actualizar grupos
            user.groups.clear()  # Limpiamos anteriores (regla de negocio simple: un solo rol principal)
            if data['role']:
                user.groups.add(data['role'])
        else:
            # Crear Nuevo
            user = User.objects.create_user(
                username=data['username'],
                password=data['password'],
                email=person.email,
                first_name=person.first_name,
                last_name=person.last_name,
                is_active=data['is_active'],
                is_staff=data['is_staff']
            )
            if data['role']:
                user.groups.add(data['role'])

            person.user = user
            person.save()

        return user
