from django import forms
from .models import PayrollPeriod, PayrollConstant, RubroBudgetMapping, Income, Deduction, InstitutionalContribution


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
        fields = ['is_fixed', 'dynamic_suffix']
        widgets = {
            'is_fixed': forms.CheckboxInput(attrs={'class': 'form-check-input mt-2'}),
            'dynamic_suffix': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Ej: 06.02 o 5.01.01.001.001.5.1.05.12'})
        }


class BaseRubroForm(forms.ModelForm):
    """Formulario maestro que inyecta la lógica de mapeo presupuestario"""
    has_mapping = forms.BooleanField(label='¿Afecta al Presupuesto Institucional?', required=False,
                                     help_text="Marque esta casilla si este rubro debe generar una afectación presupuestaria.")
    dynamic_suffix = forms.CharField(label='Sufijo Presupuestario (Ej: 5.1.01.05)', required=False, max_length=50,
                                     widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 5.1.01.05'}))
    is_fixed = forms.BooleanField(label='¿Es Partida Fija?', required=False,
                                  help_text="Si es fija, no tomará el programa del empleado, usará el texto exacto.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si el rubro ya existe y tiene un mapeo, cargamos los datos en el formulario
        if self.instance and self.instance.pk:
            mapping = getattr(self.instance, 'budget_mapping', None)
            if mapping:
                self.fields['has_mapping'].initial = True
                self.fields['dynamic_suffix'].initial = mapping.dynamic_suffix
                self.fields['is_fixed'].initial = mapping.is_fixed

    def save(self, commit=True):
        # 1. Guardamos el Ingreso/Egreso normal
        instance = super().save(commit=commit)

        # 2. Lógica del Mapeo Presupuestario
        if commit:
            has_mapping = self.cleaned_data.get('has_mapping')
            if has_mapping:
                suffix = self.cleaned_data.get('dynamic_suffix')
                is_fixed = self.cleaned_data.get('is_fixed')
                kwargs = {'dynamic_suffix': suffix, 'is_fixed': is_fixed}

                # Determinamos a qué modelo pertenece y creamos/actualizamos el mapeo
                if isinstance(instance, Income):
                    RubroBudgetMapping.objects.update_or_create(income=instance, defaults=kwargs)
                elif isinstance(instance, Deduction):
                    RubroBudgetMapping.objects.update_or_create(deduction=instance, defaults=kwargs)
                elif isinstance(instance, InstitutionalContribution):
                    RubroBudgetMapping.objects.update_or_create(contribution=instance, defaults=kwargs)
            else:
                # Si desmarcaron la casilla, borramos el mapeo de la base de datos
                if hasattr(instance, 'budget_mapping') and instance.budget_mapping:
                    instance.budget_mapping.delete()

        return instance


# Heredamos la magia para cada modelo
class IncomeForm(BaseRubroForm):
    class Meta:
        model = Income
        # 'code' se incluye pero como campo oculto (HiddenInput)
        fields = ['name', 'code', 'description', 'is_active', 'debit_account', 'credit_account']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Sueldo Básico'}),
            'code': forms.HiddenInput(),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción del ingreso (opcional)'}),
            'debit_account': forms.Select(attrs={'class': 'form-select'}),
            'credit_account': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input mt-2'})
        }


class DeductionForm(BaseRubroForm):
    class Meta:
        model = Deduction
        # Incluimos 'priority' para que el campo esté disponible en el formulario/modal
        fields = ['name', 'code', 'priority', 'description', 'is_active', 'debit_account', 'credit_account']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: IESS'}),
            'code': forms.HiddenInput(),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción del descuento (opcional)'}),
            'debit_account': forms.Select(attrs={'class': 'form-select'}),
            'credit_account': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input mt-2'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Ej: 1'})
        }


class InstitutionalContributionForm(BaseRubroForm):
    class Meta:
        model = InstitutionalContribution
        # 'code' oculto: generado automáticamente desde el nombre
        fields = ['name', 'code', 'description', 'is_active', 'debit_account', 'credit_account']
        widgets = {
            'code': forms.HiddenInput(),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Aporte Patronal'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción del aporte (opcional)'}),
            'debit_account': forms.Select(attrs={'class': 'form-select'}),
            'credit_account': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input mt-2'})
        }
