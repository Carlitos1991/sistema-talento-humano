from django import forms

from accounting.models import Account
from .models import PayrollPeriod, PayrollConstant, RubroBudgetMapping, Income, Deduction, InstitutionalContribution


class PayrollPeriodForm(forms.ModelForm):
    # Campos adicionales que se carguen via JS
    year = forms.CharField(
        max_length=4,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'pattern': '[0-9]{4}',
            'placeholder': 'AAAA',
            'inputmode': 'numeric',
            'maxlength': '4'
        }),
        help_text='Ingrese un año de 4 dígitos'
    )

    class Meta:
        model = PayrollPeriod
        fields = ['month', 'year', 'start_date', 'end_date', 'working_days']
        widgets = {
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'readonly': 'readonly'
            }, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'readonly': 'readonly'
            }, format='%Y-%m-%d'),
            'month': forms.Select(attrs={'class': 'form-select'}),
            'working_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'readonly': 'readonly'
            }),
        }

    def clean_year(self):
        year = self.cleaned_data.get('year')
        if year:
            if not year.isdigit() or len(year) != 4:
                raise forms.ValidationError('El año debe contener exactamente 4 dígitos numéricos.')
            try:
                year_int = int(year)
                if year_int < 1900 or year_int > 2100:
                    raise forms.ValidationError('El año debe estar entre 1900 y 2100.')
            except ValueError:
                raise forms.ValidationError('El año debe ser un número válido.')
        return year

    def clean(self):
        cleaned_data = super().clean()
        month = cleaned_data.get('month')
        year = cleaned_data.get('year')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        working_days = cleaned_data.get('working_days')

        # Validar que los campos calculados tengan valores
        if month and year:
            if not start_date:
                self.add_error('start_date', 'La fecha de inicio debe ser calculada (recarga el modal)')
            if not end_date:
                self.add_error('end_date', 'La fecha de fin debe ser calculada (recarga el modal)')
            if not working_days or working_days == 0:
                self.add_error('working_days', 'Los días laborables deben ser calculados (recarga el modal)')

        return cleaned_data


