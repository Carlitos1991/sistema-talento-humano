from django import forms

from core.models import CatalogItem
from employee.models import Employee
from institution.models import AdministrativeUnit
from schedule.models import Schedule
from .models import ContractType, LaborRegime, ManagementPeriod


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
            'labor_regime': forms.HiddenInput(),
        }


class HistoricalManagementPeriodForm(forms.ModelForm):
    document_number_input = forms.CharField(
        label='Número de Documento / Contrato',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control uppercase-input',
            'placeholder': 'Ej: ML-DTH-2016-0145 (Opcional, se autogenera si queda vacío)'
        })
    )

    class Meta:
        model = ManagementPeriod
        fields = [
            'employee',
            'contract_type',
            'administrative_unit',
            'manual_position',
            'manual_remuneration',
            'elaboration_date',
            'start_date',
            'end_date',
            'signed_document',
        ]
        widgets = {
            'employee': forms.Select(attrs={
                'class': 'form-control select2-employee-ajax',
                'data-minimum-input-length': '3',
                'data-placeholder': 'Escriba cédula, apellidos o nombres (mín. 3 letras)...',
            }),
            'contract_type': forms.Select(attrs={'class': 'form-control select2-field'}),
            'administrative_unit': forms.Select(attrs={'class': 'form-control select2-field'}),
            'manual_position': forms.TextInput(attrs={'class': 'form-control uppercase-input'}),
            'manual_remuneration': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'elaboration_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'signed_document': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.is_historical = True
        self.fields['employee'].queryset = Employee.objects.none()
        if self.data.get('employee'):
            try:
                emp_id = int(self.data.get('employee'))
                self.fields['employee'].queryset = Employee.objects.filter(pk=emp_id).select_related('person')
            except (ValueError, TypeError):
                pass
        elif self.instance and self.instance.pk and self.instance.employee_id:
            self.fields['employee'].queryset = Employee.objects.filter(pk=self.instance.employee_id).select_related(
                'person')

        self.fields['contract_type'].queryset = ContractType.objects.filter(is_active=True).select_related(
            'labor_regime'
        )
        self.fields['administrative_unit'].queryset = AdministrativeUnit.objects.filter(is_active=True).order_by('name')
        self.fields['administrative_unit'].required = False
        self.fields['elaboration_date'].required = False
        self.fields['end_date'].required = True

    def clean_signed_document(self):
        file = self.cleaned_data.get('signed_document')
        if file:
            if not file.name.lower().endswith('.pdf'):
                raise forms.ValidationError('Solo se permiten archivos en formato PDF.')
            if file.size > 2 * 1024 * 1024:
                raise forms.ValidationError('El archivo PDF no debe superar los 2 MB.')
        return file

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if not cleaned_data.get('elaboration_date') and start_date:
            cleaned_data['elaboration_date'] = start_date
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'La fecha de fin no puede ser anterior a la fecha de inicio.')
        return cleaned_data


class ManagementPeriodCreateForm(forms.ModelForm):
    action_start_date = forms.DateField(required=False)
    action_end_date = forms.DateField(required=False)
    is_boss = forms.BooleanField(required=False)

    class Meta:
        model = ManagementPeriod
        fields = [
            'employee',
            'budget_line',
            'contract_type',
            'administrative_unit',
            'schedule',
            'manual_position',
            'manual_remuneration',
            'institutional_need_memo',
            'budget_certification',
            'workplace',
            'job_functions',
            'elaboration_date',
            'start_date',
            'end_date',
            'action_motivation',
            'action_explanation',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_date'].required = False
        self.fields['budget_line'].required = False

    def clean(self):
        cleaned_data = super().clean()
        employee = cleaned_data.get('employee')
        if employee and not cleaned_data.get('budget_line'):
            cleaned_data['budget_line'] = employee.current_budget_line.first()

        contract_type = cleaned_data.get('contract_type')
        is_action = (
                contract_type
                and (contract_type.contract_type_category or '').upper() == ContractType.TYPE_ACCION_PERSONAL
        )

        if is_action:
            resolved_start = cleaned_data.get('action_start_date') or cleaned_data.get('start_date')
            resolved_end = cleaned_data.get('action_end_date') or cleaned_data.get('end_date')
            if not resolved_start:
                self.add_error('start_date', 'La fecha rige desde es obligatoria.')
            cleaned_data['start_date'] = resolved_start
            cleaned_data['end_date'] = resolved_end
        elif not cleaned_data.get('start_date'):
            self.add_error('start_date', 'La fecha de inicio es obligatoria.')

        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'La fecha de finalización no puede ser anterior a la fecha de inicio.')
        return cleaned_data


class ManagementPeriodPartialUpdateForm(forms.Form):
    doc = forms.CharField(max_length=100, required=False)
    workplace = forms.CharField(max_length=255, required=False)
    memo = forms.CharField(max_length=100, required=False)
    cert = forms.CharField(max_length=100, required=False)
    start = forms.DateField(required=True)
    end = forms.DateField(required=False)
    schedule = forms.ModelChoiceField(
        queryset=Schedule.objects.filter(is_active=True),
        required=False,
    )
    functions = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start')
        end_date = cleaned_data.get('end')
        if start_date and end_date and end_date < start_date:
            self.add_error('end', 'La fecha de fin no puede ser anterior a la fecha de inicio.')
        return cleaned_data


class ManagementPeriodTerminateForm(forms.Form):
    reason = forms.CharField(
        label='Motivo de Salida',
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-control uppercase-input', 'rows': 3}),
    )
    end_date = forms.DateField(
        label='Fecha Fin de Gestión',
        required=True,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    termination_reason = forms.ModelChoiceField(
        queryset=CatalogItem.objects.filter(catalog__code='TERMINATION_REASON', is_active=True),
        required=False,
    )
