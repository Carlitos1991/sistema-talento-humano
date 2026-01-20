from django import forms
from .models import Competency, ManualCatalog, ManualCatalogItem, ValuationNode


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
    target_role = forms.ModelChoiceField(
        queryset=ValuationNode.objects.none(),
        required=False,
        label='Rol Permitido',
        widget=forms.Select(attrs={
            'class': 'form-control select2-roles',
            'id': 'id_target_role'
        }),
        empty_label='Seleccione un rol...'
    )
    
    class Meta:
        model = ManualCatalogItem
        fields = ['name', 'code', 'description', 'target_role']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Analizar'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: ANALIZAR'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Obtener nodos ROLE con sus nombres legibles
        role_nodes = ValuationNode.objects.filter(
            node_type='ROLE', 
            is_active=True
        ).select_related('catalog_item').order_by('catalog_item__name')
        
        self.fields['target_role'].queryset = role_nodes
        # Personalizar la representación de cada opción
        self.fields['target_role'].label_from_instance = lambda obj: obj.catalog_item.name if obj.catalog_item else f"Rol #{obj.id}"

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            return code.upper().replace(' ', '_')
        return code
