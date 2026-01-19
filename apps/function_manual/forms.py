from django import forms
from .models import Competency, ManualCatalog, ManualCatalogItem


class CompetencyForm(forms.ModelForm):
    class Meta:
        model = Competency
        fields = ['name', 'type', 'definition', 'suggested_level']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la competencia'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'definition': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'suggested_level': forms.Select(attrs={'class': 'form-control select2'}),
        }


class ManualCatalogForm(forms.ModelForm):
    """
    Formulario para creación y edición de Catálogos del Manual de Funciones.
    """

    class Meta:
        model = ManualCatalog
        fields = ['name', 'code', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Niveles de Complejidad'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: COMPLEXITY_LEVELS'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción opcional del catálogo'
            }),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            return code.upper().replace(' ', '_')
        return code


class ManualCatalogItemForm(forms.ModelForm):
    class Meta:
        model = ManualCatalogItem
        # Agregamos target_groups a los campos
        fields = ['name', 'code', 'description', 'target_groups']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Analizar'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: ANALIZAR'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            # Estilo para el nuevo campo
            'target_groups': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: SP1,SP2,SP3 o TODOS'
            }),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            return code.upper().replace(' ', '_')
        return code
