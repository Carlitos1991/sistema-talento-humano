from django import forms

from core.forms import BaseFormMixin
from core.models import CatalogItem
from institution.models import AdministrativeUnit
from .models import AcademicTitle, BankAccount, Training, WorkExperience, PayrollInfo

from django import forms
from core.models import CatalogItem
from .models import AcademicTitle


class AcademicTitleForm(forms.ModelForm):
    class Meta:
        model = AcademicTitle
        fields = ['education_level', 'title_obtained', 'educational_institution', 'graduation_year',
                  'senescyt_number', ]
        widgets = {
            'title_obtained': forms.TextInput(
                attrs={'class': 'input-field uppercase-input', 'placeholder': 'EJ: INGENIERO EN SISTEMAS'}),
            'educational_institution': forms.TextInput(
                attrs={'class': 'input-field uppercase-input', 'placeholder': 'EJ: UNIVERSIDAD NACIONAL DE LOJA'}),
            'graduation_year': forms.NumberInput(
                attrs={'class': 'input-field', 'placeholder': 'EJ: 2020', 'min': '1950', 'max': '2100'}),
            'senescyt_number': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'EJ: 1005-12-345678'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['education_level'].queryset = CatalogItem.objects.filter(catalog__code='EDUCATION_LEVELS',
                                                                             is_active=True).order_by('name')
        self.fields['education_level'].widget.attrs.update({'class': 'input-field select2-field'})
        self.fields['education_level'].empty_label = "-- Seleccione Nivel --"


class WorkExperienceForm(forms.ModelForm):
    class Meta:
        model = WorkExperience
        fields = ['company_name', 'position', 'start_date', 'end_date', 'is_current', 'responsibilities']
        widgets = {
            'company_name': forms.TextInput(
                attrs={'class': 'input-field uppercase-input', 'placeholder': 'EJ: MUNICIPIO DE LOJA'}),
            'position': forms.TextInput(
                attrs={'class': 'input-field uppercase-input', 'placeholder': 'EJ: ANALISTA ADMINISTRATIVO'}),
            'start_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'input-field', 'type': 'date'}),
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'input-field', 'type': 'date'}),
            'responsibilities': forms.Textarea(
                attrs={'class': 'input-field', 'rows': 2, 'placeholder': 'EJ: TAREAS ADMINISTRATIVAS'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'checkbox-lg'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_date'].input_formats = ['%Y-%m-%d']
        self.fields['end_date'].input_formats = ['%Y-%m-%d']


class TrainingForm(forms.ModelForm):
    class Meta:
        model = Training
        fields = ['training_name', 'institution', 'hours', 'completion_date']
        widgets = {
            'training_name': forms.TextInput(
                attrs={'class': 'input-field uppercase-input', 'placeholder': 'EJ: CURSO DE TALENTO HUMANO'}),
            'institution': forms.TextInput(attrs={'class': 'input-field uppercase-input', 'placeholder': 'EJ: SECAP'}),
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
        fields = ['monthly_payment', 'reserve_funds', 'family_dependents', 'education_dependents', 'roles_entry_date',
                  'roles_count', 'immediate_reserve_funds']
        labels = {
            'monthly_payment': 'Mensualiza Décimos',
            'reserve_funds': 'Fondos de Reserva',
            'family_dependents': 'Hijos dependientes',
            'education_dependents': 'Hijos con discapacidad',
            'roles_entry_date': 'Fecha Ingreso a Roles',
            'roles_count': 'Número de Roles', 'immediate_reserve_funds': 'Derecho a Fondos de Reserva Inmediato'
        }
        widgets = {
            'monthly_payment': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reserve_funds': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'family_dependents': forms.NumberInput(attrs={'class': 'input-field', 'min': 0, 'max': 20}),
            'education_dependents': forms.NumberInput(attrs={'class': 'input-field', 'min': 0, 'max': 20}),
            'roles_entry_date': forms.DateInput(attrs={'class': 'input-field', 'type': 'date'}),
            'roles_count': forms.NumberInput(attrs={'class': 'input-field', 'min': 0}),
            'immediate_reserve_funds': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
