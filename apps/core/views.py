from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.generic import TemplateView, ListView, UpdateView
from .forms import CatalogForm, CatalogItemForm, LocationForm, AuthorityForm
from .forms import UserProfileForm
from .models import Catalog, CatalogItem, Location, Authority
from .models import User
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.views.generic import View
from django.contrib.auth.decorators import permission_required


# --- 1. LOGIN & AUTH ---
class CustomLoginView(LoginView):
    template_name = 'core/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('core:dashboard')

    def form_invalid(self, form):
        messages.error(self.request, "Credenciales incorrectas. Intente nuevamente.")
        return super().form_invalid(form)


# --- 2. DASHBOARD ---
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            has_employee_dashboard = request.user.has_perm('auth.dashboard_empleado')
            has_hr_dashboard = request.user.has_perm('auth.dashboard_talento_humano')
            has_boss_dashboard = request.user.has_perm('auth.dashboard_jefe')

            if has_employee_dashboard and not has_hr_dashboard and not has_boss_dashboard:
                return redirect('employee:self_dashboard')

        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from employee.models import Employee
        from budget.models import BudgetLine
        from person.models import Person
        from function_manual.models import JobProfile
        from core.models import CatalogItem
        from django.db.models import Count, Q, Avg, Sum
        from datetime import date, timedelta
        from django.utils import timezone
        
        # === ESTADÍSTICAS DE EMPLEADOS (SOLO ACTIVOS) ===
        active_employees = Employee.objects.filter(is_active=True)
        
        employee_stats = active_employees.values(
            'employment_status__code',
            'employment_status__name'
        ).annotate(total=Count('id'))
        
        stats_dict = {stat['employment_status__code']: stat['total'] for stat in employee_stats if stat['employment_status__code']}
        
        context['total_employees'] = active_employees.count()
        context['empleados'] = stats_dict.get('EMPLEADO', 0)
        context['trabajadores'] = stats_dict.get('TRABAJADOR', 0)
        context['contratados'] = stats_dict.get('CONTRATADO', 0)
        context['profesionales'] = stats_dict.get('PROFESIONAL', 0)
        
        # === ESTADÍSTICAS DE PARTIDAS (SOLO ACTIVAS) ===
        active_budgets = BudgetLine.objects.exclude(status_item__code='INACTIVA')
        budget_stats = active_budgets.values(
            'status_item__code',
            'status_item__name'
        ).annotate(total=Count('id'))
        
        budget_dict = {stat['status_item__code']: stat['total'] for stat in budget_stats if stat['status_item__code']}
        
        context['total_partidas'] = active_budgets.count()
        context['partidas_ocupadas'] = budget_dict.get('OCUPADA', 0)
        context['partidas_libres'] = budget_dict.get('LIBRE', 0)
        context['partidas_concurso'] = budget_dict.get('CONCURSO', 0)
        context['partidas_litigio'] = budget_dict.get('LITIGIO', 0)
        
        # === ESTADÍSTICAS ADICIONALES ===
        # Porcentaje de ocupación
        if context['total_partidas'] > 0:
            context['porcentaje_ocupacion'] = round((context['partidas_ocupadas'] / context['total_partidas']) * 100, 1)
        else:
            context['porcentaje_ocupacion'] = 0
            
        # Género
        gender_stats = active_employees.values(
            'person__gender__name'
        ).annotate(total=Count('id'))
        
        context['empleados_masculino'] = 0
        context['empleados_femenino'] = 0
        
        for stat in gender_stats:
            if stat['person__gender__name']:
                gender_name = stat['person__gender__name'].upper()
                if 'MASCULINO' in gender_name or 'HOMBRE' in gender_name:
                    context['empleados_masculino'] = stat['total']
                elif 'FEMENINO' in gender_name or 'MUJER' in gender_name:
                    context['empleados_femenino'] = stat['total']
        
        # Empleados con título universitario (sumar TERCER_NIVEL, CUARTO_NIVEL y TECNOLOGO)
        try:
            levels = ['TERCER_NIVEL', 'CUARTO_NIVEL', 'TECNOLOGO']
            # Personas únicas (deduplicadas) que tengan al menos un título en cualquiera de los niveles indicados
            person_ids = Employee.objects.filter(
                is_active=True,
                person__curriculum__academic_titles__education_level__code__in=levels
            ).values_list('person_id', flat=True).distinct()
            context['empleados_con_titulo'] = person_ids.count()

            # Mantener desglose por código por si se necesita mostrar por separado
            context['empleados_cuarto_nivel'] = Employee.objects.filter(
                is_active=True,
                person__curriculum__academic_titles__education_level__code='CUARTO_NIVEL'
            ).values_list('person_id', flat=True).distinct().count()

            context['empleados_tecnologo'] = Employee.objects.filter(
                is_active=True,
                person__curriculum__academic_titles__education_level__code='TECNOLOGO'
            ).values_list('person_id', flat=True).distinct().count()
        except Exception:
            context['empleados_con_titulo'] = 0
            context['empleados_cuarto_nivel'] = 0
            context['empleados_tecnologo'] = 0
        
        # Empleados con discapacidad
        context['empleados_con_discapacidad'] = active_employees.filter(
            person__has_disability=True
        ).count()
        
        # Empleados sustitutos
        context['empleados_sustitutos'] = active_employees.filter(
            person__is_substitute=True
        ).count()
        
        # Próximos jubilados (mayores de 60 años)
        fecha_jubilacion = date.today() - timedelta(days=365*60)
        context['proximos_jubilados'] = active_employees.filter(
            person__birth_date__lte=fecha_jubilacion
        ).count()
        
        # Áreas con más empleados
        top_areas = active_employees.values(
            'area__name'
        ).annotate(
            total=Count('id')
        ).order_by('-total')[:5]
        
        context['top_areas'] = [
            {'name': area['area__name'] or 'Sin área', 'total': area['total']} 
            for area in top_areas
        ]
        
        # === DATOS PARA GRÁFICOS ===
        context['employee_chart_data'] = {
            'labels': ['Empleados', 'Trabajadores', 'Contratados', 'Profesionales'],
            'values': [
                context['empleados'],
                context['trabajadores'],
                context['contratados'],
                context['profesionales']
            ]
        }
        
        context['budget_chart_data'] = {
            'labels': ['Libres', 'Ocupadas', 'Litigio', 'Concurso'],
            'values': [
                context['partidas_libres'],
                context['partidas_ocupadas'],
                context['partidas_litigio'],
                context['partidas_concurso']
            ]
        }
        
        context['gender_chart_data'] = {
            'labels': ['Masculino', 'Femenino'],
            'values': [context['empleados_masculino'], context['empleados_femenino']]
        }

        # === ESTADÍSTICAS DE PERFILES (JobProfile) ===
        try:
            qs_profiles = JobProfile.objects.all()
            context['profiles_total'] = qs_profiles.count()

            # Contar solo aquellos que realmente están legalizados.
            # Requerimos que los tres authority fields existan y además que exista el documento legalizado.
            profiles_legalized = 0
            for p in qs_profiles.only('prepared_by_id', 'reviewed_by_id', 'approved_by_id', 'legalized_document'):
                if p.prepared_by_id and p.reviewed_by_id and p.approved_by_id and p.legalized_document:
                    profiles_legalized += 1

            context['profiles_legalized'] = profiles_legalized
            context['profiles_pending'] = context['profiles_total'] - context['profiles_legalized']
        except Exception:
            context['profiles_total'] = 0
            context['profiles_legalized'] = 0
            context['profiles_pending'] = 0
        
        return context


# --- 3. PERFIL DE USUARIO ---
class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'core/profile.html'
    success_url = reverse_lazy('core:profile')

    def get_object(self):
        # Forzamos a que el objeto a editar sea SIEMPRE el usuario logueado
        return self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "¡Tu perfil ha sido actualizado correctamente!")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Error al actualizar. Revisa los campos.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasamos la Person si existe
        if hasattr(self.request.user, 'person'):
            context['person'] = self.request.user.person
        return context


# --- 4. CATÁLOGOS ---
# --- 4.1 LISTA DE CATÁLOGOS ---
def get_catalog_stats_dict():
    """Retorna un diccionario con las estadísticas actuales de Catálogos."""
    return {
        'total': Catalog.objects.count(),
        'active': Catalog.objects.filter(is_active=True).count(),
        'inactive': Catalog.objects.filter(is_active=False).count(),
    }


class CatalogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Catalog
    template_name = 'core/catalogs/catalog_list.html'
    context_object_name = 'catalogs'
    permission_required = 'core.view_catalog'

    # paginate_by = 10

    def get_queryset(self):
        query = self.request.GET.get('q')
        qs = Catalog.objects.all()

        if query:
            qs = qs.filter(name__icontains=query)
        return qs.order_by('-created_at')[:200]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = CatalogForm()
        stats = get_catalog_stats_dict()
        context['stats_total'] = stats['total']
        context['stats_active'] = stats['active']
        context['stats_inactive'] = stats['inactive']
        return context


# --- 4.2 CREAR CATÁLOGOS ---
class CatalogCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Catalog
    form_class = CatalogForm
    template_name = 'core/catalogs/modals/modal_catalog_form.html'  # Solo renderiza el form si es GET
    permission_required = 'core.add_catalog'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            catalog = form.save()
            stats = get_catalog_stats_dict()
            return JsonResponse({
                'success': True,
                'message': 'Catálogo creado correctamente.',
                'data': {'id': catalog.id, 'name': catalog.name, 'new_stats': stats}
                # Para actualizar lista sin recargar
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


# --- 4.3 Vista para OBTENER datos (JSON) ---
def catalog_detail_json(request, pk):
    """Retorna los datos de un catálogo específico para editar"""
    catalog = get_object_or_404(Catalog, pk=pk)
    return JsonResponse({
        'success': True,
        'data': {
            'id': catalog.id,
            'name': catalog.name,
            'code': catalog.code,
            'is_active': catalog.is_active
        }
    })


# --- 4.4 EDITAR CATÁLOGOS ---
class CatalogUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Catalog
    form_class = CatalogForm
    template_name = 'core/catalogs/modals/modal_catalog_form.html'
    permission_required = 'core.change_catalog'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()  # Obtener la instancia a editar
        form = self.get_form()

        if form.is_valid():
            catalog = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Catálogo actualizado correctamente.',
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


# --- 4.5 cambiar estado ---
@require_POST  # Por seguridad, solo permitimos POST
@permission_required('core.change_catalog', raise_exception=True)
def catalog_toggle_status(request, pk):
    """Alterna el estado (Activo/Inactivo) de un catálogo"""
    # Verificamos que el usuario esté logueado (puedes usar decorador login_required también)
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'No autorizado'}, status=403)

    catalog = get_object_or_404(Catalog, pk=pk)

    # Usamos el método de tu modelo BaseModel
    catalog.toggle_status()

    status_label = "activado" if catalog.is_active else "desactivado"
    stats = get_catalog_stats_dict()
    return JsonResponse({
        'success': True,
        'message': f'El catálogo "{catalog.name}" ha sido {status_label} correctamente.',
        'new_stats': stats
    })


