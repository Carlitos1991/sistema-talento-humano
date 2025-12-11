# apps/core/forms.py
from django import forms
from .models import User, Catalog


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
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'cedula', 'avatar']
        # Definimos etiquetas en español si el modelo no las tiene (el tuyo ya las tiene)


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
