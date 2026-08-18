from django import forms

from accounting.models import Account
from .models import PayrollPeriod, PayrollConstant, PayrollRubric


class PayrollPeriodForm(forms.ModelForm):
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
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'readonly': 'readonly'},
                                          format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'readonly': 'readonly'},
                                        format='%Y-%m-%d'),
            'month': forms.Select(attrs={'class': 'form-select'}),
            'working_days': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }

    def clean_year(self):
        year = self.cleaned_data.get('year')
        if year:
            if not year.isdigit() or len(year) != 4:
                raise forms.ValidationError('El año debe contener 4 dígitos.')
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


class PayrollRubricForm(forms.ModelForm):
    code = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'style': 'background-color: #f1f5f9; cursor: not-allowed; font-weight: bold;',
            'placeholder': 'Se autogenera...'
        })
    )
    income_account = forms.ModelChoiceField(queryset=Account.objects.all(),
                                            required=False,
                                            widget=forms.Select(attrs={'class': 'form-select'})
                                            )

    class Meta:
        model = PayrollRubric
        fields = [
            'rubric_type', 'name', 'code', 'is_salary', 'description',
            'spending_context', 'abbreviation', 'is_active', 'order', 'priority',
            'debit_account', 'credit_account', 'debit_account_prod', 'credit_account_prod',
            'debit_account_inv', 'credit_account_inv', 'income_account',
            'has_mapping', 'dynamic_suffix', 'is_fixed',
            'is_taxable', 'is_overtime', 'is_upload'
        ]
        widgets = {
            'rubric_type': forms.Select(attrs={'class': 'form-select'}),
            'spending_context': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Sueldo Básico'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción del rubro (Opcional)'}),
            'dynamic_suffix': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 5.1.01.05'}),
            'abbreviation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: SBU'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 100'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 100'}),
            'debit_account': forms.Select(attrs={'class': 'form-select'}),
            'credit_account': forms.Select(attrs={'class': 'form-select'}),
            'debit_account_prod': forms.Select(attrs={'class': 'form-select'}),
            'credit_account_prod': forms.Select(attrs={'class': 'form-select'}),
            'debit_account_inv': forms.Select(attrs={'class': 'form-select'}),
            'credit_account_inv': forms.Select(attrs={'class': 'form-select'}),
            'income_account': forms.Select(attrs={'class': 'form-select'}),
            'is_salary': forms.CheckboxInput(attrs={'class': 'switch-input switch-primary'}),
            'has_mapping': forms.CheckboxInput(attrs={'class': 'switch-input switch-primary'}),
            'is_fixed': forms.CheckboxInput(attrs={'class': 'switch-input switch-danger'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'switch-input switch-success'}),
            'is_taxable': forms.CheckboxInput(attrs={'class': 'switch-input switch-danger'}),
            'is_overtime': forms.CheckboxInput(attrs={'class': 'switch-input switch-warning'}),
            'is_upload': forms.CheckboxInput(attrs={'class': 'switch-input switch-warning'}),
        }

    def clean(self):
        cleaned_data = super().clean()

        # Generación automática del código basada en el nombre
        if not cleaned_data.get('code') and cleaned_data.get('name'):
            import unicodedata, re
            clean_name = ''.join(
                (c for c in unicodedata.normalize('NFD', cleaned_data['name']) if unicodedata.category(c) != 'Mn')
            )
            cleaned_data['code'] = re.sub(r'[^a-zA-Z0-9_]', '', clean_name.replace(' ', '_')).upper()
            self.instance.code = cleaned_data['code']

        return cleaned_data