# --- 5. ITEMS DE CATÁLOGO  ---
# --- 5.1 CREAR ITEMS ---
class CatalogItemCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = CatalogItem
    form_class = CatalogItemForm
    template_name = 'core/catalogs/modals/modal_item_form.html'  # Solo renderiza el form si es GET
    permission_required = 'core.add_catalogitem'

    def post(self, request, *args, **kwargs):
        catalog_id = request.POST.get('catalog_id')
        if not catalog_id:
            return JsonResponse({'success': False, 'message': 'Falta el ID del catálogo.'}, status=400)
        catalog = get_object_or_404(Catalog, pk=catalog_id)
        form = self.get_form()
        if form.is_valid():
            code = form.cleaned_data.get('code')
            if CatalogItem.objects.filter(catalog=catalog, code=code).exists():
                return JsonResponse({
                    'success': False,
                    'errors': {'code': ['Ya existe un item con este código en este catálogo.']}
                }, status=400)

            try:
                # 3. Guardado con asignación del padre
                item = form.save(commit=False)
                item.catalog = catalog
                item.save()

                return JsonResponse({
                    'success': True,
                    'message': f'Item creado en "{catalog.name}".',
                    'data': {'id': item.id, 'name': item.name}
                })
            except Exception as e:
                return JsonResponse({'success': False, 'message': str(e)}, status=500)
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


def item_list_json(request, catalog_id):
    """Devuelve los items de un catálogo específico"""
    items = CatalogItem.objects.filter(catalog_id=catalog_id).order_by('code')
    data = []
    for item in items:
        data.append({
            'id': item.id,
            'code': item.code,
            'name': item.name,
            'is_active': item.is_active
        })
    return JsonResponse({'success': True, 'data': data})


def item_detail_json(request, pk):
    """Para cargar el formulario de edición de item"""
    item = get_object_or_404(CatalogItem, pk=pk)
    return JsonResponse({
        'success': True,
        'data': {
            'id': item.id,
            'catalog_id': item.catalog_id,
            'name': item.name,
            'code': item.code
        }
    })


