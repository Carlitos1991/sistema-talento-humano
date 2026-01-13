from django import forms
from .models import AcademicTitle, BankAccount


class AcademicTitleForm(forms.ModelForm):
    class Meta:
        model = AcademicTitle
        fields = ['education_level', 'title_obtained', 'educational_institution', 'graduation_year', 'senescyt_number',
                  'is_current']
        widgets = {
            'education_level': forms.Select(attrs={'class': 'input-field select2-field'}),
            'title_obtained': forms.TextInput(attrs={'class': 'input-field uppercase-input'}),
            'educational_institution': forms.TextInput(attrs={'class': 'input-field uppercase-input'}),
            'graduation_year': forms.NumberInput(attrs={'class': 'input-field', 'placeholder': 'Ej: 2023'}),
            'senescyt_number': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Opcional'}),
        }


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['bank', 'account_type', 'account_number', 'holder_name']
        widgets = {
            'bank': forms.Select(attrs={'class': 'input-field select2-field'}),
            'account_type': forms.Select(attrs={'class': 'input-field select2-field'}),
            'account_number': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Ej: 1234567890'}),
            'holder_name': forms.TextInput(attrs={'class': 'input-field uppercase-input'}),
        }
