from django import forms
from .models import SanctionType, Sanction
from employee.models import Employee


class SanctionTypeForm(forms.ModelForm):
    class Meta:
        model = SanctionType
        fields = ['name', 'description', 'is_active', 'requires_attachment']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field', 
                'placeholder': 'Ej. Amonestación Escrita'
            }),
            'description': forms.Textarea(attrs={
                'class': 'input-field', 
                'rows': 3,
                'placeholder': 'Descripción del tipo de sanción'
            }),
            'is_active': forms.CheckboxInput(),
            'requires_attachment': forms.CheckboxInput(),
        }


class SanctionForm(forms.ModelForm):
    class Meta:
        model = Sanction
        fields = [
            'employee', 'sanction_type', 'sanction_number', 'severity',
            'description', 'legal_basis',
            'incident_date', 'sanction_date', 'start_date', 'end_date',
            'days', 'observations', 'attachment_file'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select select2'}),
            'sanction_type': forms.Select(attrs={'class': 'form-select select2'}),
            'sanction_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. SAN-2026-001'
            }),
            'severity': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describa la falta cometida'
            }),
            'legal_basis': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Base legal de la sanción'
            }),
            'incident_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'sanction_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'observations': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones adicionales'
            }),
            'attachment_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter active employees
        self.fields['employee'].queryset = Employee.objects.filter(is_active=True)
        # Filter active sanction types
        self.fields['sanction_type'].queryset = SanctionType.objects.filter(is_active=True)
