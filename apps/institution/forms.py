from django import forms
from core.forms import BaseFormMixin
from employee.models import Employee
from .models import AdministrativeUnit, OrganizationalLevel, Deliverable


class AdministrativeUnitForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = AdministrativeUnit
        fields = ['name', 'level', 'parent', 'boss', 'code', 'address', 'phone']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: Dirección Financiera'
            }),
            'level': forms.Select(attrs={
                'class': 'input-field',
            }),
            'parent': forms.Select(attrs={
                'class': 'input-field',
            }),
            'boss': forms.Select(attrs={
                'class': 'input-field select2-ajax',
                'data-placeholder': 'Escriba para buscar empleado...',
            }),
            'code': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: FIN-001'
            }),
            'address': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ubicación física de la oficina'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Extensión o directo'
            }),
        }
        labels = {
            'name': 'Nombre de la Unidad',
            'level': 'Nivel Jerárquico',
            'parent': 'Unidad Padre (Dependencia)',
            'boss': 'Jefe / Responsable',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Lógica para el campo 'parent' (Optimización de QuerySet)
        self.fields['parent'].queryset = AdministrativeUnit.objects.none()

        # Caso A: Envío de datos (POST) con valor seleccionado
        if 'parent' in self.data and self.data.get('parent'):
            try:
                parent_id = int(self.data.get('parent'))
                self.fields['parent'].queryset = AdministrativeUnit.objects.filter(pk=parent_id)
            except (ValueError, TypeError):
                pass
        # Caso B: Edición (Instancia existente con padre)
        elif self.instance.pk and self.instance.parent:
            self.fields['parent'].queryset = AdministrativeUnit.objects.filter(pk=self.instance.parent.pk)

        # 2. Lógica para 'boss' (Select2 AJAX - Carga vacía inicial)
        self.fields['boss'].queryset = Employee.objects.none()
        self.fields['boss'].required = False
        if 'boss' in self.data and self.data.get('boss'):
            try:
                boss_id = int(self.data.get('boss'))
                self.fields['boss'].queryset = Employee.objects.filter(pk=boss_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.boss:
            self.fields['boss'].queryset = Employee.objects.filter(pk=self.instance.boss.pk)

        if self.instance.pk:
            self.fields['level'].disabled = True
            self.fields['level'].required = False


class OrganizationalLevelForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = OrganizationalLevel
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ej: DIRECCIÓN GENERAL', 'class': 'uppercase-input'}),
        }
        labels = {
            'name': 'Nombre del Nivel',
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            return name.upper()
        return name

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.pk:
            active_orders = set(
                OrganizationalLevel.objects.filter(is_active=True)
                .values_list('level_order', flat=True)
            )
            next_order = 1
            while next_order in active_orders:
                next_order += 1
            instance.level_order = next_order
            instance.is_active = True
        if commit:
            instance.save()
        return instance


class DeliverableForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Deliverable
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ej: Reporte Mensual de Nómina', 'class': 'input-field'}),
            'description': forms.Textarea(
                attrs={'placeholder': 'Detalle los requisitos del entregable...', 'rows': 3, 'class': 'input-field'}),
        }