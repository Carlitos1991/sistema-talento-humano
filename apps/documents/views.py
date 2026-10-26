import os
import re
from datetime import datetime
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView
from django.views.generic import UpdateView

from institution.models import AdministrativeUnit
from .forms import DelegateTaskForm
from .forms import DocumentForm
from .forms import DocumentTypeForm
from .forms import ProcedureReceptionForm
from .forms import UserSignatureUploadForm, UserProfileSettingsForm
from .models import DocumentType
from .models import Procedure, ProcedureTask, ProcedureTrace, Document
from .models import ProcedureSumilla

from io import BytesIO
from django.template.loader import get_template
from django.utils.html import strip_tags
from xhtml2pdf import pisa
from .utils import generate_document_filing_code


# -------------------------------------------------------------------------
# 1. MODAL RESPONDER AL TRÁMITE (Solo tipos internos y activos)
# -------------------------------------------------------------------------
# views.py

@login_required
def procedure_create_response_modal(request, pk):
    """
    Despliega el modal de respuesta a un trámite:
    - Excluye tipos de documentos externos (solo muestra internos activos).
    - Permite elegir el nivel (Institucional o Personal).
    - Carga la plantilla inicial para el editor.
    """
    procedure = get_object_or_404(Procedure, pk=pk, is_active=True)
    user = request.user

    # Perfil institucional y área de trabajo
    person = getattr(user, 'person', None)
    employee = getattr(person, 'employee_profile', None) if person else None
    user_unit = employee.area if employee else None

    # Nombre y cargo seguros
    user_full_name = person.full_name if person and hasattr(person, 'full_name') else (
            user.get_full_name() or user.username)
    user_position = getattr(employee, 'job_position', None) or getattr(employee, 'position', None) or "Servidor Público"

    # FILTRAR: Solo tipos de documento internos y activos
    doc_types = DocumentType.objects.filter(is_active=True).exclude(
        is_external=True
    ).order_by('name')

    # Si no había campo is_external en filtro, fallback por nombre
    if not doc_types.exists():
        doc_types = DocumentType.objects.filter(is_active=True).exclude(
            name__icontains='externo'
        ).order_by('name')

    # Unidades jerárquicas desde la del usuario hacia arriba
    hierarchy_units = []
    curr = user_unit
    while curr:
        hierarchy_units.insert(0, curr)
        curr = curr.parent

    # Tipo inicial por defecto (Memorando o primer interno)
    selected_type = doc_types.first()
    suggested_code = ""
    if selected_type and user_unit:
        suggested_code = generate_document_filing_code(user_unit, user, selected_type, is_personal=True)

    now = timezone.now()
    default_template = f"""
    <div style="text-align: right; margin-bottom: 20px;">
        <strong>Loja, {now.day} de {now.strftime('%B')} de {now.year}</strong>
    </div>
    <table style="width: 100%; margin-bottom: 25px; border-collapse: collapse;">
        <tr>
            <td style="width: 15%; padding: 4px 0;"><strong>PARA:</strong></td>
            <td style="padding: 4px 0;">{procedure.external_sender or 'Despacho'}</td>
        </tr>
        <tr>
            <td style="padding: 4px 0;"><strong>DE:</strong></td>
            <td style="padding: 4px 0;">{user_full_name} &mdash; {user_position}</td>
        </tr>
        <tr>
            <td style="padding: 4px 0;"><strong>ASUNTO:</strong></td>
            <td style="padding: 4px 0;">Respuesta a trámite {procedure.code}: {procedure.subject}</td>
        </tr>
    </table>
    <hr style="border: 0; border-top: 1px solid #cbd5e1; margin-bottom: 20px;">
    <p>De mi consideración:</p>
    <p>En atención al trámite de la referencia, cumplo con informar a usted lo siguiente...</p>
    """

    return render(request, 'documents/modals/modal_create_response_doc.html', {
        'procedure': procedure,
        'doc_types': doc_types,
        'hierarchy_units': hierarchy_units,
        'user_unit': user_unit,
        'user_full_name': user_full_name,
        'user_position': user_position,
        'suggested_code': suggested_code,
        'default_template': default_template,
    })


