from django.views.decorators.csrf import csrf_exempt

# Vista para reubicar empleado (relocate_employee)

# apps/employee/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.views.generic import DetailView

from core.models import CatalogItem, Location
from person.models import Person
from .forms import AcademicTitleForm, WorkExperienceForm, TrainingForm
from .models import Employee, Curriculum, AcademicTitle, WorkExperience, Training, InstitutionalData
from budget.models import BudgetLine
from budget.models import BudgetAssignmentHistory
from contract.models import ManagementPeriod
from permitrequest.models import PermitRequest
from personnel_actions.models import PersonnelAction
from payroll.models import Payslip
from sanctions.models import Sanction
from vacation.models import EmployeeVacationBalance
from decimal import Decimal
from django.urls import reverse


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
                    return JsonResponse({'success': False, 'message': f'La persona {emp.person.full_name} ya tiene asignada la partida {existing_assignment.code}.'})
                return JsonResponse({'success': True, 'id': emp.id, 'full_name': emp.person.full_name, 'email': emp.person.email or 'Sin correo registrado', 'photo_url': emp.person.photo.url if emp.person.photo else None})
            else:
                return JsonResponse({'success': False, 'message': 'Se encontró la Persona pero no tiene perfil de Empleado. Cree el perfil de Empleado antes de asignar la partida.'})
        except Person.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'No se encontró un registro de Persona o Empleado con esa cédula.'})


