from django import forms
from .models import Schedule, ScheduleObservation, EmployeeScheduleHistory


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = '__all__'
        exclude = ['created_by', 'updated_by', 'is_active']
        widgets = {
            'morning_start': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'morning_end': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'afternoon_start': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'afternoon_end': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        m_start = cleaned_data.get('morning_start')
        m_end = cleaned_data.get('morning_end')

        if m_start and m_end and not cleaned_data.get('morning_crosses_midnight'):
            if m_start >= m_end:
                self.add_error('morning_end', 'La hora de fin debe ser posterior al inicio.')

        return cleaned_data


class ScheduleObservationForm(forms.ModelForm):
    class Meta:
        model = ScheduleObservation
        fields = [
            'name', 'description', 'start_date', 'end_date',
            'is_holiday', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del feriado/observación'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Detalle'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'is_holiday': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_date'].input_formats = ['%Y-%m-%d']
        self.fields['end_date'].input_formats = ['%Y-%m-%d']


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
