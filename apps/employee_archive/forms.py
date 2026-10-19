from django import forms

from core.models import User
from employee.models import Employee
from institution.models import AdministrativeUnit

from .models import EmployeeArchiveDocument
from .models import EmployeeArchiveLoan
from .models import EmployeeArchiveVersion
from .models import EmployeeDocumentType


class EmployeeDocumentTypeForm(forms.ModelForm):
    class Meta:
        model = EmployeeDocumentType
        fields = ['code', 'name', 'description', 'is_required', 'has_expiration', 'max_size_mb', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                classes = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{classes} form-control'.strip()

        self.fields['code'].widget.attrs.update({'placeholder': 'Ej: CERT_MEDICO'})
        self.fields['name'].widget.attrs.update({'placeholder': 'Ej: Certificado Medico'})
        self.fields['description'].widget.attrs.update({'placeholder': 'Descripcion breve del tipo documental'})
        self.fields['max_size_mb'].widget.attrs.update({'placeholder': 'Ej: 10', 'min': 1})


class EmployeeArchiveDocumentForm(forms.ModelForm):
    class Meta:
        model = EmployeeArchiveDocument
        fields = ['document_type', 'status', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                classes = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{classes} form-control'.strip()


class EmployeeArchiveVersionForm(forms.ModelForm):
    class Meta:
        model = EmployeeArchiveVersion
        fields = ['file', 'issue_date', 'expiration_date', 'observations']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'expiration_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'observations': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                classes = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{classes} form-control'.strip()


class ArchiveLoanRequestForm(forms.ModelForm):
    class Meta:
        model = EmployeeArchiveLoan
        fields = ['request_observation']
        widgets = {
            'request_observation': forms.Textarea(
                attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Observacion de solicitud'})
        }


class UserFullNameModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        full_name = f"{obj.first_name or ''} {obj.last_name or ''}".strip()
        if full_name:
            return f"{full_name} ({obj.username})"
        return obj.username


class ArchiveManualLoanForm(forms.ModelForm):
    borrower_user = UserFullNameModelChoiceField(
        queryset=User.objects.none(),
        empty_label="-- Seleccione un funcionario de Talento Humano --",
        widget=forms.Select(attrs={'class': 'form-control select2'})
    )

    class Meta:
        model = EmployeeArchiveLoan
        fields = ['borrower_user', 'delivery_observation']
        widgets = {
            'delivery_observation': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Observación de entrega (opcional)'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Obtener la unidad configurada como Talento Humano
        th_unit = AdministrativeUnit.objects.filter(is_human_resources=True, is_active=True).first()

        if th_unit:
            # 2. Obtener los IDs de la unidad y todas sus subdependencias recursivamente
            valid_unit_ids = th_unit.get_descendant_ids()

            # 3. Filtrar empleados en esas áreas (usando area_id)
            th_employees = Employee.objects.filter(
                area_id__in=valid_unit_ids,
                is_active=True
            ).select_related('person')

            # IDs de personas pertenecientes a Talento Humano
            person_ids = [emp.person_id for emp in th_employees if emp.person_id]

            # 4. Obtener usuarios vinculados a esas personas
            # Si tu modelo User tiene ForeignKey/OneToOneField hacia Person (ej. user.person o person.user):
            try:
                # Caso A: User tiene relación directa con Person
                th_users = User.objects.filter(
                    person_id__in=person_ids,
                    is_active=True
                ).order_by('first_name', 'last_name', 'username')

                # Si no encuentra por person_id o tu User usa el username como número de cédula:
                if not th_users.exists():
                    doc_numbers = [emp.person.document_number for emp in th_employees if
                                   emp.person and emp.person.document_number]
                    th_users = User.objects.filter(
                        username__in=doc_numbers,
                        is_active=True
                    ).order_by('first_name', 'last_name', 'username')

            except Exception:
                # Caso B: Fallback por número de cédula/documento coincidente con username
                doc_numbers = [emp.person.document_number for emp in th_employees if
                               emp.person and emp.person.document_number]
                th_users = User.objects.filter(
                    username__in=doc_numbers,
                    is_active=True
                ).order_by('first_name', 'last_name', 'username')

            self.fields['borrower_user'].queryset = th_users if th_users.exists() else User.objects.filter(
                is_active=True).order_by('first_name', 'last_name', 'username')
        else:
            # Fallback si aún no se marca ninguna unidad como Talento Humano
            self.fields['borrower_user'].queryset = User.objects.filter(
                is_active=True
            ).order_by('first_name', 'last_name', 'username')


class ArchiveLoanDeliverForm(forms.Form):
    delivery_observation = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Observacion de entrega'})
    )


class ArchiveLoanReturnReportForm(forms.Form):
    return_observation = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Observacion de devolucion'})
    )


class ArchiveLoanReturnValidationForm(forms.Form):
    validation_observation = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Observacion de validacion'})
    )
