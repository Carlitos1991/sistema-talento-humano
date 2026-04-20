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
import os

from .forms import DocumentForm
from .forms import DocumentTypeForm
from .models import Document
from .models import DocumentType
from django.views.generic import UpdateView
from django.http import HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


class DocumentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Document
    template_name = 'documents/document_list.html'
    context_object_name = 'documents'
    paginate_by = 10
    permission_required = 'documents.view_document'

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True)
        # Permitir filtrar por año vía parámetro GET (por defecto año actual)
        try:
            year = int(self.request.GET.get('year') or timezone.now().year)
        except (TypeError, ValueError):
            year = timezone.now().year

        # Filtrar por año solicitado para el listado (siempre se aplica)
        queryset = queryset.filter(registration_date__year=year)

        # Si el usuario NO tiene permiso de eliminar, además restringir a sus propios documentos
        if not getattr(self.request.user, 'is_superuser', False) and not self.request.user.has_perm('documents.delete_document'):
            queryset = queryset.filter(created_by=self.request.user)
        q = self.request.GET.get('q')
        if q:
            # Buscar por número de expediente, asunto o por nombre/apellidos del responsable (sender_name)
            queryset = queryset.filter(
                Q(filing_code__icontains=q) |
                Q(subject__icontains=q) |
                Q(sender_name__icontains=q)
            )

        # Filtrado por tipo de documento (parametro 'documents' desde frontend)
        documents_param = self.request.GET.get('documents')
        if documents_param:
            try:
                rc = int(documents_param)
                queryset = queryset.filter(category_id=rc)
            except (ValueError, TypeError):
                # Si no es convertible, ignoramos el filtro
                pass
        # Ordenamiento (opcional)
        sort_field = self.request.GET.get('sort_field')
        sort_dir = self.request.GET.get('sort_dir', 'asc')
        if sort_field:
            # Mapear campos seguros desde la plantilla a campos del modelo
            mapping = {
                'filing_code': 'filing_code',
                'category': 'category__name',
                'subject': 'subject',
                'recipient_name': 'recipient_name',
                'sender_name': 'sender_name',
                'registration_date': 'registration_date'
            }
            field = mapping.get(sort_field, None)
            if field:
                if sort_dir == 'desc':
                    field = f'-{field}'
                try:
                    queryset = queryset.order_by(field)
                except Exception:
                    pass
        return queryset

    def get(self, request, *args, **kwargs):
        # Si es petición AJAX, devolvemos solo la tabla parcial
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            # Aplicar paginación al resultado antes de renderizar el partial
            page = request.GET.get('page') or 1
            try:
                page = int(page)
            except (ValueError, TypeError):
                page = 1
            paginator, page_obj, object_list, is_paginated = self.paginate_queryset(self.object_list, self.paginate_by)
            # Calcular índice global (secuencia numérica) sobre TODOS los documentos activos
            global_order = list(Document.objects.filter(is_active=True).order_by('-registration_date').values_list('id', flat=True))
            rank_map = {did: idx + 1 for idx, did in enumerate(global_order)}
            # Anotar cada objeto de la página con su índice global para mostrar en la tabla
            for o in object_list:
                try:
                    o.global_index = rank_map.get(o.id)
                except Exception:
                    o.global_index = None

            html = render_to_string(
                'documents/partials/partial_document_table.html',
                {'documents': object_list},
                request=request
            )
            # Estadísticas por tipo de documento (solo del año solicitado)
            try:
                year = int(request.GET.get('year') or timezone.now().year)
            except (TypeError, ValueError):
                year = timezone.now().year

            types_qs = DocumentType.objects.filter(is_active=True).annotate(
                count=Count('documents', filter=Q(documents__is_active=True, documents__registration_date__year=year)),
                user_count=Count('documents', filter=Q(documents__is_active=True, documents__registration_date__year=year, documents__created_by=request.user))
            ).order_by('name')

            stats = {
                'total': Document.objects.filter(is_active=True, registration_date__year=year).count(),
                'total_user': Document.objects.filter(is_active=True, registration_date__year=year, created_by=request.user).count(),
                'regimes': [
                    {'code': t.id, 'name': t.name, 'count': t.count, 'user_count': t.user_count}
                    for t in types_qs
                ]
            }

            pagination = {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count
            }
            return JsonResponse({'html': html, 'stats': stats, 'pagination': pagination})
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Estadísticas limitadas al año solicitado (por defecto año actual)
        try:
            year = int(self.request.GET.get('year') or timezone.now().year)
        except (TypeError, ValueError):
            year = timezone.now().year

        types_qs = DocumentType.objects.filter(is_active=True).annotate(
            count=Count('documents', filter=Q(documents__is_active=True, documents__registration_date__year=year)),
            user_count=Count('documents', filter=Q(documents__is_active=True, documents__registration_date__year=year, documents__created_by=self.request.user))
        ).order_by('name')

        ctx['stats'] = {
            'total': Document.objects.filter(is_active=True, registration_date__year=year).count(),
            'total_user': Document.objects.filter(is_active=True, registration_date__year=year, created_by=self.request.user).count(),
            'regimes': [
                {'code': t.id, 'name': t.name, 'count': t.count, 'user_count': t.user_count}
                for t in types_qs
            ]
        }
        # Anotar índices globales para los objetos de la página (mismo criterio que en la petición AJAX)
        try:
            global_order = list(Document.objects.filter(is_active=True).order_by('-registration_date').values_list('id', flat=True))
            rank_map = {did: idx + 1 for idx, did in enumerate(global_order)}
            docs = ctx.get('documents')
            if docs:
                for d in docs:
                    setattr(d, 'global_index', rank_map.get(d.id))
        except Exception:
            pass

        return ctx


class DocumentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Document
    form_class = DocumentForm
    template_name = 'documents/modals/modal_document_form.html'  # Usado para obtener el HTML del modal si fuera server-side, o referencial
    permission_required = 'documents.add_document'
    success_url = reverse_lazy('documents:document_list')

    def form_valid(self, form):
        # Asignar creador antes de guardar
        form.instance.created_by = self.request.user
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


class DocumentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Document
    form_class = DocumentForm
    permission_required = 'documents.change_document'

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'success': True, 'message': 'Documento actualizado correctamente.'})

    def form_invalid(self, form):
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


def document_detail(request, pk):
    try:
        doc = Document.objects.get(pk=pk)
        data = {
            'id': doc.id,
            'filing_code': doc.filing_code,
            'category': doc.category.id if doc.category else None,
            'category_name': doc.category.name if doc.category else None,
            'subject': doc.subject,
            'recipient_name': doc.recipient_name,
            'sender_name': doc.sender_name,
            'observation': doc.observation,
            'file_url': doc.file_attachment.url if doc.file_attachment else None,
        }
        return JsonResponse({'success': True, 'data': data})
    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Documento no encontrado'}, status=404)


@require_POST
def upload_document_file(request, pk):
    try:
        doc = Document.objects.get(pk=pk)
    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Documento no encontrado'}, status=404)

    file = request.FILES.get('file') or request.FILES.get('file_attachment')
    if not file:
        return JsonResponse({'success': False, 'message': 'No se recibió archivo'}, status=400)

    # Reemplazar o asignar archivo
    doc.file_attachment = file
    doc.save()
    return JsonResponse({'success': True, 'message': 'Archivo guardado correctamente.', 'file_url': doc.file_attachment.url})


@require_POST
def delete_document_file(request, pk):
    try:
        doc = Document.objects.get(pk=pk)
    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Documento no encontrado'}, status=404)

    # Borrar fichero físico si existe
    if doc.file_attachment:
        try:
            if os.path.isfile(doc.file_attachment.path):
                os.remove(doc.file_attachment.path)
        except Exception:
            pass
    doc.file_attachment = None
    doc.save()
    return JsonResponse({'success': True, 'message': 'Archivo eliminado.'})


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

    # Contar documentos de este tipo en el año actual y activos
    # El siguiente número será el total + 1 (secuencia por año)
    total_count = Document.objects.filter(category_id=category_id, registration_date__year=year, is_active=True).count()

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

    # Contar documentos de este tipo en el año actual y activos
    # El siguiente número será el total + 1 (secuencia por año)
    total_count = Document.objects.filter(category_id=cid, registration_date__year=year, is_active=True).count()
    next_num = total_count + 1

    next_code = f"{prefix}{next_num:03d}{('-' + initials) if initials else ''}"
    return JsonResponse({'success': True, 'code': next_code, 'next_number': next_num})
