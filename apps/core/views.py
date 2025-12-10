from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView, UpdateView
from .forms import UserProfileForm
from .models import User, Catalog


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


# --- 4. LISTA DE CATÁLOGOS ---
class CatalogListView(LoginRequiredMixin, ListView):
    model = Catalog
    template_name = 'core/catalogs/catalog_list.html'
    context_object_name = 'catalogs'
    paginate_by = 10

    def get_queryset(self):
        query = self.request.GET.get('q')
        qs = Catalog.objects.all()

        if query:
            qs = qs.filter(name__icontains=query)
        return qs.order_by('-created_at')[:50]
