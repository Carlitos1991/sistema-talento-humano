from .models import Document, DocumentType, Procedure
from django import forms
from cryptography.hazmat.primitives.serialization import pkcs12
from core.models import User
from .models import Document, DocumentType, Procedure
from .models import UserSignatureProfile


class UserSignatureUploadForm(forms.ModelForm):
    signature_file = forms.FileField(
        required=True,
        widget=forms.FileInput(attrs={'class': 'input-field', 'accept': '.p12,.pfx'}),
        label="Archivo de Firma (.p12 / .pfx)"
    )
    signature_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'input-field', 'placeholder': 'Contraseña del certificado'}),
        label="Contraseña"
    )

    class Meta:
        model = UserSignatureProfile
        fields = []

    def clean(self):
        cleaned_data = super().clean()
        sig_file = cleaned_data.get('signature_file')
        password = cleaned_data.get('signature_password')

        if sig_file and password:
            try:
                p12_data = sig_file.read()
                # Rebobinar el puntero para que Django luego lo pueda guardar en disco
                sig_file.seek(0)

                # Carga e inspección exclusiva en memoria
                private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                    p12_data,
                    password.encode('utf-8')
                )

                if certificate is None:
                    raise forms.ValidationError("El archivo no contiene un certificado X.509 válido.")

                # Extraer atributos
                subject = certificate.subject.rfc4514_string()
                issuer = certificate.issuer.rfc4514_string()
                serial_number = str(certificate.serial_number)
                valid_from = certificate.not_valid_before_utc
                valid_to = certificate.not_valid_after_utc

                cleaned_data['cert_info'] = {
                    'subject_dn': subject,
                    'issuer': issuer,
                    'serial_number': serial_number,
                    'valid_from': valid_from,
                    'valid_to': valid_to,
                }

            except ValueError:
                raise forms.ValidationError("Contraseña incorrecta o archivo de certificado dañado.")
            except Exception as e:
                raise forms.ValidationError(f"Error procesando la firma electrónica: {str(e)}")

        return cleaned_data


class UserProfileSettingsForm(forms.ModelForm):
    """
    Permite al servidor actualizar su nombre personalizado de firma.
    """

    class Meta:
        model = User
        fields = ['custom_name']
        widgets = {
            'custom_name': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: Ing. Carlos Chacha G.'
            })
        }


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            'filing_code', 'category', 'sender_name',
            'recipient_name', 'subject', 'file_attachment', 'observation'
        ]
        widgets = {
            'filing_code': forms.TextInput(attrs={
                'class': 'input-field readonly-styled',
                'readonly': 'readonly'
            }),
            'category': forms.Select(attrs={
                'class': 'input-field form-control select2',
                'style': 'width: 100%'
            }),
            'sender_name': forms.TextInput(attrs={
                'class': 'input-field readonly-styled',
                'readonly': 'readonly',
                'placeholder': 'Responsable / Remitente'
            }),
            'recipient_name': forms.TextInput(attrs={
                'class': 'input-field',
                'required': 'required',
                'maxlength': '255',
                'placeholder': 'Nombre o cargo a quien va dirigido'
            }),
            'subject': forms.TextInput(attrs={
                'class': 'input-field',
                'required': 'required',
                'maxlength': '255',
                'placeholder': 'Breve descripción del asunto'
            }),
            'file_attachment': forms.FileInput(attrs={
                'class': 'input-field form-control',
                'accept': '.pdf'
            }),
            'observation': forms.Textarea(attrs={
                'class': 'form-control input-textarea',
                'rows': 3,
                'placeholder': 'Observaciones adicionales'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recipient_name'].required = True
        self.fields['subject'].required = True
        self.fields['sender_name'].required = False

    def clean_sender_name(self):
        if self.instance and self.instance.pk:
            return self.instance.sender_name
        return self.cleaned_data.get('sender_name')


class DocumentTypeForm(forms.ModelForm):
    class Meta:
        model = DocumentType
        fields = ['name', 'code_prefix', 'is_external', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field form-control',
                'placeholder': 'Ej: Memorando, Oficio, Informe Técnico'
            }),
            'code_prefix': forms.TextInput(attrs={
                'class': 'input-field form-control',
                'placeholder': 'Ej: MEM, OFI, INF'
            }),
            'is_external': forms.CheckboxInput(attrs={
                'class': 'switch-input switch-blue'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'switch-input switch-green'
            }),
        }


class DelegateTaskForm(forms.Form):
    """
    Formulario para la sumilla y delegación de tareas (individual o compartida).
    """
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={
            'class': 'input-field form-control select2',
            'style': 'width: 100%'
        }),
        label="Funcionario Responsable",
        required=True
    )
    instruction = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'input-field',
            'placeholder': 'Ej: Para informe técnico, revisión previa, contestar...',
            'required': 'required'
        }),
        label="Instrucción Principal"
    )
    days_limit = forms.IntegerField(
        initial=3,
        min_value=1,
        max_value=30,
        widget=forms.NumberInput(attrs={
            'class': 'input-field',
            'required': 'required'
        }),
        label="Días Plazo"
    )
    is_main_task = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label="Es Responsable Principal (Consolida la respuesta)"
    )
    observation = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Texto detallado de la sumilla o proveído...'
        }),
        label="Texto de la Sumilla",
        required=False
    )

    def __init__(self, *args, **kwargs):
        unit = kwargs.pop('unit', None)
        super().__init__(*args, **kwargs)
        if unit:
            from employee.models import Employee
            # Empleados adscritos al área asignada
            employees = Employee.objects.filter(area=unit, is_active=True).select_related('person')
            user_ids = []
            for emp in employees:
                # Localizar el usuario técnico asociado a la persona
                user = User.objects.filter(person=emp.person, is_active=True).first()
                if user:
                    user_ids.append(user.id)
            self.fields['assigned_to'].queryset = User.objects.filter(id__in=user_ids)


class ProcedureReceptionForm(forms.ModelForm):
    """
    Formulario de Ventanilla / Recepción para registrar documentos u oficios externos.
    """
    scanned_file = forms.FileField(
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'input-field form-control',
            'accept': '.pdf',
            'required': 'required'
        }),
        label="Documento Escaneado (PDF obligatorio)"
    )

    class Meta:
        model = Procedure
        fields = [
            'category', 'external_number', 'external_sender',
            'external_id_card', 'external_email', 'priority', 'subject'
        ]
        widgets = {
            'category': forms.Select(attrs={
                'class': 'input-field form-control select2',
                'style': 'width: 100%'
            }),
            'external_number': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: OFI-2026-089-GAD'
            }),
            'external_sender': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Nombre de la persona, dependencia o institución remitente',
                'required': 'required'
            }),
            'external_id_card': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Cédula o RUC (Opcional)'
            }),
            'external_email': forms.EmailInput(attrs={
                'class': 'input-field',
                'placeholder': 'correo@notificacion.gob.ec'
            }),
            'priority': forms.Select(attrs={
                'class': 'input-field form-control'
            }),
            'subject': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Descripción clara del trámite solicitado',
                'required': 'required'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = DocumentType.objects.filter(
            is_external=True,
            is_active=True
        ).order_by('name')
        self.fields['external_sender'].required = True
        self.fields['subject'].required = True
