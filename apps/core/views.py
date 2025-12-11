from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.generic import TemplateView, ListView, UpdateView
from .forms import CatalogForm
from .forms import UserProfileForm
from .models import Catalog
from .models import User
from django.shortcuts import get_object_or_404
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
