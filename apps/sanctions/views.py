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


# REMOVED - EmployeeSanctionHistoryView no longer needed as we redirect to admin page


# ==========================================
# VIEWS: SANCTION CREATION AND MANAGEMENT
# ==========================================

class GenerateSanctionFormView(LoginRequiredMixin, View):
    """View to generate a sanction for a specific employee"""

    def get(self, request):
        from personnel_actions.models import Authorities
        
        employee_id = request.GET.get('employee_id')
        employee = get_object_or_404(Employee, pk=employee_id)
        
        form = SanctionForm(initial={'employee': employee})
        authorities = Authorities.objects.filter(status=True)
        
        context = {
            'form': form,
            'employee': employee,
            'authorities': authorities
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
            
            # Create Personnel Action first
            try:
                action_type = ActionType.objects.get(code='SANCIONES')
            except ActionType.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Error: Tipo de acción "SANCIONES" no existe. Por favor, créelo en el admin.'
                }, status=400)
            
            # Generate sequential action number based on all PersonnelActions
            year = datetime.now().year
            last_action = PersonnelAction.objects.filter(
                number__endswith=f'-{year}'
            ).order_by('-created_at').first()
            
            if last_action:
                # Extract number from format like 0001-2026
                try:
                    last_num = int(last_action.number.split('-')[0])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            action_number = f'{new_num:04d}-{year}'
            
            # Create PersonnelAction
            personnel_action = PersonnelAction.objects.create(
                employee=sanction.employee,
                action_type=action_type,
                number=action_number,
                explanation=sanction.description,
                motivation=sanction.legal_basis or 'Sanción disciplinaria según LOSEP',
                date_issue=sanction.incident_date,
                date_effective=sanction.sanction_date,
                is_registered=False,
                authority_1_id=request.POST.get('authority_1') or None,
                authority_2_id=request.POST.get('authority_2') or None,
                reviewer_id=request.POST.get('reviewer') or None,
                elaboration_id=request.POST.get('elaboration') or None,
                register_id=request.POST.get('register') or None,
                created_by=request.user
            )
            
            # Link sanction to personnel action and save
            sanction.personnel_action = personnel_action
            sanction.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Sanción registrada correctamente con número {action_number}.'
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
        
        # Filter by employee_id if provided in URL
        employee_id = self.kwargs.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        
        # Filter by search query
        query = self.request.GET.get('q', '').strip()
        if query:
            # If filtering by employee, search by date or number
            if employee_id:
                # Try to parse as date (dd/mm/yyyy or yyyy-mm-dd)
                date_query = None
                try:
                    # Try dd/mm/yyyy format
                    from datetime import datetime
                    if '/' in query:
                        date_query = datetime.strptime(query, '%d/%m/%Y').date()
                    elif '-' in query and len(query) == 10:
                        date_query = datetime.strptime(query, '%Y-%m-%d').date()
                except:
                    pass
                
                if date_query:
                    queryset = queryset.filter(
                        Q(sanction_date=date_query) |
                        Q(incident_date=date_query)
                    )
                else:
                    # Search by number or other text fields
                    queryset = queryset.filter(
                        Q(personnel_action__number__icontains=query) |
                        Q(sanction_type__name__icontains=query)
                    )
            else:
                # Otherwise, search by employee info, number, and type
                queryset = queryset.filter(
                    Q(personnel_action__number__icontains=query) |
                    Q(employee__person__first_name__icontains=query) |
                    Q(employee__person__last_name__icontains=query) |
                    Q(employee__person__document_number__icontains=query) |
                    Q(sanction_type__name__icontains=query)
                )
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by severity
        severity = self.request.GET.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        return queryset.order_by('-sanction_date', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add employee info if filtering by employee
        employee_id = self.kwargs.get('employee_id')
        if employee_id:
            try:
                from employee.models import Employee
                context['filtered_employee'] = Employee.objects.select_related('person').get(pk=employee_id)
            except Employee.DoesNotExist:
                context['filtered_employee'] = None
        
        return context

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


class EditSanctionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to edit an existing sanction"""
    permission_required = 'sanctions.change_sanction'

    def get(self, request, pk):
        from personnel_actions.models import Authorities
        
        sanction = get_object_or_404(
            Sanction.objects.select_related('employee__person', 'personnel_action'),
            pk=pk
        )
        
        # Check if sanction is already registered
        if sanction.personnel_action and sanction.personnel_action.is_registered:
            return HttpResponse(
                '<div class="alert alert-warning" style="padding: 20px; text-align: center;">'
                '<i class="fas fa-exclamation-triangle" style="font-size: 3rem; color: #f59e0b;"></i>'
                '<p style="margin-top: 1rem; font-size: 1.1rem; color: #92400e;">Esta sanción ya está registrada y no puede ser editada.</p>'
                '</div>',
                status=403
            )
        
        form = SanctionForm(instance=sanction)
        authorities = Authorities.objects.filter(status=True)
        
        # Get current authorities from PersonnelAction
        selected_authorities = {}
        if sanction.personnel_action:
            if sanction.personnel_action.authority_1:
                selected_authorities['authority_1'] = sanction.personnel_action.authority_1.id
            if sanction.personnel_action.authority_2:
                selected_authorities['authority_2'] = sanction.personnel_action.authority_2.id
            if sanction.personnel_action.reviewer:
                selected_authorities['reviewer'] = sanction.personnel_action.reviewer.id
            if sanction.personnel_action.elaboration:
                selected_authorities['elaboration'] = sanction.personnel_action.elaboration.id
            if sanction.personnel_action.register:
                selected_authorities['register'] = sanction.personnel_action.register.id
        
        context = {
            'form': form,
            'employee': sanction.employee,
            'authorities': authorities,
            'sanction': sanction,
            'selected_authorities': selected_authorities,
            'is_edit': True
        }
        
        html = render_to_string(
            'sanctions/modals/modal_generate_sanction_form.html',
            context,
            request=request
        )
        return HttpResponse(html)

    def post(self, request, pk):
        sanction = get_object_or_404(Sanction.objects.select_related('personnel_action'), pk=pk)
        
        # Check if sanction is already registered
        if sanction.personnel_action and sanction.personnel_action.is_registered:
            return JsonResponse({
                'success': False,
                'message': 'Esta sanción ya está registrada y no puede ser editada.'
            }, status=403)
        
        form = SanctionForm(request.POST, request.FILES, instance=sanction)
        
        if form.is_valid():
            sanction = form.save(commit=False)
            sanction.updated_by = request.user
            
            # Update PersonnelAction if exists
            if sanction.personnel_action:
                personnel_action = sanction.personnel_action
                personnel_action.explanation = sanction.description
                personnel_action.motivation = sanction.legal_basis or 'Sanción disciplinaria según LOSEP'
                personnel_action.date_issue = sanction.incident_date
                personnel_action.date_effective = sanction.sanction_date
                
                # Update authorities from POST
                authority_1_id = request.POST.get('authority_1')
                authority_2_id = request.POST.get('authority_2')
                reviewer_id = request.POST.get('reviewer')
                elaboration_id = request.POST.get('elaboration')
                register_id = request.POST.get('register')
                
                if authority_1_id:
                    from personnel_actions.models import Authorities
                    personnel_action.authority_1 = Authorities.objects.get(pk=authority_1_id)
                if authority_2_id:
                    personnel_action.authority_2 = Authorities.objects.get(pk=authority_2_id)
                if reviewer_id:
                    personnel_action.reviewer = Authorities.objects.get(pk=reviewer_id)
                if elaboration_id:
                    personnel_action.elaboration = Authorities.objects.get(pk=elaboration_id)
                if register_id:
                    personnel_action.register = Authorities.objects.get(pk=register_id)
                
                personnel_action.save()
            
            sanction.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Sanción actualizada correctamente.'
            })
        
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


class RegisterSanctionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to register a sanction (mark PersonnelAction as registered)"""
    permission_required = 'sanctions.change_sanction'

    def post(self, request, pk):
        from django.utils import timezone
        
        sanction = get_object_or_404(Sanction.objects.select_related('personnel_action'), pk=pk)
        
        if not sanction.personnel_action:
            return JsonResponse({
                'success': False,
                'message': 'Esta sanción no tiene una acción de personal asociada.'
            }, status=400)
        
        if sanction.personnel_action.is_registered:
            return JsonResponse({
                'success': False,
                'message': 'Esta sanción ya está registrada.'
            }, status=400)
        
        # Update PersonnelAction
        personnel_action = sanction.personnel_action
        personnel_action.is_registered = True
        personnel_action.registration_date = timezone.now().date()
        personnel_action.save()
        
        # Update sanction status to ACTIVE
        sanction.status = 'ACTIVE'
        sanction.updated_by = request.user
        sanction.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Sanción registrada correctamente.'
        })


