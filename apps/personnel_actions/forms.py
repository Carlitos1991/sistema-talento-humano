from django import forms
from .models import PersonnelAction, ActionMovement, ActionType
from core.models import User


class PersonnelActionForm(forms.ModelForm):
    class Meta:
        model = PersonnelAction
        fields = ['employee', 'action_type', 'number', 'motivation',
                  'date_issue', 'date_effective', 'explanation']
        widgets = {
            'employee': forms.Select(attrs={'class': 'input-field-select select2'}),
            'action_type': forms.Select(attrs={'class': 'input-field-select select2'}),
            'motivation': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Ej: Nombramiento definitivo'}),
            'date_issue': forms.DateInput(attrs={'type': 'date', 'class': 'input-field'}, format='%Y-%m-%d'),
            'date_effective': forms.DateInput(attrs={'type': 'date', 'class': 'input-field'}, format='%Y-%m-%d'),
            'explanation': forms.Textarea(attrs={'rows': 4, 'class': 'input-textarea',
                                                 'placeholder': 'Descripción detallada de la acción de personal'}),
            'number': forms.TextInput(attrs={'class': 'input-field'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['number'].required = False
        self.fields['date_issue'].input_formats = ['%Y-%m-%d']
        self.fields['date_effective'].input_formats = ['%Y-%m-%d']


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
        fields = ['name', 'code', 'is_active', 'default_authority_1', 'default_authority_2', 'default_reviewer',
                  'default_register']
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
