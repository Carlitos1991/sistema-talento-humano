from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView
from django.utils import timezone
from datetime import datetime
import re
import os
from django.shortcuts import render
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
        # Permitir filtrar por rango de fechas vía parámetros GET (date_from/date_to)
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from and date_to:
            try:
                d_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                d_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(registration_date__date__range=(d_from, d_to))
            except Exception:
                # Si las fechas no son válidas, fallback a año actual
                year = timezone.now().year
                queryset = queryset.filter(registration_date__year=year)
        else:
            # Permitir filtrar por año vía parámetro GET (por defecto año actual)
            try:
                year = int(self.request.GET.get('year') or timezone.now().year)
            except (TypeError, ValueError):
                year = timezone.now().year
            queryset = queryset.filter(registration_date__year=year)

        # Si el usuario NO tiene permiso de eliminar, además restringir a sus propios documentos
        if not getattr(self.request.user, 'is_superuser', False) and not self.request.user.has_perm(
                'documents.delete_document'):
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
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            is_export = request.GET.get('export') == 'true'

            if is_export:
                self.object_list = self.get_queryset()
                # Calcular índice global para la exportación
                global_order = list(
                    Document.objects.filter(is_active=True).order_by('-registration_date').values_list('id', flat=True))
                rank_map = {did: idx + 1 for idx, did in enumerate(global_order)}
                for o in self.object_list:
                    o.global_index = rank_map.get(o.id)

                html = render_to_string(
                    'documents/partials/partial_document_table.html',
                    {'documents': self.object_list},
                    request=request
                )
                return HttpResponse(html)

            # --- Lógica para peticiones AJAX normales (no exportación) ---
            self.object_list = self.get_queryset()
            paginator, page_obj, object_list, is_paginated = self.paginate_queryset(self.object_list, self.paginate_by)

            # Calcular índice global para la página actual
            global_order = list(
                Document.objects.filter(is_active=True).order_by('-registration_date').values_list('id', flat=True))
            rank_map = {did: idx + 1 for idx, did in enumerate(global_order)}
            for o in object_list:
                o.global_index = rank_map.get(o.id)

            html = render_to_string(
                'documents/partials/partial_document_table.html',
                {'documents': object_list},
                request=request
            )

            # Estadísticas
            date_from = request.GET.get('date_from')
            date_to = request.GET.get('date_to')
            stats_qs_filter = Q(documents__is_active=True)
            stats_total_filter = Q(is_active=True)

            if date_from and date_to:
                try:
                    d_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                    d_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                    stats_qs_filter &= Q(documents__registration_date__date__range=(d_from, d_to))
                    stats_total_filter &= Q(registration_date__date__range=(d_from, d_to))
                except Exception:
                    year = timezone.now().year
                    stats_qs_filter &= Q(documents__registration_date__year=year)
                    stats_total_filter &= Q(registration_date__year=year)
            else:
                year = timezone.now().year
                stats_qs_filter &= Q(documents__registration_date__year=year)
                stats_total_filter &= Q(registration_date__year=year)

            types_qs = DocumentType.objects.filter(is_active=True).annotate(
                count=Count('documents', filter=stats_qs_filter),
                user_count=Count('documents', filter=stats_qs_filter & Q(documents__created_by=request.user))
            ).order_by('name')

            stats = {
                'total': Document.objects.filter(stats_total_filter).count(),
                'total_user': Document.objects.filter(stats_total_filter, created_by=request.user).count(),
                'regimes': [{'code': t.id, 'name': t.name, 'count': t.count, 'user_count': t.user_count} for t in
                            types_qs]
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
        # Estadísticas limitadas a rango de fechas si se envían, sino por año (por defecto año actual)
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from and date_to:
            try:
                d_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                d_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                types_qs = DocumentType.objects.filter(is_active=True).annotate(
                    count=Count('documents', filter=Q(documents__is_active=True,
                                                      documents__registration_date__date__range=(d_from, d_to))),
                    user_count=Count('documents', filter=Q(documents__is_active=True,
                                                           documents__registration_date__date__range=(d_from, d_to),
                                                           documents__created_by=self.request.user))
                ).order_by('name')

                ctx['stats'] = {
                    'total': Document.objects.filter(is_active=True,
                                                     registration_date__date__range=(d_from, d_to)).count(),
                    'total_user': Document.objects.filter(is_active=True, registration_date__date__range=(d_from, d_to),
                                                          created_by=self.request.user).count(),
                    'regimes': [
                        {'code': t.id, 'name': t.name, 'count': t.count, 'user_count': t.user_count}
                        for t in types_qs
                    ]
                }
            except Exception:
                # Fallback a año actual
                try:
                    year = int(self.request.GET.get('year') or timezone.now().year)
                except (TypeError, ValueError):
                    year = timezone.now().year
                types_qs = DocumentType.objects.filter(is_active=True).annotate(
                    count=Count('documents',
                                filter=Q(documents__is_active=True, documents__registration_date__year=year)),
                    user_count=Count('documents',
                                     filter=Q(documents__is_active=True, documents__registration_date__year=year,
                                              documents__created_by=self.request.user))
                ).order_by('name')

                ctx['stats'] = {
                    'total': Document.objects.filter(is_active=True, registration_date__year=year).count(),
                    'total_user': Document.objects.filter(is_active=True, registration_date__year=year,
                                                          created_by=self.request.user).count(),
                    'regimes': [
                        {'code': t.id, 'name': t.name, 'count': t.count, 'user_count': t.user_count}
                        for t in types_qs
                    ]
                }
        else:
            try:
                year = int(self.request.GET.get('year') or timezone.now().year)
            except (TypeError, ValueError):
                year = timezone.now().year
            types_qs = DocumentType.objects.filter(is_active=True).annotate(
                count=Count('documents', filter=Q(documents__is_active=True, documents__registration_date__year=year)),
                user_count=Count('documents',
                                 filter=Q(documents__is_active=True, documents__registration_date__year=year,
                                          documents__created_by=self.request.user))
            ).order_by('name')

            ctx['stats'] = {
                'total': Document.objects.filter(is_active=True, registration_date__year=year).count(),
                'total_user': Document.objects.filter(is_active=True, registration_date__year=year,
                                                      created_by=self.request.user).count(),
                'regimes': [
                    {'code': t.id, 'name': t.name, 'count': t.count, 'user_count': t.user_count}
                    for t in types_qs
                ]
            }
        # Anotar índices globales para los objetos de la página (mismo criterio que en la petición AJAX)
        try:
            global_order = list(
                Document.objects.filter(is_active=True).order_by('-registration_date').values_list('id', flat=True))
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
    template_name = 'documents/modals/modal_document_form.html'
    permission_required = 'documents.add_document'

    def get(self, request, *args, **kwargs):
        category_id = request.GET.get('category_id')
        category = get_object_or_404(DocumentType, pk=category_id)

        # Calcular siguiente código
        year = timezone.now().year
        prefix = f'ML-DTH-{year}-'
        initials = ''.join([w[0].upper() for w in re.findall(r"[A-Za-zÀ-ÿ]+", category.name)])
        total_count = Document.objects.filter(category=category, registration_date__year=year, is_active=True).count()
        next_code = f"{prefix}{total_count + 1:03d}{('-' + initials) if initials else ''}"

        return render(request, self.template_name, {
            'form': self.get_form(),
            'category': category,
            'next_code': next_code
        })

    def post(self, request, *args, **kwargs):
        # Reutilizamos la lógica de creación múltiple si envían quantity
        quantity = int(request.POST.get('quantity') or 1)
        if quantity > 1:
            return create_multiple_documents(request)

        form = self.get_form()
        if form.is_valid():
            form.instance.created_by = request.user
            form.save()
            return JsonResponse({'status': 'success', 'message': 'Documento creado correctamente.'})
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class DocumentTypeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = DocumentType
    template_name = 'documents/type_list.html'
    context_object_name = 'types'
    permission_required = 'documents.view_documenttype'

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(name__icontains=q)
        return queryset.order_by('name')

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'documents/partials/partial_type_table.html',
                context,
                request=self.request
            )
            return HttpResponse(html)
        return super().render_to_response(context, **response_kwargs)


