from django import forms

from core.models import User

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
            'request_observation': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Observacion de solicitud'})
        }


class ArchiveManualLoanForm(forms.ModelForm):
    class Meta:
        model = EmployeeArchiveLoan
        fields = ['borrower_user', 'delivery_observation']
        widgets = {
            'delivery_observation': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Observacion de prestamo manual'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['borrower_user'].queryset = User.objects.filter(is_active=True).order_by('username')
        self.fields['borrower_user'].widget.attrs.update({'class': 'form-control'})


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
