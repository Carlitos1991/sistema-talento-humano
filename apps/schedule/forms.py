from django import forms
from .models import Schedule, ScheduleObservation, EmployeeScheduleHistory


class ScheduleForm(forms.ModelForm):
    vigente_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = Schedule
        fields = [
            'name', 'description', 'late_tolerance_minutes', 'daily_hours',
            'morning_start', 'morning_end', 'morning_crosses_midnight',
            'afternoon_start', 'afternoon_end', 'afternoon_crosses_midnight',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'EJ: JORNADA ORDINARIA 8H'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descripción breve del horario'
            }),
            'late_tolerance_minutes': forms.NumberInput(attrs={
                'class': 'form-control with-icon',
                'min': '0'
            }),
            'morning_start': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'morning_end': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'afternoon_start': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'afternoon_end': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'morning_crosses_midnight': forms.CheckboxInput(attrs={
                'class': 'switch-input switch-blue'
            }),
            'afternoon_crosses_midnight': forms.CheckboxInput(attrs={
                'class': 'switch-input switch-blue'
            }),
            'monday': forms.CheckboxInput(attrs={'class': 'hidden'}),
            'tuesday': forms.CheckboxInput(attrs={'class': 'hidden'}),
            'wednesday': forms.CheckboxInput(attrs={'class': 'hidden'}),
            'thursday': forms.CheckboxInput(attrs={'class': 'hidden'}),
            'friday': forms.CheckboxInput(attrs={'class': 'hidden'}),
            'saturday': forms.CheckboxInput(attrs={'class': 'hidden'}),
            'sunday': forms.CheckboxInput(attrs={'class': 'hidden'}),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'switch-input switch-green'
            }),
        }


class ScheduleObservationForm(forms.ModelForm):
    class Meta:
        model = ScheduleObservation
        fields = ['name', 'is_holiday', 'start_date', 'end_date', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control uppercase-input',
                'placeholder': 'Ej: FERIADO POR INDEPENDENCIA DE LOJA'
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Detalle adicional sobre el feriado u observación...'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'switch-input switch-green'
            }),
        }


class ScheduleSearchForm(forms.Form):
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del horario'})
    )
    is_active = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos'), ('true', 'Activos'), ('false', 'Inactivos')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class ObservationSearchForm(forms.Form):
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'Desde'}),
        label='Fecha Desde'
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'Hasta'}),
        label='Fecha Hasta'
    )
    is_holiday = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos'), ('true', 'Feriados'), ('false', 'Observaciones')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_active = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos'), ('true', 'Activos'), ('false', 'Inactivos')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