# --- CREAR (Responde JSON para Vue) ---
class DocumentTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = DocumentType
    form_class = DocumentTypeForm
    template_name = 'documents/modals/modal_type_form.html'  # Revisa que coincida exactamente con la carpeta
    permission_required = 'documents.add_documenttype'

    def get(self, request, *args, **kwargs):
        try:
            self.object = None
            form = self.get_form()
            return render(request, self.template_name, {'form': form})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return HttpResponse(f"Error cargando formulario: {str(e)}", status=500)

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Tipo de documento creado correctamente.'
            })
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            errors_data = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({
                'success': False,
                'errors': errors_data
            }, status=400)
        return super().form_invalid(form)


# --- EDITAR (Responde JSON para Vue) ---
class DocumentTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = DocumentType
    form_class = DocumentTypeForm
    template_name = 'documents/modals/modal_type_form.html'
    permission_required = 'documents.change_documenttype'

    def get(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
            form = self.get_form()
            return render(request, self.template_name, {'form': form, 'object': self.object})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return HttpResponse(f"Error cargando formulario: {str(e)}", status=500)

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Registro actualizado correctamente.'
            })
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            errors_data = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({
                'success': False,
                'errors': errors_data
            }, status=400)
        return super().form_invalid(form)


class DocumentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Document
    form_class = DocumentForm
    template_name = 'documents/modals/modal_document_form.html'
    permission_required = 'documents.change_document'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return render(request, self.template_name, {
            'form': self.get_form(),
            'object': self.object
        })

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        try:
            form.instance.sender_name = self.request.user.get_full_name() or str(self.request.user)
        except Exception:
            pass
        self.object = form.save()
        return JsonResponse({'status': 'success', 'message': 'Documento actualizado correctamente.'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


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
            'created_by': doc.created_by.get_full_name() if getattr(doc, 'created_by', None) else None,
            'updated_by': doc.updated_by.get_full_name() if getattr(doc, 'updated_by', None) else None,
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
    return JsonResponse(
        {'success': True, 'message': 'Archivo guardado correctamente.', 'file_url': doc.file_attachment.url})


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
    if not request.user.has_perm('documents.change_documenttype'):
        return JsonResponse({'success': False, 'message': 'Sin permisos suficientes.'}, status=403)

    doc_type = get_object_or_404(DocumentType, pk=pk)
    doc_type.is_active = not doc_type.is_active
    doc_type.save()

    return JsonResponse({
        'status': 'success',
        'success': True,
        'message': f'Estado de "{doc_type.name}" cambiado a {"Activo" if doc_type.is_active else "Inactivo"}.'
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
    # Validación: 'recipient_name' es obligatorio
    if not recipient_name or not recipient_name.strip():
        return JsonResponse({'success': False, 'message': 'El campo "A Quién va Dirigido" es obligatorio.'}, status=400)
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
        try:
            doc.created_by = request.user
        except Exception:
            pass
        doc.save()
        created.append({'id': doc.id, 'filing_code': doc.filing_code})

    return JsonResponse({'success': True, 'created': created,
                         'message': f'Documento{"s" if len(created) > 1 else ""} creado{"s" if len(created) > 1 else ""} exitosamente'})


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