class EmployeeDetailWizardView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Person
    template_name = 'employee/employee_detail_wizard.html'
    context_object_name = 'person'
    permission_required = 'person.view_person'

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
        employee = getattr(self.object, 'employee_profile', None)
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
                        'position_name': current_contract.budget_line.position_item.name if getattr(current_contract, 'budget_line', None) and getattr(current_contract.budget_line, 'position_item', None) else '',
                        'contract_type_name': str(current_contract.contract_type) if current_contract.contract_type else '',
                        'start_date': current_contract.start_date.strftime('%d/%m/%Y') if current_contract.start_date else '',
                        'end_date': current_contract.end_date.strftime('%d/%m/%Y') if current_contract.end_date else '',
                        'administrative_unit': current_contract.administrative_unit.name if current_contract.administrative_unit else '',
                        'status_name': current_contract.status.name if current_contract.status else '',
                        'signed_document_url': current_contract.signed_document.url if getattr(current_contract, 'signed_document', None) else None
                    }
                else:
                    context['current_contract'] = None

                periods = ManagementPeriod.objects.filter(employee=employee).select_related('contract_type', 'status', 'administrative_unit').order_by('-start_date')[:50]
                ch = []
                for per in periods:
                    ch.append({
                        'id': per.id,
                        'document_number': per.document_number,
                        'position_name': per.budget_line.position_item.name if getattr(per, 'budget_line', None) and getattr(per.budget_line, 'position_item', None) else '',
                        'contract_type_name': str(per.contract_type) if per.contract_type else '',
                        'start_date': per.start_date.strftime('%d/%m/%Y') if per.start_date else '',
                        'end_date': per.end_date.strftime('%d/%m/%Y') if per.end_date else '',
                        'administrative_unit': per.administrative_unit.name if per.administrative_unit else '',
                        'status_name': per.status.name if per.status else '',
                        'signed_document_url': per.signed_document.url if getattr(per, 'signed_document', None) else None
                    })
                context['contract_history'] = ch
            else:
                context['current_contract'] = None
                context['contract_history'] = []
        except Exception:
            context['current_contract'] = None
            context['contract_history'] = []

        # Permiso actual y historial de permisos (vacaciones/horas/otros)
        try:
            if employee:
                latest_perm = PermitRequest.objects.filter(employee=employee).order_by('-start_date', '-created_at').first()
                if latest_perm:
                    context['current_permission'] = {
                        'id': latest_perm.id,
                        'permit_type': latest_perm.permit_type.name if latest_perm.permit_type else str(latest_perm.permit_type),
                        'start_date': latest_perm.start_date if latest_perm.start_date else None,
                        'end_date': latest_perm.end_date if latest_perm.end_date else None,
                        'status': dict(PermitRequest.STATUS_CHOICES).get(latest_perm.status, latest_perm.status),
                        'status_code': latest_perm.status,
                        'days': latest_perm.days,
                        'hours': latest_perm.hours,
                        'justification_file_url': latest_perm.justification_file.url if getattr(latest_perm, 'justification_file', None) else None
                    }
                else:
                    context['current_permission'] = None

                perms = PermitRequest.objects.filter(employee=employee).order_by('-start_date')[:50]
                ph = []
                for p in perms:
                    ph.append({
                        'id': p.id,
                        'permit_type': p.permit_type.name if p.permit_type else '',
                        'start_date': p.start_date if p.start_date else None,
                        'end_date': p.end_date if p.end_date else None,
                        'status': dict(PermitRequest.STATUS_CHOICES).get(p.status, p.status),
                        'status_code': p.status,
                        'days': p.days,
                        'hours': p.hours,
                        'justification_file_url': p.justification_file.url if getattr(p, 'justification_file', None) else None
                    })
                context['permissions_history'] = ph
            else:
                context['current_permission'] = None
                context['permissions_history'] = []
        except Exception:
            context['current_permission'] = None
            context['permissions_history'] = []

        # Acciones de personal (historial)
        try:
            if employee:
                actions_qs = PersonnelAction.objects.filter(employee=employee).select_related('action_type').order_by('-date_issue')[:50]
                actions_list = []
                for a in actions_qs:
                    mv = a.movement.first() if hasattr(a, 'movement') else None
                    from_area = mv.previous_unit.name if mv and mv.previous_unit else ''
                    to_area = mv.new_unit.name if mv and mv.new_unit else ''
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
                payslips_qs = Payslip.objects.filter(employee=employee).select_related('period').order_by('-period__year', '-period__id')[:12]
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
                        'print_url': reverse('payroll:payslip_detail', args=[payslip.pk])
                    })
                context['payment_roles_history'] = roles_history
            else:
                context['payment_roles_history'] = []
        except Exception:
            context['payment_roles_history'] = []

        # Historial de sanciones
        try:
            if employee:
                sanctions_qs = Sanction.objects.filter(employee=employee).select_related('sanction_type').order_by('-sanction_date')[:50]
                sh = []
                for s in sanctions_qs:
                    sh.append({
                        'type': s.sanction_type.name if s.sanction_type else '',
                        'description': s.description,
                        'reason': s.legal_basis,
                        'severity': dict(Sanction.SEVERITY_CHOICES).get(s.severity, s.severity) if hasattr(Sanction, 'SEVERITY_CHOICES') else s.severity,
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
                balances_qs = EmployeeVacationBalance.objects.filter(employee=employee).select_related('period').order_by('-created_at')[:50]
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
                last_balance = EmployeeVacationBalance.objects.filter(employee=employee).order_by('-created_at').select_related('period').first()
                if last_balance:
                    total_capacity = Decimal(str(last_balance.total_days or 0)) + Decimal(str(last_balance.additional_days or 0))
                    permits_used = Decimal(str(last_balance.permit_days or 0))
                    vacations_used = Decimal(str(last_balance.vacation_days or 0))
                    # saldo esperado (por seguridad usar balance_days de la BD si existe)
                    saldo_db = Decimal(str(last_balance.balance_days or (total_capacity - (permits_used + vacations_used))))
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
    if request.method == 'POST':
        person = get_object_or_404(Person, pk=person_id)
        economic_data, created = EconomicData.objects.get_or_create(person=person)

        instance = getattr(economic_data, 'payroll_info', None)
        form = PayrollInfoForm(request.POST, instance=instance)

        if form.is_valid():
            payroll = form.save(commit=False)
            payroll.economic_data = economic_data
            payroll.save()
            return JsonResponse({'success': True, 'message': 'Información de nómina actualizada.'})
            # Debug: return posted data and form errors to help client-side troubleshooting
            try:
                posted = dict(request.POST)
            except Exception:
                posted = {}
            import logging
            logger = logging.getLogger(__name__)
            logger.debug('update_payroll_info invalid form errors: %s', form.errors)
            logger.debug('update_payroll_info POST data: %s', posted)
            return JsonResponse({'success': False, 'errors': form.errors, 'posted': posted}, status=400)
    return None


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
    if request.method == 'POST':
        person = get_object_or_404(Person, pk=person_id)
        economic_data, created = EconomicData.objects.get_or_create(person=person)

        instance = getattr(economic_data, 'payroll_info', None)
        form = PayrollInfoForm(request.POST, instance=instance)

        if form.is_valid():
            payroll = form.save(commit=False)
            payroll.economic_data = economic_data
            payroll.save()
            return JsonResponse({'success': True, 'message': 'Información de nómina actualizada.'})

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    return None


@login_required
@require_POST
def upload_cv_api(request, person_id):
    """API para subir la hoja de vida en PDF"""
    try:
        person = get_object_or_404(Person, pk=person_id)
        # Obtenemos o creamos el objeto Curriculum vinculado a la persona
        curriculum, created = Curriculum.objects.get_or_create(person=person)

        pdf_file = request.FILES.get('pdf_file')

        if not pdf_file:
            return JsonResponse({'success': False, 'message': 'No se seleccionó ningún archivo.'}, status=400)

        # Validación Senior: Tipo de archivo y tamaño (ej: 5MB)
        if not pdf_file.name.lower().endswith('.pdf'):
            return JsonResponse({'success': False, 'message': 'Solo se permiten archivos PDF.'}, status=400)

        if pdf_file.size > 5 * 1024 * 1024:
            return JsonResponse({'success': False, 'message': 'El archivo es muy pesado (máximo 5MB).'}, status=400)

        # Guardar el archivo
        curriculum.pdf_file = pdf_file
        curriculum.save()

        return JsonResponse({
            'success': True,
            'message': 'Hoja de vida actualizada correctamente.',
            'file_url': curriculum.pdf_file.url
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def curriculum_tab_partial(request, person_id):
    """Retorna únicamente el fragmento HTML de la pestaña de Currículum"""
    person = get_object_or_404(Person, pk=person_id)
    # Reutilizamos el mismo template parcial
    html = render_to_string('employee/partials/wizard/tab_curriculum.html', {'person': person}, request=request)
    return HttpResponse(html)


@transaction.atomic
def add_academic_title_api(request, person_id):
    person = get_object_or_404(Person, pk=person_id)
    curriculum, _ = Curriculum.objects.get_or_create(person=person)
    form = AcademicTitleForm(request.POST)
    if form.is_valid():
        title = form.save(commit=False)
        title.curriculum = curriculum
        title.save()
        return JsonResponse({'success': True, 'message': 'Título registrado correctamente'})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


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
