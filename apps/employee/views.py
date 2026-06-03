from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.views import View
from django.utils.decorators import method_decorator
import json
from django.utils import timezone
from .models import TeleworkActivity
from biometric.models import OfflineAttendanceRegistry
# Vista para reubicar empleado (relocate_employee)
from schedule.models import EmployeeScheduleHistory
# apps/employee/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.views.generic import DetailView
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from core.models import CatalogItem, Location
from person.models import Person
from person.models import PersonAuditLog
from person.utils import log_person_audit, PERSON_AUDIT_SECTIONS
from .forms import AcademicTitleForm, WorkExperienceForm, TrainingForm
from .models import Employee, Curriculum, AcademicTitle, WorkExperience, Training, InstitutionalData, EconomicData, \
    EmployeeProfileVisibility
from budget.models import BudgetLine
from budget.models import BudgetAssignmentHistory
from contract.models import ManagementPeriod
from permitrequest.models import PermitRequest, PermitType
from personnel_actions.models import PersonnelAction
from payroll.models import Payslip
from sanctions.models import Sanction
from vacation.models import EmployeeVacationBalance
from decimal import Decimal
from datetime import datetime, time
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)


def _safe_related(instance, attr_name, default=None):
    """Acceso seguro a relaciones OneToOne/ForeignKey opcionales."""
    if instance is None:
        return default
    try:
        return getattr(instance, attr_name)
    except ObjectDoesNotExist:
        return default
    except Exception:
        return default


@login_required
def search_employee_by_cedula(request):
    cedula = request.GET.get('q', '').strip()

    if not cedula:
        return JsonResponse({'success': False, 'message': 'Cédula no proporcionada.'})

    try:
        # Buscamos el Empleado a través de su relación con Persona (incluir inactivos)
        emp = Employee.objects.select_related('person').get(person__document_number=cedula)

        # VALIDACIÓN: ¿Este empleado ya ocupa OTRA partida?
        # Buscamos si el ID de este empleado ya está en algún BudgetLine
        existing_assignment = BudgetLine.objects.filter(current_employee=emp).first()

        if existing_assignment:
            return JsonResponse({
                'success': False,
                'message': f'La persona {emp.person.full_name} ya tiene asignada la partida {existing_assignment.code}.'
            })

        # Si está libre, devolvemos data para el modal
        return JsonResponse({
            'success': True,
            'id': emp.id,
            'full_name': emp.person.full_name,
            'email': emp.person.email or 'Sin correo registrado',
            'photo_url': emp.person.photo.url if emp.person.photo else None
        })

    except Employee.DoesNotExist:
        # Si no existe Employee, buscar directamente en Person (incluir inactivos)
        try:
            p = Person.objects.get(document_number=cedula)
            # Si existe Person pero no Employee, informar para crear perfil
            if hasattr(p, 'employee_profile') and p.employee_profile:
                emp = p.employee_profile
                existing_assignment = BudgetLine.objects.filter(current_employee=emp).first()
                if existing_assignment:
                    return JsonResponse({'success': False,
                                         'message': f'La persona {emp.person.full_name} ya tiene asignada la partida {existing_assignment.code}.'})
                return JsonResponse({'success': True, 'id': emp.id, 'full_name': emp.person.full_name,
                                     'email': emp.person.email or 'Sin correo registrado',
                                     'photo_url': emp.person.photo.url if emp.person.photo else None})
            else:
                return JsonResponse({'success': False,
                                     'message': 'Se encontró la Persona pero no tiene perfil de Empleado. Cree el perfil de Empleado antes de asignar la partida.'})
        except Person.DoesNotExist:
            return JsonResponse(
                {'success': False, 'message': 'No se encontró un registro de Persona o Empleado con esa cédula.'})


