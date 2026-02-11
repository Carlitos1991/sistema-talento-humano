from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from datetime import datetime

from .models import SanctionType, Sanction
from .forms import SanctionTypeForm, SanctionForm
from employee.models import Employee
from budget.models import BudgetLine
from personnel_actions.models import PersonnelAction, ActionType, ActionMovement


# --- MIXIN FOR AJAX SEARCH (Hybrid) ---
class JSONResponseMixin:
    """
    Mixin to handle AJAX responses in ListViews (Dynamic search).
    If it's AJAX, renders only the partial table and returns it in JSON.
    """

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.partial_template_name, context, request=self.request)
            return JsonResponse({'html': html})
        return super().render_to_response(context, **response_kwargs)


# ==========================================
# VIEWS: SANCTION TYPES (Configuration)
# ==========================================

class SanctionTypeListView(LoginRequiredMixin, PermissionRequiredMixin, JSONResponseMixin, ListView):
    model = SanctionType
    template_name = 'sanctions/sanctions_type_list.html'
    partial_template_name = 'sanctions/partials/partial_sanctions_type_list.html'
    context_object_name = 'types'
    permission_required = 'sanctions.view_sanctiontype'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')

        if query:
            queryset = queryset.filter(Q(name__icontains=query))

        return queryset

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.partial_template_name, context, request=self.request)
            
            # Get pagination information
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


class SanctionTypeCreateView(LoginRequiredMixin, CreateView):
    model = SanctionType
    form_class = SanctionTypeForm
    template_name = 'sanctions/modals/modal_sanctions_type_form.html'
    success_url = reverse_lazy('sanctions:type_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm('sanctions.add_sanctiontype'):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tiene permisos para crear tipos de sanción'}, status=403)
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
            return JsonResponse({'success': True, 'message': 'Tipo de sanción creado correctamente.'})
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class SanctionTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = SanctionType
    form_class = SanctionTypeForm
    template_name = 'sanctions/modals/modal_sanctions_type_form.html'
    success_url = reverse_lazy('sanctions:type_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm('sanctions.change_sanctiontype'):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tiene permisos para modificar tipos de sanción'}, status=403)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            context = self.get_context_data(form=form)
            html = render_to_string(self.template_name, context, request=request)
            return HttpResponse(html)
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Tipo de sanción actualizado correctamente.'})
        return super().form_valid(form)
    
    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class SanctionTypeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = SanctionType
    success_url = reverse_lazy('sanctions:type_list')
    permission_required = 'sanctions.delete_sanctiontype'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Eliminado correctamente.'})
        return super().delete(request, *args, **kwargs)


class SanctionTypeToggleView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Toggle active status of sanction type"""
    permission_required = 'sanctions.change_sanctiontype'

    def post(self, request, pk):
        sanction_type = get_object_or_404(SanctionType, pk=pk)
        sanction_type.is_active = not sanction_type.is_active
        sanction_type.save()
        
        status = "activado" if sanction_type.is_active else "desactivado"
        return JsonResponse({
            'success': True,
            'message': f'Tipo de sanción {status} correctamente.',
            'is_active': sanction_type.is_active
        })


# ==========================================
# VIEWS: EMPLOYEE LIST TO GENERATE SANCTIONS
# ==========================================

class EmployeeSanctionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """View to list active employees and manage their sanctions"""
    model = Employee
    template_name = 'sanctions/employee_sanction_list.html'
    context_object_name = 'employees'
    permission_required = 'sanctions.view_sanction'
    paginate_by = 10

    def get_queryset(self):
        queryset = Employee.objects.filter(
            is_active=True
        ).select_related(
            'person',
            'area',
            'employment_status'
        )
        
        # Search by names, last names or document number
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
        
        # Get IDs of employees in current page
        employee_ids = [emp.id for emp in context['employees']]
        
        # Efficient query: get all budget lines at once
        budgets_dict = {}
        if employee_ids:
            budgets = BudgetLine.objects.filter(
                current_employee_id__in=employee_ids,
                is_active=True
            ).select_related('position_item')
            
            for budget in budgets:
                budgets_dict[budget.current_employee_id] = budget
        
        # Add budget information for each employee
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
                'sanctions/partials/partial_employee_list.html',
                context,
                request=self.request
            )
            
            # Pagination information
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


class EmployeeSanctionHistoryView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to show sanction history of an employee"""
    permission_required = 'sanctions.view_sanction'

    def get(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)
        sanctions = Sanction.objects.filter(employee=employee).select_related(
            'sanction_type', 'created_by'
        ).order_by('-sanction_date')
        
        context = {
            'employee': employee,
            'sanctions': sanctions
        }
        
        html = render_to_string(
            'sanctions/modals/modal_employee_sanction_history.html',
            context,
            request=request
        )
        return HttpResponse(html)


