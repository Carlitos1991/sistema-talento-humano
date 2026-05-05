from django import forms
from .models import VacationPeriod, EmployeeVacationBalance
from permitrequest.models import PermitRequest
import datetime


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
        error_messages = {
            'name': {
                'unique': 'Ya existe Periodo con este Nombre Periodo.',
            }
        }


# En vacation/forms.py, actualiza FirstVacationForm

class FirstVacationForm(forms.ModelForm):
    total_days = forms.DecimalField(
        label='Días',
        required=True,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '1',
            'min': '0'
        })
    )

    hours = forms.IntegerField(
        label='Horas',
        required=True,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '7'
        })
    )

    minutes = forms.IntegerField(
        label='Minutos',
        required=True,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '59'
        })
    )

    observation_detail = forms.CharField(
        label='Detalle / Motivo',
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': '3',
            'placeholder': 'Especifique el motivo de esta carga inicial...'
        })
    )

    class Meta:
        model = EmployeeVacationBalance
        fields = ['period']  # total_days se maneja manualmente
        widgets = {
            'period': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        employee_id = kwargs.pop('employee_id', None)
        initial_days = kwargs.pop('initial_days', 0)
        super().__init__(*args, **kwargs)

        # Si quieres que sugiera los 15 o 30 días pero permita cambiar:
        if initial_days:
            self.fields['total_days'].initial = int(initial_days)

        # Filtrar periodos (mantener tu lógica actual)
        periods_qs = VacationPeriod.objects.filter(is_active=True).order_by('name')
        if employee_id:
            from employee.models import Employee
            try:
                employee = Employee.objects.get(pk=employee_id)
                last_balance = EmployeeVacationBalance.objects.filter(employee=employee).order_by('-created_at').first()
                if last_balance:
                    periods_qs = periods_qs.filter(name__gt=last_balance.period.name)
            except Employee.DoesNotExist:
                pass
        self.fields['period'].queryset = periods_qs


class VacationLiquidationForm(forms.Form):
    """
    Formulario para liquidar vacaciones.
    """
    start_date = forms.DateField(
        label='Fecha Desde',
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    end_date = forms.DateField(
        label='Fecha Hasta',
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    # Campos para autoridades
    nominating_authority = forms.ModelChoiceField(
        label='Autoridad Nominadora',
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    human_resources_responsible = forms.ModelChoiceField(
        label='Responsable de Talento Humano',
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    registration_responsible = forms.ModelChoiceField(
        label='Responsable de Registro',
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    review_responsible = forms.ModelChoiceField(
        label='Responsable de Revisar',
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    elaborated_by = forms.ModelChoiceField(
        label='Elaborado por',
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.available_days = kwargs.pop('available_days', 0)
        super().__init__(*args, **kwargs)

        # Cargar usuarios activos para firmas
        from core.models import User
        active_users = User.objects.filter(is_active=True).order_by('username')
        self.fields['nominating_authority'].queryset = active_users
        self.fields['human_resources_responsible'].queryset = active_users
        self.fields['registration_responsible'].queryset = active_users
        self.fields['review_responsible'].queryset = active_users
        self.fields['elaborated_by'].queryset = active_users
        label_builder = lambda obj: f"{obj.signature_name} - {obj.signature_position}"
        self.fields['nominating_authority'].label_from_instance = label_builder
        self.fields['human_resources_responsible'].label_from_instance = label_builder
        self.fields['registration_responsible'].label_from_instance = label_builder
        self.fields['review_responsible'].label_from_instance = label_builder
        self.fields['elaborated_by'].label_from_instance = label_builder

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if end_date < start_date:
                raise forms.ValidationError('La fecha hasta debe ser posterior a la fecha desde.')

            # Calcular días solicitados (incluye ambos días)
            delta = end_date - start_date
            days_requested = delta.days + 1

            if days_requested > self.available_days:
                raise forms.ValidationError(
                    f'No puede solicitar {days_requested} días. Saldo disponible: {self.available_days} días.'
                )

            cleaned_data['days_requested'] = days_requested

        return cleaned_data