# -------------------------------------------------------------------------
# 2. PROCESAR GUARDADO DE LA RESPUESTA (Borrador o Firma Electrónica)
# -------------------------------------------------------------------------
@login_required
@require_POST
def save_response_document(request, pk):
    """
    Guarda el documento generado como respuesta:
    - Genera el PDF a partir del HTML.
    - Si se selecciona firma electrónica, valida el certificado .p12 configurado.
    - Permite imprimir directamente para firma manual.
    """
    procedure = get_object_or_404(Procedure, pk=pk, is_active=True)
    user = request.user

    # Obtención segura de perfil y datos del actuante sin AttributeErrors
    person = getattr(user, 'person', None)
    employee = getattr(person, 'employee_profile', None) if person else None
    actor_name = person.full_name if person and hasattr(person, 'full_name') else (
            user.get_full_name() or user.username
    )
    actor_pos = getattr(employee, 'job_position', None) or getattr(employee, 'position', None) or "Servidor Público"

    category_id = request.POST.get('category_id')
    filing_code = request.POST.get('filing_code')
    content_html = request.POST.get('content_html', '').strip()
    sign_mode = request.POST.get('sign_mode', 'MANUAL')  # 'ELECTRONIC' o 'MANUAL'
    cert_password = request.POST.get('cert_password', '').strip()

    category = get_object_or_404(DocumentType, pk=category_id)

    if not content_html:
        return JsonResponse({'success': False, 'message': 'El cuerpo del documento no puede estar vacío.'}, status=400)

    with transaction.atomic():
        # 1. Crear registro oficial del documento
        doc = Document.objects.create(
            procedure=procedure,
            filing_code=filing_code,
            category=category,
            subject=f"Respuesta a {procedure.code}: {procedure.subject}",
            sender_name=actor_name,
            recipient_name=procedure.external_sender or "Despacho",
            body_html=content_html,
            is_entry_document=False,
            is_final_response=True,
            created_by=user
        )

        # 2. Generar archivo PDF en memoria mediante xhtml2pdf
        html_template = get_template('documents/pdf/template_official_document.html')
        rendered_html = html_template.render({
            'document': doc,
            'content_html': content_html,
            'user': user,
            'procedure': procedure,
            'is_signed': (sign_mode == 'ELECTRONIC')
        })

        pdf_io = BytesIO()
        pisa_status = pisa.CreatePDF(
            src=rendered_html,
            dest=pdf_io,
            encoding='utf-8'
        )
        if pisa_status.err:
            return JsonResponse({'success': False, 'message': 'Error generando el PDF del documento.'}, status=500)
        if pisa_status.err:
            return JsonResponse({'success': False, 'message': 'Error generando el PDF del documento.'}, status=500)

        pdf_bytes = pdf_io.getvalue()

        # 3. Validación y legalización digital (.p12 en memoria)
        if sign_mode == 'ELECTRONIC':
            sig_profile = getattr(user, 'signature_profile', None)
            if not sig_profile or not sig_profile.certificate_file:
                return JsonResponse({
                    'success': False,
                    'message': 'No cuenta con un certificado .p12 activo en su perfil.'
                }, status=400)

            if not cert_password:
                return JsonResponse({
                    'success': False,
                    'message': 'Debe ingresar la contraseña de su firma electrónica para legalizar.'
                }, status=400)

            # Validar credenciales del certificado
            from cryptography.hazmat.primitives.serialization import pkcs12
            try:
                sig_profile.certificate_file.open('rb')
                p12_data = sig_profile.certificate_file.read()
                pkcs12.load_key_and_certificates(p12_data, cert_password.encode('utf-8'))
            except Exception:
                return JsonResponse({'success': False, 'message': 'Contraseña del certificado incorrecta.'}, status=400)

            doc.doc_status = Document.DocumentStatus.SIGNED
        else:
            doc.doc_status = Document.DocumentStatus.APPROVED

        # 4. Almacenar el archivo PDF generado en disco/storage
        from django.core.files.base import ContentFile
        clean_code = filing_code.replace('/', '_').replace('-', '_')
        doc.file_attachment.save(f"{clean_code}.pdf", ContentFile(pdf_bytes), save=True)

        # 5. Cerrar las tareas pendientes del usuario para este trámite
        ProcedureTask.objects.filter(
            procedure=procedure,
            assigned_to=user,
            status__in=[ProcedureTask.TaskStatus.PENDING, ProcedureTask.TaskStatus.IN_PROCESS]
        ).update(status=ProcedureTask.TaskStatus.CLOSED)

        # 6. Registrar hito en la Hoja de Ruta Inmutable (Contraloría)
        mode_text = "con Firma Electrónica" if sign_mode == 'ELECTRONIC' else "para Firma Física / Manual"
        action_val = ProcedureTrace.TraceAction.DISPATCH if hasattr(ProcedureTrace.TraceAction,
                                                                    'DISPATCH') else ProcedureTrace.TraceAction.REPORT_ATTACHED

        ProcedureTrace.objects.create(
            procedure=procedure,
            document=doc,
            actor=user,
            actor_name=actor_name,
            actor_position=actor_pos,
            unit_name="Oficina Virtual",
            action=action_val,
            observation=f"Respuesta generada bajo radicado {doc.filing_code} ({mode_text})."
        )

    return JsonResponse({
        'success': True,
        'document_id': doc.id,
        'message': f'Documento {doc.filing_code} generado y vinculado exitosamente.'
    })


