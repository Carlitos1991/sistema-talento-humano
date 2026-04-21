from django import forms
from .models import Document, DocumentType

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['filing_code', 'category', 'sender_name', 'recipient_name', 'subject', 'file_attachment', 'observation']
        widgets = {
            'filing_code': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control select2', 'style': 'width: 100%'}),
            'sender_name': forms.TextInput(attrs={'class': 'form-control'}),
            'recipient_name': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'file_attachment': forms.FileInput(attrs={'class': 'form-control'}),
            'observation': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure recipient_name is required at form level (server-side validation)
        if 'recipient_name' in self.fields:
            self.fields['recipient_name'].required = True

class DocumentTypeForm(forms.ModelForm):
    class Meta:
        model = DocumentType
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Oficio, Memorando...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }