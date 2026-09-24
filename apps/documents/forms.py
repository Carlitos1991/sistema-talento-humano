from django import forms
from .models import Document, DocumentType


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
        # Obligatoriedad estricta y límite a nivel de campo Django
        self.fields['recipient_name'].required = True
        self.fields['recipient_name'].max_length = 255

        self.fields['subject'].required = True
        self.fields['subject'].max_length = 255

        # 'sender_name' no requiere entrada obligatoria del usuario ya que es readonly
        self.fields['sender_name'].required = False

    def clean_sender_name(self):
        """
        Protección en backend: si es edición conserva el valor existente,
        o mantiene el valor cargado por la vista evitando manipulaciones desde el inspector.
        """
        if self.instance and self.instance.pk:
            return self.instance.sender_name
        return self.cleaned_data.get('sender_name')


class DocumentTypeForm(forms.ModelForm):
    class Meta:
        model = DocumentType
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field form-control',
                'placeholder': 'Ej: Oficio, Memorando...'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
