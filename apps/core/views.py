"""
Controladores HTTP del módulo Core.
Implementa el patrón Thin Views delegando lógica de negocio a `services.py`
y validación de datos a `forms.py`.
"""
import logging
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash, views as auth_views
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import ListView, TemplateView, UpdateView, View

from .forms import (
    CatalogForm,
    CatalogItemForm,
    LocationForm,
    SystemConfigurationSetupForm,
    SystemLetterheadForm,
    UserProfileForm,
)
from .models import Catalog, CatalogItem, Location, SystemConfiguration, User
from .services import AuthService, DashboardService

logger = logging.getLogger(__name__)


# =====================================================================
# 1. AUTENTICACIÓN Y CUENTAS
# =====================================================================
class CustomLoginView(LoginView):
    template_name = 'core/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        user_obj = form.get_user()
        if getattr(user_obj, 'last_login', None) is None:
            self.request.session['force_change_on_login'] = True

        response = super().form_valid(form)
        plain_password = form.cleaned_data.get('password')
        AuthService.handle_post_login(self.request, self.request.user, plain_password)
        return response

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy('core:dashboard')

    def form_invalid(self, form):
        messages.error(self.request, 'Credenciales incorrectas. Intente nuevamente.')
        context = self.get_context_data(
            form=form,
            username=(self.request.POST.get('username') or '').strip(),
        )
        return self.render_to_response(context)


class CustomLogoutView(auth_views.LogoutView):
    def get_next_page(self):
        next_url = self.request.POST.get(self.redirect_field_name) or self.request.GET.get(self.redirect_field_name)
        if next_url:
            return f"{reverse('core:login')}?{urlencode({self.redirect_field_name: next_url})}"
        return reverse_lazy('core:login')


class ForgotPasswordView(TemplateView):
    template_name = 'core/forgot_password.html'

    def post(self, request, *args, **kwargs):
        identifier = (request.POST.get('identificador') or '').strip()
        birth_date_raw = (request.POST.get('birth_date') or '').strip()

        if not identifier or not birth_date_raw:
            return JsonResponse({
                'status': 'error',
                'message': 'Debe ingresar su usuario o correo y la fecha de nacimiento.',
            })

        result = AuthService.request_password_recovery(request, identifier, birth_date_raw)
        return JsonResponse(result)


class LocalPasswordResetView(View):
    template_name = 'core/local_password_reset.html'

    def get(self, request, token):
        user = AuthService.validate_local_reset_token(token)
        if user is None:
            return render(
                request,
                self.template_name,
                {'invalid_token': True, 'error': 'El enlace no es válido o ya expiró.'},
                status=400,
            )
        return render(request, self.template_name, {'token': token})

    def post(self, request, token):
        user = AuthService.validate_local_reset_token(token)
        if user is None:
            return render(
                request,
                self.template_name,
                {'invalid_token': True, 'error': 'El enlace no es válido o ya expiró.'},
                status=400,
            )

        password = request.POST.get('password') or ''
        confirm_password = request.POST.get('confirm_password') or ''
        if password != confirm_password:
            return render(
                request,
                self.template_name,
                {'token': token, 'error': 'Las contraseñas no coinciden.'},
                status=400,
            )

        try:
            validate_password(password, user)
        except Exception as exc:
            return render(
                request,
                self.template_name,
                {'token': token, 'error': ' '.join(exc.messages)},
                status=400,
            )

        try:
            AuthService.apply_local_password_reset(user, password)
            return render(request, self.template_name, {'completed': True})
        except Exception:
            logger.exception("[AUTH][RESET] Error aplicando restablecimiento local para user_id=%s", user.pk)
            return render(
                request,
                self.template_name,
                {'token': token, 'error': 'No se pudo actualizar la contraseña. Intente nuevamente más tarde.'},
                status=503,
            )


class ChangePasswordView(LoginRequiredMixin, View):
    def post(self, request):
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not new_password or new_password != confirm_password:
            return JsonResponse({'success': False, 'message': 'Las contraseñas no coinciden.'}, status=400)

        if len(new_password) < 8:
            return JsonResponse({'success': False, 'message': 'La contraseña debe tener al menos 8 caracteres.'},
                                status=400)

        success, message, status_code = AuthService.change_authenticated_password(request.user, new_password)
        if not success:
            return JsonResponse({'success': False, 'message': message}, status=status_code)

        update_session_auth_hash(request, request.user)
        if 'force_change_on_login' in request.session:
            del request.session['force_change_on_login']

        return JsonResponse({'success': True, 'message': message})


class SyncKeycloakPasswordView(LoginRequiredMixin, View):
    """Retira el indicador de cambio obligatorio tras confirmar vinculación institucional."""

    def post(self, request):
        if 'force_change_on_login' in request.session:
            del request.session['force_change_on_login']
            request.session.modified = True

        messages.success(request, 'Cuenta vinculada exitosamente con el sistema institucional.')
        return redirect('core:dashboard')


