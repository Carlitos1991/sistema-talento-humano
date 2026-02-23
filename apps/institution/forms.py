from django import forms
from core.forms import BaseFormMixin
from employee.models import Employee
from .models import AdministrativeUnit, OrganizationalLevel, Deliverable, InstitutionOrganigram


class AdministrativeUnitForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = AdministrativeUnit
        fields = ['name', 'level', 'parent', 'boss', 'code', 'address', 'phone', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Ej: Dirección Financiera'}),
            'code': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Generado automáticamente'}),
            'address': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Ubicación física'}),
            'phone': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Extensión'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'toggle-slider', 'role': 'switch'}),

            # CAMPOS OCULTOS
            'level': forms.HiddenInput(),
            'parent': forms.HiddenInput(),
            'boss': forms.HiddenInput(),
        }
        labels = {
            'name': 'Nombre de la Unidad',
            'code': 'Código / Partida (Único)',
            'address': 'Ubicación',
            'phone': 'Teléfono',
            'is_active': 'Estado'
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        # Validación de unicidad manual para mensaje personalizado
        if code:
            # Excluimos la propia instancia si estamos editando
            qs = AdministrativeUnit.objects.filter(code=code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError(f"El código '{code}' ya pertenece a otra unidad administrativa.")
        return code

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['boss'].required = False
        self.fields['parent'].required = False
        self.fields['level'].required = True


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


class OrganigramForm(BaseFormMixin, forms.ModelForm):
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


class AssignBossForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = AdministrativeUnit
        fields = ['boss']
        widgets = {
            'boss': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_boss_assign',
                'data-placeholder': 'Buscar empleado...',
                'data-ajax-url': '/institution/api/employee/search/',
                'data-minimum-input-length': '3',
                'data-allow-clear': 'true',
                'style': 'width:100%'
            }),
        }
        labels = {
            'boss': 'Seleccione Funcionario Responsable'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar el jefe actual si existe, si no, queryset vacío
        boss_qs = Employee.objects.none()
        boss_id = None
        if self.instance and self.instance.boss:
            boss_id = self.instance.boss.pk
            boss_qs = Employee.objects.filter(pk=boss_id)
        # Si viene un valor por POST (Select2), incluirlo también
        data = kwargs.get('data') or getattr(self, 'data', None)
        if data and data.get('boss'):
            try:
                post_boss_id = int(data.get('boss'))
                if not boss_qs.filter(pk=post_boss_id).exists():
                    boss_qs = Employee.objects.filter(pk__in=filter(None, [boss_id, post_boss_id]))
            except Exception:
                pass
        self.fields['boss'].queryset = boss_qs
