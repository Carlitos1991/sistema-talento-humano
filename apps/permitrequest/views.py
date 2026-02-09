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
from employee.models import Employee
from budget.models import BudgetLine


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

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.partial_template_name, context, request=self.request)
            
            # Obtener información de paginación
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
                'html': html,
                'pagination': pagination_data
            })
        return super().render_to_response(context, **response_kwargs)


class PermitTypeCreateView(LoginRequiredMixin, CreateView):
    model = PermitType
    form_class = PermitTypeForm
    template_name = 'permissions/modals/modal_permissions_type_form.html'
    success_url = reverse_lazy('permissions:type_list')

    def dispatch(self, request, *args, **kwargs):
        # Verificar permisos manualmente para mejor control de respuesta AJAX
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
            # Renderizar solo el contenido del modal con contexto completo
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

    def get_initial(self):
        initial = super().get_initial()
        # Si venimos de "Crear Sub-item", pre-llenamos el padre
        parent_id = self.request.GET.get('parent')
        if parent_id:
            initial['parent'] = parent_id
        return initial


class PermitTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = PermitType
    form_class = PermitTypeForm
    template_name = 'permissions/modals/modal_permissions_type_form.html'
    success_url = reverse_lazy('permissions:type_list')

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
    success_url = reverse_lazy('permissions:type_list')
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
        
        # Búsqueda por nombres, apellidos o cédula
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(person__first_name__icontains=query) |
                Q(person__last_name__icontains=query) |
                Q(person__document_number__icontains=query)
            )
        
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
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm('permitrequest.add_permitrequest'):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'No tiene permisos para generar permisos'
                }, status=403)
            return HttpResponse('Acceso denegado', status=403)
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        employee_id = request.GET.get('employee')
        if not employee_id:
            return JsonResponse({
                'success': False,
                'message': 'ID de empleado no proporcionado'
            }, status=400)
        
        employee = get_object_or_404(Employee, pk=employee_id)
        
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


# ==========================================
# VISTAS OBSOLETAS - REEMPLAZADAS POR PermitAdminListView y employee_list
# ==========================================
# Estas vistas usaban permissions_permit_list.html y permissions_permit_form.html
# que fueron reemplazados por el nuevo sistema de administración
# Se mantienen comentadas por si se necesitan referencias

# class PermitRequestListView(LoginRequiredMixin, PermissionRequiredMixin, JSONResponseMixin, ListView):
#     model = PermitRequest
#     template_name = 'permissions/permissions_permit_list.html'
#     partial_template_name = 'permissions/partial_permissions_permit_list.html'
#     context_object_name = 'permits'
#     permission_required = 'permissions.view_permitrequest'
#     paginate_by = 10

#     def get_queryset(self):
#         queryset = super().get_queryset().select_related('employee', 'permit_type')
#         query = self.request.GET.get('q')
#         status = self.request.GET.get('status')

#         if query:
#             queryset = queryset.filter(
#                 Q(employee__person__last_name__icontains=query) |
#                 Q(employee__person__first_name__icontains=query) |
#                 Q(employee__person__document_number__icontains=query)
#             )

#         if status:
#             queryset = queryset.filter(status=status)

#         return queryset


# class PermitRequestCreateView(LoginRequiredMixin, CreateView):
#     model = PermitRequest
#     form_class = PermitRequestForm
#     template_name = 'permissions/permissions_permit_form.html'
#     success_url = reverse_lazy('permissions:permit_list')

#     def dispatch(self, request, *args, **kwargs):
#         if not request.user.has_perm('permitrequest.add_permitrequest'):
#             if request.headers.get('x-requested-with') == 'XMLHttpRequest':
#                 return JsonResponse({
#                     'success': False,
#                     'message': 'No tiene permisos para crear permisos'
#                 }, status=403)
#             return HttpResponse('Acceso denegado', status=403)
#         return super().dispatch(request, *args, **kwargs)

#     def form_valid(self, form):
#         form.instance.created_by = self.request.user
#         self.object = form.save()
        
#         if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
#             return JsonResponse({
#                 'success': True,
#                 'message': 'Permiso registrado correctamente'
#             })
#         return super().form_valid(form)
    
#     def form_invalid(self, form):
#         if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
#             return JsonResponse({
#                 'success': False,
#                 'message': 'Error al guardar el permiso',
#                 'errors': form.errors
#             }, status=400)
#         return super().form_invalid(form)


# class PermitRequestUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
#     model = PermitRequest
#     form_class = PermitRequestForm
#     template_name = 'permissions/permissions_permit_form.html'
#     success_url = reverse_lazy('permissions:permit_list')
#     permission_required = 'permissions.change_permitrequest'

#     def form_valid(self, form):
#         form.instance.updated_by = self.request.user
#         return super().form_valid(form)


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
        
        html = render_to_string(
            'permissions/modals/modal_permit_detail.html',
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
        
        if action == 'approve':
            permit.status = 'APPROVED'
            if not response_note:
                response_note = "Se acepta el permiso"
            message = 'Permiso aprobado correctamente'
        elif action == 'reject':
            permit.status = 'REJECTED'
            if not response_note:
                return JsonResponse({
                    'success': False,
                    'message': 'Debe ingresar el motivo de la negativa'
                }, status=400)
            message = 'Permiso rechazado correctamente'
        else:
            return JsonResponse({
                'success': False,
                'message': 'Acción no válida'
            }, status=400)
        
        from django.utils import timezone
        permit.response_note = response_note
        permit.response_date = timezone.now()
        permit.response_by = request.user
        permit.updated_by = request.user
        permit.save()
        
        return JsonResponse({
            'success': True,
            'message': message
        })