class CreateUserFromLoginView(TemplateView):
    template_name = 'core/create_user_from_login.html'

    def post(self, request, *args, **kwargs):
        document_number = (request.POST.get('cedula') or '').strip()
        if not document_number:
            return JsonResponse({'status': 'error', 'message': 'Debe ingresar la cédula para continuar.'})

        result = AuthService.self_register_employee(request, document_number)
        return JsonResponse(result)


# =====================================================================
# 2. PANEL PRINCIPAL (DASHBOARD) Y PERFIL
# =====================================================================
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        force_boss_view = self.request.GET.get('view') == 'jefe'
        context.update(DashboardService.build_dashboard_context(self.request.user, force_boss_view))
        return context


class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'core/profile.html'
    success_url = reverse_lazy('core:profile')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '¡Tu perfil ha sido actualizado correctamente!')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Error al actualizar. Revisa los campos.')
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self.request.user, 'person'):
            context['person'] = self.request.user.person
        return context


# =====================================================================
# 3. GESTIÓN DE CATÁLOGOS E ÍTEMS
# =====================================================================
class CatalogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Catalog
    template_name = 'core/catalogs/catalog_list.html'
    context_object_name = 'catalogs'
    permission_required = 'core.view_catalog'

    def get_queryset(self):
        qs = Catalog.objects.all().order_by('name')
        query = (self.request.GET.get('q') or '').strip()
        if query:
            qs = qs.filter(Q(code__icontains=query) | Q(name__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_catalogs = Catalog.objects.all()
        context['stats_total'] = all_catalogs.count()
        context['stats_active'] = all_catalogs.filter(is_active=True).count()
        context['stats_inactive'] = all_catalogs.filter(is_active=False).count()
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'core/catalogs/partials/partial_catalog_table.html',
                context,
                request=self.request,
            )
            return JsonResponse({'html': html})
        return super().render_to_response(context, **response_kwargs)


class CatalogModalFormView(LoginRequiredMixin, PermissionRequiredMixin, View):
    def get_permission_required(self):
        if self.kwargs.get('pk'):
            return ('core.change_catalog',)
        return ('core.add_catalog',)

    def get(self, request, pk=None):
        if pk:
            catalog = get_object_or_404(Catalog, pk=pk)
            is_edit = True
            action_url = reverse('core:catalog_update', args=[pk])
        else:
            catalog = None
            is_edit = False
            action_url = reverse('core:catalog_create')

        html = render_to_string(
            'core/catalogs/modals/modal_catalog_form.html',
            {'catalog': catalog, 'is_edit': is_edit, 'action_url': action_url},
            request=request,
        )
        return HttpResponse(html)


class CatalogCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.add_catalog'

    def post(self, request):
        form = CatalogForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        catalog = form.save(commit=False)
        catalog.created_by = request.user
        catalog.save()
        return JsonResponse({'success': True, 'message': 'Catálogo creado exitosamente.'})


class CatalogUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_catalog'

    def post(self, request, pk):
        catalog = get_object_or_404(Catalog, pk=pk)
        form = CatalogForm(request.POST, instance=catalog)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        updated_catalog = form.save(commit=False)
        updated_catalog.updated_by = request.user
        updated_catalog.save()
        return JsonResponse({'success': True, 'message': 'Catálogo actualizado exitosamente.'})


class CatalogToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_catalog'

    def post(self, request, pk):
        instance = get_object_or_404(Catalog, pk=pk)
        instance.is_active = not instance.is_active
        instance.updated_by = request.user
        instance.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        return JsonResponse({
            'success': True,
            'message': f'Estado del catálogo actualizado a {"Activo" if instance.is_active else "Inactivo"}.',
        })


class CatalogItemListModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.view_catalogitem'

    def get(self, request, catalog_id):
        catalog = get_object_or_404(Catalog, pk=catalog_id)
        items = CatalogItem.objects.filter(catalog=catalog).order_by('code')
        html = render_to_string(
            'core/catalogs/modals/modal_item_list.html',
            {'catalog': catalog, 'items': items},
            request=request,
        )
        return HttpResponse(html)


class CatalogItemModalFormView(LoginRequiredMixin, PermissionRequiredMixin, View):
    def get_permission_required(self):
        if self.kwargs.get('pk'):
            return ('core.change_catalogitem',)
        return ('core.add_catalogitem',)

    def get(self, request, catalog_id, pk=None):
        catalog = get_object_or_404(Catalog, pk=catalog_id)
        if pk:
            item = get_object_or_404(CatalogItem, pk=pk, catalog=catalog)
            is_edit = True
            action_url = reverse('core:catalog_item_update', args=[item.id])
        else:
            item = None
            is_edit = False
            action_url = reverse('core:catalog_item_create', args=[catalog.id])

        html = render_to_string(
            'core/catalogs/modals/modal_item_form.html',
            {'catalog': catalog, 'item': item, 'is_edit': is_edit, 'action_url': action_url},
            request=request,
        )
        return HttpResponse(html)


class CatalogItemCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.add_catalogitem'

    def post(self, request, catalog_id):
        catalog = get_object_or_404(Catalog, pk=catalog_id)
        form = CatalogItemForm(request.POST, catalog=catalog)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        item = form.save(commit=False)
        item.catalog = catalog
        item.created_by = request.user
        item.save()
        return JsonResponse({'success': True, 'message': 'Ítem registrado exitosamente.'})


class CatalogItemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_catalogitem'

    def post(self, request, pk):
        item = get_object_or_404(CatalogItem, pk=pk)
        form = CatalogItemForm(request.POST, instance=item)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        updated_item = form.save(commit=False)
        updated_item.updated_by = request.user
        updated_item.save()
        return JsonResponse({'success': True, 'message': 'Ítem actualizado exitosamente.'})


class CatalogItemToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_catalogitem'

    def post(self, request, pk):
        item = get_object_or_404(CatalogItem, pk=pk)
        item.is_active = not item.is_active
        item.updated_by = request.user
        item.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        return JsonResponse({
            'success': True,
            'message': f'Estado del ítem actualizado a {"Activo" if item.is_active else "Inactivo"}.',
        })


# =====================================================================
# 4. UBICACIONES GEOGRÁFICAS (LOCATIONS)
# =====================================================================
class LocationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Location
    template_name = 'core/locations/location_list.html'
    context_object_name = 'locations'
    permission_required = 'core.view_location'

    def get_queryset(self):
        level = self.request.GET.get('level')
        parent_id = self.request.GET.get('parent_id')
        query = (self.request.GET.get('q') or '').strip()

        qs = Location.objects.select_related('parent').order_by('name')
        if parent_id:
            qs = qs.filter(parent_id=parent_id)
        elif level and level != 'all':
            qs = qs.filter(level=level)
        elif not query:
            qs = qs.filter(level=1)

        if query:
            qs = qs.filter(name__icontains=query)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_locations = Location.objects.filter(is_active=True)
        context['stats_country'] = active_locations.filter(level=1).count()
        context['stats_province'] = active_locations.filter(level=2).count()
        context['stats_city'] = active_locations.filter(level=3).count()
        context['stats_parish'] = active_locations.filter(level=4).count()

        parent_id = self.request.GET.get('parent_id')
        level = self.request.GET.get('level')
        current_display_level = '1'

        if parent_id:
            parent = Location.objects.filter(pk=parent_id).first()
            if parent:
                current_display_level = str(min(parent.level + 1, 4))
        elif level and level != 'all':
            current_display_level = str(level)

        context['current_display_level'] = current_display_level
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'core/locations/partials/partial_location_table.html',
                context,
                request=self.request,
            )
            return JsonResponse({
                'html': html,
                'current_display_level': context.get('current_display_level', '1'),
                'stats': {},
            })
        return super().render_to_response(context, **response_kwargs)


class LocationCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.add_location'
    template_name = 'core/locations/modals/modal_location_form.html'

    def get(self, request, *args, **kwargs):
        parent_id = request.GET.get('parent_id')
        parent_obj = None
        current_level = 1
        level_map = {1: 'País', 2: 'Provincia', 3: 'Ciudad', 4: 'Parroquia'}

        if parent_id and parent_id != 'null' and parent_id.isdigit():
            parent_obj = Location.objects.filter(pk=int(parent_id)).first()
            if parent_obj:
                current_level = min(parent_obj.level + 1, 4)

        modal_title = f"Nuevo {level_map.get(current_level, 'Ubicación')}"
        if parent_obj:
            modal_title += f" de {parent_obj.name}"

        context = {
            'action_url': reverse('core:location_create'),
            'is_edit': False,
            'current_level': current_level,
            'level_label': level_map.get(current_level, 'Ubicación'),
            'parent_id': parent_obj.id if parent_obj else '',
            'parent_name': parent_obj.name if parent_obj else '- Raíz -',
            'modal_title': modal_title,
        }
        return HttpResponse(render_to_string(self.template_name, context, request=request))

    def post(self, request, *args, **kwargs):
        form = LocationForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        location = form.save(commit=False)
        location.created_by = request.user
        location.save()
        return JsonResponse({
            'success': True,
            'message': 'Ubicación registrada exitosamente.',
            'new_stats': {},
        })


class LocationUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_location'
    template_name = 'core/locations/modals/modal_location_form.html'

    def get(self, request, pk, *args, **kwargs):
        location = get_object_or_404(Location, pk=pk)
        level_map = {1: 'País', 2: 'Provincia', 3: 'Ciudad', 4: 'Parroquia'}

        context = {
            'location': location,
            'action_url': reverse('core:location_update', args=[location.id]),
            'is_edit': True,
            'current_level': location.level,
            'level_label': level_map.get(location.level, 'Ubicación'),
            'parent_id': location.parent_id or '',
            'parent_name': location.parent.name if location.parent else '- Raíz -',
            'modal_title': f"Editar Ubicación: {location.name}",
        }
        return HttpResponse(render_to_string(self.template_name, context, request=request))

    def post(self, request, pk, *args, **kwargs):
        location = get_object_or_404(Location, pk=pk)
        form = LocationForm(request.POST, instance=location)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        updated_location = form.save(commit=False)
        updated_location.updated_by = request.user
        updated_location.save()
        return JsonResponse({
            'success': True,
            'message': 'Ubicación actualizada exitosamente.',
            'new_stats': {},
        })


@login_required
@require_POST
@permission_required('core.change_location', raise_exception=True)
def location_toggle_status(request, pk):
    """Alterna el estado activo/inactivo de una ubicación geográfica."""
    location = get_object_or_404(Location, pk=pk)
    location.is_active = not location.is_active
    location.updated_by = request.user
    location.save(update_fields=['is_active', 'updated_by', 'updated_at'])

    status_label = 'activada' if location.is_active else 'desactivada'
    return JsonResponse({
        'success': True,
        'message': f'La ubicación "{location.name}" ha sido {status_label} correctamente.',
        'new_stats': {},
    })


class LocationCascadeOptionsView(LoginRequiredMixin, View):
    """Retorna opciones de ubicaciones activas para selectores Select2 en cascada."""

    def get(self, request, *args, **kwargs):
        parent_id = request.GET.get('parent_id')
        if parent_id:
            qs = Location.objects.filter(parent_id=parent_id, is_active=True).order_by('name')
        else:
            qs = Location.objects.filter(level=1, is_active=True).order_by('name')

        data = [{'id': loc.id, 'name': loc.name} for loc in qs]
        return JsonResponse({'success': True, 'data': data})


# =====================================================================
# 5. CONFIGURACIÓN DEL SISTEMA Y HOJA MEMBRETADA
# =====================================================================
class SystemLetterheadView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.view_systemconfiguration'
    template_name = 'core/system_letterhead.html'

    def get_configuration(self):
        return SystemConfiguration.get_current() or SystemConfiguration.objects.order_by('-effective_date').first()

    def get(self, request):
        configuration = self.get_configuration()
        return render(request, self.template_name, {
            'form': SystemLetterheadForm(instance=configuration),
            'config_form': SystemConfigurationSetupForm(instance=configuration),
            'configuration': configuration,
        })

    def post(self, request):
        if not request.user.has_perm('core.change_systemconfiguration'):
            messages.error(request, 'No tiene permisos para modificar la hoja membretada.')
            return redirect('core:system_letterhead')

        configuration = self.get_configuration()
        action_type = request.POST.get('action_type', 'letterhead')

        if action_type == 'setup':
            config_form = SystemConfigurationSetupForm(request.POST, request.FILES, instance=configuration)
            form = SystemLetterheadForm(instance=configuration)
            if config_form.is_valid():
                config = config_form.save(commit=False)
                if configuration is None:
                    config.created_by = request.user
                config.updated_by = request.user
                config.save()
                messages.success(request, 'Configuración general guardada correctamente.')
                return redirect('core:system_letterhead')

            return render(request, self.template_name, {
                'form': form,
                'config_form': config_form,
                'configuration': configuration,
            })

        if configuration is None:
            messages.error(request, 'Debe registrar primero la configuración general del sistema.')
            return render(request, self.template_name, {
                'form': SystemLetterheadForm(),
                'config_form': SystemConfigurationSetupForm(request.POST, request.FILES),
                'configuration': configuration,
            })

        form = SystemLetterheadForm(request.POST, request.FILES, instance=configuration)
        if form.is_valid():
            config = form.save(commit=False)
            config.updated_by = request.user
            config.save()
            messages.success(request, 'Hoja membretada actualizada correctamente.')
            return redirect('core:system_letterhead')

        return render(request, self.template_name, {
            'form': form,
            'config_form': SystemConfigurationSetupForm(instance=configuration),
            'configuration': configuration,
        })


# =====================================================================
# 6. MANEJADORES DE ERROR HTTP
# =====================================================================
def custom_page_not_found(request, exception=None):
    return render(request, '404.html', status=404)


def custom_permission_denied(request, exception=None):
    return render(request, '403.html', status=403)


def custom_server_error(request, exception=None):
    return render(request, '500.html', status=500)
