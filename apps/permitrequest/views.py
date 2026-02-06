from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
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
    partial_template_name = 'permissions/partials/partial_permissions_type_list.html'  # Tabla sola
    context_object_name = 'types'
    permission_required = 'permitrequest.view_permittype'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        parent_id = self.request.GET.get('parent_id')  # Nuevo parámetro

        if query:
            queryset = queryset.filter(Q(name__icontains=query))

        # Filtro para navegar sub-items
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        else:
            if not query:  # Si hay busqueda, buscamos en todo, si no, solo padres
                queryset = queryset.filter(parent__isnull=True)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasamos el padre actual para poner un botón de "Volver" si es necesario
        parent_id = self.request.GET.get('parent_id')
        if parent_id:
            try:
                context['current_parent'] = PermitType.objects.get(pk=parent_id)
            except PermitType.DoesNotExist:
                context['current_parent'] = None
        return context


class PermitTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PermitType
    form_class = PermitTypeForm
    template_name = 'permissions/modals/modal_permissions_type_form.html'
    success_url = reverse_lazy('permissions:type_list')
    permission_required = 'permitrequest.add_permittype'

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Renderizar solo el contenido del modal
            html = render_to_string(self.template_name, {'form': form, 'request': request})
            return HttpResponse(html)
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Tipo de permiso creado correctamente.'})
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return super().form_invalid(form)

    def get_initial(self):
        initial = super().get_initial()
        # Si venimos de "Crear Sub-item", pre-llenamos el padre
        parent_id = self.request.GET.get('parent')
        if parent_id:
            initial['parent'] = parent_id
        return initial


class PermitTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = PermitType
    form_class = PermitTypeForm
    template_name = 'permissions/modals/modal_permissions_type_form.html'
    success_url = reverse_lazy('permissions:type_list')
    permission_required = 'permitrequest.change_permittype'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Renderizar solo el contenido del modal
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, {'form': form, 'request': request})
            return JsonResponse({'html': html}) if False else HttpResponse(html)
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Tipo de permiso actualizado correctamente.'})
        return super().form_valid(form)
    
    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class PermitTypeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = PermitType
    success_url = reverse_lazy('permissions:type_list')
    permission_required = 'permitrequest.delete_permittype'

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


class PermitTypeToggleView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.change_permittype'

    def post(self, request, pk):
        permit_type = get_object_or_404(PermitType, pk=pk)
        permit_type.is_active = not permit_type.is_active
        permit_type.save()
        
        status_text = 'activado' if permit_type.is_active else 'desactivado'
        return JsonResponse({
            'success': True,
            'message': f'Tipo de permiso "{permit_type.name}" {status_text} correctamente'
        })
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            permit = get_object_or_404(PermitType, pk=pk)
            permit.is_active = not permit.is_active  # Invertir estado
            permit.save()

            status_text = "activado" if permit.is_active else "desactivado"
            return JsonResponse({'success': True, 'message': f'Tipo de permiso {status_text} correctamente.'})
        return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)