class EmployeeDetailWizardView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Person
    template_name = 'employee/employee_detail_wizard.html'
    context_object_name = 'person'
    permission_required = 'person.view_person'

    def has_permission(self):
        # Los admins (staff/superuser) pueden ver todo sin restricción de permiso específico
        if self.request.user.is_staff or self.request.user.is_superuser:
            return True
        # Para otros usuarios, verificar el permiso requerido
        return super().has_permission()

    def get_queryset(self):
        return Person.objects.select_related(
            'employee_profile__area',
            'employee_profile__employment_status',
            'curriculum',
            'economic_data__bank_account',
            'economic_data__payroll_info',
            'document_type',
            'gender', 'country', 'province', 'canton', 'parish'
        ).all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_person = _safe_related(self.request.user, 'person', None)
        employee = _safe_related(self.object, 'employee_profile', None)

        curriculum, _ = Curriculum.objects.get_or_create(person=self.object)
        economic_data, _ = EconomicData.objects.get_or_create(person=self.object)
        institutional_data = None
        if employee:
            institutional_data, _ = InstitutionalData.objects.get_or_create(employee=employee)
            current_schedule_assignment = EmployeeScheduleHistory.objects.filter(
                employee=employee,
                is_current=True
            ).select_related('schedule').first()
        context['current_schedule_assignment'] = current_schedule_assignment
        context['curriculum_titles_count'] = 0
        context['curriculum_experiences_count'] = 0
        context['curriculum_courses_count'] = 0
        context['employee_area_name'] = 'SIN AREA ASIGNADA'
        context['employee_profile'] = employee
        context['curriculum_obj'] = curriculum
        context['economic_data'] = economic_data
        context['bank_account'] = _safe_related(economic_data, 'bank_account', None)
        context['payroll_info'] = _safe_related(economic_data, 'payroll_info', None)
        context['institutional_data'] = institutional_data
        if curriculum:
            try:
                context['curriculum_titles_count'] = curriculum.academic_titles.count()
                context['curriculum_experiences_count'] = curriculum.work_experiences.count()
                context['curriculum_courses_count'] = curriculum.trainings.count()
            except Exception:
                context['curriculum_titles_count'] = 0
                context['curriculum_experiences_count'] = 0
                context['curriculum_courses_count'] = 0
        if employee and getattr(employee, 'area', None):
            context['employee_area_name'] = employee.area.name or 'SIN AREA ASIGNADA'

        log_person_audit(
            self.request,
            self.object,
            PersonAuditLog.Action.VIEW,
            PERSON_AUDIT_SECTIONS['personal']
        )
        context['can_generate_self_permit'] = bool(
            context.get('person') and employee and (
                    self.request.user.has_perm('permitrequest.add_permitrequest') or
                    (user_person and user_person.id == self.object.id)
            )
        )
        context['can_insist_rejected_permits'] = bool(
            self.request.user.has_perm('permitrequest.add_permitrequest') or
            (user_person and user_person.id == self.object.id)
        )
        default_enabled_tabs = ['personal', 'curriculum', 'economic', 'institutional']
        # Recuperar visibilidad de pestañas
        visibilities = []
        if hasattr(self.object, 'user') and self.object.user:
            visibilities = EmployeeProfileVisibility.objects.filter(
                user=self.object.user
            ).values_list('tab_id', 'is_visible')

        visibility_dict = {v[0]: v[1] for v in visibilities}

        all_tabs = [
            'personal', 'curriculum', 'economic', 'institutional',
            'budget', 'contracts', 'actions', 'permissions',
            'payments', 'sanctions', 'vacations'
        ]
        # Ocultar pestañas si es self_dashboard
        if hasattr(self, 'is_self_dashboard') and self.is_self_dashboard:
            restricted = ['budget', 'contracts', 'actions', 'sanctions', 'permissions', 'vacations', 'payments']
            # Para el dashboard del empleado, todas las pestañas se rigen por visibility_dict
            for r in restricted:
                if r not in visibility_dict:
                    visibility_dict[r] = 'false'

        final_visibility = {}
        for tab_id in all_tabs:
            if tab_id in visibility_dict:
                # Si ya existe en BD, usamos lo que diga la BD (true o false)
                final_visibility[tab_id] = str(visibility_dict[tab_id]).lower()
            else:
                # Si no existe en BD, activamos solo si está en la lista de los 4 primeros
                is_visible = tab_id in default_enabled_tabs
                final_visibility[tab_id] = str(is_visible).lower()
        import json
        context['tab_visibilities'] = json.dumps(final_visibility)

        context['can_view_restricted_tabs'] = True
        context['restricted_tab_ids'] = ''

        # Permiso para editar
        context['can_edit_person'] = self.request.user.has_perm('person.change_person')

        # Catálogos para los modales del Wizard
        context['education_levels'] = CatalogItem.objects.filter(catalog__code='EDUCATION_LEVELS', is_active=True)
        context['banks_list'] = CatalogItem.objects.filter(catalog__code='BANCO', is_active=True)
        context['account_types_list'] = CatalogItem.objects.filter(catalog__code='ACCOUNT_TYPES', is_active=True)
        context['gender_list'] = CatalogItem.objects.filter(catalog__code='GENDERS', is_active=True)
        context['country_list'] = Location.objects.filter(level=1, is_active=True)
        context['marital_status_list'] = CatalogItem.objects.filter(catalog__code='MARITAL_STATUSES', is_active=True)
        context['blood_type_list'] = CatalogItem.objects.filter(catalog__code='BLOOD_TYPES', is_active=True)
        context['disability_types'] = CatalogItem.objects.filter(catalog__code='DISABILITY_TYPES', is_active=True)
        context['relationships'] = CatalogItem.objects.filter(catalog__code='RELATIONSHIPS', is_active=True)

        # Jerarquía Institucional
        hierarchy_list = []
        if employee and employee.area:
            unit = employee.area
            # Recorremos hacia arriba hasta la raíz
            while unit:
                hierarchy_list.insert(0, {
                    'name': unit.name,
                    'level_name': unit.level.name
                })
                unit = unit.parent
        context['hierarchy_list'] = hierarchy_list

        # Partida presupuestaria actual y su historial
        try:
            if employee:
                # Partida actual (si existe)
                current = BudgetLine.objects.filter(current_employee=employee).first()
                if current:
                    context['current_partida'] = {
                        'code': current.number_individual,
                        'budget': current.code,
                        'name': (current.position_item.name if current.position_item else '') or str(current),
                        'remuneration': str(current.remuneration) if current.remuneration is not None else '—',
                        'category': (current.category_item.name if getattr(current, 'category_item', None) else '')
                    }
                else:
                    context['current_partida'] = None

                # Historial de partidas asignadas a este empleado
                assignments = BudgetAssignmentHistory.objects.filter(employee=employee).select_related('budget_line')
                history = []
                for a in assignments:
                    bl = a.budget_line
                    history.append({
                        'partida_code': bl.number_individual or bl.code,
                        'position_name': (bl.position_item.name if bl.position_item else ''),
                        'remuneration': str(bl.remuneration),
                        'partida_name': str(bl),
                        'code': bl.code
                    })
                context['partida_history'] = history
            else:
                context['current_partida'] = None
                context['partida_history'] = []
        except Exception:
            context['current_partida'] = None
            context['partida_history'] = []

        # Contrato actual y historial de contratos
        try:
            if employee:
                latest = ManagementPeriod.objects.filter(employee=employee).order_by('-start_date').first()
                if latest and latest.is_currently_active:
                    current_contract = latest
                else:
                    current_contract = latest

                if current_contract:
                    context['current_contract'] = {
                        'id': current_contract.id,
                        'document_number': current_contract.document_number,
                        'position_name': current_contract.budget_line.position_item.name if getattr(current_contract,
                                                                                                    'budget_line',
                                                                                                    None) and getattr(
                            current_contract.budget_line, 'position_item', None) else '',
                        'contract_type_name': str(
                            current_contract.contract_type) if current_contract.contract_type else '',
                        'start_date': current_contract.start_date.strftime(
                            '%d/%m/%Y') if current_contract.start_date else '',
                        'end_date': current_contract.end_date.strftime('%d/%m/%Y') if current_contract.end_date else '',
                        'administrative_unit': current_contract.administrative_unit.name if current_contract.administrative_unit else '',
                        'status_name': current_contract.status.name if current_contract.status else '',
                        'signed_document_url': current_contract.signed_document.url if getattr(current_contract,
                                                                                               'signed_document',
                                                                                               None) else None
                    }
                else:
                    context['current_contract'] = None

                periods = ManagementPeriod.objects.filter(employee=employee).select_related('contract_type', 'status',
                                                                                            'administrative_unit').order_by(
                    '-start_date')[:50]
                ch = []
                for per in periods:
                    ch.append({
                        'id': per.id,
                        'document_number': per.document_number,
                        'position_name': per.budget_line.position_item.name if getattr(per, 'budget_line',
                                                                                       None) and getattr(
                            per.budget_line, 'position_item', None) else '',
                        'contract_type_name': str(per.contract_type) if per.contract_type else '',
                        'start_date': per.start_date.strftime('%d/%m/%Y') if per.start_date else '',
                        'end_date': per.end_date.strftime('%d/%m/%Y') if per.end_date else '',
                        'administrative_unit': per.administrative_unit.name if per.administrative_unit else '',
                        'status_name': per.status.name if per.status else '',
                        'signed_document_url': per.signed_document.url if getattr(per, 'signed_document',
                                                                                  None) else None
                    })
                context['contract_history'] = ch
            else:
                context['current_contract'] = None
                context['contract_history'] = []
        except Exception:
            context['current_contract'] = None
            context['contract_history'] = []

        # Permiso actual y historial de permisos (vacaciones/horas/otros)
        # Compatible con configuraciones con/sin TZ activa.
        now = timezone.now().date()
        month_names = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        default_permissions_month_label = f"{month_names.get(now.month, '')} de {now.year}"
        try:
            if employee:
                latest_perm = PermitRequest.objects.filter(employee=employee).order_by('-start_date',
                                                                                       '-created_at').first()
                if latest_perm:
                    context['current_permission'] = {
                        'id': latest_perm.id,
                        'permit_type': latest_perm.permit_type.name if latest_perm.permit_type else str(
                            latest_perm.permit_type),
                        'start_date': latest_perm.start_date if latest_perm.start_date else None,
                        'end_date': latest_perm.end_date if latest_perm.end_date else None,
                        'status': dict(PermitRequest.STATUS_CHOICES).get(latest_perm.status, latest_perm.status),
                        'status_code': latest_perm.status,
                        'days': latest_perm.days,
                        'hours': latest_perm.hours,
                        'justification_file_url': latest_perm.justification_file.url if getattr(latest_perm,
                                                                                                'justification_file',
                                                                                                None) else None
                    }
                else:
                    context['current_permission'] = None

                perms = PermitRequest.objects.filter(
                    employee=employee,
                ).exclude(status__in=['CANCELED', 'INACTIVE']).select_related('permit_type').order_by('-start_date',
                                                                                                      '-created_at')

                type_ids = list(
                    perms.values_list('permit_type_id', flat=True).distinct()
                )
                context['permission_filter_types'] = list(
                    PermitType.objects.filter(id__in=type_ids).order_by('name').values_list('id', 'name')
                )
                context['permissions_month_label'] = default_permissions_month_label

                ph = []
                for p in perms:
                    duration_days = int(p.days or 0)
                    duration_hours = int(p.hours or 0)
                    duration_minutes = int(getattr(p, 'minutes', 0) or 0)

                    # Si no hay duración persistida, calcularla desde fechas/horas.
                    if duration_days == 0 and duration_hours == 0 and duration_minutes == 0 and p.start_date and p.end_date:
                        start_dt = datetime.combine(p.start_date, p.start_time or time.min)
                        end_dt = datetime.combine(p.end_date, p.end_time or time.min)
                        if end_dt < start_dt:
                            end_dt = start_dt

                        total_minutes = int((end_dt - start_dt).total_seconds() // 60)
                        if total_minutes == 0 and p.end_date > p.start_date:
                            total_minutes = (p.end_date - p.start_date).days * 24 * 60

                        # Convención laboral: 1 día = 8 horas.
                        duration_days = total_minutes // (8 * 60)
                        remainder = total_minutes % (8 * 60)
                        duration_hours = remainder // 60
                        duration_minutes = remainder % 60

                    duration_parts = [f"Días: {duration_days}", f"Horas: {duration_hours}"]
                    if duration_minutes > 0:
                        duration_parts.append(f"Min: {duration_minutes}")

                    ph.append({
                        'id': p.id,
                        'permit_type_id': p.permit_type_id,
                        'permit_type': p.permit_type.name if p.permit_type else '',
                        'start_date': p.start_date if p.start_date else None,
                        'start_time': p.start_time if p.start_time else None,
                        'end_date': p.end_date if p.end_date else None,
                        'status': dict(PermitRequest.STATUS_CHOICES).get(p.status, p.status),
                        'status_code': p.status,
                        'days': duration_days,
                        'hours': duration_hours,
                        'minutes': duration_minutes,
                        'duration_text': ' | '.join(duration_parts),
                        'response_note': p.response_note or '',
                        'justification_file_url': p.justification_file.url if getattr(p, 'justification_file',
                                                                                      None) else None
                    })
                context['permissions_history'] = ph
            else:
                context['current_permission'] = None
                context['permissions_history'] = []
                context['permission_filter_types'] = []
                context['permissions_month_label'] = default_permissions_month_label
        except Exception:
            context['current_permission'] = None
            context['permissions_history'] = []
            context['permission_filter_types'] = []
            context['permissions_month_label'] = default_permissions_month_label

        # Acciones de personal (historial)
        try:
            if employee:
                actions_qs = PersonnelAction.objects.filter(employee=employee).select_related('action_type').order_by(
                    '-date_issue')[:50]
                actions_list = []
                for a in actions_qs:
                    mv = a.movement.first() if hasattr(a, 'movement') else None
                    from_area = mv.previous_unit if mv and mv.previous_unit else ''
                    to_area = mv.new_unit if mv and mv.new_unit else ''
                    actions_list.append({
                        'id': a.pk,
                        'number': a.number,
                        'action_name': a.action_type.name if a.action_type else '',
                        'from_area': from_area,
                        'to_area': to_area,
                        'issued_date': a.date_issue,
                        'effective_date': a.date_effective,
                        'document_url': reverse('personnel_actions:action_pdf', args=[a.pk])
                    })
                context['actions_list'] = actions_list
            else:
                context['actions_list'] = []
        except Exception:
            context['actions_list'] = []

        # Roles de pago (historial)
        try:
            if employee:
                payslips_qs = Payslip.objects.filter(employee=employee).select_related('period').order_by(
                    '-period__year', '-period__id')[:12]
                roles_history = []
                for payslip in payslips_qs:
                    period = payslip.period
                    roles_history.append({
                        'id': payslip.pk,
                        'period_month': period.month if period else '',
                        'period_year': period.year if period else '',
                        'total_income': float(payslip.total_income or 0),
                        'total_deduction': float(payslip.total_deduction or 0),
                        'net_pay': float(payslip.net_pay or 0),
                        'print_url': reverse('payroll:payslip_print', args=[payslip.pk])
                    })
                context['payment_roles_history'] = roles_history
            else:
                context['payment_roles_history'] = []
        except Exception:
            context['payment_roles_history'] = []

        # Historial de sanciones
        try:
            if employee:
                sanctions_qs = Sanction.objects.filter(employee=employee).select_related('sanction_type').order_by(
                    '-sanction_date')[:50]
                sh = []
                for s in sanctions_qs:
                    sh.append({
                        'type': s.sanction_type.name if s.sanction_type else '',
                        'description': s.description,
                        'reason': s.legal_basis,
                        'severity': dict(Sanction.SEVERITY_CHOICES).get(s.severity, s.severity) if hasattr(Sanction,
                                                                                                           'SEVERITY_CHOICES') else s.severity,
                        'severity_code': s.severity,
                        'date': s.sanction_date
                    })
                context['sanctions_history'] = sh
            else:
                context['sanctions_history'] = []
        except Exception:
            context['sanctions_history'] = []

        # Vacaciones: saldos por periodo
        try:
            if employee:
                # Traer balances (lista) para mostrar en la UI
                balances_qs = EmployeeVacationBalance.objects.filter(employee=employee).select_related(
                    'period').order_by('-created_at')[:50]
                vb = []
                for b in balances_qs:
                    total_with_previous = (Decimal(str(b.total_days or 0)) + Decimal(str(b.additional_days or 0)))
                    vb.append({
                        'id': b.id,
                        'period': b.period.name if b.period else '',
                        'total_days': float(b.total_days or 0),
                        'total_with_previous_balance': float(total_with_previous),
                        'balance_days': float(b.balance_days or 0),
                        'additional_days': float(b.additional_days or 0),
                        'permit_days': float(b.permit_days or 0),
                        'vacation_days': float(b.vacation_days or 0),
                        'taken_days': float(getattr(b, 'taken_days', 0) or 0),
                        'observation': b.observation
                    })

                # Calcular totales para el gráfico circular usando EL ÚLTIMO período creado
                last_balance = EmployeeVacationBalance.objects.filter(employee=employee).order_by(
                    '-created_at').select_related('period').first()
                if last_balance:
                    total_capacity = Decimal(str(last_balance.total_days or 0)) + Decimal(
                        str(last_balance.additional_days or 0))
                    permits_used = Decimal(str(last_balance.permit_days or 0))
                    vacations_used = Decimal(str(last_balance.vacation_days or 0))
                    # saldo esperado (por seguridad usar balance_days de la BD si existe)
                    saldo_db = Decimal(
                        str(last_balance.balance_days or (total_capacity - (permits_used + vacations_used))))
                else:
                    total_capacity = Decimal('0.0')
                    permits_used = Decimal('0.0')
                    vacations_used = Decimal('0.0')
                    saldo_db = Decimal('0.0')

                context['vacation_balances'] = vb
                context['vacation_chart'] = {
                    'total_capacity': float(total_capacity),
                    'permits': float(permits_used),
                    'vacations': float(vacations_used),
                    'saldo': float(saldo_db)
                }
            else:
                context['vacation_balances'] = []
                context['vacation_chart'] = {'total_capacity': 0, 'permits': 0, 'vacations': 0, 'saldo': 0}
        except Exception:
            context['vacation_balances'] = []
            context['vacation_chart'] = {'total_capacity': 0, 'permits': 0, 'vacations': 0, 'saldo': 0}

        return context


@require_POST
def bulk_update_tab_visibility(request):
    tab_id = request.POST.get('tab_id')
    is_visible = request.POST.get('is_visible') == 'true'

    if not tab_id:
        return JsonResponse({'success': False, 'message': 'ID de pestaña no válido.'})

    with transaction.atomic():
        EmployeeProfileVisibility.objects.filter(tab_id=tab_id).delete()
        users = User.objects.filter(person__isnull=False)
        new_configs = [
            EmployeeProfileVisibility(user=u, tab_id=tab_id, is_visible=is_visible)
            for u in users
        ]
        EmployeeProfileVisibility.objects.bulk_create(new_configs)

    return JsonResponse({
        'success': True,
        'message': f'Pestaña "{tab_id}" actualizada para {len(new_configs)} empleados.'
    })


class EmployeeSelfDashboardView(EmployeeDetailWizardView):
    template_name = 'employee/employee_dashboard.html'
    permission_required = ()

    def get_object(self, queryset=None):
        user_person = _safe_related(self.request.user, 'person', None)
        if not user_person:
            raise Http404("El usuario no tiene persona asociada.")
        self.is_self_dashboard = True
        return user_person

    def get_context_data(self, **kwargs):
        # We let the parent class generate the context and handle tab visibilities
        context = super().get_context_data(**kwargs)

        # We need to make sure the self dashboard context matches the standard output if there's any errors
        if not context.get('person'):
            person = self.get_object()
            curriculum, _ = Curriculum.objects.get_or_create(person=person)
            context.update({
                'person': person,
                'employee_profile': _safe_related(person, 'employee_profile', None),
                'curriculum_obj': curriculum,
                'curriculum_titles_count': curriculum.academic_titles.count() if curriculum else 0,
                'curriculum_experiences_count': curriculum.work_experiences.count() if curriculum else 0,
                'curriculum_courses_count': curriculum.trainings.count() if curriculum else 0,
                'employee_area_name': 'SIN AREA ASIGNADA',
                'can_generate_self_permit': False,
                'can_insist_rejected_permits': False,
                'education_levels': CatalogItem.objects.filter(catalog__code='EDUCATION_LEVELS', is_active=True),
                'banks_list': CatalogItem.objects.filter(catalog__code='BANCO', is_active=True),
                'account_types_list': CatalogItem.objects.filter(catalog__code='ACCOUNT_TYPES', is_active=True),
                'gender_list': CatalogItem.objects.filter(catalog__code='GENDERS', is_active=True),
                'country_list': Location.objects.filter(level=1, is_active=True),
                'marital_status_list': CatalogItem.objects.filter(catalog__code='MARITAL_STATUSES', is_active=True),
                'blood_type_list': CatalogItem.objects.filter(catalog__code='BLOOD_TYPES', is_active=True),
                'disability_types': CatalogItem.objects.filter(catalog__code='DISABILITY_TYPES', is_active=True),
                'relationships': CatalogItem.objects.filter(catalog__code='RELATIONSHIPS', is_active=True),
                'hierarchy_list': [],
                'current_partida': None,
                'partida_history': [],
                'current_contract': None,
                'contract_history': [],
                'current_permission': None,
                'permissions_history': [],
                'permission_filter_types': [],
                'permissions_month_label': '',
                'actions_list': [],
                'payment_roles_history': [],
                'sanctions_history': [],
                'vacation_balances': [],
                'vacation_chart': {'total_capacity': 0, 'permits': 0, 'vacations': 0, 'saldo': 0},
                'economic_data': _safe_related(person, 'economic_data', None),
                'bank_account': None,
                'payroll_info': None,
                'institutional_data': None,
            })

        return context


@transaction.atomic
def upload_cv_pdf(request, person_id):
    if request.method == 'POST':
        person = get_object_or_404(Person, pk=person_id)
        curriculum, created = Curriculum.objects.get_or_create(person=person)

        pdf_file = request.FILES.get('pdf_file')
        if pdf_file:
            curriculum.pdf_file = pdf_file
            curriculum.save()
            return JsonResponse({'success': True, 'message': 'PDF actualizado correctamente.'})
    return JsonResponse({'success': False, 'message': 'Error al subir archivo.'}, status=400)


@transaction.atomic
def add_academic_title(request, person_id):
    if request.method == 'POST':
        person = get_object_or_404(Person, pk=person_id)
        curriculum, created = Curriculum.objects.get_or_create(person=person)

        form = AcademicTitleForm(request.POST)
        if form.is_valid():
            title = form.save(commit=False)
            title.curriculum = curriculum
            title.save()
            return JsonResponse({'success': True, 'message': 'Título académico registrado.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    return None


from .models import EconomicData, BankAccount, PayrollInfo
from .forms import BankAccountForm, PayrollInfoForm


@transaction.atomic
def add_bank_account(request, person_id):
    if request.method == 'POST':
        person = get_object_or_404(Person, pk=person_id)
        # Aseguramos que existan los datos económicos
        economic_data, created = EconomicData.objects.get_or_create(person=person)

        # Si ya tiene una cuenta, la editamos, si no, creamos una nueva
        instance = getattr(economic_data, 'bank_account', None)
        form = BankAccountForm(request.POST, instance=instance)

        if form.is_valid():
            bank_acc = form.save(commit=False)
            bank_acc.economic_data = economic_data
            bank_acc.save()
            log_person_audit(
                request,
                person,
                PersonAuditLog.Action.UPDATE,
                PERSON_AUDIT_SECTIONS['economic'],
                'Actualizó cuenta bancaria'
            )
            return JsonResponse({'success': True, 'message': 'Cuenta bancaria registrada con éxito.'})

        # Debug: log errors and return posted data to help trace client-side issues
        import logging
        logger = logging.getLogger(__name__)
        try:
            posted = dict(request.POST)
        except Exception:
            posted = {}
        logger.debug('add_bank_account invalid form errors: %s', form.errors)
        logger.debug('add_bank_account POST data: %s', posted)
        return JsonResponse({'success': False, 'errors': form.errors, 'posted': posted}, status=400)
    return None


@transaction.atomic
def update_payroll_info(request, person_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido.'}, status=405)

    person = get_object_or_404(Person, pk=person_id)
    economic_data, _ = EconomicData.objects.get_or_create(person=person)

    instance = getattr(economic_data, 'payroll_info', None)
    post_data = request.POST.copy()

    # Permite actualizaciones parciales desde toggles JS sin romper validaciones del ModelForm.
    if 'family_dependents' not in post_data:
        post_data['family_dependents'] = str(getattr(instance, 'family_dependents', 0) or 0)
    if 'education_dependents' not in post_data:
        post_data['education_dependents'] = str(getattr(instance, 'education_dependents', 0) or 0)
    if 'roles_count' not in post_data:
        post_data['roles_count'] = str(getattr(instance, 'roles_count', 0) or 0)
    if 'roles_entry_date' not in post_data:
        entry_date = getattr(instance, 'roles_entry_date', None)
        post_data['roles_entry_date'] = entry_date.isoformat() if entry_date else ''

    form = PayrollInfoForm(post_data, instance=instance)
    if form.is_valid():
        payroll = form.save(commit=False)
        payroll.economic_data = economic_data
        payroll.save()
        log_person_audit(
            request,
            person,
            PersonAuditLog.Action.UPDATE,
            PERSON_AUDIT_SECTIONS['economic'],
            'Actualizó información de nómina'
        )
        return JsonResponse({'success': True, 'message': 'Información de nómina actualizada.'})

    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
def get_payroll_info_api(request, person_id):
    person = get_object_or_404(Person, pk=person_id)
    try:
        payroll = person.economic_data.payroll_info
        data = {
            'monthly_payment': payroll.monthly_payment,
            'reserve_funds': payroll.reserve_funds,
            'family_dependents': payroll.family_dependents,
            'education_dependents': payroll.education_dependents,
            'roles_entry_date': payroll.roles_entry_date,
            'roles_count': payroll.roles_count
        }
        return JsonResponse({'success': True, 'data': data})
    except Exception:
        return JsonResponse({'success': False, 'data': {}})


@login_required
def get_bank_account_api(request, person_id):
    person = get_object_or_404(Person, pk=person_id)
    try:
        bank_account = person.economic_data.bank_account
        data = {
            'bank': bank_account.bank.id,
            'account_type': bank_account.account_type.id,
            'account_number': bank_account.account_number,
            'holder_name': bank_account.holder_name
        }
        return JsonResponse({'success': True, 'data': data})
    except Exception:
        return JsonResponse({'success': False, 'data': {}})


@transaction.atomic
def upload_cv_pdf(request, person_id):
    if request.method == 'POST':
        person = get_object_or_404(Person, pk=person_id)
        curriculum, created = Curriculum.objects.get_or_create(person=person)

        pdf_file = request.FILES.get('pdf_file')
        if pdf_file:
            curriculum.pdf_file = pdf_file
            curriculum.save()
            return JsonResponse({'success': True, 'message': 'PDF actualizado correctamente.'})
    return JsonResponse({'success': False, 'message': 'Error al subir archivo.'}, status=400)


@transaction.atomic
def add_academic_title_api(request, person_id):
    if request.method == 'POST':
        person = get_object_or_404(Person, pk=person_id)
        curriculum, _ = Curriculum.objects.get_or_create(person=person)

        form = AcademicTitleForm(request.POST)
        if form.is_valid():
            title = form.save(commit=False)
            title.curriculum = curriculum
            title.save()
            return JsonResponse({'success': True, 'message': 'Título registrado correctamente'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    return None


@require_POST
def edit_academic_title_api(request, title_id):
    title = get_object_or_404(AcademicTitle, pk=title_id)
    form = AcademicTitleForm(request.POST, instance=title)
    if form.is_valid():
        form.save()
        return JsonResponse({'success': True, 'message': 'Título actualizado correctamente'})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@transaction.atomic
def add_work_experience_api(request, person_id):
    if request.method == 'POST':
        person = get_object_or_404(Person, pk=person_id)
        curriculum, _ = Curriculum.objects.get_or_create(person=person)

        form = WorkExperienceForm(request.POST)
        if form.is_valid():
            experience = form.save(commit=False)
            experience.curriculum = curriculum
            experience.save()
            return JsonResponse({'success': True, 'message': 'Experiencia laboral registrada correctamente.'})

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    return None


@require_POST
@transaction.atomic
def edit_work_experience_api(request, experience_id):
    experience = get_object_or_404(WorkExperience, pk=experience_id)
    form = WorkExperienceForm(request.POST, instance=experience)
    if form.is_valid():
        form.save()
        return JsonResponse({'success': True, 'message': 'Experiencia actualizada correctamente'})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@transaction.atomic
def add_training_api(request, person_id):
    if request.method == 'POST':
        person = get_object_or_404(Person, pk=person_id)
        curriculum, _ = Curriculum.objects.get_or_create(person=person)

        form = TrainingForm(request.POST)
        if form.is_valid():
            training = form.save(commit=False)
            training.curriculum = curriculum
            training.save()
            return JsonResponse({'success': True, 'message': 'Capacitación registrada correctamente.'})

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    return None


@require_POST
@transaction.atomic
def edit_training_api(request, training_id):
    training = get_object_or_404(Training, pk=training_id)
    form = TrainingForm(request.POST, instance=training)
    if form.is_valid():
        form.save()
        return JsonResponse({'success': True, 'message': 'Capacitación actualizada correctamente'})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


def list_academic_titles_api(request, person_id):
    person = get_object_or_404(Person, pk=person_id)

    if hasattr(person, 'curriculum') and person.curriculum:
        titles = person.curriculum.academic_titles.all()
    else:
        titles = []

    items = [
        {
            'id': title.id,
            'name': title.title_obtained,
            'code': title.education_level.name if title.education_level else 'N/A',
            'institution': title.educational_institution,
            'year': title.graduation_year
        }
        for title in titles
    ]

    return JsonResponse({'success': True, 'items': items})


def list_work_experience_api(request, person_id):
    from datetime import date
    person = get_object_or_404(Person, pk=person_id)

    total_years = 0
    total_months = 0
    items = []

    if hasattr(person, 'curriculum') and person.curriculum:
        experiences = person.curriculum.work_experiences.all()

        total_days = 0
        for exp in experiences:
            start = exp.start_date
            end = date.today() if exp.is_current else (exp.end_date or date.today())
            if start:
                total_days += (end - start).days

        total_years = total_days // 365
        remaining_days = total_days % 365
        total_months = remaining_days // 30

        items = [
            {
                'id': exp.id,
                'name': f"{exp.position} - {exp.company_name}",
                'code': 'EXP',
                'company': exp.company_name,
                'position': exp.position,
                'start_date': exp.start_date.isoformat() if exp.start_date else None,
                'end_date': exp.end_date.isoformat() if exp.end_date else None,
                'is_current': exp.is_current
            }
            for exp in experiences
        ]

    return JsonResponse({
        'success': True,
        'items': items,
        'total_years': total_years,
        'total_months': total_months
    })


def list_training_api(request, person_id):
    person = get_object_or_404(Person, pk=person_id)

    if hasattr(person, 'curriculum') and person.curriculum:
        trainings = person.curriculum.trainings.all()
    else:
        trainings = []

    items = [
        {
            'id': training.id,
            'name': training.training_name,
            'code': f"{training.hours}h",
            'institution': training.institution,
            'date': training.completion_date.strftime('%d/%m/%Y') if training.completion_date else ''
        }
        for training in trainings
    ]

    return JsonResponse({'success': True, 'items': items})


@require_POST
def delete_academic_title_api(request, title_id):
    title = get_object_or_404(AcademicTitle, pk=title_id)
    person_id = title.curriculum.person_id
    title.delete()
    return JsonResponse({'success': True, 'message': 'Registro eliminado', 'person_id': person_id})


@require_POST
def delete_cv_item_api(request, item_type, item_id):
    models = {'academic': AcademicTitle, 'experience': WorkExperience, 'training': Training}
    item = get_object_or_404(models[item_type], pk=item_id)
    item.delete()
    return JsonResponse({'success': True, 'message': 'Eliminado correctamente'})


def get_cv_item_detail_api(request, item_type, item_id):
    models = {'academic': AcademicTitle, 'experience': WorkExperience, 'training': Training}
    item = get_object_or_404(models[item_type], pk=item_id)
    # Serialización manual para evitar errores de fecha
    if item_type == 'academic':
        data = {
            'id': item.id,
            'education_level': item.education_level_id,
            'title_obtained': item.title_obtained,
            'educational_institution': item.educational_institution,
            'graduation_year': item.graduation_year,
            'senescyt_number': item.senescyt_number or ''
        }
    elif item_type == 'experience':
        data = {'id': item.id, 'company_name': item.company_name, 'position': item.position,
                'start_date': item.start_date.isoformat(),
                'end_date': item.end_date.isoformat() if item.end_date else '', 'is_current': item.is_current}
    else:  # training
        data = {'id': item.id, 'training_name': item.training_name, 'institution': item.institution,
                'hours': item.hours,
                'completion_date': item.completion_date.isoformat() if item.completion_date else ''}

    return JsonResponse({'success': True, 'data': data})


@login_required
@login_required
def get_institutional_data_api(request, person_id):
    try:
        person = get_object_or_404(Person, pk=person_id)
        employee = getattr(person, 'employee_profile', None)

        if not employee:
            return JsonResponse({'success': False, 'message': 'Empleado no encontrado'}, status=404)

        # Obtener o crear datos institucionales
        inst_data, created = InstitutionalData.objects.get_or_create(employee=employee)

        # Datos derivados de Presupuesto (Solo lectura por ahora)
        current_budget = employee.current_budget_line.first()  # Reverse relation
        regime_name = current_budget.regime_item.name if (
                current_budget and current_budget.regime_item) else 'Sin definir'
        position_name = current_budget.position_item.name if (
                current_budget and current_budget.position_item) else 'Sin definir'

        data = {
            'area': employee.area.id if employee.area else None,
            'area_name': employee.area.name if employee.area else 'Sin Asignar',
            'employment_status': employee.employment_status.id if employee.employment_status else None,
            'employment_status_name': employee.employment_status.name if employee.employment_status else 'Sin Definir',
            'is_boss': employee.is_boss if hasattr(employee, 'is_boss') else False,
            'regime_name': regime_name,
            'position': position_name,

            # Campos Editables de InstitutionalData
            'file_number': inst_data.file_number or '',
            'biometric_id': inst_data.biometric_id or '',
            'institutional_email': inst_data.institutional_email or '',
            'observations': inst_data.observations or '',
            'collective_contract': inst_data.collective_contract,
            'entry_date': inst_data.entry_date.isoformat() if inst_data.entry_date else ''
        }
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@transaction.atomic
def save_institutional_data_api(request, person_id):
    if request.method == 'POST':
        try:
            person = get_object_or_404(Person, pk=person_id)
            employee = person.employee_profile

            # 1. Actualizar Datos del Empleado (Area y Estado)
            area_id = request.POST.get('area')
            status_id = request.POST.get('employment_status')

            if area_id:
                if area_id == 'null' or area_id == '':
                    employee.area = None
                else:
                    employee.area_id = area_id

            if status_id:
                if status_id == 'null' or status_id == '':
                    employee.employment_status = None
                else:
                    employee.employment_status_id = status_id

            employee.save()

            # 2. Actualizar Datos Institucionales (Expediente)
            inst_data, created = InstitutionalData.objects.get_or_create(employee=employee)

            inst_data.file_number = request.POST.get('file_number')
            inst_data.biometric_id = request.POST.get('biometric_id')
            # Guardar correo institucional como None si viene vacío para evitar conflicto con unique=True
            inst_email = request.POST.get('institutional_email')
            inst_email = inst_email.strip() if inst_email and isinstance(inst_email, str) else inst_email
            inst_data.institutional_email = inst_email if inst_email else None
            inst_data.observations = request.POST.get('observations')
            # Nuevos campos
            collective_contract = request.POST.get('collective_contract')
            inst_data.collective_contract = (
                    collective_contract == 'true' or collective_contract == 'on' or collective_contract == '1')
            entry_date = request.POST.get('entry_date')
            inst_data.entry_date = entry_date if entry_date else None

            inst_data.save()
            log_person_audit(
                request,
                person,
                PersonAuditLog.Action.UPDATE,
                PERSON_AUDIT_SECTIONS['institutional']
            )

            return JsonResponse({'success': True, 'message': 'Datos institucionales actualizados correctamente'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)


@login_required
def get_areas_list_api(request):
    """Retorna todas las unidades administrativas activas para select2"""
    from institution.models import AdministrativeUnit
    areas = AdministrativeUnit.objects.filter(is_active=True).values('id', 'name', 'code')
    return JsonResponse({'success': True, 'data': list(areas)})


@login_required
def get_employment_statuses_api(request):
    """Retorna los estados laborales activos para select2"""
    from core.models import CatalogItem
    statuses = CatalogItem.objects.filter(
        catalog__code='EMPLOYMENT_STATUS',
        is_active=True
    ).values('id', 'name')
    return JsonResponse({'success': True, 'data': list(statuses)})


@login_required
def relocate_employee(request):
    """Recibe un POST con employee_id y area_id, y actualiza el área del empleado."""
    try:
        person_id = request.POST.get('person_id')
        unit_id = request.POST.get('unit_id')
        if not person_id or not unit_id:
            return JsonResponse({'success': False, 'message': 'Faltan parámetros.'}, status=400)
        person = get_object_or_404(Person, pk=person_id)
        employee = getattr(person, 'employee_profile', None)
        if not employee:
            return JsonResponse(
                {'success': False, 'message': 'No se encontró el perfil de empleado para esta persona.'}, status=404)
        employee.area_id = unit_id
        employee.save()
        return JsonResponse({'success': True, 'message': 'Empleado reubicado correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@method_decorator(require_POST, name='dispatch')
class UpdateProfileVisibilityView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'person.change_person'

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            person_id = data.get('user_id')
            tab_id = data.get('tab_id')
            is_visible = data.get('is_visible')

            if not all([person_id, tab_id, isinstance(is_visible, bool)]):
                return JsonResponse({'success': False, 'message': 'Faltan datos o son incorrectos.'}, status=400)

            person = get_object_or_404(Person, pk=person_id)
            user = person.user

            if not user:
                return JsonResponse({'success': False, 'message': 'La persona no tiene un usuario asociado.'},
                                    status=400)

            visibility, created = EmployeeProfileVisibility.objects.get_or_create(
                user=user,
                tab_id=tab_id,
                defaults={'is_visible': is_visible}
            )

            if not created:
                visibility.is_visible = is_visible
                visibility.save()

            return JsonResponse({'success': True, 'message': 'Visibilidad actualizada correctamente.'})
        except Exception as e:
            logger.exception("Error al actualizar visibilidad")
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def get_telework_data_api(request, person_id):
    person = get_object_or_404(Person, pk=person_id)
    employee = person.employee_profile
    today = timezone.now().date()

    # Obtener marcaciones de hoy
    punches = OfflineAttendanceRegistry.objects.filter(
        employee=employee,
        captured_at__date=today
    ).order_by('captured_at')

    # Obtener actividades de hoy
    activities = TeleworkActivity.objects.filter(
        employee=employee,
        created_at__date=today
    ).order_by('-created_at')

    # Lógica de 2 horas (Alerta)
    last_activity = activities.first()
    needs_update = False
    if last_activity:
        diff = timezone.now() - last_activity.created_at
        if diff.total_seconds() > 7200:  # 2 horas
            needs_update = True

    return JsonResponse({
        'success': True,
        'punches': [{
            'type': p.get_punch_type_display(),
            'time': p.captured_at.strftime('%H:%M:%S'),
            'status': p.sync_status
        } for p in punches],
        'activities': [{
            'id': a.id,
            'title': a.title,
            'detail': a.detail,
            'status': a.get_status_display(),
            'percentage': a.percentage,
            'time': a.created_at.strftime('%H:%M')
        } for a in activities],
        'needs_update': needs_update
    })


@require_POST
def add_telework_activity_api(request, person_id):
    person = get_object_or_404(Person, pk=person_id)
    employee = person.employee_profile

    title = request.POST.get('title')
    detail = request.POST.get('detail')
    percentage = request.POST.get('percentage', 0)

    activity = TeleworkActivity.objects.create(
        employee=employee,
        title=title,
        detail=detail,
        percentage=percentage,
        status='COMPLETED' if int(percentage) == 100 else 'IN_PROGRESS'
    )

    return JsonResponse({'success': True, 'message': 'Actividad registrada'})


@require_POST
def mark_telework_attendance_api(request, person_id):
    person = get_object_or_404(Person, pk=person_id)
    employee = person.employee_profile
    punch_type = request.POST.get('punch_type')  # INCOME o EXIT

    # En teletrabajo web, si no hay GPS real, usamos 0,0 o coordenadas de oficina
    OfflineAttendanceRegistry.objects.create(
        employee=employee,
        punch_type=punch_type,
        captured_at=timezone.now(),
        latitude=0,
        longitude=0,
        source='WEB',
        sync_status='SYNCED'
    )
    return JsonResponse({'success': True, 'message': f'Marcación de {punch_type} exitosa'})
