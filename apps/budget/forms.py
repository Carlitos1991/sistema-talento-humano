from django import forms
from apps.core.forms import BaseFormMixin
from apps.core.models import CatalogItem
from .models import BudgetLine, Program, Subprogram, Project, Activity


class UppercaseFormMixin:
    """Mixin para convertir todos los CharField y TextField a mayúsculas automáticamente"""

    def clean(self):
        cleaned_data = super().clean()
        for field_name, value in cleaned_data.items():
            if isinstance(value, str):
                cleaned_data[field_name] = value.strip().upper()
        return cleaned_data


class BudgetLineForm(BaseFormMixin, forms.ModelForm):
    program = forms.ModelChoiceField(queryset=Program.objects.filter(is_active=True), label="Área / Programa",
                                     required=False)
    subprogram = forms.ModelChoiceField(queryset=Subprogram.objects.none(), label="Subprograma", required=False)
    project = forms.ModelChoiceField(queryset=Project.objects.none(), label="Proyecto", required=False)

    class Meta:
        model = BudgetLine
        fields = [
            'program', 'subprogram', 'project', 'activity',  # Jerarquía
            'number_individual', 'code', 'status_item', 'remuneration',  # Identificación
            'regime_item', 'group_item', 'category_item', 'position_item', 'grade_item', 'spending_type_item',
            # Clasificación
            'observation'
        ]
        widgets = {
            'number_individual': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Ej: 1050'}),
            'code': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Ej: 51.01.05'}),
            'remuneration': forms.NumberInput(attrs={'class': 'input-field', 'step': '0.01'}),
            'observation': forms.Textarea(attrs={'class': 'input-field', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Configuración inicial de QuerySets vacíos para hijos
        self.fields['subprogram'].queryset = Subprogram.objects.none()
        self.fields['project'].queryset = Project.objects.none()
        self.fields['activity'].queryset = Activity.objects.none()
        self.fields['code'].widget.attrs['readonly'] = True
        self.fields['code'].widget.attrs['class'] = 'input-field readonly-styled'
        # 2. Lógica de Python para repoblar combos en caso de error o edición
        # Esto asegura que si falla la validación, los combos no se vacíen

        # A. Si hay datos POST (intento de envío o cambio de cascada)
        if 'program' in self.data:
            try:
                program_id = int(self.data.get('program'))
                self.fields['subprogram'].queryset = Subprogram.objects.filter(program_id=program_id).order_by('code')
            except (ValueError, TypeError):
                pass

        if 'subprogram' in self.data:
            try:
                sub_id = int(self.data.get('subprogram'))
                self.fields['project'].queryset = Project.objects.filter(subprogram_id=sub_id).order_by('code')
            except (ValueError, TypeError):
                pass

        if 'project' in self.data:
            try:
                proj_id = int(self.data.get('project'))
                self.fields['activity'].queryset = Activity.objects.filter(project_id=proj_id).order_by('code')
            except (ValueError, TypeError):
                pass

        # B. Si estamos EDITANDO una instancia existente
        elif self.instance.pk and self.instance.activity:
            activity = self.instance.activity
            project = activity.project
            subprogram = project.subprogram
            program = subprogram.program

            # Pre-cargar los valores en los campos auxiliares
            self.fields['program'].initial = program
            self.fields['subprogram'].queryset = Subprogram.objects.filter(program=program).order_by('code')
            self.fields['subprogram'].initial = subprogram

            self.fields['project'].queryset = Project.objects.filter(subprogram=subprogram).order_by('code')
            self.fields['project'].initial = project

            self.fields['activity'].queryset = Activity.objects.filter(project=project).order_by('code')
            self.fields['activity'].initial = activity

    def clean_remuneration(self):
        """Ejemplo de validación estricta en Python"""
        data = self.cleaned_data['remuneration']
        if data <= 0:
            raise forms.ValidationError("El RMU debe ser mayor a 0.")
        return data


class ProgramForm(UppercaseFormMixin, BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Program
        fields = ['code', 'name']


class SubprogramForm(UppercaseFormMixin, BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Subprogram
        fields = ['program', 'code', 'name']


class ProjectForm(UppercaseFormMixin, BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = ['subprogram', 'code', 'name']


class ActivityForm(UppercaseFormMixin, BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Activity
        fields = ['project', 'code', 'name']


def block_parent_field(form, field_name, parent_id):
    if field_name in form.fields:
        if parent_id:
            form.fields[field_name].initial = parent_id
        form.fields[field_name].widget.attrs['readonly'] = True
        form.fields[field_name].widget.attrs['style'] = 'pointer-events: none; background-color: #f1f5f9; opacity: 0.8;'
