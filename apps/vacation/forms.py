import datetime
from decimal import Decimal
from django import forms
from django.conf import settings
from django.utils import timezone
import pytz

from .models import VacationPeriod, EmployeeVacationBalance, VacationRequest
from permitrequest.models import PermitRequest


class PeriodForm(forms.ModelForm):
    class Meta:
        model = VacationPeriod
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: 2024-2025'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'switch-input'
            }),
        }
        labels = {
            'name': 'Nombre del Periodo',
            'is_active': 'Periodo Activo',
        }
        error_messages = {
            'name': {
                'unique': 'Ya existe un Periodo con este nombre.',
            }
        }


class FirstVacationForm(forms.ModelForm):
    total_days = forms.DecimalField(
        label='Días',
        required=True,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'input-field',
            'step': '1',
            'min': '0'
        })
    )

    hours = forms.IntegerField(
        label='Horas',
        required=True,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'input-field',
            'min': '0',
            'max': '7'
        })
    )

    minutes = forms.IntegerField(
        label='Minutos',
        required=True,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'input-field',
            'min': '0',
            'max': '59'
        })
    )

    observation_detail = forms.CharField(
        label='Detalle / Motivo',
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'input-field',
            'rows': '3',
            'placeholder': 'Especifique el motivo de esta carga inicial...'
        })
    )

    class Meta:
        model = EmployeeVacationBalance
        fields = ['period']
        widgets = {
            'period': forms.Select(attrs={'class': 'input-field'}),
        }

    def __init__(self, *args, **kwargs):
        employee_id = kwargs.pop('employee_id', None)
        initial_days = kwargs.pop('initial_days', 0)
        super().__init__(*args, **kwargs)

        if initial_days:
            self.fields['total_days'].initial = int(initial_days)

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


class HourPermitVacationForm(forms.Form):
    start_date = forms.DateField(
        label='Fecha de Inicio',
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'input-field',
            'type': 'date'
        })
    )

    start_time = forms.TimeField(
        label='Hora de Inicio',
        required=True,
        widget=forms.TimeInput(attrs={
            'class': 'input-field',
            'type': 'time'
        })
    )

    hours = forms.IntegerField(
        label='Número de Horas',
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'input-field',
            'min': '0',
            'max': '7'
        }),
        help_text='Valores permitidos: 0 a 7 horas'
    )

    minutes = forms.IntegerField(
        label='Número de Minutos',
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'input-field',
            'min': '0',
            'max': '59'
        }),
        help_text='Valores permitidos: 0 a 59 minutos'
    )

    def clean(self):
        cleaned_data = super().clean()
        hours = cleaned_data.get('hours', 0) or 0
        minutes = cleaned_data.get('minutes', 0) or 0
        start_date = cleaned_data.get('start_date')
        start_time = cleaned_data.get('start_time')

        if hours == 0 and minutes == 0:
            raise forms.ValidationError('Debe especificar al menos horas o minutos.')

        if hours < 0 or hours > 7:
            raise forms.ValidationError('Las horas deben estar entre 0 y 7.')

        if minutes < 0 or minutes > 59:
            raise forms.ValidationError('Los minutos deben estar entre 0 y 59.')

        if start_date and start_time:
            tz = pytz.timezone(settings.TIME_ZONE) if hasattr(settings, 'TIME_ZONE') else pytz.UTC
            now = timezone.now().astimezone(tz)
            permit_datetime = tz.localize(datetime.datetime.combine(start_date, start_time))

            if permit_datetime < now:
                raise forms.ValidationError('No se pueden crear permisos con fechas u horas anteriores.')

        return cleaned_data


class DayPermitVacationForm(forms.Form):
    start_date = forms.DateField(
        label='Fecha de Inicio',
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'input-field',
            'type': 'date'
        })
    )

    days = forms.IntegerField(
        label='Número de Días',
        required=True,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'input-field',
            'min': '1'
        }),
        help_text='Número de días de permiso'
    )

    def clean_days(self):
        days = self.cleaned_data.get('days')
        if days and days < 1:
            raise forms.ValidationError('Debe especificar al menos 1 día.')
        return days

    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        if start_date:
            tz = pytz.timezone(settings.TIME_ZONE) if hasattr(settings, 'TIME_ZONE') else pytz.UTC
            today = timezone.now().astimezone(tz).date()

            if start_date < today:
                raise forms.ValidationError('No se pueden crear permisos con fechas anteriores.')
        return start_date


class VacationLiquidationForm(forms.Form):
    start_date = forms.DateField(
        label='Fecha Desde',
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'input-field',
            'type': 'date'
        })
    )

    end_date = forms.DateField(
        label='Fecha Hasta',
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'input-field',
            'type': 'date'
        })
    )

    nominating_authority = forms.ModelChoiceField(
        label='Autoridad Nominadora',
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'input-field select2'})
    )

    human_resources_responsible = forms.ModelChoiceField(
        label='Responsable de Talento Humano',
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'input-field select2'})
    )

    registration_responsible = forms.ModelChoiceField(
        label='Responsable de Registro',
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'input-field select2'})
    )

    review_responsible = forms.ModelChoiceField(
        label='Responsable de Revisar',
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'input-field select2'})
    )

    elaborated_by = forms.ModelChoiceField(
        label='Elaborado por',
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'input-field select2'})
    )

    def __init__(self, *args, **kwargs):
        self.available_days = kwargs.pop('available_days', 0)
        super().__init__(*args, **kwargs)

        from core.models import User
        active_users = User.objects.filter(is_active=True).order_by('username')
        for f in ['nominating_authority', 'human_resources_responsible', 'registration_responsible',
                  'review_responsible', 'elaborated_by']:
            self.fields[f].queryset = active_users
            self.fields[f].label_from_instance = lambda \
                obj: f"{getattr(obj, 'signature_name', obj.username)} - {getattr(obj, 'signature_position', '')}"

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if end_date < start_date:
                raise forms.ValidationError('La fecha hasta debe ser posterior a la fecha desde.')

            delta = end_date - start_date
            days_requested = delta.days + 1

            if days_requested > self.available_days:
                raise forms.ValidationError(
                    f'No puede solicitar {days_requested} días. Saldo disponible: {self.available_days} días.'
                )

            cleaned_data['days_requested'] = days_requested

        return cleaned_data
