import re
import unicodedata
from decimal import Decimal
from django import forms

from core.models import User
from employee.models import Employee
from .models import MedicalLicense, MedicalLicenseType, LicenseSubstitute, LicenseSchedule, LicenseTypeRequirement
from personnel_actions.forms import PersonnelActionForm
from personnel_actions.models import ActionType
from .services import render_license_action_text


class MedicalLicenseForm(forms.ModelForm):
    has_substitute = forms.BooleanField(
        required=False,
        label="¿Requiere Funcionario Sustituto?",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    substitute = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=False,
        label="Funcionario Sustituto",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    has_reduced_hours = forms.BooleanField(
        required=False,
        label="¿Aplica Reducción de Jornada?",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    reduced_hours = forms.DecimalField(
        required=False,
        max_digits=4,
        decimal_places=2,
        label="Horas de Reducción Diaria",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'})
    )

    personnel_action_number = forms.CharField(
        required=False,
        label="Nº Borrador Acción de Personal",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Autogenerado o Manual'})
    )

    class Meta:
        model = MedicalLicense
        fields = [
            'employee',
            'license_type',
            'start_date',
            'end_date',
            'cie10_code',
            'diagnosis',
            'issuing_entity',
            'doctor_name',
            'medical_certificate_number',
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'license_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cie10_code': forms.TextInput(attrs={'class': 'form-control'}),
            'diagnosis': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'issuing_entity': forms.TextInput(attrs={'class': 'form-control'}),
            'doctor_name': forms.TextInput(attrs={'class': 'form-control'}),
            'medical_certificate_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError("La fecha de fin no puede ser anterior a la fecha de inicio.")

        if cleaned_data.get('has_substitute') and not cleaned_data.get('substitute'):
            self.add_error('substitute', 'Debe seleccionar un funcionario sustituto.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=commit)

        if commit:
            if self.cleaned_data.get('has_substitute') and self.cleaned_data.get('substitute'):
                LicenseSubstitute.objects.update_or_create(
                    license=instance,
                    defaults={
                        'substitute_employee': self.cleaned_data.get('substitute'),
                        'start_date': instance.start_date,
                        'end_date': instance.end_date,
                    }
                )
            if self.cleaned_data.get('has_reduced_hours'):
                LicenseSchedule.objects.update_or_create(
                    license=instance,
                    defaults={
                        'modality': LicenseSchedule.MODALITY_REDUCTION_HOURS,
                        'reduction_hours': self.cleaned_data.get('reduced_hours') or Decimal("2.00")
                    }
                )
        return instance


class LicensePersonnelActionForm(PersonnelActionForm):
    date_from = forms.DateField(
        label='Fecha desde',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'input-field'}, format='%Y-%m-%d')
    )
    date_to = forms.DateField(
        label='Fecha hasta (dejar vacía si es indefinida)',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'input-field'}, format='%Y-%m-%d')
    )
    schedule_mode = forms.ChoiceField(
        label='Modalidad de jornada',
        required=False,
        choices=[
            ('FULL_DAY', 'Una sola jornada completa'),
            ('ENTRY_DELAY', 'Entrada 2 horas después'),
            ('EXIT_EARLY', 'Salida 2 horas antes'),
            ('LUNCH', 'Permiso en horario de almuerzo'),
            ('CUSTOM', 'Horario personalizado'),
        ],
        widget=forms.Select(attrs={'class': 'input-field'})
    )
    custom_entry_time = forms.TimeField(
        label='Hora desde', required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'input-field'})
    )
    custom_exit_time = forms.TimeField(
        label='Hora hasta', required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'input-field'})
    )

    def __init__(self, *args, license_instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.license_instance = license_instance
        if license_instance:
            self.fields['employee'].queryset = Employee.objects.filter(
                pk=license_instance.employee_id
            ).select_related('person')
            self.fields['action_type'].queryset = ActionType.objects.filter(
                code='LICENCIA', is_active=True
            )
        self.fields['employee'].disabled = True
        self.fields['action_type'].disabled = True
        if license_instance:
            self.initial.setdefault('date_from', license_instance.start_date)
            self.initial.setdefault('date_to', license_instance.end_date)
            if not self.instance.pk or not self.instance.explanation:
                description = (license_instance.license_type.description or '').strip()
                self.initial.setdefault(
                    'explanation',
                    render_license_action_text(
                        description, license_instance.start_date, license_instance.end_date
                    )
                    or f'Licencia médica #{license_instance.pk}: {license_instance.diagnosis}'
                )
            if not self.instance.pk or not self.instance.motivation:
                self.initial.setdefault(
                    'motivation',
                    getattr(license_instance.reception, 'supporting_document', '') or ''
                )
            adjustment = getattr(license_instance, 'schedule_adjustment', None)
            if adjustment:
                self.initial.setdefault('schedule_mode', 'CUSTOM' if adjustment.custom_entry_time else 'ENTRY_DELAY')
                self.initial.setdefault('custom_entry_time', adjustment.custom_entry_time)
                self.initial.setdefault('custom_exit_time', adjustment.custom_exit_time)

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        if date_from and date_to and date_to < date_from:
            self.add_error('date_to', 'La fecha hasta no puede ser anterior a la fecha desde.')
        mode = cleaned_data.get('schedule_mode')
        if mode == 'CUSTOM' and not (cleaned_data.get('custom_entry_time') and cleaned_data.get('custom_exit_time')):
            self.add_error('custom_entry_time', 'Defina las horas de la jornada personalizada.')
        return cleaned_data


class LicenseTypeRequirementForm(forms.ModelForm):
    """Formulario para creación rápida de anexos/requisitos por AJAX."""

    class Meta:
        model = LicenseTypeRequirement
        fields = ['name', 'is_mandatory']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field form-control',
                'placeholder': 'Ej: Certificado Médico, Copia de Cédula',
                'id': 'id_req_name',
                'required': True
            }),
            'is_mandatory': forms.CheckboxInput(attrs={'class': 'switch-input switch-blue', 'id': 'id_req_mandatory'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'switch-input switch-green', 'id': 'id_req_active'}),
        }