# -------------------------------------------------------------------------
# 3. LEGALIZACIÓN / HOJA DE DISPOSICIONES DE SUMILLA
# -------------------------------------------------------------------------
@login_required
def print_sumilla_dispositions(request, task_id):
    """
    Genera la Hoja Oficial de Sumilla y Disposiciones en PDF para firma manual
    o registro físico de archivo de Contraloría.
    """
    task = get_object_or_404(ProcedureTask, pk=task_id)
    sumilla = getattr(task, 'sumilla', None)

    html_template = get_template('documents/pdf/template_sumilla_sheet.html')
    rendered_html = html_template.render({
        'task': task,
        'sumilla': sumilla,
        'procedure': task.procedure,
        'today': timezone.now()
    })

    pdf_io = BytesIO()
    pisa.CreatePDF(rendered_html, dest=pdf_io)
    response = HttpResponse(pdf_io.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Sumilla_{task.procedure.code}.pdf"'
    return response


@login_required
@require_POST
def sign_sumilla_electronically(request, task_id):
    """
    Legaliza electrónicamente la sumilla usando el certificado .p12 del jefe/director.
    """
    task = get_object_or_404(ProcedureTask, pk=task_id)
    sumilla = getattr(task, 'sumilla', None)
    if not sumilla:
        return JsonResponse({'success': False, 'message': 'Esta tarea no tiene sumilla asociada.'}, status=400)

    password = request.POST.get('password', '').strip()
    sig_profile = getattr(request.user, 'signature_profile', None)

    if not sig_profile or not sig_profile.certificate_file:
        return JsonResponse({'success': False, 'message': 'No cuenta con certificado .p12 configurado.'}, status=400)

    from cryptography.hazmat.primitives.serialization import pkcs12
    try:
        sig_profile.certificate_file.open('rb')
        p12_data = sig_profile.certificate_file.read()
        pkcs12.load_key_and_certificates(p12_data, password.encode('utf-8'))
    except Exception:
        return JsonResponse({'success': False, 'message': 'Contraseña incorrecta o certificado inválido.'}, status=400)

    sumilla.is_signed = True
    sumilla.save()

    ProcedureTrace.objects.create(
        procedure=task.procedure,
        task=task,
        actor=request.user,
        actor_name=request.user.signature_name,
        actor_position=request.user.signature_position,
        unit_name=task.unit.name if task.unit else "Dirección",
        action=ProcedureTrace.TraceAction.SUMILLED,
        observation="Sumilla legalizada digitalmente con firma electrónica oficial."
    )

    return JsonResponse({'success': True, 'message': 'Sumilla legalizada electrónicamente con éxito.'})


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
                html = render_to_string(
                    'documents/partials/partial_document_table.html',
                    {'documents': self.object_list},
                    request=request
                )
                return HttpResponse(html)

            # Paginación normal AJAX
            self.object_list = self.get_queryset()
            context = self.get_context_data()

            html = render_to_string(
                'documents/partials/partial_document_table.html',
                context,
                request=request
            )
            stats_html = render_to_string(
                'documents/partials/partial_document_stats.html',
                context,
                request=request
            )

            return JsonResponse({
                'success': True,
                'html': html,
                'stats_html': stats_html
            })

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        raw_doc_filter = self.request.GET.get('documents') or ''
        ctx['current_filters'] = {
            'q': (self.request.GET.get('q') or '').strip(),
            'date_from': (self.request.GET.get('date_from') or '').strip(),
            'date_to': (self.request.GET.get('date_to') or '').strip(),
            'documents': str(raw_doc_filter).strip(),
        }
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
    """
    Devuelve el siguiente código formateado:
    - Si viene level y procedure_id, usa la lógica jerárquica oficial o personal.
    - Si no, usa la lógica base de Ventanilla/DTH.
    """
    try:
        cid = int(category_id)
        doc_type = DocumentType.objects.get(pk=cid)
    except (TypeError, ValueError, DocumentType.DoesNotExist):
        return JsonResponse({'success': False, 'message': 'Categoría inválida'}, status=400)

    level = request.GET.get('level', 'PERSONAL')
    procedure_id = request.GET.get('procedure_id')

    if procedure_id and level:
        user = request.user
        employee = getattr(getattr(user, 'person', None), 'employee_profile', None)
        user_unit = employee.area if employee else None

        if level.startswith('UNIT_'):
            try:
                target_unit_id = int(level.replace('UNIT_', ''))
                selected_unit = AdministrativeUnit.objects.get(pk=target_unit_id)
            except Exception:
                selected_unit = user_unit
            code = generate_document_filing_code(selected_unit, user, doc_type, is_personal=False)
        else:
            code = generate_document_filing_code(user_unit, user, doc_type, is_personal=True)

        return JsonResponse({'success': True, 'code': code})

    # Lógica fallback existente
    year = timezone.now().year
    prefix = f'ML-DTH-{year}-'
    initials = ''.join([w[0].upper() for w in re.findall(r"[A-Za-zÀ-ÿ]+", doc_type.name)])
    total_count = Document.objects.filter(category_id=cid, registration_date__year=year, is_active=True).count()
    next_num = total_count + 1
    next_code = f"{prefix}{next_num:03d}{('-' + initials) if initials else ''}"

    return JsonResponse({'success': True, 'code': next_code, 'next_number': next_num})


@login_required
@require_POST
def update_user_settings(request):
    """
    Actualiza el nombre personalizado del usuario en su cuenta.
    """
    form = UserProfileSettingsForm(request.POST, instance=request.user)
    if form.is_valid():
        form.save()
        return JsonResponse({
            'success': True,
            'message': 'Datos de perfil actualizados correctamente.'
        })
    return JsonResponse({
        'success': False,
        'message': 'Error al actualizar perfil.',
        'errors': form.errors
    }, status=400)


@login_required
@require_POST
def upload_signature_certificate(request):
    """
    Valida en memoria el archivo .p12 con la clave provista y almacena los metadatos.
    """
    profile = getattr(request.user, 'signature_profile', None)
    form = UserSignatureUploadForm(request.POST, request.FILES, instance=profile)

    if form.is_valid():
        cert_info = form.cleaned_data.get('cert_info', {})
        sig_file = form.cleaned_data.get('signature_file')

        sig_profile = form.save(commit=False)
        sig_profile.user = request.user
        sig_profile.certificate_file = sig_file
        sig_profile.issuer = cert_info.get('issuer')
        sig_profile.subject_dn = cert_info.get('subject_dn')
        sig_profile.serial_number = cert_info.get('serial_number')
        sig_profile.valid_from = cert_info.get('valid_from')
        sig_profile.valid_to = cert_info.get('valid_to')
        sig_profile.save()

        return JsonResponse({
            'success': True,
            'message': f'Firma electrónica vinculada exitosamente. Válida hasta {cert_info.get("valid_to").strftime("%d/%m/%Y")}.'
        })

    errors = {k: v[0] for k, v in form.errors.items()}
    error_msg = form.errors.get('__all__', ['No se pudo vincular la firma.'])[
        0] if '__all__' in form.errors else 'Verifique los datos ingresados.'
    return JsonResponse({
        'success': False,
        'message': error_msg,
        'errors': errors
    }, status=400)


@login_required
def pass_to_secretariat_modal(request, pk):
    """
    Modal AJAX para remitir el trámite a Despacho.
    Lista a los servidores adscritos a la unidad principal más cercana y permite ingresar un mensaje opcional.
    """
    procedure = get_object_or_404(Procedure, pk=pk, is_active=True)

    # Obtener la unidad principal más cercana
    employee = getattr(getattr(request.user, 'person', None), 'employee_profile', None)
    user_unit = employee.area if employee else None

    target_unit = procedure.current_unit or user_unit
    main_dispatch_unit = target_unit.get_scheduling_root_unit() if target_unit else None
    if not main_dispatch_unit:
        main_dispatch_unit = AdministrativeUnit.objects.filter(is_main_unit=True, is_active=True).first()

    # Listar empleados de la unidad principal
    dest_employees = []
    if main_dispatch_unit:
        from employee.models import Employee
        dest_employees = Employee.objects.filter(
            area=main_dispatch_unit,
            is_active=True
        ).select_related('person')

    return render(request, 'documents/modals/modal_pass_to_despatch.html', {
        'procedure': procedure,
        'main_dispatch_unit': main_dispatch_unit,
        'employees': dest_employees,
    })


@login_required
@require_POST
def process_pass_to_secretariat(request, pk):
    """
    Procesa la remisión formal a Despacho con el destinatario seleccionado y el mensaje opcional.
    """
    procedure = get_object_or_404(Procedure, pk=pk, is_active=True)
    employee_id = request.POST.get('assigned_employee_id')
    optional_message = (request.POST.get('message') or '').strip()

    from employee.models import Employee
    assigned_employee = Employee.objects.filter(pk=employee_id, is_active=True).select_related(
        'person').first() if employee_id else None
    assigned_user = assigned_employee.person.user if assigned_employee and hasattr(assigned_employee.person,
                                                                                   'user') else None

    # Unidad principal
    main_dispatch_unit = assigned_employee.area.get_scheduling_root_unit() if assigned_employee else None
    if not main_dispatch_unit:
        main_dispatch_unit = AdministrativeUnit.objects.filter(is_main_unit=True, is_active=True).first()

    with transaction.atomic():
        procedure.status = Procedure.Status.IN_DESPATCH
        procedure.current_unit = main_dispatch_unit
        procedure.updated_by = request.user
        procedure.save()

        # Generar tarea para la unidad y servidor destinatario
        task, created = ProcedureTask.objects.get_or_create(
            procedure=procedure,
            unit=main_dispatch_unit,
            status=ProcedureTask.TaskStatus.PENDING,
            defaults={
                'assigned_to': assigned_user,
                'assigned_by': request.user,
                'created_by': request.user,
                'is_main_task': True
            }
        )
        if not created and assigned_user:
            task.assigned_to = assigned_user
            task.save()

        # Registrar en la Hoja de Ruta
        obs_text = f"Remitido al Despacho de {main_dispatch_unit.name}."
        if assigned_employee:
            obs_text += f" Atención inicial a cargo de: {assigned_employee.person.full_name}."
        if optional_message:
            obs_text += f" Nota de Ventanilla: {optional_message}"

        ProcedureTrace.objects.create(
            procedure=procedure,
            task=task,
            actor=request.user,
            actor_name=request.user.signature_name,
            actor_position=request.user.signature_position,
            unit_name="Ventanilla Única / Recepción",
            action=ProcedureTrace.TraceAction.PASSED_TO_DESPATCH,
            observation=obs_text
        )

    return JsonResponse({
        'success': True,
        'message': f'Trámite {procedure.code} remitido al Despacho de {main_dispatch_unit.name} con éxito.'
    })


@login_required
def procedure_view_pdf_modal(request, pk):
    """
    Modal grande para visualizar el PDF digitalizado de un trámite sin salir de la plataforma.
    """
    procedure = get_object_or_404(Procedure, pk=pk)
    entry_doc = procedure.documents.filter(is_entry_document=True).first()

    return render(request, 'documents/modals/modal_view_pdf.html', {
        'procedure': procedure,
        'doc': entry_doc,
    })


@login_required
def virtual_office_view(request):
    """
    Escritorio virtual interactivo con zonas de soltado (Drag & Drop).
    Permite visualizar trámites asignados al usuario o a su unidad principal.
    """
    user = request.user
    employee = getattr(getattr(user, 'person', None), 'employee_profile', None)
    user_unit = employee.area if employee else None

    # Unidad principal (ej: DIRECCIÓN DE TECNOLOGÍA)
    main_unit = user_unit.get_scheduling_root_unit() if user_unit else None
    if not main_unit:
        main_unit = AdministrativeUnit.objects.filter(is_main_unit=True, is_active=True).first()

    # Recoger IDs de unidades de su rama
    units_to_check = []
    if main_unit:
        units_to_check = main_unit.get_descendant_ids()
    elif user_unit:
        units_to_check = [user_unit.id]

    pending_procedures = Procedure.objects.filter(
        Q(current_unit=main_unit) |
        Q(current_unit=user_unit) |
        Q(current_unit_id__in=units_to_check) |
        Q(tasks__unit=main_unit) |
        Q(tasks__unit=user_unit) |
        Q(tasks__assigned_to=user),
        status__in=[Procedure.Status.IN_DESPATCH, Procedure.Status.IN_PROCESS],
        is_active=True
    ).distinct().select_related('category', 'created_by').prefetch_related(
        'tasks', 'tasks__sumilla'
    ).order_by('-created_at')

    # Vincular la tarea activa del usuario o de su unidad a cada trámite
    for proc in pending_procedures:
        # Priorizar tarea asignada al usuario
        user_task = next(
            (t for t in proc.tasks.all() if t.assigned_to_id == user.id and t.status in [
                ProcedureTask.TaskStatus.PENDING, ProcedureTask.TaskStatus.IN_PROCESS
            ]), None
        )
        # Si no hay tarea personal, buscar la tarea activa de la unidad
        if not user_task and (main_unit or user_unit):
            unit_ids = [u for u in [main_unit.id if main_unit else None, user_unit.id if user_unit else None] if u]
            user_task = next(
                (t for t in proc.tasks.all() if t.unit_id in unit_ids and t.status in [
                    ProcedureTask.TaskStatus.PENDING, ProcedureTask.TaskStatus.IN_PROCESS
                ]), None
            )
        # Fallback a la última tarea registrada
        if not user_task:
            user_task = proc.tasks.order_by('-created_at').first()

        proc.active_task = user_task

    # Unidades jerárquicas para las tarjetas de creación (solo niveles relevantes)
    unit_levels = []
    curr = user_unit
    while curr:
        unit_levels.insert(0, curr)
        curr = curr.parent

    # Subdependencias directas para sumillar hacia abajo
    child_units = []
    parent_unit = None
    if main_unit:
        child_units = AdministrativeUnit.objects.filter(parent=main_unit, is_active=True)
        if main_unit.parent:
            parent_unit = main_unit.parent.get_scheduling_root_unit()

    return render(request, 'documents/virtual_office.html', {
        'pending_procedures': pending_procedures,
        'user_unit': user_unit,
        'main_unit': main_unit,
        'unit_levels': unit_levels,
        'child_units': child_units,
        'parent_unit': parent_unit,
    })


@login_required
def modal_delegate_task(request):
    """
    Modal AJAX que se despliega al soltar un trámite sobre una unidad destino.
    """
    procedure_id = request.GET.get('procedure_id')
    unit_id = request.GET.get('unit_id')

    procedure = get_object_or_404(Procedure, pk=procedure_id)
    target_unit = get_object_or_404(AdministrativeUnit, pk=unit_id)

    form = DelegateTaskForm(unit=target_unit)

    return render(request, 'documents/modals/modal_delegate_task.html', {
        'form': form,
        'procedure': procedure,
        'target_unit': target_unit,
    })


@login_required
@require_POST
def process_delegate_task(request):
    """
    Procesa la delegación, crea la tarea concurrente, registra la sumilla y guarda la traza inmutable.
    Al delegar, cierra la tarea actual del usuario para sacarla de su bandeja.
    """
    procedure_id = request.POST.get('procedure_id')
    unit_id = request.POST.get('unit_id')

    procedure = get_object_or_404(Procedure, pk=procedure_id)
    target_unit = get_object_or_404(AdministrativeUnit, pk=unit_id)

    form = DelegateTaskForm(request.POST, unit=target_unit)
    if not form.is_valid():
        return JsonResponse({
            'success': False,
            'message': 'Corrija los errores en el formulario.',
            'errors': form.errors
        }, status=400)

    assigned_to = form.cleaned_data['assigned_to']
    instruction = form.cleaned_data['instruction']
    days_limit = form.cleaned_data['days_limit']
    is_main_task = form.cleaned_data['is_main_task']
    observation = form.cleaned_data.get('observation', '')

    with transaction.atomic():
        now = timezone.now()
        task_limit = now + timedelta(days=days_limit)

        # 1. Cerrar la tarea actual del usuario que está sumillando usando CLOSED
        ProcedureTask.objects.filter(
            procedure=procedure,
            assigned_to=request.user,
            status__in=[ProcedureTask.TaskStatus.PENDING, ProcedureTask.TaskStatus.IN_PROCESS]
        ).update(status=ProcedureTask.TaskStatus.CLOSED)

        # 2. Crear Tarea de Trámite para el destinatario
        task = ProcedureTask.objects.create(
            procedure=procedure,
            unit=target_unit,
            assigned_to=assigned_to,
            assigned_by=request.user,
            is_main_task=is_main_task,
            limit_date=task_limit,
            status=ProcedureTask.TaskStatus.PENDING,
            created_by=request.user
        )

        # 3. Registrar la Sumilla vinculada
        ProcedureSumilla.objects.create(
            task=task,
            author=request.user,
            instruction=instruction,
            observation=observation,
            is_signed=False,
            created_by=request.user
        )

        # 4. Actualizar estado y unidad actual del trámite
        procedure.current_unit = target_unit
        procedure.status = Procedure.Status.IN_PROCESS
        if not procedure.limit_date or procedure.limit_date < task_limit:
            procedure.limit_date = task_limit
        procedure.save()

        # 5. Asentar en la Hoja de Ruta Inmutable (Contraloría)
        ProcedureTrace.objects.create(
            procedure=procedure,
            task=task,
            actor=request.user,
            actor_name=request.user.signature_name,
            actor_position=request.user.signature_position,
            unit_name=target_unit.name,
            action=ProcedureTrace.TraceAction.SUMILLED,
            observation=f"Sumilla a {assigned_to.signature_name}: {instruction}. {observation}".strip()
        )

    return JsonResponse({
        'success': True,
        'message': f'Trámite {procedure.code} derivado exitosamente a {target_unit.name}.'
    })


class ProcedureReceptionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Bandeja de recepción donde ventanilla ingresa y audita los trámites radicados.
    """
    model = Procedure
    template_name = 'documents/procedure_reception_list.html'
    context_object_name = 'procedures'
    paginate_by = 10
    permission_required = 'documents.add_document'

    def get_queryset(self):
        qs = Procedure.objects.filter(
            procedure_type=Procedure.ProcedureType.RECEPCION,
            is_active=True
        ).select_related('category', 'created_by').order_by('-created_at')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(code__icontains=q) |
                Q(subject__icontains=q) |
                Q(external_sender__icontains=q) |
                Q(external_number__icontains=q)
            )
        return qs

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'documents/partials/partial_reception_table.html',
                context,
                request=self.request
            )
            return HttpResponse(html)
        return super().render_to_response(context, **response_kwargs)


from .utils import generate_document_filing_code


@login_required
def procedure_reception_create(request):
    """
    Modal AJAX para registrar el documento físico escaneado.
    Genera el correlativo secuencial institucional: TR-YYYY-0001
    """
    year = timezone.now().year

    if request.method == 'GET':
        total_count = Procedure.objects.filter(created_at__year=year).count() + 1
        suggested_code = f"TR-{year}-{total_count:04d}"

        form = ProcedureReceptionForm()
        return render(request, 'documents/modals/modal_reception_form.html', {
            'form': form,
            'suggested_code': suggested_code
        })

    if request.method == 'POST':
        form = ProcedureReceptionForm(request.POST, request.FILES)
        if not form.is_valid():
            return JsonResponse({
                'success': False,
                'message': 'Corrija los errores en el formulario.',
                'errors': form.errors
            }, status=400)

        with transaction.atomic():
            total_count = Procedure.objects.filter(created_at__year=year).count() + 1
            radicado_code = f"TR-{year}-{total_count:04d}"

            procedure = form.save(commit=False)
            procedure.code = radicado_code
            procedure.procedure_type = Procedure.ProcedureType.RECEPCION
            procedure.status = Procedure.Status.DRAFT
            procedure.created_by = request.user
            procedure.save()

            scanned_file = form.cleaned_data['scanned_file']
            doc = Document.objects.create(
                procedure=procedure,
                filing_code=f"DOC-{radicado_code}",
                category=procedure.category,
                subject=procedure.subject,
                sender_name=procedure.external_sender,
                recipient_name="Despacho de Dirección",
                file_attachment=scanned_file,
                is_entry_document=True,
                created_by=request.user
            )

            ProcedureTrace.objects.create(
                procedure=procedure,
                document=doc,
                actor=request.user,
                actor_name=request.user.signature_name,
                actor_position=request.user.signature_position,
                unit_name="Ventanilla Única / Recepción",
                action=ProcedureTrace.TraceAction.RECEPTION,
                observation=f"Documento registrado en ventanilla bajo radicado {radicado_code}."
            )

        return JsonResponse({
            'success': True,
            'message': f'Trámite {radicado_code} registrado correctamente en Ventanilla.'
        })


@login_required
def procedure_trace_modal(request, pk):
    """
    Modal AJAX que renderiza la Hoja de Ruta cronológica inmutable del trámite.
    """
    procedure = get_object_or_404(Procedure, pk=pk)
    traces = procedure.traces.all().order_by('created_at')

    return render(request, 'documents/modals/modal_procedure_trace.html', {
        'procedure': procedure,
        'traces': traces
    })


@login_required
def procedure_reception_update(request, pk):
    """
    Permite editar los datos de un trámite siempre que no haya sido derivado a dependencias inferiores.
    """
    procedure = get_object_or_404(Procedure, pk=pk, is_active=True)

    # Validación estricta: Si ya tiene tareas activas delegadas hacia abajo, no se puede alterar
    if procedure.tasks.exists():
        return HttpResponse("No se puede editar este trámite porque ya fue derivado a dependencias subordinadas.",
                            status=403)

    if request.method == 'GET':
        form = ProcedureReceptionForm(instance=procedure)
        # El archivo escaneado no es obligatorio en edición si ya existe
        form.fields['scanned_file'].required = False
        return render(request, 'documents/modals/modal_reception_update_form.html', {
            'form': form,
            'procedure': procedure
        })

    if request.method == 'POST':
        form = ProcedureReceptionForm(request.POST, request.FILES, instance=procedure)
        form.fields['scanned_file'].required = False

        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        with transaction.atomic():
            proc = form.save(commit=False)
            proc.updated_by = request.user
            proc.save()

            # Si cargaron un nuevo PDF de reemplazo
            if 'scanned_file' in request.FILES:
                entry_doc = proc.documents.filter(is_entry_document=True).first()
                if entry_doc:
                    entry_doc.file_attachment = request.FILES['scanned_file']
                    entry_doc.updated_by = request.user
                    entry_doc.save()
                else:
                    Document.objects.create(
                        procedure=proc,
                        filing_code=f"DOC-{proc.code}",
                        category=proc.category,
                        subject=proc.subject,
                        sender_name=proc.external_sender,
                        recipient_name="Despacho de Dirección",
                        file_attachment=request.FILES['scanned_file'],
                        is_entry_document=True,
                        created_by=request.user
                    )

            ProcedureTrace.objects.create(
                procedure=proc,
                actor=request.user,
                actor_name=request.user.signature_name,
                actor_position=request.user.signature_position,
                unit_name="Ventanilla Única / Recepción",
                action=ProcedureTrace.TraceAction.RECEPTION,
                observation="Actualización de datos generales del trámite en ventanilla."
            )

        return JsonResponse({'success': True, 'message': 'Trámite actualizado correctamente.'})


@login_required
@require_POST
def procedure_cancel_or_delete(request, pk):
    """
    - Si NO ha sido asignado: pasa is_active=False y libera el número de trámite.
    - Si YA fue asignado: cambia a anulado (ARCHIVED) con motivo obligatorio.
    """
    procedure = get_object_or_404(Procedure, pk=pk, is_active=True)
    reason = (request.POST.get('reason') or '').strip()

    has_assignments = procedure.tasks.exists()

    with transaction.atomic():
        if not has_assignments:
            # Caso A: No fue asignado a nadie. Se da de baja lógica y se libera el correlativo
            old_code = procedure.code
            timestamp = int(timezone.now().timestamp())
            procedure.code = f"{old_code}-ANULADO-{timestamp}"
            procedure.is_active = False
            procedure.updated_by = request.user
            procedure.save()

            ProcedureTrace.objects.create(
                procedure=procedure,
                document=doc,
                actor=request.user,
                actor_name=request.user.signature_name,
                actor_position=request.user.signature_position,
                unit_name="Ventanilla Única / Recepción",
                action=ProcedureTrace.TraceAction.ARCHIVED,
                observation=f"Baja de trámite sin asignación previa. Se libera el número {old_code}. Motivo: {reason or 'Sin especificar'}"
            )

            return JsonResponse({
                'success': True,
                'message': f'Trámite dado de baja correctamente. El número {old_code} ha quedado libre para una nueva radicación.'
            })
        else:
            # Caso B: Ya tuvo asignaciones. No se puede liberar el número, queda como anulado con motivo
            if not reason:
                return JsonResponse({
                    'success': False,
                    'message': 'El trámite ya fue asignado previamente. Debe ingresar obligatoriamente el motivo de anulación.'
                }, status=400)

            procedure.status = Procedure.Status.ARCHIVED
            procedure.closed_at = timezone.now()
            procedure.updated_by = request.user
            procedure.save()

            # Marcar tareas como cerradas
            procedure.tasks.update(status=ProcedureTask.TaskStatus.CLOSED)

            ProcedureTrace.objects.create(
                procedure=procedure,
                actor=request.user,
                actor_name=request.user.signature_name,
                actor_position=request.user.signature_position,
                unit_name="Ventanilla Única / Recepción",
                action=ProcedureTrace.TraceAction.ARCHIVED,
                observation=f"Trámite Anulado y Archivado institucionalmente. Motivo: {reason}"
            )

            return JsonResponse({
                'success': True,
                'message': f'Trámite {procedure.code} anulado y archivado formalmente con el motivo registrado.'
            })


@login_required
@xframe_options_sameorigin
def serve_procedure_pdf(request, pk):
    """
    Sirve el archivo PDF directamente con 'Content-Disposition: inline' y
    'X-Frame-Options: SAMEORIGIN', permitiendo su visualización en modal
    tanto en entorno local como en servidor.
    """
    procedure = get_object_or_404(Procedure, pk=pk)
    entry_doc = procedure.documents.filter(is_entry_document=True).first()

    if not entry_doc or not entry_doc.file_attachment:
        raise Http404("El trámite no cuenta con documento PDF adjunto.")

    try:
        # Abrir el binario del archivo desde MEDIA_ROOT / Storage
        file_path = entry_doc.file_attachment.path
        if not os.path.exists(file_path):
            raise Http404("El archivo físico no existe en el disco.")

        with open(file_path, 'rb') as pdf_file:
            response = HttpResponse(pdf_file.read(), content_type='application/pdf')
            filename = os.path.basename(file_path)
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response
    except Exception:
        # Fallback para storages remotos
        try:
            content = entry_doc.file_attachment.read()
            response = HttpResponse(content, content_type='application/pdf')
            filename = os.path.basename(entry_doc.file_attachment.name)
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response
        except Exception:
            raise Http404("No fue posible leer el archivo PDF.")


@login_required
@xframe_options_sameorigin
def print_document_pdf(request, pk):
    """
    Sirve el PDF generado del documento (Memorando, Oficio, Circular, etc.)
    en modo 'inline' para su visualización e impresión física directa.
    """
    doc = get_object_or_404(Document, pk=pk, is_active=True)

    if not doc.file_attachment:
        raise Http404("El documento no cuenta con archivo PDF adjunto.")

    try:
        file_path = doc.file_attachment.path
        if not os.path.exists(file_path):
            raise Http404("El archivo físico no se encuentra en el servidor.")

        with open(file_path, 'rb') as pdf_file:
            response = HttpResponse(pdf_file.read(), content_type='application/pdf')
            clean_filename = os.path.basename(file_path)
            response['Content-Disposition'] = f'inline; filename="{clean_filename}"'
            return response
    except NotImplementedError:
        # Fallback para storages remotos que no implementan path directo
        response = HttpResponse(doc.file_attachment.read(), content_type='application/pdf')
        clean_filename = os.path.basename(doc.file_attachment.name)
        response['Content-Disposition'] = f'inline; filename="{clean_filename}"'
        return response
