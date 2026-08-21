from django import forms
from .models import Account


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['code', 'name', 'type', 'is_active', 'order']

        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1.1.1'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la cuenta'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Automático si se deja en blanco'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'switch-input switch-green'}),
        }