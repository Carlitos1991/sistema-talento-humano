from django import forms
from .models import PermitType, PermitRequest
from employee.models import Employee


class PermitTypeForm(forms.ModelForm):
    class Meta:
        model = PermitType
        fields = [
            'name', 'parent', 'is_active',
            'needs_justification', 'affects_vacation', 'requires_attachment'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Ej. Calamidad Doméstica'}),
            'parent': forms.Select(attrs={'class': 'input-field select2'}),
            'is_active': forms.CheckboxInput(),
            'needs_justification': forms.CheckboxInput(),
            'affects_vacation': forms.CheckboxInput(),
            'requires_attachment': forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['parent'].queryset = PermitType.objects.exclude(pk=self.instance.pk)


class PermitRequestForm(forms.ModelForm):
    class Meta:
        model = PermitRequest
        fields = [
            'employee', 'permit_type',
            'start_date', 'end_date',
            'start_time', 'end_time',
            'days', 'hours', 'minutes',
            'justification_file'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select select2'}),
            'permit_type': forms.Select(attrs={'class': 'form-select select2'}),

            # Widgets nativos de HTML5 para fechas y horas
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),

            'days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 23}),
            'minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 59}),

            'justification_file': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar empleados activos
        self.fields['employee'].queryset = Employee.objects.filter(is_active=True).order_by('last_name')
        # Solo mostrar tipos de permisos activos y que sean hijos (opcional, depende de regla de negocio)
        self.fields['permit_type'].queryset = PermitType.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')

        if start and end and start > end:
            self.add_error('end_date', 'La fecha de fin no puede ser anterior a la de inicio.')

        return cleaned_data
