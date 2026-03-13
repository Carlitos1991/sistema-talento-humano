from django import forms
from .models import Account


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['code', 'name', 'type', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1000'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Caja'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
