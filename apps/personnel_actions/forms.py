from django import forms
from django.db.models import Q
from core.models import User
from .models import PersonnelAction, ActionMovement, ActionType


class PersonnelActionForm(forms.ModelForm):
    class Meta:
        model = PersonnelAction
        fields = [
            'employee', 'action_type', 'number', 'motivation',
            'date_issue', 'date_effective', 'explanation',
            'authority_1', 'authority_2', 'reviewer', 'register'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'input-field-select select2'}),
            'action_type': forms.Select(attrs={'class': 'input-field-select select2'}),
            'motivation': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Ej: Nombramiento definitivo'}),
            'date_issue': forms.DateInput(attrs={'type': 'date', 'class': 'input-field'}, format='%Y-%m-%d'),
            'date_effective': forms.DateInput(attrs={'type': 'date', 'class': 'input-field'}, format='%Y-%m-%d'),
            'explanation': forms.Textarea(attrs={
                'rows': 4,
                'class': 'input-textarea',
                'placeholder': 'Descripción detallada de la acción de personal'
            }),
            'number': forms.TextInput(attrs={'class': 'input-field'}),
            'authority_1': forms.Select(attrs={'class': 'input-field-select select2 action-signature-select'}),
            'authority_2': forms.Select(attrs={'class': 'input-field-select select2 action-signature-select'}),
            'reviewer': forms.Select(attrs={'class': 'input-field-select select2 action-signature-select'}),
            'register': forms.Select(attrs={'class': 'input-field-select select2 action-signature-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['number'].required = False
        self.fields['date_issue'].input_formats = ['%Y-%m-%d']
        self.fields['date_effective'].input_formats = ['%Y-%m-%d']

        signature_fields = ['authority_1', 'authority_2', 'reviewer', 'register']
        signature_queryset = User.objects.filter(is_active=True).select_related('person')

        if self.instance and self.instance.pk:
            selected_ids = [
                getattr(self.instance, field_name).pk
                for field_name in signature_fields
                if getattr(self.instance, field_name)
            ]
            if selected_ids:
                signature_queryset = User.objects.filter(
                    Q(is_active=True) | Q(pk__in=selected_ids)
                ).select_related('person').distinct()

        signature_queryset = signature_queryset.order_by('first_name', 'last_name', 'username')

        def signature_label(user):
            label = user.signature_name or user.get_full_name() or user.username
            if getattr(user, 'signature_position', None):
                label = f'{label} - {user.signature_position}'
            return label

        for field_name in signature_fields:
            field = self.fields[field_name]
            field.queryset = signature_queryset
            field.label_from_instance = signature_label
            field.empty_label = 'Seleccione una firma'
            field.required = False

    def clean(self):
        cleaned_data = super().clean()
        action_type = cleaned_data.get('action_type')
        is_create = not self.instance.pk

        if action_type and is_create and not action_type.default_authority_1:
            self.add_error(
                'action_type',
                'Control de Configuración: Este Tipo de Acción no tiene configuradas las "Firmas por Defecto". '
                'Por favor, configure las firmas predefinidas en el catálogo de Tipos de Acción antes de usarlo.'
            )
        if self.instance and self.instance.pk:
            if not cleaned_data.get('authority_1'):
                if self.instance.authority_1:
                    cleaned_data['authority_1'] = self.instance.authority_1
                elif action_type and action_type.default_authority_1:
                    cleaned_data['authority_1'] = action_type.default_authority_1
                else:
                    self.add_error('authority_1', 'La primera autoridad no puede quedar vacía al editar.')

        return cleaned_data


class ActionMovementForm(forms.ModelForm):
    class Meta:
        model = ActionMovement
        fields = [
            'previous_remuneration', 'new_remuneration',
            'new_unit', 'new_position', 'new_budget_line', 'location_text'
        ]
        widgets = {
            'new_unit': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Unidad Administrativa Nueva'}),
            'new_position': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Puesto Nuevo'}),
            'new_budget_line': forms.Select(attrs={'class': 'input-field-select select2'}),
            'previous_remuneration': forms.NumberInput(attrs={'class': 'input-field'}),
            'new_remuneration': forms.NumberInput(attrs={'class': 'input-field'}),
            'location_text': forms.TextInput(attrs={'class': 'input-field'}),
        }


class ActionTypeForm(forms.ModelForm):
    class Meta:
        model = ActionType
        fields = [
            'code',
            'name',
            'default_authority_1',
            'default_authority_2',
            'default_reviewer',
            'default_register',
            'is_acting',
            'is_acting_termination',
            'requires_budget_movement',
            'requires_unit_movement',
            'is_active',
        ]
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'input-field form-control',
                'placeholder': 'Ej: ENCARGO_DIR',
                'id': 'id_action_type_code',
                'maxlength': '50',
            }),
            'name': forms.TextInput(attrs={
                'class': 'input-field form-control',
                'placeholder': 'Ej: Encargo de Dirección / Subrogación',
                'id': 'id_action_type_name',
                'maxlength': '150',
            }),
            'default_authority_1': forms.Select(attrs={
                'class': 'input-field form-control select2-modal',
                'id': 'id_default_authority_1',
                'style': 'width: 100%;',
            }),
            'default_authority_2': forms.Select(attrs={
                'class': 'input-field form-control select2-modal',
                'id': 'id_default_authority_2',
                'style': 'width: 100%;',
            }),
            'default_reviewer': forms.Select(attrs={
                'class': 'input-field form-control select2-modal',
                'id': 'id_default_reviewer',
                'style': 'width: 100%;',
            }),
            'default_register': forms.Select(attrs={
                'class': 'input-field form-control select2-modal',
                'id': 'id_default_register',
                'style': 'width: 100%;',
            }),
            'is_acting': forms.CheckboxInput(attrs={'class': 'switch-input switch-green', 'id': 'id_is_acting', }),
            'is_acting_termination': forms.CheckboxInput(attrs={
                'class': 'switch-input switch-green',
                'id': 'id_is_acting_termination',
            }),
            'requires_budget_movement': forms.CheckboxInput(attrs={
                'class': 'switch-input switch-green',
                'id': 'id_requires_budget_movement',
            }),
            'requires_unit_movement': forms.CheckboxInput(attrs={
                'class': 'switch-input switch-green',
                'id': 'id_requires_unit_movement',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'switch-input switch-green',
                'id': 'id_is_active',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Helper para rotular firmantes con su cargo si existe
        def get_user_label(user):
            name = getattr(user, 'signature_name', None) or user.get_full_name() or user.username
            pos = getattr(user, 'signature_position', None)
            return f"{name} - {pos}" if pos else name

        active_users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        user_choices = [('', '-- Sin firma por defecto --')] + [
            (u.id, get_user_label(u)) for u in active_users
        ]

        for field_name in ['default_authority_1', 'default_authority_2', 'default_reviewer', 'default_register']:
            self.fields[field_name].choices = user_choices
            self.fields[field_name].required = False

        if not self.instance.pk:
            self.initial['is_active'] = True
