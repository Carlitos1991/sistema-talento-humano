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


class FirstVacationForm(forms.ModelForm):
    """
    Formulario para crear el primer periodo de vacaciones de un empleado.
    """
    total_days = forms.DecimalField(
        label='Días de Vacaciones',
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        })
    )
    
    class Meta:
        model = EmployeeVacationBalance
        fields = ['period', 'total_days']
        widgets = {
            'period': forms.Select(attrs={
                'class': 'form-control',
            }),
        }
        labels = {
            'period': 'Periodo de Vacaciones',
        }
    
    def __init__(self, *args, **kwargs):
        employee_id = kwargs.pop('employee_id', None)
        initial_days = kwargs.pop('initial_days', None)
        super().__init__(*args, **kwargs)
        
        # Establecer valor inicial de días si se proporciona
        if initial_days is not None:
            self.fields['total_days'].initial = initial_days
        
        # Ordenar campos
        self.order_fields(['period', 'total_days'])
        
        # Obtener períodos activos
        periods_qs = VacationPeriod.objects.filter(is_active=True).order_by('name')
        
        # Si hay employee_id, filtrar períodos posteriores al último asignado
        if employee_id:
            from employee.models import Employee
            try:
                employee = Employee.objects.get(pk=employee_id)
                last_balance = EmployeeVacationBalance.objects.filter(
                    employee=employee
                ).select_related('period').order_by('-created_at').first()
                
                if last_balance:
                    # Excluir el último período y todos los anteriores (comparación por nombre)
                    last_period_name = last_balance.period.name
                    periods_qs = periods_qs.filter(name__gt=last_period_name)
            except Employee.DoesNotExist:
                pass
        
        self.fields['period'].queryset = periods_qs
    
    def clean_period(self):
        period = self.cleaned_data.get('period')
        if not period:
            raise forms.ValidationError('Este campo es obligatorio.')
        return period