class PayrollConstantForm(forms.ModelForm):
    class Meta:
        model = PayrollConstant
        fields = ['name', 'code', 'value', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Salario Básico'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: SBU'}),
            'value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input mt-2'})
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
    """Formulario maestro que inyecta la lógica de mapeo presupuestario y autogenera códigos"""
    has_mapping = forms.BooleanField(label='¿Afecta al Presupuesto Institucional?', required=False,
                                     help_text="Marque esta casilla si este rubro debe generar una afectación presupuestaria.")
    dynamic_suffix = forms.CharField(label='Sufijo Presupuestario (Ej: 5.1.01.05)', required=False, max_length=50,
                                     widget=forms.TextInput(
                                         attrs={'class': 'form-control', 'placeholder': 'Ej: 5.1.01.05'}))
    is_fixed = forms.BooleanField(label='¿Es Partida Fija?', required=False,
                                  help_text="Si es fija, no tomará el programa del empleado, usará el texto exacto.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. CANDADO ESTRICTO: El código SIEMPRE es de solo lectura y no es obligatorio para el usuario
        if 'code' in self.fields:
            self.fields['code'].required = False
            self.fields['code'].widget.attrs['readonly'] = True
            self.fields['code'].widget.attrs[
                'style'] = 'background-color: #f1f5f9; cursor: not-allowed; color: #64748b; font-weight: bold;'

            # Mensaje que sale cuando estás creando uno nuevo
            if not self.instance.pk:
                self.fields['code'].widget.attrs['placeholder'] = 'Se autogenerará al guardar...'

        # 2. Cargar los datos del mapeo presupuestario (Si es edición)
        if self.instance and self.instance.pk:
            mapping = getattr(self.instance, 'budget_mapping', None)
            if mapping:
                self.fields['has_mapping'].initial = True
                self.fields['dynamic_suffix'].initial = mapping.dynamic_suffix
                self.fields['is_fixed'].initial = mapping.is_fixed

    def clean(self):
        cleaned_data = super().clean()
        code = cleaned_data.get('code')
        name = cleaned_data.get('name')

        # 3. AUTOGENERACIÓN MÁGICA Y SEGURA
        # Si el código viene vacío (nuevo rubro), lo generamos basándonos en el nombre
        if not code and name:
            import unicodedata
            import re

            # Paso A: Quitamos tildes y acentos (Ej: "Pensión" -> "Pension")
            clean_name = ''.join((c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn'))
            # Paso B: Reemplazamos espacios por guiones bajos y borramos símbolos raros
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '', clean_name.replace(' ', '_'))

            nuevo_codigo = clean_name.upper()

            # Lo inyectamos en los datos validados para que Django lo guarde
            cleaned_data['code'] = nuevo_codigo
            self.instance.code = nuevo_codigo

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if commit:
            instance.save()

            # Lógica del Mapeo Presupuestario
            has_mapping = self.cleaned_data.get('has_mapping')
            if has_mapping:
                suffix = self.cleaned_data.get('dynamic_suffix')
                is_fixed = self.cleaned_data.get('is_fixed')
                kwargs = {'dynamic_suffix': suffix, 'is_fixed': is_fixed}

                from .models import Income, Deduction, InstitutionalContribution, RubroBudgetMapping
                if isinstance(instance, Income):
                    RubroBudgetMapping.objects.update_or_create(income=instance, defaults=kwargs)
                elif isinstance(instance, Deduction):
                    RubroBudgetMapping.objects.update_or_create(deduction=instance, defaults=kwargs)
                elif isinstance(instance, InstitutionalContribution):
                    RubroBudgetMapping.objects.update_or_create(contribution=instance, defaults=kwargs)
            else:
                if hasattr(instance, 'budget_mapping') and instance.budget_mapping:
                    instance.budget_mapping.delete()

        return instance


class IncomeForm(BaseRubroForm):
    class Meta:
        model = Income
        fields = ['name', 'code', 'order', 'description', 'is_active', 'debit_account', 'credit_account',
                  'abbreviation']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Sueldo Básico'}),
            'abbreviation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Coop. Mun.'}),
            'code': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Código del sistema (Ej: IESS_PER)'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Ej: 1'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción del ingreso (opcional)'}),
            'debit_account': forms.Select(attrs={'class': 'form-select'}),
            'credit_account': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input mt-2'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtramos para que solo muestre cuentas activas y las ordenamos por código
        if 'debit_account' in self.fields:
            self.fields['debit_account'].queryset = Account.objects.filter(is_active=True).order_by('code')
        if 'credit_account' in self.fields:
            self.fields['credit_account'].queryset = Account.objects.filter(is_active=True).order_by('code')


class DeductionForm(BaseRubroForm):
    class Meta:
        model = Deduction
        # Incluimos 'priority' para que el campo esté disponible en el formulario/modal
        fields = ['name', 'code', 'order', 'priority', 'description', 'is_active', 'debit_account', 'income_account',
                  'credit_account', 'abbreviation']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Cooperativa Municipal'}),
            'income_account': forms.Select(attrs={'class': 'form-select'}),
            'abbreviation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Coop. Mun.'}),
            'code': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Código del sistema (Ej: IESS_PER)'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Ej: 1'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción del descuento (opcional)'}),
            'debit_account': forms.Select(attrs={'class': 'form-select'}),
            'credit_account': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input mt-2'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Ej: 1'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'debit_account' in self.fields:
            self.fields['debit_account'].queryset = Account.objects.filter(is_active=True).order_by('code')
        if 'credit_account' in self.fields:
            self.fields['credit_account'].queryset = Account.objects.filter(is_active=True).order_by('code')
        if 'income_account' in self.fields:
            self.fields['income_account'].queryset = Account.objects.filter(is_active=True).order_by('code')


class InstitutionalContributionForm(BaseRubroForm):
    class Meta:
        model = InstitutionalContribution
        # 'code' oculto: generado automáticamente desde el nombre
        fields = ['name', 'code', 'order', 'description', 'is_active', 'debit_account', 'credit_account',
                  'abbreviation']
        widgets = {
            'code': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Código del sistema (Ej: IESS_PER)'}),
            'abbreviation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Coop. Mun.'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Ej: 1'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Aporte Patronal'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción del aporte (opcional)'}),
            'debit_account': forms.Select(attrs={'class': 'form-select'}),
            'credit_account': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input mt-2'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'debit_account' in self.fields:
            self.fields['debit_account'].queryset = Account.objects.filter(is_active=True).order_by('code')
        if 'credit_account' in self.fields:
            self.fields['credit_account'].queryset = Account.objects.filter(is_active=True).order_by('code')
