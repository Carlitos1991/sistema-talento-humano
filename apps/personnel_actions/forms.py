from django import forms
from .models import PersonnelAction, ActionMovement, ActionType
from core.models import User


class PersonnelActionForm(forms.ModelForm):
    class Meta:
        model = PersonnelAction
        fields = ['employee', 'action_type', 'number', 'motivation',
                  'date_issue', 'date_effective', 'explanation',
                  'authority_1', 'authority_2', 'reviewer', 'register']
        widgets = {
            'employee': forms.Select(attrs={'class': 'input-field-select select2'}),
            'action_type': forms.Select(attrs={'class': 'input-field-select select2'}),
            'motivation': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Ej: Nombramiento definitivo'}),
            'date_issue': forms.DateInput(attrs={'type': 'date', 'class': 'input-field'}, format='%Y-%m-%d'),
            'date_effective': forms.DateInput(attrs={'type': 'date', 'class': 'input-field'}, format='%Y-%m-%d'),
            'explanation': forms.Textarea(attrs={'rows': 4, 'class': 'input-textarea', 'placeholder': 'Descripción detallada de la acción de personal'}),
            'authority_1': forms.Select(attrs={
                'class': 'input-field-select select2',
                'data-ajax-url': '/personnel_actions/api/users/search/',
                'data-placeholder': 'Buscar usuario...',
                'data-minimum-input-length': '3',
                'style': 'width:100%'
            }),
            'authority_2': forms.Select(attrs={
                'class': 'input-field-select select2',
                'data-ajax-url': '/personnel_actions/api/users/search/',
                'data-placeholder': 'Buscar usuario...',
                'data-minimum-input-length': '3',
                'style': 'width:100%'
            }),
            'reviewer': forms.Select(attrs={
                'class': 'input-field-select select2',
                'data-ajax-url': '/personnel_actions/api/users/search/',
                'data-placeholder': 'Buscar usuario...',
                'data-minimum-input-length': '3',
                'style': 'width:100%'
            }),
            'register': forms.Select(attrs={
                'class': 'input-field-select select2',
                'data-ajax-url': '/personnel_actions/api/users/search/',
                'data-placeholder': 'Buscar usuario...',
                'data-minimum-input-length': '3',
                'style': 'width:100%'
            }),
            'number': forms.TextInput(attrs={'class': 'input-field'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer que el número no sea requerido ya que se genera automáticamente
        self.fields['number'].required = False
        # Asegurar que los campos de fecha usen el formato correcto
        self.fields['date_issue'].input_formats = ['%Y-%m-%d']
        self.fields['date_effective'].input_formats = ['%Y-%m-%d']

        for signer_field in ['authority_1', 'authority_2', 'reviewer', 'register']:
            # Inicialmente no cargar todos los usuarios en el queryset para evitar renders pesados.
            # Si estamos editando y existe un valor, incluir solo ese valor; si viene en POST, incluirlo también.
            data = kwargs.get('data') or getattr(self, 'data', None)
            ids = []
            # Valor preexistente (edición)
            try:
                existing = getattr(self.instance, signer_field)
            except Exception:
                existing = None
            if existing and getattr(existing, 'pk', None):
                ids.append(existing.pk)

            # Si viene un valor por POST, incluirlo también
            if data and data.get(signer_field):
                try:
                    post_id = int(data.get(signer_field))
                    if post_id not in ids:
                        ids.append(post_id)
                except Exception:
                    pass

            if ids:
                self.fields[signer_field].queryset = User.objects.filter(pk__in=ids)
            else:
                self.fields[signer_field].queryset = User.objects.none()

            # Mostrar texto amigable en las opciones (si existen)
            self.fields[signer_field].label_from_instance = (
                lambda user: f"{user.signature_name} - {user.signature_position}" if getattr(user, 'signature_position', None) else (getattr(user, 'signature_name', '') or getattr(user, 'username', ''))
            )


class ActionMovementForm(forms.ModelForm):
    class Meta:
        model = ActionMovement
        fields = ['previous_remuneration', 'new_remuneration',
                  'new_unit', 'new_position', 'new_budget_line', 'location_text']
        widgets = {
            'new_unit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unidad Administrativa Nueva'}),
            'new_position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Puesto Nuevo'}),
            'new_budget_line': forms.Select(attrs={'class': 'form-select select2'}),
            'previous_remuneration': forms.NumberInput(attrs={'class': 'form-control'}),
            'new_remuneration': forms.NumberInput(attrs={'class': 'form-control'}),
            'location_text': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ActionTypeForm(forms.ModelForm):
    class Meta:
        model = ActionType
        fields = ['name', 'code', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'EJ: NOMBRAMIENTO PROVISIONAL'}),
            'code': forms.TextInput(attrs={
                'class': 'form-control uppercase-input',
                'placeholder': 'EJ: NOM-PROV',
                'oninput': 'this.value = this.value.toUpperCase()'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            return code.upper()
        return code
