from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.template.loader import render_to_string

from .models import PermitType, PermitRequest
from .forms import PermitTypeForm, PermitRequestForm


# --- MIXIN PARA BÚSQUEDA AJAX (Híbrido) ---
class JSONResponseMixin:
    """
    Mixin para manejar respuestas AJAX en ListViews (Búsqueda dinámica).
    Si es AJAX, renderiza solo la tabla parcial y la devuelve en JSON.
    """

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.partial_template_name, context, request=self.request)
            return JsonResponse({'html': html})
        return super().render_to_response(context, **response_kwargs)


# ==========================================
# VISTAS: TIPOS DE PERMISO (Configuración)
# ==========================================

class PermitTypeListView(LoginRequiredMixin, PermissionRequiredMixin, JSONResponseMixin, ListView):
    model = PermitType
    template_name = 'permissions/permissions_type_list.html'
    partial_template_name = 'permissions/partial_permissions_type_list.html'  # Tabla sola
    context_object_name = 'types'
    permission_required = 'permissions.view_permittype'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
            )
        return queryset


class PermitTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PermitType
    form_class = PermitTypeForm
    template_name = 'permissions/modals/modal_permissions_type_form.html'
    success_url = reverse_lazy('permissions:type_list')
    permission_required = 'permissions.add_permittype'

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # 200 OK -> Éxito
            return JsonResponse({'success': True, 'message': 'Tipo de permiso creado correctamente.'})
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # 400 Bad Request -> Enviamos errores de validación
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class PermitTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = PermitType
    form_class = PermitTypeForm
    template_name = 'permissions/modals/modal_permissions_type_form.html'
    success_url = reverse_lazy('permissions:type_list')
    permission_required = 'permissions.change_permittype'

    # Lógica similar para manejo de errores en Modales AJAX...
    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Actualizado correctamente.'})
        return super().form_valid(form)


class PermitTypeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = PermitType
    success_url = reverse_lazy('permissions:type_list')
    permission_required = 'permissions.delete_permittype'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Eliminado correctamente.'})
        return super().delete(request, *args, **kwargs)


# ==========================================
# VISTAS: SOLICITUDES DE PERMISO (Gestión)
# ==========================================

class PermitRequestListView(LoginRequiredMixin, PermissionRequiredMixin, JSONResponseMixin, ListView):
    model = PermitRequest
    template_name = 'permissions/permissions_permit_list.html'
    partial_template_name = 'permissions/partial_permissions_permit_list.html'
    context_object_name = 'permits'
    permission_required = 'permissions.view_permitrequest'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('employee', 'permit_type')
        query = self.request.GET.get('q')

        # Filtros adicionales (puedes expandir esto)
        status = self.request.GET.get('status')

        if query:
            queryset = queryset.filter(
                Q(employee__first_name__icontains=query) |
                Q(employee__last_name__icontains=query) |
                Q(employee__identification__icontains=query)
            )

        if status:
            queryset = queryset.filter(status=status)

        return queryset


class PermitRequestCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PermitRequest
    form_class = PermitRequestForm
    template_name = 'permissions/permissions_permit_form.html'  # Página completa (no modal)
    success_url = reverse_lazy('permissions:permit_list')
    permission_required = 'permissions.add_permitrequest'

    def form_valid(self, form):
        # Asignar auditoría
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class PermitRequestUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = PermitRequest
    form_class = PermitRequestForm
    template_name = 'permissions/permissions_permit_form.html'
    success_url = reverse_lazy('permissions:permit_list')
    permission_required = 'permissions.change_permitrequest'

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


def permit_type_detail_api(request, pk):
    """
    Devuelve detalles de configuración de un tipo de permiso en JSON.
    Usado por el frontend para validar adjuntos y mostrar alertas.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        permit_type = PermitType.objects.get(pk=pk)
        data = {
            'id': permit_type.id,
            'name': permit_type.name,
            'affects_vacation': permit_type.affects_vacation,
            'requires_attachment': permit_type.requires_attachment,
            'needs_justification': permit_type.needs_justification
        }
        return JsonResponse(data)
    except PermitType.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