# --- 5.2 ACTUALIZAR ITEMS ---
class CatalogItemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = CatalogItem
    form_class = CatalogItemForm
    template_name = 'core/catalogs/modals/modal_item_form.html'
    permission_required = 'security.change_catalogitem'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            item = form.save()
            return JsonResponse({'success': True, 'message': 'Item actualizado correctamente.'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)


# --- 5.3 CAMBIAR ESTADO ITEMS ---
@require_POST
@permission_required('core.change_catalogitem', raise_exception=True)
def item_toggle_status(request, pk):
    """Activar/Inactivar Item"""
    item = get_object_or_404(CatalogItem, pk=pk)
    item.toggle_status()
    return JsonResponse({
        'success': True,
        'message': f'Item "{item.name}" {"activado" if item.is_active else "desactivado"}.',
        'is_active': item.is_active
    })


# --- 6. UBICACIONES ---
def get_location_stats_dict():
    """Retorna un diccionario con las estadísticas actuales de Catálogos."""
    return {
        'country': Location.objects.filter(level=1, is_active=True).count(),
        'province': Location.objects.filter(level=2, is_active=True).count(),
        'city': Location.objects.filter(level=3, is_active=True).count(),
        'parish': Location.objects.filter(level=4, is_active=True).count(),
    }


# --- 6.1 LISTA DE UBICACIONES ---
class LocationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Location
    template_name = 'core/locations/location_list.html'
    context_object_name = 'locations'
    permission_required = 'core.view_location'

    def get_queryset(self):
        level = self.request.GET.get('level')
        parent_id = self.request.GET.get('parent_id')
        query = self.request.GET.get('q')

        qs = Location.objects.all().order_by('name')

        if parent_id:
            qs = qs.filter(parent_id=parent_id)
        elif level and level != 'all':
            qs = qs.filter(level=level)
        else:
            if not query:
                qs = qs.filter(level=1)

        if query:
            qs = qs.filter(name__icontains=query)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = LocationForm()

        # Stats
        base_stats = Location.objects.filter(is_active=True)
        context['stats_country'] = base_stats.filter(level=1).count()
        context['stats_province'] = base_stats.filter(level=2).count()
        context['stats_city'] = base_stats.filter(level=3).count()
        context['stats_parish'] = base_stats.filter(level=4).count()

        # --- LÓGICA DE NIVEL VISUAL (Para iluminar los stats) ---
        parent_id = self.request.GET.get('parent_id')
        level = self.request.GET.get('level')

        current_display_level = '1'  # Por defecto Paises

        if parent_id:
            # Si estamos filtrando por padre, estamos viendo el nivel de sus hijos.
            # Buscamos al padre para saber su nivel + 1
            try:
                parent = Location.objects.get(pk=parent_id)
                current_display_level = str(parent.level + 1)
            except Location.DoesNotExist:
                pass
        elif level and level != 'all':
            current_display_level = str(level)

        context['current_display_level'] = current_display_level

        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return render(request, 'core/locations/partials/partial_location_table.html', context)
        return super().get(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        """
        Sobrescribimos esto para devolver JSON si se solicita,
        usado por los selectores en cascada.
        """
        if self.request.GET.get('format') == 'json' or self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Solo si estamos pidiendo datos para selects (filtrado por padre)
            if self.request.GET.get('parent_id'):
                data = list(self.object_list.values('id', 'name'))
                return JsonResponse(data, safe=False)

        return super().render_to_response(context, **response_kwargs)


class LocationCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'core/locations/modals/modal_location_form.html'
    permission_required = 'core.create_location'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            location = form.save()
            stats = get_location_stats_dict()
            return JsonResponse({
                'success': True,
                'message': 'Ubicación creada correctamente.',
                'data': {'id': location.id, 'name': location.name, 'new_stats': stats}
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


class LocationUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'core/locations/modals/modal_location_form.html'
    permission_required = 'core.change_location'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()  # Obtener la instancia a editar
        form = self.get_form()

        if form.is_valid():
            location = form.save()
            stats = get_location_stats_dict()
            return JsonResponse({
                'success': True,
                'message': 'Ubicación actualizada correctamente.',
                'data': {'id': location.id, 'name': location.name, 'new_stats': stats}
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


def location_detail_json(request, pk):
    """
    Retorna los datos de una ubicación.
    Útil para editar y para calcular el nivel de una nueva ubicación hija.
    """
    location = get_object_or_404(Location, pk=pk)
    return JsonResponse({
        'success': True,
        'data': {
            'id': location.id,
            'name': location.name,
            'level': location.level,
            'parent': location.parent_id,
            'parent_name': location.parent.name if location.parent else None
        }
    })


@require_POST
@permission_required('core.change_location', raise_exception=True)
def location_toggle_status(request, pk):
    """Alterna el estado de una Ubicación"""
    location = get_object_or_404(Location, pk=pk)
    location.toggle_status()

    status_label = "activada" if location.is_active else "desactivada"

    # Recalculamos estadísticas para devolverlas si fuera necesario
    stats = get_location_stats_dict()

    return JsonResponse({
        'success': True,
        'message': f'La ubicación "{location.name}" ha sido {status_label} correctamente.',
        'new_stats': stats
    })


class LocationJsonView(View):
    """Retorna ubicaciones filtradas por padre para los selectores en cascada"""

    def get(self, request):
        parent_id = request.GET.get('parent_id')
        if parent_id:
            locations = Location.objects.filter(parent_id=parent_id, is_active=True).order_by('name')
        else:
            locations = Location.objects.filter(level=1, is_active=True).order_by('name')

        data = [{'id': loc.id, 'name': loc.name} for loc in locations]
        return JsonResponse({
            'success': True,
            'data': data
        })


# --- AUTORIDADES ---
class AuthorityListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Authority
    template_name = 'core/authorities/authority_list.html'
    context_object_name = 'authorities'
    permission_required = 'core.view_authority'

    def get_queryset(self):
        query = self.request.GET.get('q')
        qs = Authority.objects.all()
        if query:
            qs = qs.filter(name__icontains=query) | qs.filter(position__icontains=query)
        return qs.order_by('-created_at')

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            from django.template.loader import render_to_string
            html = render_to_string(
                'core/authorities/partials/partial_authority_table.html',
                {'authorities': self.object_list},
                request=request
            )
            return JsonResponse({'html': html})
        return super().get(request, *args, **kwargs)


class AuthorityCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Authority
    form_class = AuthorityForm
    permission_required = 'core.add_authority'

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({
            'success': True,
            'message': 'Autoridad creada correctamente.'
        })

    def form_invalid(self, form):
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


class AuthorityUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Authority
    form_class = AuthorityForm
    permission_required = 'core.change_authority'

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({
            'success': True,
            'message': 'Autoridad actualizada correctamente.'
        })

    def form_invalid(self, form):
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


def authority_detail(request, pk):
    """Retorna los datos de una autoridad específica para editar"""
    authority = get_object_or_404(Authority, pk=pk)
    return JsonResponse({
        'success': True,
        'data': {
            'id': authority.id,
            'name': authority.name,
            'position': authority.position,
            'is_active': authority.is_active
        }
    })


@require_POST
@permission_required('core.change_authority', raise_exception=True)
def authority_toggle_status(request, pk):
    """Alterna el estado (Activo/Inactivo) de una autoridad"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'No autorizado'}, status=403)

    authority = get_object_or_404(Authority, pk=pk)
    authority.toggle_status()

    status_label = "activado" if authority.is_active else "desactivado"
    return JsonResponse({
        'success': True,
        'message': f'La autoridad "{authority.name}" ha sido {status_label} correctamente.',
        'is_active': authority.is_active
    })


# === MANEJADORES DE ERRORES PERSONALIZADOS ===
def custom_page_not_found(request, exception=None):
    """Manejador personalizado para error 404"""
    from django.shortcuts import render
    return render(request, '404.html', status=404)


# --- CAMBIO DE CONTRASEÑA ---
class ChangePasswordView(LoginRequiredMixin, View):
    """Vista para cambiar la contraseña del usuario"""
    
    def post(self, request):
        """Procesa el cambio de contraseña"""
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Petición inválida'}, status=400)
        
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        # Validaciones
        if not new_password or not confirm_password:
            return JsonResponse({
                'success': False,
                'message': 'Los campos de contraseña no pueden estar vacíos.'
            })
        
        if new_password != confirm_password:
            return JsonResponse({
                'success': False,
                'message': 'Las contraseñas no coinciden.'
            })
        
        if len(new_password) < 8:
            return JsonResponse({
                'success': False,
                'message': 'La contraseña debe tener al menos 8 caracteres.'
            })
        
        # Verificar requisitos de contraseña
        import re
        if not re.search(r'[A-Z]', new_password):
            return JsonResponse({
                'success': False,
                'message': 'La contraseña debe contener al menos una mayúscula.'
            })
        
        if not re.search(r'[a-z]', new_password):
            return JsonResponse({
                'success': False,
                'message': 'La contraseña debe contener al menos una minúscula.'
            })
        
        if not re.search(r'[0-9]', new_password):
            return JsonResponse({
                'success': False,
                'message': 'La contraseña debe contener al menos un número.'
            })
        
        # Actualizar contraseña
        try:
            user = request.user
            user.set_password(new_password)
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Tu contraseña ha sido cambiada exitosamente.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Ocurrió un error: {str(e)}'
            })


def custom_page_not_found(request, exception=None):
    """Manejador personalizado para error 404"""
    from django.shortcuts import render
    return render(request, '404.html', status=404)


def custom_permission_denied(request, exception=None):
    """Manejador personalizado para error 403"""
    from django.shortcuts import render
    return render(request, '403.html', status=403)


def custom_server_error(request, exception=None):
    """Manejador personalizado para error 500"""
    from django.shortcuts import render
    return render(request, '500.html', status=500)