class LicenseTypeForm(forms.ModelForm):
    requirements_list = forms.ModelMultipleChoiceField(
        queryset=LicenseTypeRequirement.objects.filter(is_active=True),
        widget=forms.SelectMultiple(attrs={
            'class': 'input-field form-control select2-modal-requirements',
            'id': 'id_requirements_list',
        }),
        required=False,
        label="Anexos y Requisitos Preconfigurados"
    )

    class Meta:
        model = MedicalLicenseType
        fields = [
            'code',
            'name',
            'description',
            'requirements_list',
            'default_authority_1',
            'default_authority_2',
            'default_reviewer',
            'default_register',
            'is_active',
        ]
        widgets = {
            'code': forms.HiddenInput(attrs={'id': 'id_license_type_code'}),
            'name': forms.TextInput(attrs={
                'class': 'input-field form-control',
                'placeholder': 'Ej: Calamidad Doméstica',
                'id': 'id_license_type_name',
                'maxlength': '150',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'input-field form-control',
                'rows': 2,
                'placeholder': 'Ej: En la ciudad de Loja se concede [DIAS] días de licencia...'
            }),
            'default_authority_1': forms.Select(attrs={
                'class': 'input-field form-control select2-modal',
                'id': 'id_default_authority_1',
            }),
            'default_authority_2': forms.Select(attrs={
                'class': 'input-field form-control select2-modal',
                'id': 'id_default_authority_2',
            }),
            'default_reviewer': forms.Select(attrs={
                'class': 'input-field form-control select2-modal',
                'id': 'id_default_reviewer',
            }),
            'default_register': forms.Select(attrs={
                'class': 'input-field form-control select2-modal',
                'id': 'id_default_register',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'switch-input switch-green',
                'id': 'id_is_active',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].required = False

        def get_user_label(user):
            name = getattr(user, 'signature_name', None) or user.get_full_name() or user.username
            pos = getattr(user, 'signature_position', None)
            return f"{name} - {pos}" if pos else name

        active_users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        user_choices = [('', '-- Sin firma por defecto --')] + [
            (u.id, get_user_label(u)) for u in active_users
        ]

        for field_name in ['default_authority_1', 'default_authority_2', 'default_reviewer', 'default_register']:
            self.fields[field_name].choices = user_choices
            self.fields[field_name].required = False

        if self.instance and self.instance.pk:
            self.initial['requirements_list'] = self.instance.requirements.all()
        else:
            self.initial['is_active'] = True

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name', '')

        if name:
            nfkd = unicodedata.normalize('NFKD', name)
            ascii_name = ''.join([c for c in nfkd if not unicodedata.combining(c)])
            clean_code = re.sub(r'[^a-zA-Z0-9\s_]', '', ascii_name)
            clean_code = re.sub(r'[\s]+', '_', clean_code.strip()).upper()
            cleaned_data['code'] = clean_code

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get('code'):
            instance.code = self.cleaned_data['code']
        if commit:
            instance.save()
            instance.requirements.set(self.cleaned_data.get('requirements_list', []))
        return instance
