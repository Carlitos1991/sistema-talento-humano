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
    # Campo auxiliar para seleccionar Roles cuando se trata de Verbos
    roles = forms.ModelMultipleChoiceField(
        queryset=ManualCatalogItem.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2', 'multiple': 'multiple'}),
        label="Roles aplicables (Para Verbos de Acción)"
    )

    class Meta:
        model = ManualCatalogItem
        fields = ['name', 'code', 'description', 'target_groups']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Analizar'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: ANALIZAR'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'target_groups': forms.HiddenInput(),  # Ocultamos el input original
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar roles disponibles
        self.fields['roles'].queryset = ManualCatalogItem.objects.filter(
            catalog__code='JOB_ROLES', is_active=True
        )

        # Si estamos editando y hay target_groups con datos
        if self.instance.pk and self.instance.target_groups:
            # Intentar parsear los IDs
            try:
                # Si es "TODOS" o "SP1", no se marcará nada en el select de IDs, 
                # lo cual es correcto pues estamos migrando la lógica.
                # Solo si son IDs numéricos se seleccionarán.
                ids = [int(x) for x in self.instance.target_groups.split(',') if x.strip().isdigit()]
                self.fields['roles'].initial = ids
            except ValueError:
                pass

    def clean(self):
        cleaned_data = super().clean()
        roles = cleaned_data.get('roles')
        
        # Si se seleccionaron roles, guardarlos como string separado por comas
        if roles:
            ids = [str(r.id) for r in roles]
            cleaned_data['target_groups'] = ",".join(ids)
        else:
            # Si no se selecciona nada, asumimos vacío (o mantén TODOS si era la intención, pero aquí limpiamos)
            # Verifica si el usuario quiere mantener el valor original si no toca los roles?
            # En un form post, si roles está vacío, significa que deseleccionó todo.
            # Pero si target_groups tenía "TODOS" (legacy), lo perderemos. Es aceptable.
            cleaned_data['target_groups'] = ""
        
        return cleaned_data

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            return code.upper().replace(' ', '_')
        return code
