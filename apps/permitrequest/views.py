from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.core import signing
from django.http import Http404
from django.utils import timezone
from io import BytesIO
import base64
from django.core.paginator import Paginator, EmptyPage
from types import SimpleNamespace
import logging

logger = logging.getLogger(__name__)

from .models import PermitType, PermitRequest
from .forms import PermitTypeForm, PermitRequestForm
from employee.models import Employee
from budget.models import BudgetLine


PERMIT_PUBLIC_TOKEN_SALT = 'permitrequest.public.validation'


def build_public_permit_token(permit_id):
    """Genera un token firmado para validación pública de permisos."""
    return signing.dumps({'permit_id': permit_id}, salt=PERMIT_PUBLIC_TOKEN_SALT)


def parse_public_permit_token(token):
    """Obtiene el ID del permiso desde un token firmado."""
    payload = signing.loads(token, salt=PERMIT_PUBLIC_TOKEN_SALT)
    permit_id = payload.get('permit_id')
    if not permit_id:
        raise signing.BadSignature('Token sin permit_id')
    return int(permit_id)


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
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(description__icontains=q)
            )
        return queryset.order_by('name')
    def get_initial(self):
        initial = super().get_initial()
        # Si venimos de "Crear Sub-item", pre-llenamos el padre
        parent_id = self.request.GET.get('parent')
        if parent_id:
            initial['parent'] = parent_id
        return initial


class PermitTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PermitType
    form_class = PermitTypeForm
    template_name = 'permissions/modals/modal_permissions_type_form.html'
    success_url = reverse_lazy('permissions:permit_type_list')
    permission_required = 'permitrequest.add_permittype'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm('permitrequest.add_permittype'):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tiene permisos para crear tipos de permiso'}, status=403)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            context = self.get_context_data(form=form)
            html = render_to_string(self.template_name, context, request=request)
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


class PermitTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = PermitType
    form_class = PermitTypeForm
    template_name = 'permissions/modals/modal_permissions_type_form.html'
    success_url = reverse_lazy('permissions:permit_type_list')

    def dispatch(self, request, *args, **kwargs):
        # Verificar permisos manualmente para mejor control de respuesta AJAX
        if not request.user.has_perm('permitrequest.change_permittype'):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tiene permisos para modificar tipos de permiso'}, status=403)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Renderizar solo el contenido del modal con contexto completo
            context = self.get_context_data(form=form)
            html = render_to_string(self.template_name, context, request=request)
            return HttpResponse(html)
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
    success_url = reverse_lazy('permissions:permit_type_list')
    permission_required = 'permitrequest.delete_permittype'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Eliminado correctamente.'})
        return super().delete(request, *args, **kwargs)


# ==========================================
# VISTAS: LISTA DE EMPLEADOS PARA GENERAR PERMISOS
# ==========================================

class EmployeePermitListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Vista para listar empleados activos y gestionar sus permisos"""
    model = Employee
    template_name = 'permissions/employee_permit_list.html'
    context_object_name = 'employees'
    permission_required = 'permitrequest.view_permitrequest'
    paginate_by = 10

    def get_queryset(self):
        queryset = Employee.objects.filter(
            is_active=True
        ).select_related(
            'person',
            'area',
            'employment_status'
        )
        
        # Búsqueda por nombres, apellidos o cédula (tokenizada)
        query = self.request.GET.get('q', '').strip()
        if query:
            tokens = [t for t in query.split() if t]
            # Para cada token, requerimos que aparezca en first_name, last_name o document_number
            for tok in tokens:
                tok_q = Q(person__first_name__icontains=tok) | Q(person__last_name__icontains=tok) | Q(person__document_number__icontains=tok)
                queryset = queryset.filter(tok_q)
        
        return queryset.order_by('person__last_name', 'person__first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener IDs de empleados en la página actual
        employee_ids = [emp.id for emp in context['employees']]
        
        # Consulta eficiente: obtener todas las partidas de una vez
        budgets_dict = {}
        if employee_ids:
            budgets = BudgetLine.objects.filter(
                current_employee_id__in=employee_ids,
                is_active=True
            ).select_related('position_item')
            
            for budget in budgets:
                budgets_dict[budget.current_employee_id] = budget
        
        # Agregar información de partida presupuestaria para cada empleado
        employees_with_budget = []
        for employee in context['employees']:
            budget = budgets_dict.get(employee.id, None)
            employees_with_budget.append({
                'employee': employee,
                'budget': budget
            })
        
        context['employees_data'] = employees_with_budget
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'permissions/partials/partial_employee_list.html',
                context,
                request=self.request
            )
            
            # Información de paginación
            page_obj = context.get('page_obj')
            if page_obj:
                pagination_data = {
                    'start_index': page_obj.start_index(),
                    'end_index': page_obj.end_index(),
                    'total_count': page_obj.paginator.count,
                    'current_page': page_obj.number,
                    'total_pages': page_obj.paginator.num_pages,
                    'has_previous': page_obj.has_previous(),
                    'has_next': page_obj.has_next(),
                }
            else:
                pagination_data = {
                    'start_index': 0,
                    'end_index': 0,
                    'total_count': 0,
                    'current_page': 1,
                    'total_pages': 1,
                    'has_previous': False,
                    'has_next': False,
                }
            
            return JsonResponse({
                'success': True,
                'html': html,
                'pagination': pagination_data
            })
        return super().render_to_response(context, **response_kwargs)


class EmployeePermitHistoryView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Vista para obtener el historial de permisos de un empleado"""
    permission_required = 'permitrequest.view_permitrequest'

    def get(self, request, employee_id):
        if not request.user.has_perm('permitrequest.view_permitrequest'):
            return JsonResponse({
                'success': False,
                'message': 'No tiene permisos para ver esta información'
            }, status=403)
        
        try:
            employee = get_object_or_404(Employee, pk=employee_id)
            # Accesos seguros a datos de la persona relacionada (evitar AttributeError si no existe)
            emp_person = getattr(employee, 'person', None)
            employee_name = getattr(emp_person, 'full_name', '') if emp_person else (getattr(employee, 'get_full_name', lambda: '')() or '')
            employee_identification = getattr(emp_person, 'document_number', '') if emp_person else ''
            permits = PermitRequest.objects.filter(
                employee=employee
            ).select_related('permit_type').order_by('-created_at')
            
            permits_data = []
            for permit in permits:
                permits_data.append({
                    'id': permit.id,
                    'permit_type__name': permit.permit_type.name,
                    'start_date': permit.start_date.strftime('%Y-%m-%d') if permit.start_date else None,
                    'end_date': permit.end_date.strftime('%Y-%m-%d') if permit.end_date else None,
                    'status': permit.status,
                    'created_at': permit.created_at.strftime('%Y-%m-%d %H:%M:%S') if permit.created_at else None
                })
            
            return JsonResponse({
                'success': True,
                'employee_name': employee.person.full_name,
                'employee_identification': employee.person.document_number,
                'permits': permits_data
            })
        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False,
                'message': f'Error al cargar historial: {str(e)}',
                'traceback': traceback.format_exc()
            }, status=500)


class GeneratePermitFormView(LoginRequiredMixin, View):
    """Vista para cargar el formulario de generar permiso"""

    def _resolve_request_employee(self, request):
        user_person = getattr(request.user, 'person', None)
        employee_profile = getattr(user_person, 'employee_profile', None) if user_person else None

        if employee_profile:
            return employee_profile

        from person.models import Person

        person_by_document = Person.objects.filter(
            document_number=request.user.username
        ).select_related('employee_profile').first()
        if person_by_document and getattr(person_by_document, 'employee_profile', None):
            return person_by_document.employee_profile

        if request.user.email:
            person_by_email = Person.objects.filter(
                email__iexact=request.user.email
            ).select_related('employee_profile').first()
            if person_by_email and getattr(person_by_email, 'employee_profile', None):
                return person_by_email.employee_profile

        return None

    def _can_generate_for_employee(self, request, employee):
        if request.user.has_perm('permitrequest.add_permitrequest'):
            return True
        request_employee = self._resolve_request_employee(request)
        return bool(request_employee and request_employee.id == employee.id)
    
    def get(self, request):
        employee_raw = request.GET.get('employee')
        if not employee_raw:
            return JsonResponse({
                'success': False,
                'message': 'ID de empleado no proporcionado'
            }, status=400)

        # Normalizar: eliminar separadores de miles u otros caracteres no numéricos
        import re
        employee_id = re.sub(r'[^0-9]', '', str(employee_raw))
        if not employee_id:
            return JsonResponse({
                'success': False,
                'message': 'ID de empleado inválido'
            }, status=400)

        employee = get_object_or_404(Employee, pk=int(employee_id))

        if not self._can_generate_for_employee(request, employee):
            return JsonResponse({
                'success': False,
                'message': 'No tiene permisos para generar permisos'
            }, status=403)
        
        # Obtener tipos padre (sin parent)
        parent_types = PermitType.objects.filter(
            is_active=True,
            parent__isnull=True
        ).order_by('name')
        
        html = render_to_string(
            'permissions/modals/modal_generate_permit_form.html',
            {
                'employee': employee,
                'parent_types': parent_types,
            },
            request=request
        )
        return HttpResponse(html)
    
    def post(self, request):
        """Procesa el formulario de generación de permiso"""
        try:
            employee_raw = request.POST.get('employee')
            import re
            employee_id = re.sub(r'[^0-9]', '', str(employee_raw or ''))
            if not employee_id:
                raise ValueError('ID de empleado inválido')
            employee = get_object_or_404(Employee, pk=int(employee_id))

            if not self._can_generate_for_employee(request, employee):
                return JsonResponse({
                    'success': False,
                    'message': 'No tiene permisos para generar permisos'
                }, status=403)
            
            # Crear instancia de PermitRequest
            permit = PermitRequest()
            permit.employee = employee
            permit.permit_type_id = request.POST.get('permit_subtype') or request.POST.get('permit_type')
            permit.start_date = request.POST.get('start_date')
            permit.start_time = request.POST.get('start_time')
            permit.end_date = request.POST.get('end_date')
            permit.end_time = request.POST.get('end_time')
            permit.days = int(request.POST.get('days') or 0)
            permit.hours = int(request.POST.get('hours') or 0)
            permit.minutes = int(request.POST.get('minutes') or 0)
            permit.response_note = request.POST.get('reason', '').strip()
            permit.created_by = request.user
            permit.updated_by = request.user
            permit.status = 'REQUESTED'
            
            # Manejar archivo adjunto
            if 'justification_file' in request.FILES:
                permit.justification_file = request.FILES['justification_file']
            
            permit.save()
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Permiso generado correctamente'
                })
            return redirect('permissions:permit_employee_list')
            
        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': f'Error al generar el permiso: {str(e)}'
                }, status=400)
            return HttpResponse(f'Error: {str(e)}', status=400)


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


class PermitTypeToggleView(LoginRequiredMixin, View):

    def post(self, request, pk):
        # Verificar permisos manualmente
        if not request.user.has_perm('permitrequest.change_permittype'):
            return JsonResponse({
                'success': False,
                'message': 'No tiene permisos para cambiar el estado'
            }, status=403)
        
        permit_type = get_object_or_404(PermitType, pk=pk)
        permit_type.is_active = not permit_type.is_active
        permit_type.save()
        
        status_text = 'activado' if permit_type.is_active else 'desactivado'
        return JsonResponse({
            'success': True,
            'message': f'Tipo de permiso "{permit_type.name}" {status_text} correctamente'
        })


class PermitTypeSubItemsView(LoginRequiredMixin, View):
    """Vista para obtener los subitems de un tipo de permiso en JSON."""

    def get(self, request, pk):
        # Verificar permisos manualmente para respuesta JSON apropiada
        if not request.user.has_perm('permitrequest.view_permittype'):
            return JsonResponse({
                'success': False,
                'message': 'No tiene permisos para ver esta información'
            }, status=403)
        
        parent = get_object_or_404(PermitType, pk=pk)
        subtypes = PermitType.objects.filter(parent=parent).values(
            'id', 'name', 'needs_justification', 'affects_vacation', 'is_active'
        )
        return JsonResponse({
            'success': True,
            'parent_name': parent.name,
            'parent_id': parent.id,
            'items': list(subtypes)
        })


