# apps/person/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat

from budget.models import BudgetLine
from core.models import CatalogItem
from employee.models import Employee, InstitutionalData
from institution.models import AdministrativeUnit
from .models import Person
from .forms import PersonForm


class PersonListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Person
    template_name = 'person/person_list.html'
    context_object_name = 'people'
    paginate_by = 10
    permission_required = 'person.view_person'

    def paginate_queryset(self, queryset, page_size):
        """Nunca lanza EmptyPage — corrige page fuera de rango."""
        paginator = self.get_paginator(queryset, page_size)
        try:
            page_num = int(self.request.GET.get('page', 1))
        except (ValueError, TypeError):
            page_num = 1
        # Clamp: nunca menor que 1, nunca mayor que el total
        page_num = max(1, min(page_num, paginator.num_pages or 1))
        page = paginator.page(page_num)
        return paginator, page, page.object_list, page.has_other_pages()

    def get_queryset(self):
        # 1. Base Query con optimización y ANOTACIÓN de Nombre Completo
        qs = Person.objects.select_related(
            'document_type',
            'user',
            'employee_profile__area',
            'employee_profile__employment_status',
            'marital_status'  # Agregamos esto para optimizar
        ).annotate(
            full_name_str=Concat('first_name', Value(' '), 'last_name', output_field=CharField())
        ).order_by('last_name')

        # --- BÚSQUEDA RÁPIDA (Parámetro 'q' como en usuarios) ---
        q = self.request.GET.get('q')

        # --- BÚSQUEDA AVANZADA (Filtros Backend) ---
        # Recogemos parámetros
        cedula = self.request.GET.get('cedula')
        nombres = self.request.GET.get('nombres')
        area_id = self.request.GET.get('area')
        status_id = self.request.GET.get('status')
        marital_id = self.request.GET.get('marital_status')
        gender_id = self.request.GET.get('gender')

        # Detectar si hay búsqueda avanzada activa
        has_advanced_search = any([cedula, nombres, area_id, status_id, marital_id, gender_id])

        # --- FILTRO BASE: Solo empleados activos si NO hay búsqueda avanzada ---
        if not has_advanced_search and not q:
            qs = qs.filter(employee_profile__is_active=True)

        # Búsqueda rápida
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(document_number__icontains=q) |
                Q(email__icontains=q) |
                Q(full_name_str__icontains=q)
            )

        # Aplicamos filtros avanzados si existen
        if cedula:
            qs = qs.filter(document_number__icontains=cedula)

        if nombres:
            # Busca en nombre, apellido O la concatenación de ambos
            qs = qs.filter(
                Q(first_name__icontains=nombres) |
                Q(last_name__icontains=nombres) |
                Q(full_name_str__icontains=nombres)
            )

        if area_id:
            qs = qs.filter(employee_profile__area_id=area_id)

        if status_id:
            qs = qs.filter(employee_profile__employment_status_id=status_id)

        if marital_id:
            qs = qs.filter(marital_status_id=marital_id)

        if gender_id:
            qs = qs.filter(gender_id=gender_id)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Formularios y Catálogos para el Modal de Búsqueda Avanzada
        context['form'] = PersonForm()
        context['marital_status_list'] = CatalogItem.objects.filter(catalog__code='MARITAL_STATUSES', is_active=True)
        context['areas_list'] = AdministrativeUnit.objects.filter(is_active=True)
        # Heredar todos los estados del catálogo EMPLOYMENT_STATUS
        context['status_list'] = CatalogItem.objects.filter(catalog__code='EMPLOYMENT_STATUS').order_by('name')
        context['gender_list'] = CatalogItem.objects.filter(catalog__code='GENDERS', is_active=True)

        # --- 3. ESTADÍSTICAS DINÁMICAS (Solo Estados Activos) ---
        from employee.models import Employee

        # Códigos de estados activos
        active_status_codes = ['EMPLEADO', 'TRABAJADOR', 'CONTRATADO', 'PROFESIONAL']

        # Estadísticas solo de empleados activos
        active_employees = Employee.objects.filter(
            employment_status__code__in=active_status_codes,
            is_active=True
        )

        stats_qs = active_employees.values(
            'employment_status__name',
            'employment_status__code',
            'employment_status__id'
        ).annotate(total=Count('id')).order_by('-total')

        # Convertimos a lista para fácil manejo en template
        stats = []
        total_active_employees = active_employees.count()

        # Tarjeta "Total Activos"
        stats.append({
            'label': 'Total Activos',
            'count': total_active_employees,
            'icon': 'fa-users',
            'class': 'color-one',
            'filter_val': ''  # Vacío limpia el filtro
        })

        # Tarjetas dinámicas por cada estado activo
        icons_map = {
            'EMPLEADO': 'fa-user-tie',
            'TRABAJADOR': 'fa-hard-hat',
            'CONTRATADO': 'fa-user-clock',
            'PROFESIONAL': 'fa-user-graduate'
        }
        colors = ['color-two', 'color-three', 'color-four', 'color-five']

        for idx, item in enumerate(stats_qs):
            code = item['employment_status__code']
            stats.append({
                'label': item['employment_status__name'] or 'Sin Estado',
                'count': item['total'],
                'icon': icons_map.get(code, 'fa-user-tag'),
                'class': colors[idx] if idx < len(colors) else 'color-one',
                'filter_val': item['employment_status__id']
            })

        context['stats_cards'] = stats
        return context

    def get(self, request, *args, **kwargs):
        # AJAX: devuelve solo la tabla parcial (búsqueda, paginación, filtros)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()

            # Modo exportación: devolver TODOS los registros sin paginación
            if request.GET.get('page_size') == '99999':
                from django.core.paginator import Paginator
                qs = self.object_list
                total = qs.count()
                # Un único "página" con todos los registros
                paginator = Paginator(qs, max(total, 1))
                page_obj = paginator.page(1)
                # Construir contexto mínimo sin pasar por paginate_queryset
                context = {
                    'people': qs,  # todos los registros
                    'page_obj': page_obj,
                    'paginator': paginator,
                    'is_paginated': False,
                    'request': request,
                }
            else:
                context = self.get_context_data()

            html = render_to_string('person/partials/partial_person_table.html', context, request=request)
            return JsonResponse({'success': True, 'html': html})

        return super().get(request, *args, **kwargs)


class PersonCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Person
    form_class = PersonForm
    template_name = 'person/modals/modal_person_form.html'
    permission_required = 'person.create_person'

    def post(self, request, *args, **kwargs):
        # Nota: request.FILES es necesario para la foto
        form = PersonForm(request.POST, request.FILES)
        if form.is_valid():
            person = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Persona registrada correctamente.',
                # Devolvemos datos útiles por si quieres actualizar la tabla via JS sin recargar
                'data': {'id': person.id, 'full_name': person.full_name}
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class PersonUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Person
    form_class = PersonForm
    template_name = 'person/modals/modal_person_form.html'
    permission_required = 'person.change_person'

    def post(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()

            # Verificar si la foto actual existe físicamente
            if self.object.photo:
                try:
                    # Intentar acceder al archivo
                    if not self.object.photo.storage.exists(self.object.photo.name):
                        # La foto no existe físicamente, limpiar el campo
                        print(f"Foto no encontrada: {self.object.photo.name}, limpiando campo...")
                        self.object.photo = None
                        self.object.save(update_fields=['photo'])
                except Exception as e:
                    # Error al acceder a la foto (ruta inválida, etc), limpiar el campo
                    print(f"Error al verificar foto: {e}, limpiando campo...")
                    self.object.photo = None
                    self.object.save(update_fields=['photo'])

            # Procesar el formulario
            if 'photo' in request.FILES:
                # Hay una nueva foto
                form = PersonForm(request.POST, request.FILES, instance=self.object)
            else:
                # No hay nueva foto
                form = PersonForm(request.POST, instance=self.object)

            if form.is_valid():
                form.save()
                return JsonResponse({'success': True, 'message': 'Datos actualizados correctamente.'})
            else:
                # Log de errores para debugging
                print("Errores de formulario:", form.errors)
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        except Exception as e:
            # Log del error real
            import traceback
            print("Error en PersonUpdateView:", str(e))
            traceback.print_exc()
            return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'}, status=500)


def person_detail_json(request, pk):
    p = get_object_or_404(Person, pk=pk)
    data = {
        'id': p.id,
        'document_type': p.document_type_id,
        'document_type_name': p.document_type.name if p.document_type else '',
        'document_number': p.document_number,
        'first_name': p.first_name,
        'last_name': p.last_name,
        'email': p.email,
        'birth_date': p.birth_date.isoformat() if p.birth_date else None,
        'gender': p.gender_id,
        'marital_status': p.marital_status_id,
        'blood_type': p.blood_type_id,
        'country': p.country_id,
        'province': p.province_id,
        'canton': p.canton_id,
        'parish': p.parish_id,
        'address_reference': p.address_reference,
        'phone_number': p.phone_number,
        'photo_url': p.photo.url if p.photo else None,
        # --- CAMPOS DE SALUD E INCLUSIÓN ---
        'has_disability': p.has_disability,
        'disability_type': p.disability_type_id,
        'disability_percentage': p.disability_percentage,
        'has_catastrophic_illness': p.has_catastrophic_illness,
        'catastrophic_illness_description': p.catastrophic_illness_description,
        'is_substitute': p.is_substitute,
        'substitute_family_member_id': p.substitute_family_member_id,
        'substitute_family_member_name': p.substitute_family_member_name,
        'substitute_family_member_relationship': p.substitute_family_member_relationship_id,
        'substitute_family_member_disability_type': p.substitute_family_member_disability_type_id,
        'substitute_family_member_disability_percentage': p.substitute_family_member_disability_percentage,
        # --- EMERGENCIA ---
        'emergency_contact_name': p.emergency_contact_name,
        'emergency_contact_phone': p.emergency_contact_phone,
        'emergency_contact_relationship': p.emergency_contact_relationship_id,
    }
    return JsonResponse({'success': True, 'data': data})


def person_quick_view_partial(request, pk):
    """
    Retorna un fragmento HTML con la información resumida de una persona.
    """
    person = get_object_or_404(
        Person.objects.select_related(
            'document_type',
            'gender',
            'employee_profile__area',
            'employee_profile__employment_status'
        ),
        pk=pk
    )
    employee_pk = Employee.objects.get(person=pk)
    budget = BudgetLine.objects.get(current_employee=employee_pk)
    institutional_data = InstitutionalData.objects.get(employee=employee_pk)
    return render(request, 'person/partials/partial_person_quick_view.html', {
        'person': person, 'budget': budget, 'institutional_data': institutional_data
    })


@method_decorator(require_POST, name='dispatch')
class RelocateEmployeeView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'person.change_person'  # Ajusta según tus permisos

    def post(self, request, *args, **kwargs):
        person_id = request.POST.get('person_id')
        unit_id = request.POST.get('unit_id')

        if not person_id or not unit_id:
            return JsonResponse({'success': False, 'message': 'Faltan datos (Persona o Unidad).'})

        try:
            # 1. Obtener la persona
            person = get_object_or_404(Person, pk=person_id)

            # 2. Verificar que tenga perfil de empleado
            if not hasattr(person, 'employee_profile'):
                return JsonResponse({'success': False, 'message': 'Esta persona no tiene perfil de empleado activo.'})

            # 3. Obtener la unidad destino
            new_unit = get_object_or_404(AdministrativeUnit, pk=unit_id)

            # 4. Actualizar
            employee = person.employee_profile
            old_unit_name = employee.area.name if employee.area else "Sin Unidad"

            employee.area = new_unit
            employee.save()

            return JsonResponse({
                'success': True,
                'message': f'Reubicación exitosa: {person.first_name}  {person.last_name} pasó de "{old_unit_name}" a "{new_unit.name}".'
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
