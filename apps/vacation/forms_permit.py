from django import forms
from permitrequest.models import PermitRequest
import datetime
from django.utils import timezone


class HourPermitVacationForm(forms.Form):
    """
    Formulario para crear permisos por horas con cargo a vacaciones.
    """
    start_date = forms.DateField(
        label='Fecha de Inicio',
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    start_time = forms.TimeField(
        label='Hora de Inicio',
        required=True,
        widget=forms.TimeInput(attrs={
            'class': 'form-control',
            'type': 'time'
        })
    )
    
    hours = forms.IntegerField(
        label='Número de Horas',
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
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
            'class': 'form-control',
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
        
        # Validar que la fecha y hora no sean pasadas
        if start_date and start_time:
            from django.conf import settings
            import pytz
            
            # Obtener la zona horaria configurada
            tz = pytz.timezone(settings.TIME_ZONE) if hasattr(settings, 'TIME_ZONE') else pytz.UTC
            now = timezone.now().astimezone(tz)
            
            # Combinar fecha y hora, y hacerla aware
            permit_datetime = tz.localize(datetime.datetime.combine(start_date, start_time))
            
            if permit_datetime < now:
                raise forms.ValidationError(
                    'No se pueden crear permisos con fechas anteriores.'
                )
        
        return cleaned_data


class DayPermitVacationForm(forms.Form):
    """
    Formulario para crear permisos por días con cargo a vacaciones.
    """
    start_date = forms.DateField(
        label='Fecha de Inicio',
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    days = forms.IntegerField(
        label='Número de Días',
        required=True,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
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
            from django.conf import settings
            import pytz
            
            # Obtener la zona horaria configurada
            tz = pytz.timezone(settings.TIME_ZONE) if hasattr(settings, 'TIME_ZONE') else pytz.UTC
            now = timezone.now().astimezone(tz)
            today = now.date()
            
            if start_date < today:
                raise forms.ValidationError(
                    'No se pueden crear permisos con fechas anteriores.'
                )
        return start_date
