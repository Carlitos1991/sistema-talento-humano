from django import forms
from .models import AcademicTitle, BankAccount, Training, WorkExperience, PayrollInfo


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


class WorkExperienceForm(forms.ModelForm):
    class Meta:
        model = WorkExperience
        fields = ['company_name', 'position', 'start_date', 'end_date', 'is_current', 'responsibilities']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'input-field uppercase-input'}),
            'position': forms.TextInput(attrs={'class': 'input-field uppercase-input'}),
            'start_date': forms.DateInput(attrs={'class': 'input-field', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'input-field', 'type': 'date'}),
            'responsibilities': forms.Textarea(attrs={'class': 'input-field', 'rows': 2}),
        }


class TrainingForm(forms.ModelForm):
    class Meta:
        model = Training
        # Quitamos 'certificate_number' de la lista
        fields = ['training_name', 'institution', 'hours', 'completion_date']
        widgets = {
            'training_name': forms.TextInput(attrs={'class': 'input-field uppercase-input'}),
            'institution': forms.TextInput(attrs={'class': 'input-field uppercase-input'}),
            'hours': forms.NumberInput(attrs={'class': 'input-field'}),
            'completion_date': forms.DateInput(attrs={'class': 'input-field', 'type': 'date'}),
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


class PayrollInfoForm(forms.ModelForm):
    class Meta:
        model = PayrollInfo  # Make sure PayrollInfo is imported at top
        fields = ['monthly_payment', 'reserve_funds', 'family_dependents', 'education_dependents', 'roles_entry_date', 'roles_count']
        widgets = {
             'monthly_payment': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
             'reserve_funds': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
             'family_dependents': forms.NumberInput(attrs={'class': 'input-field', 'min': 0, 'max': 20}),
             'education_dependents': forms.NumberInput(attrs={'class': 'input-field', 'min': 0, 'max': 20}),
             'roles_entry_date': forms.DateInput(attrs={'class': 'input-field', 'type': 'date'}),
             'roles_count': forms.NumberInput(attrs={'class': 'input-field', 'min': 0}),
        }
