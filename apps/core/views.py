from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.generic import TemplateView, ListView, UpdateView
from .forms import CatalogForm, CatalogItemForm, LocationForm
from .forms import UserProfileForm
from .models import Catalog, CatalogItem, Location
from .models import User
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST


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
        messages.success(self.request, "¡Tu perfil ha sido actualizado correctamente!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Error al actualizar. Revisa los campos.")
        return super().form_invalid(form)


# --- 4. CATÁLOGOS ---
# --- 4.1 LISTA DE CATÁLOGOS ---
def get_catalog_stats_dict():
    """Retorna un diccionario con las estadísticas actuales de Catálogos."""
    return {
        'total': Catalog.objects.count(),
        'active': Catalog.objects.filter(is_active=True).count(),
        'inactive': Catalog.objects.filter(is_active=False).count(),
    }


class CatalogListView(LoginRequiredMixin, ListView):
    model = Catalog
    template_name = 'core/catalogs/catalog_list.html'
    context_object_name = 'catalogs'

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
class CatalogCreateView(LoginRequiredMixin, CreateView):
    model = Catalog
    form_class = CatalogForm
    template_name = 'core/catalogs/modals/modal_catalog_form.html'  # Solo renderiza el form si es GET

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
class CatalogUpdateView(LoginRequiredMixin, UpdateView):
    model = Catalog
    form_class = CatalogForm
    template_name = 'core/catalogs/modals/modal_catalog_form.html'

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
class CatalogItemCreateView(LoginRequiredMixin, CreateView):
    model = CatalogItem
    form_class = CatalogItemForm
    template_name = 'core/catalogs/modals/modal_item_form.html'  # Solo renderiza el form si es GET

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
class CatalogItemUpdateView(LoginRequiredMixin, UpdateView):
    model = CatalogItem
    form_class = CatalogItemForm
    template_name = 'core/catalogs/modals/modal_item_form.html'

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
class LocationListView(LoginRequiredMixin, ListView):
    model = Location
    template_name = 'core/locations/location_list.html'
    context_object_name = 'locations'

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


class LocationCreateView(LoginRequiredMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'core/locations/modals/modal_location_form.html'

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


class LocationUpdateView(LoginRequiredMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'core/locations/modals/modal_location_form.html'

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
