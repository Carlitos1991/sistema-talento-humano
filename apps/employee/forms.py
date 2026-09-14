from django import forms
from .models import InstitutionalData, BankAccount, Training, WorkExperience, PayrollInfo
from institution.models import AdministrativeUnit
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
            'training_name': forms.TextInput(attrs={
                'class': 'input-field uppercase-input',
                'placeholder': 'EJ: TALLER DE GESTIÓN PÚBLICA'
            }),
            'institution': forms.TextInput(attrs={
                'class': 'input-field uppercase-input',
                'placeholder': 'EJ: INSTITUTO DE CAPACITACIÓN'
            }),
            'hours': forms.NumberInput(attrs={
                'class': 'input-field',
                'placeholder': 'EJ: 40',
                'min': '1'
            }),
            'completion_date': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': 'input-field', 'type': 'date'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['completion_date'].input_formats = ['%Y-%m-%d']


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['bank', 'account_type', 'account_number', 'holder_name']
        widgets = {
            'bank': forms.Select(attrs={'class': 'input-field'}),
            'account_type': forms.Select(attrs={'class': 'input-field'}),
            'account_number': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: 1045892301'
            }),
            'holder_name': forms.TextInput(attrs={
                'class': 'input-field uppercase-input',
                'placeholder': 'NOMBRE COMPLETO DEL TITULAR'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['bank'].queryset = CatalogItem.objects.filter(catalog__code='BANCO', is_active=True).order_by('name')
        self.fields['bank'].empty_label = "— Seleccione banco —"
        self.fields['account_type'].queryset = CatalogItem.objects.filter(catalog__code='ACCOUNT_TYPES', is_active=True).order_by('name')
        self.fields['account_type'].empty_label = "— Seleccione tipo —"

class InstitutionalDataForm(forms.ModelForm):
    class Meta:
        model = InstitutionalData
        fields = [
            'file_number', 'biometric_id', 'entry_date',
            'institutional_email', 'collective_contract',
            'original_dependency', 'original_dependency_reason',
            'observations'
        ]
        widgets = {
            'file_number': forms.TextInput(attrs={'class': 'input-field uppercase-input', 'placeholder': 'EJ: TC-360'}),
            'biometric_id': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'EJ: BIO-123456'}),
            'entry_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'input-field', 'type': 'date'}),
            'institutional_email': forms.EmailInput(
                attrs={'class': 'input-field', 'placeholder': 'usuario@loja.gob.ec'}),
            'collective_contract': forms.CheckboxInput(attrs={'class': 'checkbox-lg'}),
            'original_dependency': forms.Select(attrs={'class': 'input-field'}),
            'original_dependency_reason': forms.Textarea(attrs={'class': 'input-field', 'rows': 2,
                                                                'placeholder': 'Describa el motivo del traslado o asignación original...'}),
            'observations': forms.Textarea(
                attrs={'class': 'input-field', 'rows': 3, 'placeholder': 'Observaciones adicionales...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['entry_date'].input_formats = ['%Y-%m-%d']
        self.fields['original_dependency'].queryset = AdministrativeUnit.objects.filter(is_active=True).order_by('name')
        self.fields['original_dependency'].empty_label = "— Seleccione dependencia original —"


class PayrollInfoForm(forms.ModelForm):
    class Meta:
        model = PayrollInfo
        fields = [
            'monthly_payment', 'reserve_funds', 'immediate_reserve_funds',
            'family_dependents', 'education_dependents',
            'roles_entry_date', 'roles_count'
        ]
        widgets = {
            'monthly_payment': forms.CheckboxInput(attrs={'class': 'checkbox-lg'}),
            'reserve_funds': forms.CheckboxInput(attrs={'class': 'checkbox-lg'}),
            'immediate_reserve_funds': forms.CheckboxInput(attrs={'class': 'checkbox-lg'}),
            'family_dependents': forms.NumberInput(attrs={'class': 'input-field', 'min': '0', 'max': '20'}),
            'education_dependents': forms.NumberInput(attrs={'class': 'input-field', 'min': '0', 'max': '20'}),
            'roles_entry_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'input-field', 'type': 'date'}),
            'roles_count': forms.NumberInput(attrs={'class': 'input-field', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['roles_entry_date'].input_formats = ['%Y-%m-%d']