def get_subtypes_api(request, parent_id):
    """API para obtener subtipos de un tipo de permiso padre"""
    subtypes = PermitType.objects.filter(
        parent_id=parent_id,
        is_active=True
    ).values('id', 'name', 'needs_justification', 'requires_attachment')
    
    return JsonResponse({
        'success': True,
        'subtypes': list(subtypes)
    })


# ==========================================
# VISTAS: ADMINISTRACIÓN DE PERMISOS
# ==========================================

class PermitAdminListView(LoginRequiredMixin, PermissionRequiredMixin, JSONResponseMixin, ListView):
    """Vista para administrar permisos (aprobar/rechazar)"""
    model = PermitRequest
    template_name = 'permissions/permit_admin_list.html'
    partial_template_name = 'permissions/partials/partial_permit_admin_table.html'
    context_object_name = 'permits'
    permission_required = 'permitrequest.view_permitrequest'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'employee__person', 
            'permit_type'
        ).order_by('-created_at')
        
        query = self.request.GET.get('q')
        status = self.request.GET.get('status')

        if query:
            queryset = queryset.filter(
                Q(employee__person__first_name__icontains=query) |
                Q(employee__person__last_name__icontains=query) |
                Q(employee__person__document_number__icontains=query) |
                Q(permit_type__name__icontains=query)
            )

        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estadísticas para las cards
        all_permits = PermitRequest.objects.all()
        context['total'] = all_permits.count()
        context['pendientes'] = all_permits.filter(status='REQUESTED').count()
        context['aprobados'] = all_permits.filter(status='APPROVED').count()
        context['rechazados'] = all_permits.filter(status='REJECTED').count()
        
        return context


class PermitDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Vista para ver el detalle de un permiso"""
    permission_required = 'permitrequest.view_permitrequest'

    def get(self, request, pk):
        permit = get_object_or_404(
            PermitRequest.objects.select_related('employee__person', 'permit_type', 'created_by', 'response_by'),
            pk=pk
        )
        
        # Si es una petición AJAX (desde el modal), usar template modal
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'permissions/modals/modal_permit_detail.html',
                {'permit': permit},
                request=request
            )
            return HttpResponse(html)
        
        # Si es acceso directo (desde QR), usar template completo con estilos
        html = render_to_string(
            'permissions/permit_detail_public.html',
            {'permit': permit},
            request=request
        )
        return HttpResponse(html)


class PublicPermitValidationView(View):
    """Vista pública para validar un permiso aprobado mediante token QR."""

    def get(self, request, token):
        try:
            permit_id = parse_public_permit_token(token)
        except (signing.BadSignature, ValueError, TypeError):
            raise Http404('Código de validación inválido')

        permit = get_object_or_404(
            PermitRequest.objects.select_related('employee__person', 'permit_type', 'created_by', 'response_by'),
            pk=permit_id,
            status='APPROVED'
        )

        html = render_to_string(
            'permissions/permit_detail_public.html',
            {'permit': permit},
            request=request
        )
        return HttpResponse(html)


class PermitResponseView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Vista para aprobar o rechazar un permiso"""
    permission_required = 'permitrequest.change_permitrequest'

    def get(self, request, pk, action):
        """Muestra el modal para ingresar el motivo"""
        permit = get_object_or_404(PermitRequest, pk=pk)
        
        if permit.status != 'REQUESTED':
            return JsonResponse({
                'success': False,
                'message': 'Este permiso ya fue procesado'
            }, status=400)
        
        default_message = "Se acepta el permiso" if action == 'approve' else ""
        
        html = render_to_string(
            'permissions/modals/modal_permit_response.html',
            {
                'permit': permit,
                'action': action,
                'default_message': default_message
            },
            request=request
        )
        return HttpResponse(html)

    def post(self, request, pk, action):
        """Procesa la aprobación o rechazo"""
        permit = get_object_or_404(PermitRequest, pk=pk)
        
        if permit.status != 'REQUESTED':
            return JsonResponse({
                'success': False,
                'message': 'Este permiso ya fue procesado'
            }, status=400)
        
        response_note = request.POST.get('response_note', '').strip()
        now = timezone.now()
        if timezone.is_aware(now):
            now = timezone.localtime(now)
        user_full_name = request.user.get_full_name().strip() or request.user.username
        
        if action == 'approve':
            permit.status = 'APPROVED'
            if not response_note:
                response_note = "Se acepta el permiso"
            action_label = 'APROBACION'
            message = 'Permiso aprobado correctamente'
        elif action == 'reject':
            permit.status = 'REJECTED'
            if not response_note:
                return JsonResponse({
                    'success': False,
                    'message': 'Debe ingresar el motivo de la negativa'
                }, status=400)
            action_label = 'RECHAZO'
            message = 'Permiso rechazado correctamente'
        else:
            return JsonResponse({
                'success': False,
                'message': 'Acción no válida'
            }, status=400)

        # Formatear nota HTML y PREPEND al historial (nuevo primero)
        from django.utils.html import escape
        if action == 'approve':
            entry_html = f"<span class=\"note-label note-justifica\" style=\"color:#16a34a\">Aprobación: {escape(response_note)}</span>"
        else:
            entry_html = f"<span class=\"note-label note-reject\" style=\"color:#dc2626\">Rechazo: {escape(response_note)}</span>"
        if permit.response_note:
            permit.response_note = entry_html + (f"\n\n{permit.response_note}" if permit.response_note else '')
        else:
            permit.response_note = entry_html
        permit.response_date = timezone.now()
        permit.response_by = request.user
        permit.updated_by = request.user
        permit.save()
        
        return JsonResponse({
            'success': True,
            'message': message,
            'status': permit.status,
            'response_note': permit.response_note or ''
        })


class PermitInsistView(LoginRequiredMixin, View):
    """Permite insistir una solicitud rechazada y reenviarla a revisión."""

    def _can_insist(self, request, permit):
        if request.user.has_perm('permitrequest.add_permitrequest'):
            return True
        user_person = getattr(request.user, 'person', None)
        return bool(user_person and permit.employee.person_id == user_person.id)

    def get(self, request, pk):
        permit = get_object_or_404(PermitRequest.objects.select_related('employee__person', 'permit_type'), pk=pk)

        if permit.status != 'REJECTED':
            return JsonResponse({
                'success': False,
                'message': 'Solo se puede insistir en permisos rechazados.'
            }, status=400)

        if not self._can_insist(request, permit):
            return JsonResponse({
                'success': False,
                'message': 'No tiene permisos para insistir esta solicitud.'
            }, status=403)

        html = render_to_string(
            'permissions/modals/modal_permit_insist.html',
            {'permit': permit},
            request=request
        )
        return HttpResponse(html)

    def post(self, request, pk):
        permit = get_object_or_404(PermitRequest.objects.select_related('employee__person'), pk=pk)

        if permit.status != 'REJECTED':
            return JsonResponse({
                'success': False,
                'message': 'Solo se puede insistir en permisos rechazados.'
            }, status=400)

        if not self._can_insist(request, permit):
            return JsonResponse({
                'success': False,
                'message': 'No tiene permisos para insistir esta solicitud.'
            }, status=403)

        insist_message = request.POST.get('insist_message', '').strip()
        if not insist_message:
            return JsonResponse({
                'success': False,
                'message': 'Debe escribir un mensaje para insistir la solicitud.'
            }, status=400)

        now = timezone.now()
        if timezone.is_aware(now):
            now = timezone.localtime(now)
        user_full_name = request.user.get_full_name().strip() or request.user.username
        insist_note = f"INSISTENCIA ({now.strftime('%d/%m/%Y %H:%M')}) por {user_full_name}: {insist_message}"

        if permit.response_note:
            permit.response_note = f"{permit.response_note}\n\n{insist_note}"
        else:
            permit.response_note = insist_note

        permit.status = 'REQUESTED'
        permit.response_date = None
        permit.response_by = None
        permit.updated_by = request.user
        permit.save(update_fields=['status', 'response_note', 'response_date', 'response_by', 'updated_by', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'La solicitud fue insistida y enviada nuevamente al jefe para revisión.'
        })


