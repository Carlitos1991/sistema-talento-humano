import datetime

import pytz
from django import forms
from django.utils import timezone
from .models import *
from core.models import User

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


class VacationSchedulePlanForm(forms.ModelForm):
    class Meta:
        model = VacationSchedulePlan
        fields = ['year', 'title', 'start_submission_date', 'end_submission_date', 'status', 'observation']
        widgets = {
            'year': forms.NumberInput(attrs={
                'class': 'form-control',
                'id': 'id_plan_year',
                'placeholder': 'Ej. 2027',
                'min': '2000',
                'max': '2100'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_plan_title',
                'placeholder': 'Ej. Cronograma General de Vacaciones 2027'
            }),
            'start_submission_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'id': 'id_plan_start_date'
            }),
            'end_submission_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'id': 'id_plan_end_date'
            }),
            'status': forms.Select(attrs={'class': 'input-field'}),
            'observation': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Directrices para las jefaturas y funcionarios...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            current_year = datetime.date.today().year
            next_year = current_year + 1

            self.fields['year'].initial = next_year
            self.fields['title'].initial = f'Cronograma de Vacaciones {next_year}'
            self.fields['start_submission_date'].initial = datetime.date(next_year, 1, 1).strftime('%Y-%m-%d')
            self.fields['end_submission_date'].initial = datetime.date(next_year, 12, 31).strftime('%Y-%m-%d')
            self.fields['status'].initial = VacationSchedulePlan.PlanStatus.DRAFT

    def clean_year(self):
        year = self.cleaned_data.get('year')
        status = self.cleaned_data.get('status')

        # Si el plan que se está guardando no es cerrado, verificamos si ya existe otro activo
        if status != VacationSchedulePlan.PlanStatus.CLOSED:
            qs = VacationSchedulePlan.objects.filter(
                year=year
            ).exclude(
                status=VacationSchedulePlan.PlanStatus.CLOSED
            )

            # Si estamos editando, excluimos la instancia actual
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError(
                    f'Ya existe un cronograma activo para el año {year}. Para crear uno nuevo con este año, debe dar de baja o cerrar el anterior.'
                )

        return year


class VacationScheduleItemForm(forms.ModelForm):
    class Meta:
        model = VacationScheduleItem
        fields = ['employee', 'start_date', 'end_date', 'observation']
        widgets = {
            'employee': forms.Select(attrs={'class': 'input-field select2'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_start_date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_end_date'}),
            'observation': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Ej. Primer período fraccionado'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')

        if start and end:
            if end < start:
                self.add_error('end_date', 'La fecha final no puede ser anterior a la inicial.')
            else:
                cleaned_data['days_quantity'] = (end - start).days + 1
        return cleaned_data


class ConsolidatedReportForm(forms.Form):
    FORMAT_CHOICES = [
        ('pdf', 'Documento PDF (Imprimible)'),
        ('excel', 'Hoja de Cálculo Excel (.xlsx)'),
    ]

    report_format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'custom-radio'}),
        initial='pdf',
        label='Formato del Reporte'
    )
    elaborated_by = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
        widget=forms.Select(attrs={'class': 'input-field select2'}),
        label='Elaborado por'
    )
    reviewed_by = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
        widget=forms.Select(attrs={'class': 'input-field select2'}),
        label='Revisado por'
    )

    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        if current_user:
            self.fields['elaborated_by'].initial = current_user
