from django import forms
from .models import LaborRegime, ContractType


class LaborRegimeForm(forms.ModelForm):
    class Meta:
        model = LaborRegime
        fields = ['code', 'name', 'description']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control uppercase-input', 'placeholder': 'EJ: LOSEP'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del régimen'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ContractTypeForm(forms.ModelForm):
    class Meta:
        model = ContractType
        fields = ['code', 'name', 'contract_type_category', 'labor_regime']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control uppercase-input'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'contract_type_category': forms.Select(attrs={'class': 'form-control'}),
            'labor_regime': forms.HiddenInput(),  # Se asigna automáticamente por contexto
        }
