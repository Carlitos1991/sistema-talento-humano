# apps/security/forms.py
from django import forms
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from apps.core.forms import BaseFormMixin


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
        label="Usuario",
        widget=forms.TextInput(attrs={'class': 'input-field lowercase-input', 'placeholder': 'ej: juan.perez'})
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={'class': 'input-field', 'placeholder': '******'})
    )
    role = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        label="Rol / Perfil",
        empty_label="-- Seleccione Rol --",
        widget=forms.Select(attrs={'class': 'input-field select2-field'})
    )

    def __init__(self, person_id=None, *args, **kwargs):
        self.person_id = person_id
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso.")
        return username

    def save(self):
        data = self.cleaned_data
        person = Person.objects.get(pk=self.person_id)

        # 1. Crear Usuario
        user = User.objects.create_user(
            username=data['username'],
            password=data['password'],
            email=person.email,
            first_name=person.first_name,
            last_name=person.last_name
        )

        # 2. Asignar Rol
        if data['role']:
            user.groups.add(data['role'])

        # 3. Vincular a la Persona
        person.user = user
        person.save()

        return user
