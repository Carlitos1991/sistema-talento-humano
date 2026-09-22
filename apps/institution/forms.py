"""
Módulo de Formularios para Gestión Institucional (SIGETH).
Contiene formularios para Unidades Administrativas, Niveles Organizacionales,
Entregables, Organigrama Institucional y Asignación de Jefes Inmediatos.
"""

from django import forms

from core.forms import BaseFormMixin
from employee.models import Employee
from .models import (
    AdministrativeUnit,
    OrganizationalLevel,
    Deliverable,
    InstitutionOrganigram
)


# ==============================================================================
# 1. FORMULARIO DE UNIDAD ADMINISTRATIVA
# ==============================================================================
class AdministrativeUnitForm(BaseFormMixin, forms.ModelForm):
    """
    Formulario para creación y actualización de unidades administrativas.
    Incluye validación de código único y control de jerarquía de niveles.
    """

    class Meta:
        model = AdministrativeUnit
        fields = [
            'name',
            'level',
            'parent',
            'boss',
            'code',
            'address',
            'phone',
            'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Ej: DIRECCIÓN GENERAL',
                'class': 'uppercase-input input-field',
                'style': 'text-transform: uppercase;',
                'oninput': 'this.value = this.value.toUpperCase();'
            }),
            'code': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Generado automáticamente'
            }),
            'address': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ubicación física'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Extensión'
            }),
            'level': forms.HiddenInput(),
            'parent': forms.HiddenInput(),
            'boss': forms.HiddenInput(),
            'is_active': forms.HiddenInput(),
        }
        labels = {
            'name': 'Nombre de la Unidad',
            'code': 'Código / Partida (Único)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Los campos jerárquicos y de jefatura se gestionan mediante modales contextuales
        self.fields['boss'].required = False
        self.fields['parent'].required = False
        self.fields['level'].required = False

    def clean_code(self):
        """Valida que el código no esté repetido entre unidades activas."""
        code = self.cleaned_data.get('code')
        if code:
            qs = AdministrativeUnit.objects.filter(code=code, is_active=True)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f"El código '{code}' ya pertenece a otra unidad administrativa."
                )
        return code

    def clean(self):
        """Mantiene el nivel jerárquico previo en caso de edición parcial."""
        cleaned_data = super().clean()
        level = cleaned_data.get('level')
        if level is None and self.instance.pk:
            cleaned_data['level'] = self.instance.level
        return cleaned_data


# ==============================================================================
# 2. FORMULARIO DE NIVEL JERÁRQUICO
# ==============================================================================
class OrganizationalLevelForm(BaseFormMixin, forms.ModelForm):
    """
    Formulario para creación y edición de niveles organizacionales.
    Asigna correlativamente el orden jerárquico (level_order) al crear un nuevo nivel.
    """

    class Meta:
        model = OrganizationalLevel
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Ej: DIRECCIÓN GENERAL',
                'class': 'uppercase-input input-field',
                'style': 'text-transform: uppercase;',
                'oninput': 'this.value = this.value.toUpperCase();'
            }),
        }
        labels = {
            'name': 'Nombre del Nivel',
        }
        error_messages = {
            'name': {
                'unique': 'Ya existe un nivel jerárquico con este nombre.'
            }
        }

    def clean_name(self):
        """Fuerza el nombre del nivel a mayúsculas."""
        name = self.cleaned_data.get('name')
        return name.upper() if name else name

    def save(self, commit=True):
        """Calcula el siguiente level_order disponible si se trata de un registro nuevo."""
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


# ==============================================================================
# 3. FORMULARIO DE ENTREGABLES (DELIVERABLES)
# ==============================================================================
class DeliverableForm(BaseFormMixin, forms.ModelForm):
    """
    Formulario de entregables asociados a una unidad administrativa.
    Inyecta placeholders y estilos de manera explícita en __init__ para
    asegurar consistencia visual frente al mixin base.
    """

    class Meta:
        model = Deliverable
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Ej: Reporte Mensual de Nómina',
                'autocomplete': 'off'
            }),
            'description': forms.Textarea(attrs={
                'class': 'input-field',
                'placeholder': 'Detalle los requisitos y especificaciones del entregable...',
                'rows': 3
            }),
        }
        labels = {
            'name': 'Nombre del Entregable',
            'description': 'Descripción / Alcance'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forzar atributos para evitar que BaseFormMixin los sobrescriba
        self.fields['name'].widget.attrs.update({
            'class': 'input-field',
            'placeholder': 'Ej: Reporte Mensual de Nómina',
            'autocomplete': 'off'
        })
        self.fields['description'].widget.attrs.update({
            'class': 'input-field',
            'placeholder': 'Detalle los requisitos y especificaciones del entregable...',
            'rows': '3'
        })


# ==============================================================================
# 4. FORMULARIO DE ORGANIGRAMA
# ==============================================================================
class OrganigramForm(BaseFormMixin, forms.ModelForm):
    """Formulario para la carga del organigrama gráfico institucional."""

    class Meta:
        model = InstitutionOrganigram
        fields = ['image']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'id': 'file-input-organigram'
            })
        }
        labels = {
            'image': 'Imagen del Organigrama'
        }


# ==============================================================================
# 5. FORMULARIO DE ASIGNACIÓN DE JEFE INMEDIATO
# ==============================================================================
class AssignBossForm(BaseFormMixin, forms.ModelForm):
    """
    Formulario AJAX para asignar el responsable directo a una unidad.
    Optimiza el queryset cargando únicamente el jefe actual y el seleccionado en POST,
    evitando la carga en memoria de miles de registros de empleados.
    """

    class Meta:
        model = AdministrativeUnit
        fields = ['boss']
        widgets = {
            'boss': forms.Select(attrs={
                'class': 'form-control select2',
                'id': 'id_boss_assign',
                'data-placeholder': 'Buscar empleado...',
                'data-ajax-url': '/institution/api/employee/search/',
                'data-minimum-input-length': '3',
                'data-allow-clear': 'true',
                'style': 'width: 100%;'
            }),
        }
        labels = {
            'boss': 'Seleccione Funcionario Responsable'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Carga optimizada: Si no se está enviando el formulario, solo busca el jefe actual
        boss_ids = []
        if self.instance and self.instance.boss_id:
            boss_ids.append(self.instance.boss_id)

        data = kwargs.get('data') or getattr(self, 'data', None)
        if data and data.get('boss'):
            try:
                posted_boss_id = int(data.get('boss'))
                if posted_boss_id not in boss_ids:
                    boss_ids.append(posted_boss_id)
            except (ValueError, TypeError):
                pass

        if boss_ids:
            self.fields['boss'].queryset = Employee.objects.filter(
                pk__in=boss_ids
            ).select_related('person')
        else:
            self.fields['boss'].queryset = Employee.objects.none()
