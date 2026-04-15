from django import forms
from .models import SanctionNotificationType, SanctionNotification, SanctionNotificationMapping, SanctionNotificationTypeMapping, SanctionType, Sanction
from employee.models import Employee


MONTH_CHOICES = [
    ('', 'Seleccione...'),
    (1, 'Enero'),
    (2, 'Febrero'),
    (3, 'Marzo'),
    (4, 'Abril'),
    (5, 'Mayo'),
    (6, 'Junio'),
    (7, 'Julio'),
    (8, 'Agosto'),
    (9, 'Septiembre'),
    (10, 'Octubre'),
    (11, 'Noviembre'),
    (12, 'Diciembre'),
]


class SanctionTypeForm(forms.ModelForm):
    class Meta:
        model = SanctionType
        fields = ['name', 'description', 'is_active', 'requires_attachment']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field', 
                'placeholder': 'Ej. Amonestación Escrita'
            }),
            'description': forms.Textarea(attrs={
                'class': 'input-field', 
                'rows': 3,
                'placeholder': 'Descripción del tipo de sanción'
            }),
            'is_active': forms.CheckboxInput(),
            'requires_attachment': forms.CheckboxInput(),
        }


class SanctionNotificationTypeForm(forms.ModelForm):
    class Meta:
        model = SanctionNotificationType
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej. Atrasos'
            }),
            'description': forms.Textarea(attrs={
                'class': 'input-field',
                'rows': 3,
                'placeholder': 'Descripción del tipo de notificación'
            }),
            'is_active': forms.CheckboxInput(),
        }


class SanctionNotificationTypeMappingForm(forms.ModelForm):
    class Meta:
        model = SanctionNotificationTypeMapping
        fields = ['placeholder', 'label', 'source_key', 'description', 'is_active', 'order']
        widgets = {
            'placeholder': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej. [AUTHORITY_1_NAME]'
            }),
            'label': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej. Autoridad 1'
            }),
            'source_key': forms.Select(attrs={'class': 'form-select select2'}),
            'description': forms.Textarea(attrs={
                'class': 'input-field',
                'rows': 3,
                'placeholder': 'Explicación corta de cuándo usar este marcador'
            }),
            'is_active': forms.CheckboxInput(),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


class SanctionNotificationMappingForm(forms.ModelForm):
    class Meta:
        model = SanctionNotificationMapping
        fields = ['placeholder', 'label', 'expression', 'description', 'is_active', 'order']
        widgets = {
            'placeholder': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej. [FULL_NAME]'
            }),
            'label': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej. Nombre completo'
            }),
            'expression': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej. person.first_name + " " + person.last_name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'input-field',
                'rows': 3,
                'placeholder': 'Describe qué hace este mapeo'
            }),
            'is_active': forms.CheckboxInput(),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


class SanctionNotificationForm(forms.ModelForm):
    month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = SanctionNotification
        fields = [
            'notification_type',
            'month',
            'year',
            'registration_date',
            'authority_1',
            'authority_2',
            'minutes_late',
            'regs_without_mark',
            'observations',
        ]
        widgets = {
            'notification_type': forms.Select(attrs={'class': 'form-select select2'}),
            'month': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000, 'max': 2100}),
            'registration_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'authority_1': forms.Select(attrs={'class': 'form-select select2'}),
            'authority_2': forms.Select(attrs={'class': 'form-select select2'}),
            'minutes_late': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'regs_without_mark': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'observations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, notification_types=None, authorities=None, **kwargs):
        super().__init__(*args, **kwargs)
        if notification_types is not None:
            self.fields['notification_type'].queryset = notification_types
        if authorities is not None:
            self.fields['authority_1'].queryset = authorities
            self.fields['authority_2'].queryset = authorities
            self.fields['authority_1'].label_from_instance = lambda obj: f"{obj.signature_name} - {obj.signature_position}"
            self.fields['authority_2'].label_from_instance = lambda obj: f"{obj.signature_name} - {obj.signature_position}"

        self.fields['notification_type'].empty_label = 'Seleccione...'
        self.fields['authority_1'].empty_label = 'Seleccione...'
        self.fields['authority_2'].empty_label = 'Seleccione...'
        self.fields['authority_1'].required = True
        self.fields['minutes_late'].required = False
        self.fields['regs_without_mark'].required = False
        self.fields['authority_2'].required = False
        self.fields['observations'].required = False

        if not self.initial.get('year'):
            from django.utils import timezone
            self.initial['year'] = timezone.now().year
        if not self.initial.get('month'):
            from django.utils import timezone
            self.initial['month'] = timezone.now().month
        if not self.initial.get('registration_date'):
            from django.utils import timezone
            self.initial['registration_date'] = timezone.now().date()

    def clean(self):
        cleaned_data = super().clean()
        authority_1 = cleaned_data.get('authority_1')
        authority_2 = cleaned_data.get('authority_2')

        if authority_1 and authority_2 and authority_1 == authority_2:
            self.add_error('authority_2', 'La segunda firma debe ser distinta a la primera.')

        return cleaned_data


class SanctionForm(forms.ModelForm):
    class Meta:
        model = Sanction
        fields = [
            'employee', 'sanction_type', 'severity',
            'description', 'legal_basis',
            'incident_date', 'sanction_date', 'start_date', 'end_date',
            'days', 'observations', 'attachment_file'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select select2'}),
            'sanction_type': forms.Select(attrs={'class': 'form-select select2'}),
            'severity': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describa la falta cometida'
            }),
            'legal_basis': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Documento que genera la Sanción'
            }),
            'incident_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'sanction_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'observations': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones adicionales'
            }),
            'attachment_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter active employees
        self.fields['employee'].queryset = Employee.objects.filter(is_active=True)
        # Filter active sanction types
        self.fields['sanction_type'].queryset = SanctionType.objects.filter(is_active=True)
        # Make duration fields not required
        self.fields['start_date'].required = False
        self.fields['end_date'].required = False
        self.fields['days'].required = False
        
        # Format dates for input type="date" (YYYY-MM-DD) when editing
        if self.instance and self.instance.pk:
            if self.instance.incident_date:
                self.initial['incident_date'] = self.instance.incident_date.strftime('%Y-%m-%d')
            if self.instance.sanction_date:
                self.initial['sanction_date'] = self.instance.sanction_date.strftime('%Y-%m-%d')
            if self.instance.start_date:
                self.initial['start_date'] = self.instance.start_date.strftime('%Y-%m-%d')
            if self.instance.end_date:
                self.initial['end_date'] = self.instance.end_date.strftime('%Y-%m-%d')
