from django import forms
from .models import VacationPeriod

class PeriodForm(forms.ModelForm):
    class Meta:
        model = VacationPeriod
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 2024-2025'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'name': 'Nombre del Periodo',
            'is_active': 'Periodo Activo',
        }