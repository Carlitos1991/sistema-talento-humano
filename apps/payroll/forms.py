from django import forms
from .models import PayrollPeriod, PayrollConstant, RubroBudgetMapping


class PayrollPeriodForm(forms.ModelForm):
    class Meta:
        model = PayrollPeriod
        fields = ['month', 'year', 'start_date', 'end_date', 'working_days']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'month': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.TextInput(attrs={'class': 'form-control'}),
            'working_days': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class PayrollConstantForm(forms.ModelForm):
    class Meta:
        model = PayrollConstant
        fields = ['name', 'code', 'value', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Salario Básico'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: SBU'}),
            'value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class RubroBudgetMappingForm(forms.ModelForm):
    class Meta:
        model = RubroBudgetMapping
        # Quitamos administrative_unit y budget_line. Agregamos is_fixed
        fields = ['rubro_type', 'rubro_code', 'is_fixed', 'dynamic_suffix', 'is_active']
        widgets = {
            'rubro_type': forms.Select(attrs={'class': 'form-control'}),
            'rubro_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: FONDOS_RESERVA'}),
            'is_fixed': forms.CheckboxInput(attrs={'class': 'form-check-input mt-2'}),
            'dynamic_suffix': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Ej: 06.02 o 5.01.01.001.001.5.1.05.12'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input mt-2'}),
        }
