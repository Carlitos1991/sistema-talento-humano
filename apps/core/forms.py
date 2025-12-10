# apps/core/forms.py
from django import forms
from .models import User


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