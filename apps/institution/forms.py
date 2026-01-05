from django import forms
from apps.core.forms import BaseFormMixin
from apps.employee.models import Employee
from .models import AdministrativeUnit, OrganizationalLevel


# --- FORMULARIO DE UNIDADES (Se mantiene igual) ---
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
        
        # Configurar queryset de parent
        self.fields['parent'].queryset = AdministrativeUnit.objects.none()
        if 'parent' in self.data:
            try:
                parent_id = int(self.data.get('parent'))
                self.fields['parent'].queryset = AdministrativeUnit.objects.filter(pk=parent_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.parent:
            self.fields['parent'].queryset = AdministrativeUnit.objects.filter(pk=self.instance.parent.pk)

        # Configurar queryset de boss - VACIO para carga con AJAX
        self.fields['boss'].queryset = Employee.objects.none()
        self.fields['boss'].required = False
        
        # Si estamos editando y hay un jefe asignado, cargarlo
        if self.instance.pk and self.instance.boss:
            self.fields['boss'].queryset = Employee.objects.filter(pk=self.instance.boss.pk)


# --- FORMULARIO DE NIVELES (CORREGIDO) ---
class OrganizationalLevelForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = OrganizationalLevel
        # SOLO el nombre. El orden es automático y no debe estar aquí.
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ej: DIRECCIÓN GENERAL', 'class': 'uppercase-input'}),
        }
        labels = {
            'name': 'Nombre del Nivel',
        }

    def clean_name(self):
        """Guardar siempre en Mayúsculas"""
        name = self.cleaned_data.get('name')
        if name:
            return name.upper()
        return name

    def save(self, commit=True):
        """
        Calcula automáticamente el orden jerárquico al guardar.
        """
        instance = super().save(commit=False)

        # Solo si es nuevo (no tiene ID), calculamos su orden
        if not instance.pk:
            # 1. Obtener órdenes ocupados en registros ACTIVOS
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
