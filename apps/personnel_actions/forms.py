from django import forms
from .models import PersonnelAction, ActionMovement

class PersonnelActionForm(forms.ModelForm):
    class Meta:
        model = PersonnelAction
        fields = ['employee', 'action_type', 'number',
                  'date_issue', 'date_effective', 'explanation',
                  'authority_1', 'authority_2', 'reviewer','elaboration','register']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select select2'}),
            'action_type': forms.Select(attrs={'class': 'form-select select2'}),
            'date_issue': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_effective': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'explanation': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'authority_1': forms.Select(attrs={'class': 'form-select select2'}),
            'authority_2': forms.Select(attrs={'class': 'form-select select2'}),
            'reviewer': forms.Select(attrs={'class': 'form-select select2'}),
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'decree_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

class ActionMovementForm(forms.ModelForm):
    class Meta:
        model = ActionMovement
        fields = ['previous_remuneration', 'new_remuneration',
                  'new_unit', 'new_position', 'location_text']
        widgets = {
             'new_unit': forms.Select(attrs={'class': 'form-select select2'}),
             'new_position': forms.Select(attrs={'class': 'form-select select2'}),
             'previous_remuneration': forms.NumberInput(attrs={'class': 'form-control'}),
             'new_remuneration': forms.NumberInput(attrs={'class': 'form-control'}),
             'location_text': forms.TextInput(attrs={'class': 'form-control'}),
        }