class PermitReportView(View):
    """Vista para generar reporte imprimible del permiso con código QR - ACCESO PÚBLICO CON VALIDACIÓN POR TOKEN"""

    def _resolve_request_employee(self, request):
        user_person = getattr(request.user, 'person', None)
        employee_profile = getattr(user_person, 'employee_profile', None) if user_person else None

        if employee_profile:
            return employee_profile

        from person.models import Person

        person_by_document = Person.objects.filter(
            document_number=request.user.username
        ).select_related('employee_profile').first()
        if person_by_document and getattr(person_by_document, 'employee_profile', None):
            return person_by_document.employee_profile

        if request.user.email:
            person_by_email = Person.objects.filter(
                email__iexact=request.user.email
            ).select_related('employee_profile').first()
            if person_by_email and getattr(person_by_email, 'employee_profile', None):
                return person_by_email.employee_profile

        return None

    def _can_view_report(self, request, permit):
        if request.user.has_perm('permitrequest.view_permitrequest'):
            return True
        request_employee = self._resolve_request_employee(request)
        return bool(request_employee and request_employee.id == permit.employee_id)

    def get(self, request, pk):
        permit = get_object_or_404(
            PermitRequest.objects.select_related('employee__person', 'permit_type', 'response_by'),
            pk=pk
        )

        # Validar acceso: si hay token en GET, validarlo; si no, requiere permisos
        token = request.GET.get('token')
        if token:
            try:
                permit_id = parse_public_permit_token(token)
                if permit_id != permit.id:
                    return HttpResponse('Código de validación no coincide', status=403)
            except (signing.BadSignature, ValueError, TypeError):
                return HttpResponse('Código de validación inválido o expirado', status=403)
        else:
            # Si no hay token, validar permisos normales
            if not self._can_view_report(request, permit):
                return HttpResponse('Acceso denegado', status=403)
        
        # Solo permitir imprimir si el permiso está aprobado
        if permit.status != 'APPROVED':
            return HttpResponse(
                '<html><body><script>alert("Solo se pueden imprimir permisos aprobados"); window.close();</script></body></html>'
            )
        
        # Generar URL pública firmada para validación mediante QR
        validation_token = build_public_permit_token(permit.id)
        detail_url = request.build_absolute_uri(
            reverse_lazy('permissions:permit_public_validate', kwargs={'token': validation_token})
        )
        
        # Importar qrcode dentro del método para evitar conflictos
        import qrcode as qr_module
        
        qr = qr_module.QRCode(
            version=1,
            error_correction=qr_module.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(detail_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convertir imagen a base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        html = render_to_string(
            'permissions/permit_report.html',
            {
                'permit': permit,
                'qr_code': img_str,
                'detail_url': detail_url,
                'validation_code': f"{validation_token[:10]}...{validation_token[-8:]}"
            },
            request=request
        )
        return HttpResponse(html)


# ==========================================
# VISTAS: BITÁCORAS
# ==========================================

class BitacoraRegisterView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Vista para mostrar el modal de registro de bitácoras"""
    permission_required = 'permitrequest.add_permitrequest'

    def get(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)
        
        html = render_to_string(
            'permissions/modals/modal_bitacora_register.html',
            {
                'employee_id': employee.id,
                'employee_name': employee.person.full_name
            },
            request=request
        )
        return HttpResponse(html)

    def post(self, request, employee_id):
        """Procesa el registro de bitácoras"""
        from datetime import datetime, timedelta
        from django.utils import timezone
        from django.core.files.storage import default_storage
        
        employee = get_object_or_404(Employee, pk=employee_id)
        
        try:
            # Validar archivo PDF
            attachment = request.FILES.get('attachment')
            if not attachment:
                return JsonResponse({
                    'success': False,
                    'message': 'Debe adjuntar un documento PDF'
                }, status=400)
            
            if not attachment.name.lower().endswith('.pdf'):
                return JsonResponse({
                    'success': False,
                    'message': 'Solo se permiten archivos PDF'
                }, status=400)
            
            # Validar tamaño (2MB máximo)
            if attachment.size > 2 * 1024 * 1024:
                return JsonResponse({
                    'success': False,
                    'message': 'El archivo no debe superar los 2MB'
                }, status=400)
            
            # Obtener tipo de permiso "Bitácora"
            bitacora_type = PermitType.objects.filter(name__icontains='Bitácora').first()
            if not bitacora_type:
                # Crear si no existe
                bitacora_type = PermitType.objects.create(
                    name='Bitácora',
                    needs_justification=True,
                    affects_vacation=False,
                    requires_attachment=True
                )
            
            # Datos del formulario
            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            num_days = int(request.POST.get('num_days', 1))
            first_start = request.POST.get('first_start', '').strip()
            first_end = request.POST.get('first_end', '').strip()
            first_crosses_midnight = request.POST.get('first_crosses_midnight') == 'on'
            second_start = request.POST.get('second_start', '').strip()
            second_end = request.POST.get('second_end', '').strip()
            second_crosses_midnight = request.POST.get('second_crosses_midnight') == 'on'
            justification = request.POST.get('justification', '').strip()
            
            # Validar que al menos una jornada esté completa
            has_first = first_start and first_end
            has_second = second_start and second_end
            
            if not has_first and not has_second:
                return JsonResponse({
                    'success': False,
                    'message': 'Debe ingresar al menos una jornada completa'
                }, status=400)
            
            # Validar justificación
            if not justification:
                return JsonResponse({
                    'success': False,
                    'message': 'Debe ingresar la justificación'
                }, status=400)
            
            # Guardar archivo
            from django.utils.text import slugify
            import os
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            employee_slug = slugify(employee.person.full_name)
            file_name = f"bitacora_{employee_slug}_{timestamp}.pdf"
            file_path = os.path.join('permits', 'bitacoras', file_name)
            saved_path = default_storage.save(file_path, attachment)
            
            # Crear permisos para cada día
            created_count = 0
            for day_offset in range(num_days):
                current_date = start_date + timedelta(days=day_offset)
                
                # Primera jornada (si está completa)
                if has_first:
                    # Si cruza medianoche, el permiso va desde current_date hasta current_date + 1
                    if first_crosses_midnight:
                        permit_start_date = current_date
                        permit_end_date = current_date + timedelta(days=1)
                    else:
                        permit_start_date = current_date
                        permit_end_date = current_date

                    # Comprobar solapamiento con bitácoras aprobadas
                    from datetime import datetime, time as dtime

                    def to_dt(d, t):
                        if t is None or t == '':
                            return datetime.combine(d, dtime.min)
                        if isinstance(t, str):
                            try:
                                hhmm = datetime.strptime(t, '%H:%M').time()
                            except Exception:
                                hhmm = datetime.strptime(t, '%H:%M:%S').time()
                            return datetime.combine(d, hhmm)
                        return datetime.combine(d, t)

                    new_start_dt = to_dt(permit_start_date, first_start)
                    new_end_dt = to_dt(permit_end_date, first_end)

                    existing_qs = PermitRequest.objects.filter(
                        employee=employee,
                        permit_type=bitacora_type,
                        status='APPROVED',
                        start_date__lte=permit_end_date,
                        end_date__gte=permit_start_date
                    )
                    conflict = None
                    for ex in existing_qs:
                        ex_start = to_dt(ex.start_date, ex.start_time)
                        ex_end = to_dt(ex.end_date or ex.start_date, ex.end_time)
                        if new_start_dt < ex_end and ex_start < new_end_dt:
                            conflict = ex
                            break

                    if conflict:
                        # Formatear fecha y hora en español para el mensaje
                        meses = {1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'}
                        def fmt_date(d):
                            return f"{d.day} de {meses.get(d.month, '')} de {d.year}"
                        def fmt_timeobj(t):
                            if not t:
                                return ''
                            if isinstance(t, str):
                                try:
                                    tt = datetime.strptime(t, '%H:%M').time()
                                except Exception:
                                    tt = datetime.strptime(t, '%H:%M:%S').time()
                                return tt.strftime('%H:%M')
                            return t.strftime('%H:%M')

                        msg = f"No se puede crear la bitácora: existe una bitácora aprobada con {fmt_date(conflict.start_date)} desde las {fmt_timeobj(conflict.start_time)}"
                        return JsonResponse({
                            'success': False,
                            'message': msg
                        }, status=400)

                    # Formatear respuesta inicial como "Creación"
                    from django.utils.html import escape
                    creation_html = f"<span class=\"note-label note-creation\" style=\"color:#0f172a\">Creación: {escape(justification)}</span>"

                    PermitRequest.objects.create(
                        employee=employee,
                        permit_type=bitacora_type,
                        start_date=permit_start_date,
                        end_date=permit_end_date,
                        start_time=first_start,
                        end_time=first_end,
                        justification_file=saved_path,
                        response_note=creation_html,  # Guardar justificación en response_note (HTML)
                        status='REQUESTED',
                        created_by=request.user,
                        updated_by=request.user
                    )
                    created_count += 1
                
                # Segunda jornada (si está completa)
                if has_second:
                    # Si cruza medianoche, el permiso va desde current_date hasta current_date + 1
                    if second_crosses_midnight:
                        permit_start_date = current_date
                        permit_end_date = current_date + timedelta(days=1)
                    else:
                        permit_start_date = current_date
                        permit_end_date = current_date

                    # Comprobar solapamiento con bitácoras aprobadas (segunda jornada)
                    from datetime import datetime, time as dtime

                    def to_dt2(d, t):
                        if t is None or t == '':
                            return datetime.combine(d, dtime.min)
                        if isinstance(t, str):
                            try:
                                hhmm = datetime.strptime(t, '%H:%M').time()
                            except Exception:
                                hhmm = datetime.strptime(t, '%H:%M:%S').time()
                            return datetime.combine(d, hhmm)
                        return datetime.combine(d, t)

                    new_start_dt = to_dt2(permit_start_date, second_start)
                    new_end_dt = to_dt2(permit_end_date, second_end)

                    existing_qs = PermitRequest.objects.filter(
                        employee=employee,
                        permit_type=bitacora_type,
                        status='APPROVED',
                        start_date__lte=permit_end_date,
                        end_date__gte=permit_start_date
                    )
                    conflict = None
                    for ex in existing_qs:
                        ex_start = to_dt2(ex.start_date, ex.start_time)
                        ex_end = to_dt2(ex.end_date or ex.start_date, ex.end_time)
                        if new_start_dt < ex_end and ex_start < new_end_dt:
                            conflict = ex
                            break

                    if conflict:
                        meses = {1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'}
                        def fmt_date2(d):
                            return f"{d.day} de {meses.get(d.month, '')} de {d.year}"
                        def fmt_timeobj2(t):
                            if not t:
                                return ''
                            if isinstance(t, str):
                                try:
                                    tt = datetime.strptime(t, '%H:%M').time()
                                except Exception:
                                    tt = datetime.strptime(t, '%H:%M:%S').time()
                                return tt.strftime('%H:%M')
                            return t.strftime('%H:%M')

                        msg = f"No se puede crear la bitácora: existe una bitácora aprobada con {fmt_date2(conflict.start_date)} desde las {fmt_timeobj2(conflict.start_time)}"
                        return JsonResponse({
                            'success': False,
                            'message': msg
                        }, status=400)

                    # Formatear respuesta inicial como "Creación" para segunda jornada
                    from django.utils.html import escape
                    creation_html2 = f"<span class=\"note-label note-creation\" style=\"color:#0f172a\">Creación: {escape(justification)}</span>"

                    PermitRequest.objects.create(
                        employee=employee,
                        permit_type=bitacora_type,
                        start_date=permit_start_date,
                        end_date=permit_end_date,
                        start_time=second_start,
                        end_time=second_end,
                        justification_file=saved_path,
                        response_note=creation_html2,  # Guardar justificación en response_note (HTML)
                        status='REQUESTED',
                        created_by=request.user,
                        updated_by=request.user
                    )
                    created_count += 1
            
            return JsonResponse({
                'success': True,
                'message': f'Se crearon {created_count} bitácora(s) correctamente'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al crear bitácoras: {str(e)}'
            }, status=400)


class BitacoraListView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Vista para listar bitácoras pendientes de un empleado"""
    permission_required = 'permitrequest.view_permitrequest'

    def get(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)
        
        # Obtener tipo de permiso "Bitácora"
        bitacora_type = PermitType.objects.filter(name__icontains='Bitácora').first()
        
        if bitacora_type:
            bitacoras = PermitRequest.objects.filter(
                employee=employee,
                permit_type=bitacora_type,
                status__in=['REQUESTED', 'REJECTED']
            ).select_related('created_by').values(
                'id', 'start_date', 'end_date', 'start_time', 'end_time',
                'status', 'created_at', 'created_by__first_name', 'created_by__last_name',
                'response_note', 'justification_file'
            ).order_by('-start_date', '-start_time')
            
            # Construir full_name del created_by (nombre + apellidos)
            for bitacora in bitacoras:
                first_name = bitacora.pop('created_by__first_name', '') or ''
                last_name = bitacora.pop('created_by__last_name', '') or ''
                full_name = f"{first_name} {last_name}".strip()
                bitacora['created_by__full_name'] = full_name if full_name else 'Sistema'
        else:
            bitacoras = []
        
        return JsonResponse({
            'success': True,
            'bitacoras': list(bitacoras),
            'employee_name': employee.person.full_name,
            'employee_identification': employee.person.document_number
        })


class BitacoraHistoryView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Vista para mostrar modal con historial de bitácoras aprobadas"""
    permission_required = 'permitrequest.view_permitrequest'

    def get(self, request, employee_id):
        try:
            employee = get_object_or_404(Employee, pk=employee_id)
            bitacora_type = PermitType.objects.filter(name__icontains='Bitácora').first()
            # Valores seguros para evitar NameError si faltan datos relacionados
            emp_person = getattr(employee, 'person', None)
            employee_name = getattr(emp_person, 'full_name', '') if emp_person else (getattr(employee, 'get_full_name', lambda: '')() or '')
            employee_identification = getattr(emp_person, 'document_number', '') if emp_person else ''

            qs = PermitRequest.objects.none()
            if bitacora_type:
                qs = PermitRequest.objects.filter(
                    employee=employee,
                    permit_type=bitacora_type,
                    status='APPROVED'
                ).select_related('response_by', 'created_by')

            # Filtering (search)
            q = request.GET.get('q', '').strip()
            if q:
                qs = qs.filter(
                    Q(response_note__icontains=q) |
                    Q(created_by__first_name__icontains=q) |
                    Q(created_by__last_name__icontains=q) |
                    Q(response_by__first_name__icontains=q) |
                    Q(response_by__last_name__icontains=q)
                )

            # Date range filter (start_date)
            date_from = request.GET.get('from', '').strip()
            date_to = request.GET.get('to', '').strip()
            if date_from:
                try:
                    qs = qs.filter(start_date__gte=date_from)
                except Exception:
                    pass
            if date_to:
                try:
                    qs = qs.filter(start_date__lte=date_to)
                except Exception:
                    pass

            # Sorting
            sort = request.GET.get('sort', '-start_date')
            # basic whitelist
            allowed_sorts = ['start_date', '-start_date', 'start_time', '-start_time', 'end_time', '-end_time', 'created_at', '-created_at']
            if sort not in allowed_sorts:
                sort = '-start_date'
            qs = qs.order_by(sort)

            # Pagination
            try:
                page = int(request.GET.get('page', 1))
            except ValueError:
                page = 1
            try:
                page_size = int(request.GET.get('page_size', 10))
            except ValueError:
                page_size = 10

            paginator = Paginator(qs, page_size)

            # Manejar caso sin resultados para evitar paginator.page(0)
            if paginator.count == 0:
                page_obj = SimpleNamespace(
                    object_list=[],
                    number=1,
                    has_previous=False,
                    has_next=False,
                    start_index=lambda: 0,
                    end_index=lambda: 0
                )
            else:
                try:
                    page_obj = paginator.page(page)
                except EmptyPage:
                    page_obj = paginator.page(paginator.num_pages)

            context = {
                'bitacoras': page_obj.object_list,
                'employee_name': employee_name,
                'page_obj': page_obj,
                'paginator': paginator,
                'q': q,
                'sort': sort,
                'page_size': page_size,
            }

            # Si se solicita JSON (para render dinámico por JS/Vue), devolver datos en JSON
            if request.GET.get('format') == 'json' or request.headers.get('Accept', '').startswith('application/json'):
                try:
                    # Construir lista serializable
                    bitacoras_list = []
                    for b in page_obj.object_list:
                        # Serializar campos y convertir FieldFile a URL/nombre si aplica
                        jf = getattr(b, 'justification_file', None)
                        jf_val = ''
                        try:
                            if jf:
                                jf_val = jf.url if hasattr(jf, 'url') else (jf.name if hasattr(jf, 'name') else str(jf))
                        except Exception:
                            jf_val = ''

                        bit = {
                            'id': b.id,
                            'start_date': b.start_date.isoformat() if getattr(b, 'start_date', None) else None,
                            'start_time': (b.start_time.strftime('%H:%M') if getattr(b, 'start_time', None) else None),
                            'end_time': (b.end_time.strftime('%H:%M') if getattr(b, 'end_time', None) else None),
                            'status': b.status,
                            'created_at': b.created_at.isoformat() if getattr(b, 'created_at', None) else None,
                            'created_by_full_name': getattr(b.created_by, 'get_full_name', lambda: '')() if b.created_by else '',
                            'response_by_full_name': getattr(b.response_by, 'get_full_name', lambda: '')() if b.response_by else '',
                            'response_date': b.response_date.isoformat() if getattr(b, 'response_date', None) else None,
                            'response_note': getattr(b, 'response_note', '') or '',
                            'justification_file': jf_val
                        }
                        bitacoras_list.append(bit)

                    return JsonResponse({
                        'success': True,
                        'bitacoras': bitacoras_list,
                        'employee_name': employee_name,
                        'page': page_obj.number,
                        'total_pages': paginator.num_pages,
                        'total_count': paginator.count,
                        'can_edit': request.user.has_perm('permitrequest.can_edit')
                    })
                except Exception:
                    logger.exception('Error serializing bitacoras for JSON response')
                    return JsonResponse({'success': False, 'message': 'Error interno al generar el historial'}, status=500)

            # render HTML solo si no se pidió JSON
            html = render_to_string('permissions/modals/modal_bitacora_history.html', context, request=request)
            return HttpResponse(html)
        except Exception:
            logger.exception('Unhandled error in BitacoraHistoryView.get')
            if request.GET.get('format') == 'json' or request.headers.get('Accept', '').startswith('application/json'):
                return JsonResponse({'success': False, 'message': 'Error interno al generar el historial'}, status=500)
            raise


class BitacoraApproveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Vista para aprobar bitácoras seleccionadas"""
    permission_required = 'permitrequest.change_permitrequest'

    def post(self, request):
        from django.utils import timezone
        import json
        

class BitacoraReviewView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Vista que permite a usuarios con permiso `can_edit` marcar una bitácora como PENDIENTE (REQUESTED)
    y añadir una entrada 'Modifica: ...' al historial.
    """
    permission_required = 'permitrequest.can_edit'

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404
        from django.utils.html import escape
        import json

        try:
            if not request.user.has_perm('permitrequest.can_edit'):
                return JsonResponse({'success': False, 'message': 'No autorizado'}, status=403)

            # intentar leer JSON del body primero
            payload = {}
            try:
                if request.body:
                    payload = json.loads(request.body.decode('utf-8'))
            except Exception:
                payload = request.POST

            reason = (payload.get('reason') if isinstance(payload, dict) else None) or request.POST.get('reason')
            if not reason:
                return JsonResponse({'success': False, 'message': 'Se requiere el motivo'}, status=400)

            pr = get_object_or_404(PermitRequest, pk=pk)

            new_note_html = f"<span class=\"note-label note-modifica\" style=\"color:#2563eb\">Modifica: {escape(reason)}</span>"
            existing = pr.response_note or ''
            pr.response_note = new_note_html + '\n\n' + existing if existing else new_note_html
            pr.status = 'REQUESTED'
            pr.save(update_fields=['response_note', 'status'])

            return JsonResponse({'success': True, 'message': 'Motivo añadido. Bitácora marcada como PENDIENTE.', 'response_note': pr.response_note})
        except Exception:
            logger.exception('Error in BitacoraReviewView.post')
            return JsonResponse({'success': False, 'message': 'Error interno'}, status=500)
        
        try:
            data = json.loads(request.body)
            bitacora_ids = data.get('ids', [])
            
            updated = PermitRequest.objects.filter(
                id__in=bitacora_ids,
                status='REQUESTED'
            ).update(
                status='APPROVED',
                response_by=request.user,
                response_date=timezone.now(),
                response_note='Aprobado masivamente',
                updated_by=request.user
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Se aprobaron {updated} bitácora(s) correctamente'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            }, status=400)


class BitacoraRejectView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Vista para rechazar bitácoras seleccionadas con motivo"""
    permission_required = 'permitrequest.change_permitrequest'

    def post(self, request):
        import json
        from django.utils import timezone

        try:
            data = json.loads(request.body)
            bitacora_ids = data.get('ids', [])
            reason = data.get('reason', '') or data.get('reason_text', '')

            if not bitacora_ids:
                return JsonResponse({'success': False, 'message': 'No se especificaron bitácoras'}, status=400)

            # Actualizar las bitácoras a REJECTED y agregar la nota de respuesta
            now = timezone.now()
            updated = 0
            qs = PermitRequest.objects.filter(id__in=bitacora_ids, status='REQUESTED')
            for pr in qs:
                old_note = pr.response_note or ''
                pr.status = 'REJECTED'
                pr.response_by = request.user
                pr.response_date = now
                # Formatear nota con etiqueta HTML en rojo (etiqueta + mensaje coloreados)
                from django.utils.html import escape
                note_html = f"<span class=\"note-label note-reject\" style=\"color:#dc2626\">Rechazo: {escape(reason)}</span>"
                pr.response_note = note_html + (f"\n\n{old_note}" if old_note else '')
                pr.updated_by = request.user
                pr.save(update_fields=['status', 'response_by', 'response_date', 'response_note', 'updated_by', 'updated_at'])
                updated += 1

            return JsonResponse({'success': True, 'message': f'Se marcaron {updated} bitácora(s) como rechazadas'})
        except Exception as e:
            logger.exception('Error rejecting bitacoras')
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=400)


class BitacoraDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Vista para eliminar bitácoras seleccionadas"""
    permission_required = 'permitrequest.delete_permitrequest'

    def post(self, request):
        import json
        
        try:
            bitacora_ids = []
            # intentar leer JSON desde body
            try:
                if request.body:
                    data = json.loads(request.body.decode('utf-8'))
                    bitacora_ids = data.get('ids', []) if isinstance(data, dict) else []
            except Exception:
                bitacora_ids = []

            # soporte para form-data (arrays 'ids[]')
            if not bitacora_ids:
                try:
                    bitacora_ids = request.POST.getlist('ids[]') or request.POST.getlist('ids') or []
                except Exception:
                    bitacora_ids = []

            # normalizar a enteros
            try:
                bitacora_ids = [int(x) for x in bitacora_ids if x != '' and x is not None]
            except Exception:
                bitacora_ids = []

            # permitir eliminar REQUESTED y REJECTED (no eliminar APPROVED por seguridad)
            qs = PermitRequest.objects.filter(id__in=bitacora_ids, status__in=['REQUESTED', 'REJECTED'])
            deleted_count = qs.count()
            if deleted_count:
                qs.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Se eliminaron {deleted_count} bitácora(s) correctamente'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            }, status=400)


class BitacoraEditView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Vista para editar horas de una bitácora (solo inicio/fin)"""
    permission_required = 'permitrequest.change_permitrequest'

    def post(self, request, pk):
        try:
            if not request.user.has_perm('permitrequest.change_permitrequest'):
                return JsonResponse({'success': False, 'message': 'No tiene permisos'}, status=403)

            pr = PermitRequest.objects.filter(pk=pk, status__in=['REQUESTED', 'REJECTED']).first()
            if not pr:
                return JsonResponse({'success': False, 'message': 'Bitácora no encontrada o ya procesada'}, status=404)

            # Si la bitácora estaba REJECTED y se está reeditando, devolver a REQUESTED
            was_rejected = (pr.status == 'REJECTED')

            # Soportar tanto JSON (tiempos) como multipart/form-data (archivo + nota + tiempos)
            content_type = request.META.get('CONTENT_TYPE', '')
            if content_type.startswith('multipart/form-data') or request.FILES:
                # FormData submission
                start_time = request.POST.get('start_time')
                end_time = request.POST.get('end_time')
                response_note = request.POST.get('response_note')
                file = request.FILES.get('justification_file')

                if start_time is not None:
                    pr.start_time = start_time or None
                if end_time is not None:
                    pr.end_time = end_time or None
                if response_note is not None:
                    # Formatear la nota según contexto: si venía REJECTED -> 'Justifica' (verde), si no -> 'Edición' (azul)
                    from django.utils.html import escape
                    if was_rejected:
                        new_note_html = f"<span class=\"note-label note-justifica\" style=\"color:#16a34a\">Justifica: {escape(response_note)}</span>"
                    else:
                        new_note_html = f"<span class=\"note-label note-modifica\" style=\"color:#2563eb\">Modifica: {escape(response_note)}</span>"
                    old_note = pr.response_note or ''
                    pr.response_note = new_note_html + (f"\n\n{old_note}" if old_note else '')
                if file:
                    pr.justification_file = file

                # Inicializar campos a guardar
                save_fields = ['updated_by', 'updated_at']

                # Si venía REJECTED, al re-editar revertimos estado a REQUESTED
                # Comprobar solapamiento con bitácoras aprobadas antes de guardar cambios
                from datetime import datetime, time as dtime

                def to_dt_edit(d, t):
                    if t is None or t == '':
                        return datetime.combine(d, dtime.min)
                    if isinstance(t, str):
                        try:
                            hhmm = datetime.strptime(t, '%H:%M').time()
                        except Exception:
                            hhmm = datetime.strptime(t, '%H:%M:%S').time()
                        return datetime.combine(d, hhmm)
                    return datetime.combine(d, t)

                candidate_start = to_dt_edit(pr.start_date, pr.start_time)
                candidate_end = to_dt_edit(pr.end_date or pr.start_date, pr.end_time)

                # Si el usuario envió nuevos tiempos, recomponer con ellos
                if start_time is not None:
                    candidate_start = to_dt_edit(pr.start_date, start_time)
                if end_time is not None:
                    candidate_end = to_dt_edit(pr.end_date or pr.start_date, end_time)

                existing_qs = PermitRequest.objects.filter(
                    employee=pr.employee,
                    permit_type=pr.permit_type,
                    status='APPROVED'
                ).exclude(pk=pr.pk).filter(
                    start_date__lte=pr.end_date or pr.start_date,
                    end_date__gte=pr.start_date
                )
                for ex in existing_qs:
                    ex_start = to_dt_edit(ex.start_date, ex.start_time)
                    ex_end = to_dt_edit(ex.end_date or ex.start_date, ex.end_time)
                    if candidate_start < ex_end and ex_start < candidate_end:
                        meses = {1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'}
                        def fmt_date_edit(d):
                            return f"{d.day} de {meses.get(d.month, '')} de {d.year}"
                        def fmt_time_edit(t):
                            if not t:
                                return ''
                            if isinstance(t, str):
                                try:
                                    tt = datetime.strptime(t, '%H:%M').time()
                                except Exception:
                                    tt = datetime.strptime(t, '%H:%M:%S').time()
                                return tt.strftime('%H:%M')
                            return t.strftime('%H:%M')

                        msg = f"No se puede actualizar la bitácora: existe una bitácora aprobada con {fmt_date_edit(ex.start_date)} desde las {fmt_time_edit(ex.start_time)}"
                        return JsonResponse({
                            'success': False,
                            'message': msg
                        }, status=400)

                # Si venía REJECTED, al re-editar revertimos estado a REQUESTED
                if was_rejected:
                    pr.status = 'REQUESTED'
                    pr.response_by = None
                    pr.response_date = None
                    save_fields.extend(['status', 'response_by', 'response_date'])
                if start_time is not None:
                    save_fields.append('start_time')
                if end_time is not None:
                    save_fields.append('end_time')
                if response_note is not None:
                    save_fields.append('response_note')
                if file:
                    save_fields.append('justification_file')

                pr.save(update_fields=save_fields)
                return JsonResponse({'success': True, 'message': 'Bitácora actualizada correctamente'})
            else:
                # JSON body (legacy behaviour: only tiempos)
                import json
                payload = json.loads(request.body or '{}')
                start_time = payload.get('start_time')
                end_time = payload.get('end_time')

                if start_time is not None:
                    pr.start_time = start_time or None
                if end_time is not None:
                    pr.end_time = end_time or None
                pr.updated_by = request.user
                pr.save(update_fields=['start_time', 'end_time', 'updated_by', 'updated_at'])
                return JsonResponse({'success': True, 'message': 'Bitácora actualizada correctamente'})
        except Exception as e:
            logger.exception('Error in BitacoraEditView.post')
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=400)
