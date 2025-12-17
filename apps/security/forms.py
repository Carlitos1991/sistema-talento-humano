# apps/security/forms.py
from django import forms
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from apps.core.forms import BaseFormMixin
from apps.core.models import User
from apps.person.models import Person  # Importamos desde tu nueva app


class RoleForm(BaseFormMixin, forms.ModelForm):
    """
    Formulario para Roles que genera la MATRIZ DE PERMISOS.
    """

    class Meta:
        model = Group
        fields = ['name']
        labels = {'name': 'Nombre del Rol'}
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ej: ANALISTA_TTHH', 'class': 'form-control uppercase-input'})
        }

    def get_permission_matrix(self):
        """
        Retorna: { 'Nombre Modulo': {'view': perm, 'add': perm, 'change': perm, 'delete': perm} }
        """
        # Apps que queremos gestionar en la matriz
        target_apps = ['core', 'person', 'security']
        content_types = ContentType.objects.filter(app_label__in=target_apps)

        matrix = {}
        for ct in content_types:
            model_name = ct.model_class()._meta.verbose_name_plural.title()
            perms = Permission.objects.filter(content_type=ct)
            if not perms.exists(): continue

            matrix[model_name] = {
                'view': perms.filter(codename__startswith='view_').first(),
                'add': perms.filter(codename__startswith='add_').first(),
                'change': perms.filter(codename__startswith='change_').first(),
                'delete': perms.filter(codename__startswith='delete_').first(),
            }
        return matrix


class CredentialCreationForm(BaseFormMixin, forms.Form):
    """
    Formulario para crear credenciales a una Persona existente.
    """
    username = forms.CharField(
        label="Nombre de Usuario",
        widget=forms.TextInput(attrs={'placeholder': 'Ej: jdoe', 'class': 'lowercase-input'})
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={'placeholder': 'Contraseña segura'})
    )
    role = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        label="Rol / Perfil",
        empty_label="Seleccione un Rol..."
    )

    def __init__(self, person_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if person_id:
            self.person = Person.objects.get(pk=person_id)

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este usuario ya existe.")
        return username

    def save(self):
        data = self.cleaned_data
        # 1. Crear Usuario
        user = User.objects.create_user(
            username=data['username'],
            password=data['password'],
            # Copiamos datos de la persona al usuario por compatibilidad
            email=self.person.email,
            first_name=self.person.first_name,
            last_name=self.person.last_name
        )

        # 2. Asignar Rol
        user.groups.add(data['role'])

        # 3. Vincular a la Persona
        self.person.user = user
        self.person.save()

        return user
