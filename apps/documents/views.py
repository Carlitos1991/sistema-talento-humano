from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView

from .forms import DocumentForm
from .forms import DocumentTypeForm
from .models import Document
from .models import DocumentType


class DocumentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Document
    template_name = 'documents/document_list.html'
    context_object_name = 'documents'
    paginate_by = 10
    permission_required = 'documents.view_document'

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True)
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                filing_code__icontains=q
            ) | queryset.filter(subject__icontains=q)
        return queryset

    def get(self, request, *args, **kwargs):
        # Si es petición AJAX, devolvemos solo la tabla parcial
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            html = render_to_string(
                'documents/partials/partial_document_table.html',
                {'documents': self.object_list},
                request=request
            )
            return JsonResponse({'html': html})
        return super().get(request, *args, **kwargs)


class DocumentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Document
    form_class = DocumentForm
    template_name = 'documents/modals/modal_document_form.html'  # Usado para obtener el HTML del modal si fuera server-side, o referencial
    permission_required = 'documents.add_document'
    success_url = reverse_lazy('documents:document_list')

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'status': 'success', 'message': 'Documento registrado correctamente.'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class DocumentTypeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = DocumentType
    template_name = 'documents/type_list.html'
    context_object_name = 'types'
    paginate_by = 10
    permission_required = 'documents.view_documenttype'

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(name__icontains=q)
        return queryset

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            html = render_to_string(
                'documents/partials/partial_type_table.html',
                {'types': self.object_list},
                request=request
            )
            return JsonResponse({'html': html})
        return super().get(request, *args, **kwargs)


# --- CREAR (Responde JSON para Vue) ---
class DocumentTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = DocumentType
    form_class = DocumentTypeForm
    permission_required = 'documents.add_documenttype'

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({
            'success': True,
            'message': 'Tipo de documento creado correctamente.'
        })

    def form_invalid(self, form):
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


# --- EDITAR (Responde JSON para Vue) ---
class DocumentTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = DocumentType
    form_class = DocumentTypeForm
    permission_required = 'documents.change_documenttype'

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({
            'success': True,
            'message': 'Registro actualizado correctamente.'
        })

    def form_invalid(self, form):
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


def document_type_detail(request, pk):
    try:
        doc_type = DocumentType.objects.get(pk=pk)
        data = {
            'id': doc_type.id,
            'name': doc_type.name,
            'is_active': doc_type.is_active
        }
        return JsonResponse({'success': True, 'data': data})
    except DocumentType.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Registro no encontrado'}, status=404)


# --- BAJA/ALTA (Toggle rápido) ---
@require_POST
def change_type_status(request, pk):
    # Verificación de permisos manual o decorator
    if not request.user.has_perm('documents.change_documenttype'):
        return JsonResponse({'success': False, 'message': 'Sin permisos'}, status=403)

    doc_type = get_object_or_404(DocumentType, pk=pk)
    doc_type.is_active = not doc_type.is_active
    doc_type.save()
    return JsonResponse({
        'success': True,
        'message': f'Estado cambiado a {"Activo" if doc_type.is_active else "Inactivo"}'
    })