class SanctionPDFView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to generate sanction PDF report"""
    permission_required = 'sanctions.view_sanction'

    def get(self, request, pk):
        from django.template.loader import get_template
        from xhtml2pdf import pisa
        from io import BytesIO
        import datetime as dt
        from django.conf import settings
        import os
        
        sanction = get_object_or_404(
            Sanction.objects.select_related(
                'employee__person__document_type',
                'employee__area',
                'sanction_type',
                'personnel_action__authority_1',
                'personnel_action__authority_2',
                'personnel_action__reviewer',
                'personnel_action__elaboration',
                'personnel_action__register',
                'created_by'
            ),
            pk=pk
        )
        
        # Get budget info
        from budget.models import BudgetLine
        budget = None
        try:
            budget = BudgetLine.objects.select_related('position_item').only(
                'id', 'current_employee', 'position_item__name', 'number_individual', 
                'remuneration', 'status_item__name'
            ).get(current_employee=sanction.employee.pk)
        except BudgetLine.DoesNotExist:
            pass
        
        # Render template
        template = get_template('sanctions/reports/sanction_pdf.html')
        html = template.render({
            'sanction': sanction,
            'employee': sanction.employee,
            'budget': budget,
            'today': dt.datetime.now()
        })
        
        # Link callback for static files
        def link_callback(uri, rel):
            if uri.startswith(settings.STATIC_URL):
                path = uri.replace(settings.STATIC_URL, '')
                if settings.STATICFILES_DIRS:
                    static_root = settings.STATICFILES_DIRS[0]
                else:
                    static_root = settings.STATIC_ROOT or os.path.join(settings.BASE_DIR, 'static')
                return os.path.join(static_root, path)
            return uri
        
        # Generate PDF
        response = HttpResponse(content_type='application/pdf')
        filename = f'Sancion_{sanction.employee.person.full_name.replace(" ", "_")}_{sanction.personnel_action.number.replace("/", "-") if sanction.personnel_action else sanction.pk}.pdf'
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        result = BytesIO()
        pdf = pisa.pisaDocument(
            BytesIO(html.encode("UTF-8")), 
            result, 
            encoding='UTF-8',
            link_callback=link_callback
        )
        
        if not pdf.err:
            response.write(result.getvalue())
            return response
        else:
            return HttpResponse('Error al generar el PDF', status=500)

