from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView
from django.utils import timezone
import re

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
                Q(filing_code__icontains=q) | Q(subject__icontains=q)
            )

        # Filtrado por tipo de documento (regime_code viene del frontend)
        regime_code = self.request.GET.get('regime_code')
        if regime_code:
            try:
                rc = int(regime_code)
                queryset = queryset.filter(category_id=rc)
            except (ValueError, TypeError):
                # Si no es convertible, ignoramos el filtro
                pass
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
            # Estadísticas por tipo de documento
            types_qs = DocumentType.objects.filter(is_active=True).annotate(
                count=Count('documents', filter=Q(documents__is_active=True))
            ).order_by('name')

            stats = {
                'total': Document.objects.filter(is_active=True).count(),
                'regimes': [
                    {'code': t.id, 'name': t.name, 'count': t.count}
                    for t in types_qs
                ]
            }

            return JsonResponse({'html': html, 'stats': stats})
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        types_qs = DocumentType.objects.filter(is_active=True).annotate(
            count=Count('documents', filter=Q(documents__is_active=True))
        ).order_by('name')

        ctx['stats'] = {
            'total': Document.objects.filter(is_active=True).count(),
            'regimes': [
                {'code': t.id, 'name': t.name, 'count': t.count}
                for t in types_qs
            ]
        }
        return ctx
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


@require_POST
def create_multiple_documents(request):
    # Crear N documentos con secuencias automáticas
    if not request.user.has_perm('documents.add_document'):
        return JsonResponse({'success': False, 'message': 'Sin permisos'}, status=403)

    try:
        category_id = int(request.POST.get('category'))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Categoría inválida'}, status=400)

    quantity = request.POST.get('quantity') or '1'
    try:
        quantity = int(quantity)
    except ValueError:
        quantity = 1
    if quantity < 1 or quantity > 20:
        return JsonResponse({'success': False, 'message': 'Cantidad inválida (1-20)'}, status=400)

    subject = request.POST.get('subject', '')
    sender_name = request.POST.get('sender_name', '')
    recipient_name = request.POST.get('recipient_name', '')
    observation = request.POST.get('observation', '')
    file_obj = request.FILES.get('file_attachment')

    # Calcular siguiente secuencia basada en el total de documentos del tipo
    year = timezone.now().year
    prefix = f'ML-DTH-{year}-'

    # Obtener iniciales del tipo de documento
    try:
        dtype = DocumentType.objects.get(pk=category_id)
        initials = ''.join([w[0].upper() for w in re.findall(r"[A-Za-zÀ-ÿ]+", dtype.name)])
    except DocumentType.DoesNotExist:
        initials = ''

    # Contar TODOS los documentos de este tipo (sin filtrar por año)
    # El siguiente número será el total + 1
    total_count = Document.objects.filter(category_id=category_id).count()

    created = []
    for i in range(1, quantity + 1):
        seq = total_count + i
        code = f"{prefix}{seq:03d}{('-' + initials) if initials else ''}"
        doc = Document(
            filing_code=code,
            category_id=category_id,
            subject=subject,
            sender_name=sender_name,
            recipient_name=recipient_name,
            observation=observation,
            registration_date=timezone.now(),
            is_active=True
        )
        if file_obj:
            # Reuse same file object — Django will handle saving copy
            doc.file_attachment = file_obj
        doc.save()
        created.append({'id': doc.id, 'filing_code': doc.filing_code})

    return JsonResponse({'success': True, 'created': created, 'message': f'Documento{"s" if len(created) > 1 else ""} creado{"s" if len(created) > 1 else ""} exitosamente'})


def next_filing_code(request, category_id):
    # Devuelve el siguiente código formateado basado en el total de registros del tipo
    try:
        cid = int(category_id)
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Categoría inválida'}, status=400)

    year = timezone.now().year
    prefix = f'ML-DTH-{year}-'
    try:
        dtype = DocumentType.objects.get(pk=cid)
        initials = ''.join([w[0].upper() for w in re.findall(r"[A-Za-zÀ-ÿ]+", dtype.name)])
    except DocumentType.DoesNotExist:
        initials = ''

    # Contar todos los documentos de este tipo (sin filtrar por año)
    # El siguiente número será el total + 1
    total_count = Document.objects.filter(category_id=cid).count()
    next_num = total_count + 1

    next_code = f"{prefix}{next_num:03d}{('-' + initials) if initials else ''}"
    return JsonResponse({'success': True, 'code': next_code, 'next_number': next_num})