# ==========================================
# VIEWS: SANCTION CREATION AND MANAGEMENT
# ==========================================

class GenerateSanctionFormView(LoginRequiredMixin, View):
    """View to generate a sanction for a specific employee"""

    def get(self, request):
        employee_id = request.GET.get('employee_id')
        employee = get_object_or_404(Employee, pk=employee_id)
        
        form = SanctionForm(initial={'employee': employee})
        
        context = {
            'form': form,
            'employee': employee
        }
        
        html = render_to_string(
            'sanctions/modals/modal_generate_sanction_form.html',
            context,
            request=request
        )
        return HttpResponse(html)

    def post(self, request):
        form = SanctionForm(request.POST, request.FILES)
        
        if form.is_valid():
            sanction = form.save(commit=False)
            sanction.created_by = request.user
            sanction.save()
            
            # Create Personnel Action
            try:
                action_type = ActionType.objects.get(code='SAN')
            except ActionType.DoesNotExist:
                # If sanction action type doesn't exist, create it or handle error
                action_type = None
            
            if action_type:
                # Generate unique action number
                year = datetime.now().year
                last_action = PersonnelAction.objects.filter(
                    number__startswith=f'SAN-{year}'
                ).order_by('-number').first()
                
                if last_action:
                    last_num = int(last_action.number.split('-')[-1])
                    new_num = last_num + 1
                else:
                    new_num = 1
                
                action_number = f'SAN-{year}-{new_num:04d}'
                
                # Create PersonnelAction
                personnel_action = PersonnelAction.objects.create(
                    employee=sanction.employee,
                    action_type=action_type,
                    number=action_number,
                    explanation=f'Sanción: {sanction.description[:100]}',
                    motivation=sanction.legal_basis or 'Sanción disciplinaria',
                    date_issue=sanction.sanction_date,
                    date_effective=sanction.start_date or sanction.sanction_date,
                    authority_1_id=1,  # Replace with actual authority
                    created_by=request.user
                )
                
                # Link sanction to personnel action
                sanction.personnel_action = personnel_action
                sanction.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Sanción registrada correctamente.'
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


class SanctionAdminListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """View to list and manage all sanctions"""
    model = Sanction
    template_name = 'sanctions/sanction_admin_list.html'
    context_object_name = 'sanctions'
    permission_required = 'sanctions.view_sanction'
    paginate_by = 15

    def get_queryset(self):
        queryset = Sanction.objects.select_related(
            'employee__person',
            'sanction_type',
            'created_by'
        )
        
        # Filter by search query
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(sanction_number__icontains=query) |
                Q(employee__person__first_name__icontains=query) |
                Q(employee__person__last_name__icontains=query) |
                Q(employee__person__document_number__icontains=query)
            )
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by severity
        severity = self.request.GET.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        return queryset.order_by('-sanction_date', '-sanction_number')

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'sanctions/partials/partial_sanction_admin_table.html',
                context,
                request=self.request
            )
            
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


class SanctionDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to show sanction details"""
    permission_required = 'sanctions.view_sanction'

    def get(self, request, pk):
        sanction = get_object_or_404(
            Sanction.objects.select_related(
                'employee__person',
                'sanction_type',
                'personnel_action',
                'created_by'
            ),
            pk=pk
        )
        
        context = {'sanction': sanction}
        
        html = render_to_string(
            'sanctions/modals/modal_sanction_detail.html',
            context,
            request=request
        )
        return HttpResponse(html)


class SanctionUpdateStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to update sanction status"""
    permission_required = 'sanctions.change_sanction'

    def post(self, request, pk):
        sanction = get_object_or_404(Sanction, pk=pk)
        new_status = request.POST.get('status')
        
        if new_status in dict(Sanction.STATUS_CHOICES):
            sanction.status = new_status
            sanction.updated_by = request.user
            sanction.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Estado de sanción actualizado correctamente.'
            })
        
        return JsonResponse({
            'success': False,
            'message': 'Estado no válido.'
        }, status=400)
