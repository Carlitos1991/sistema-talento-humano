# apps/budget/forms.py

from django import forms
from core.forms import BaseFormMixin
from core.models import CatalogItem
from .models import BudgetLine, Program, Subprogram, Project, Activity


class UppercaseFormMixin:
    """Mixin para convertir todos los CharField y TextField a mayúsculas automáticamente"""

    def clean(self):
        cleaned_data = super().clean()
        for field_name, value in cleaned_data.items():
            if isinstance(value, str):
                cleaned_data[field_name] = value.strip().upper()
        return cleaned_data


class BudgetLineForm(UppercaseFormMixin, BaseFormMixin, forms.ModelForm):
    # Campos auxiliares para la cascada (No se guardan en BudgetLine, sirven para filtrar Activity)
    program = forms.ModelChoiceField(
        queryset=Program.objects.filter(is_active=True),
        label="Área / Programa",
        required=False
    )
    subprogram = forms.ModelChoiceField(queryset=Subprogram.objects.none(), label="Subprograma", required=False)
    project = forms.ModelChoiceField(queryset=Project.objects.none(), label="Proyecto", required=False)

    class Meta:
        model = BudgetLine
        fields = [
            'program', 'subprogram', 'project', 'activity',
            'code', 'remuneration',
            'regime_item', 'group_item', 'category_item', 'position_item',
            'grade_item', 'spending_type_item', 'observation'
        ]
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'input-field readonly-styled',
                'placeholder': 'Generación automática',
                'id': 'id_code'
            }),
            'remuneration': forms.NumberInput(attrs={'class': 'input-field', 'step': '0.01', 'placeholder': 'Ej: 901'}),
            'observation': forms.Textarea(attrs={'class': 'input-field', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. CARGA DE CATÁLOGOS (Gasto y Régimen)
        # Cargamos los QuerySets completos pero los deshabilitamos visualmente
        # para que Select2 TENGA los datos pero no permita usarlos hasta el turno correcto.
        self.fields['spending_type_item'].queryset = CatalogItem.objects.filter(
            catalog__code='BUDGET_SPENDING_TYPE', is_active=True
        ).order_by('code')

        self.fields['regime_item'].queryset = CatalogItem.objects.filter(
            catalog__code='LABOR_REGIMES', is_active=True
        ).order_by('code')

        # Formato de label para que el JS haga el split(' - ') y obtenga solo el código numérico
        self.fields['spending_type_item'].label_from_instance = lambda obj: f"{obj.code} - {obj.name}"
        self.fields['regime_item'].label_from_instance = lambda obj: f"{obj.code} - {obj.name}"

        # Atributos de seguridad e ID para el JavaScript
        self.fields['code'].widget.attrs['readonly'] = True

        # Bloqueo inicial: Se habilitarán secuencialmente vía budget.js
        self.fields['spending_type_item'].widget.attrs['disabled'] = True
        self.fields['regime_item'].widget.attrs['disabled'] = True

        # 2. LÓGICA DE CASCADA (RE-POBLAR EN CASO DE POST O EDICIÓN)
        self.fields['subprogram'].queryset = Subprogram.objects.none()
        self.fields['project'].queryset = Project.objects.none()
        self.fields['activity'].queryset = Activity.objects.none()

        # A. Manejo de datos POST (Fallas de validación)
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

        # B. Manejo en modo EDICIÓN
        elif self.instance.pk and hasattr(self.instance, 'activity') and self.instance.activity:
            activity = self.instance.activity
            project = activity.project
            subprogram = project.subprogram
            program = subprogram.program

            self.fields['program'].initial = program
            self.fields['subprogram'].queryset = Subprogram.objects.filter(program=program).order_by('code')
            self.fields['subprogram'].initial = subprogram

            self.fields['project'].queryset = Project.objects.filter(subprogram=subprogram).order_by('code')
            self.fields['project'].initial = project

            self.fields['activity'].queryset = Activity.objects.filter(project=project).order_by('code')
            self.fields['activity'].initial = activity

            # Habilitar campos si ya tienen valor (Edición)
            self.fields['spending_type_item'].widget.attrs.pop('disabled', None)
            self.fields['regime_item'].widget.attrs.pop('disabled', None)

    def clean_remuneration(self):
        data = self.cleaned_data['remuneration']
        if data <= 0:
            raise forms.ValidationError("El RMU debe ser mayor a 0.")
        return data


# --- FORMULARIOS DE ESTRUCTURA ---

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


# --- HELPERS Y ACCIONES ---

def block_parent_field(form, field_name, parent_id):
    if field_name in form.fields:
        if parent_id:
            form.fields[field_name].initial = parent_id
        form.fields[field_name].widget.attrs['readonly'] = True
        form.fields[field_name].widget.attrs['style'] = 'pointer-events: none; background-color: #f1f5f9; opacity: 0.8;'


class AssignIndividualNumberForm(forms.Form):
    number = forms.IntegerField(
        label="Número de Partida Individual",
        min_value=1, max_value=9999,
        widget=forms.NumberInput(attrs={
            'class': 'input-field',
            'placeholder': 'Ej: 1, 25, 150',
            'id': 'id_individual_number_input'
        })
    )

    def clean_number(self):
        number = self.cleaned_data['number']
        formatted_number = str(number).zfill(4)
        if BudgetLine.objects.filter(number_individual=formatted_number).exists():
            raise forms.ValidationError("Este número ya ha sido asignado a otra partida.")
        return formatted_number


class BudgetChangeStatusForm(forms.Form):
    new_status = forms.ModelChoiceField(
        queryset=CatalogItem.objects.filter(catalog__code='BUDGET_STATUS').exclude(code__in=['LIBRE', 'OCUPADA']),
        label="Nuevo Estado",
        empty_label="Seleccione un estado",
        widget=forms.Select(attrs={'class': 'input-field select2-field'})
    )
    observation = forms.CharField(
        label="Observaciones", required=False,
        widget=forms.Textarea(attrs={'class': 'input-field', 'rows': 3, 'placeholder': 'Motivo del cambio...'})
    )
