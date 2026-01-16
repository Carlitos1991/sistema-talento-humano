from django import forms
from .models import Competency

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