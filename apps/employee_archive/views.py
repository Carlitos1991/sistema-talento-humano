from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Prefetch
from django.db.models import CharField
from django.db.models import Q
from django.db.models import Value
from django.http import JsonResponse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView
from django.views.generic import ListView
from django.views.generic import TemplateView
from django.views.generic import UpdateView
from django.db.models.functions import Concat

from contract.models import ManagementPeriod
from core.models import User
from employee.models import Employee
from personnel_actions.models import PersonnelAction

from .forms import ArchiveLoanDeliverForm
from .forms import ArchiveLoanRequestForm
from .forms import ArchiveLoanReturnReportForm
from .forms import ArchiveLoanReturnValidationForm
from .forms import ArchiveManualLoanForm
from .forms import EmployeeArchiveDocumentForm
from .forms import EmployeeArchiveVersionForm
from .forms import EmployeeDocumentTypeForm
from .models import EmployeeArchiveAccessLog
from .models import EmployeeArchiveDocument
from .models import EmployeeArchiveLoan
from .models import EmployeeArchiveLoanLog
from .models import EmployeeArchiveNotification
from .models import EmployeeArchiveScanTask
from .models import EmployeeArchiveVersion
from .models import EmployeeDocumentType
from .models import ensure_predefined_document_types


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _expediente_number(employee):
    institutional_data = getattr(employee, 'institutional_data', None)
    file_number = getattr(institutional_data, 'file_number', None)
    if file_number:
        return file_number
    person_document = getattr(employee.person, 'document_number', None)
    if person_document:
        return person_document
    return str(employee.id)


def _create_notification(recipient, title, message, url=''):
    EmployeeArchiveNotification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        url=url,
    )


def _log_loan_action(loan, action, actor, ip_address, observation=''):
    EmployeeArchiveLoanLog.objects.create(
        loan=loan,
        action=action,
        actor=actor,
        observation=observation or '',
        ip_address=ip_address,
    )


def _log_access(user, employee, action, ip_address, archive_document=None, version=None):
    EmployeeArchiveAccessLog.objects.create(
        user=user,
        employee=employee,
        archive_document=archive_document,
        version=version,
        action=action,
        ip_address=ip_address,
    )


def _archive_staff_users():
    return User.objects.filter(
        Q(is_superuser=True)
        | Q(user_permissions__codename='can_manage_archive_loans', user_permissions__content_type__app_label='employee_archive')
        | Q(groups__permissions__codename='can_manage_archive_loans', groups__permissions__content_type__app_label='employee_archive')
    ).distinct()


def _can_create_manual_archive_loan(user):
    return user.has_perm('employee_archive.can_create_archive_manual_loan') or user.has_perm(
        'employee_archive.change_employeearchivedocument'
    )


def _can_validate_archive_return(user):
    return user.has_perm('employee_archive.can_validate_archive_returns') or user.has_perm(
        'employee_archive.change_employeearchivedocument'
    )


def _ensure_base_archive_documents(employee, actor):
    type_map = ensure_predefined_document_types()
    docs_map = {}
    for code, document_type in type_map.items():
        archive_document, _ = EmployeeArchiveDocument.objects.get_or_create(
            employee=employee,
            document_type=document_type,
            defaults={
                'status': EmployeeArchiveDocument.Status.PENDING,
                'notes': 'Creado automaticamente como tipo base del Archivo Digital.',
                'created_by': actor,
                'updated_by': actor,
            },
        )
        docs_map[code] = archive_document
    return docs_map


def _sync_employee_scan_tasks(employee, actor, docs_map):
    contracts = ManagementPeriod.objects.filter(employee=employee).select_related('contract_type').only(
        'id', 'document_number', 'start_date', 'contract_type__name'
    )
    for contract in contracts:
        task, created = EmployeeArchiveScanTask.objects.get_or_create(
            employee=employee,
            source_type=EmployeeArchiveScanTask.SourceType.CONTRACT,
            source_id=contract.id,
            defaults={
                'document_type': docs_map['CONTRATOS'].document_type,
                'source_reference': contract.document_number,
                'title': f'Contrato: {contract.contract_type.name}',
                'source_date': contract.start_date,
                'created_by': actor,
                'updated_by': actor,
            },
        )
        if not created:
            task_changed = False
            new_reference = contract.document_number
            new_title = f'Contrato: {contract.contract_type.name}'
            if task.document_type_id != docs_map['CONTRATOS'].document_type_id:
                task.document_type = docs_map['CONTRATOS'].document_type
                task_changed = True
            if task.source_reference != new_reference:
                task.source_reference = new_reference
                task_changed = True
            if task.title != new_title:
                task.title = new_title
                task_changed = True
            if task.source_date != contract.start_date:
                task.source_date = contract.start_date
                task_changed = True
            if task_changed:
                task.updated_by = actor
                task.save()

    actions = PersonnelAction.objects.filter(employee=employee).select_related('action_type').only(
        'id', 'number', 'date_issue', 'action_type__name'
    )
    for action in actions:
        task, created = EmployeeArchiveScanTask.objects.get_or_create(
            employee=employee,
            source_type=EmployeeArchiveScanTask.SourceType.PERSONNEL_ACTION,
            source_id=action.id,
            defaults={
                'document_type': docs_map['ACCIONES_PERSONAL'].document_type,
                'source_reference': action.number,
                'title': f'Accion de Personal: {action.action_type.name}',
                'source_date': action.date_issue,
                'created_by': actor,
                'updated_by': actor,
            },
        )
        if not created:
            task_changed = False
            new_title = f'Accion de Personal: {action.action_type.name}'
            if task.document_type_id != docs_map['ACCIONES_PERSONAL'].document_type_id:
                task.document_type = docs_map['ACCIONES_PERSONAL'].document_type
                task_changed = True
            if task.source_reference != action.number:
                task.source_reference = action.number
                task_changed = True
            if task.title != new_title:
                task.title = new_title
                task_changed = True
            if task.source_date != action.date_issue:
                task.source_date = action.date_issue
                task_changed = True
            if task_changed:
                task.updated_by = actor
                task.save()


class EmployeeArchiveListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Employee
    template_name = 'employee_archive/employee_archive_list.html'
    context_object_name = 'employees'
    paginate_by = 15
    permission_required = 'employee_archive.view_employeearchivedocument'

    def get_queryset(self):
        queryset = Employee.objects.select_related('person', 'institutional_data').annotate(
            archive_search_name=Concat(
                'person__first_name',
                Value(' '),
                'person__last_name',
                output_field=CharField(),
            )
        )
        query = self.request.GET.get('q')
        if query:
            for term in [part for part in query.split() if part]:
                queryset = queryset.filter(
                    Q(archive_search_name__icontains=term)
                    | Q(person__document_number__icontains=term)
                    | Q(institutional_data__file_number__icontains=term)
                )

        # Filtrar solo expedientes prestados si se solicita
        show_loaned = self.request.GET.get('show_loaned', 'false')
        if show_loaned.lower() == 'true':
            # Mostrar solo empleados que tienen un préstamo activo (ON_LOAN)
            queryset = queryset.filter(
                archive_loans__status=EmployeeArchiveLoan.Status.ON_LOAN,
                archive_loans__is_active=True
            ).distinct()

        sort_field = self.request.GET.get('sort_field', 'employee')
        sort_dir = self.request.GET.get('sort_dir', 'asc')
        allowed_sorts = {
            'employee': ['person__last_name', 'person__first_name'],
            'document': ['person__document_number'],
            'expediente': ['institutional_data__file_number', 'person__document_number'],
        }
        sort_fields = allowed_sorts.get(sort_field, allowed_sorts['employee'])
        if sort_dir == 'desc':
            sort_fields = [f'-{field}' for field in sort_fields]

        return queryset.order_by(*sort_fields)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employees_page = list(context.get('employees', []))
        employee_ids = [row.id for row in employees_page]

        # Contar total de expedientes prestados (ON_LOAN)
        total_loaned = EmployeeArchiveLoan.objects.filter(
            status=EmployeeArchiveLoan.Status.ON_LOAN,
            is_active=True
        ).count()
        context['total_loaned_count'] = total_loaned

        holder_by_employee = {}
        request_state_by_employee = {}
        deliver_loan_by_employee = {}
        validate_loan_by_employee = {}
        if employee_ids:
            active_loans = EmployeeArchiveLoan.objects.filter(
                employee_id__in=employee_ids,
                status__in=[
                    EmployeeArchiveLoan.Status.REQUESTED,
                    EmployeeArchiveLoan.Status.ON_LOAN,
                    EmployeeArchiveLoan.Status.RETURN_REPORTED,
                ],
                is_active=True,
            ).select_related('borrower_user').order_by('employee_id', '-requested_at')

            for loan in active_loans:
                if loan.employee_id not in request_state_by_employee:
                    if loan.status == EmployeeArchiveLoan.Status.REQUESTED:
                        request_state_by_employee[loan.employee_id] = {
                            'label': 'Solicitado',
                            'at': loan.requested_at,
                        }
                        deliver_loan_by_employee[loan.employee_id] = loan.id
                    elif loan.status == EmployeeArchiveLoan.Status.RETURN_REPORTED:
                        request_state_by_employee[loan.employee_id] = {
                            'label': 'Pendiente validacion',
                            'at': loan.return_reported_at or loan.delivered_at or loan.requested_at,
                        }
                        validate_loan_by_employee[loan.employee_id] = loan.id
                    else:
                        request_state_by_employee[loan.employee_id] = {
                            'label': 'Entregado',
                            'at': loan.delivered_at or loan.requested_at,
                        }
                        validate_loan_by_employee[loan.employee_id] = loan.id

                if loan.status in [EmployeeArchiveLoan.Status.ON_LOAN, EmployeeArchiveLoan.Status.RETURN_REPORTED] and loan.employee_id not in holder_by_employee:
                    full_name = f'{loan.borrower_user.first_name or ""} {loan.borrower_user.last_name or ""}'.strip()
                    holder_by_employee[loan.employee_id] = full_name or loan.borrower_user.username

        for row in employees_page:
            row.physical_holder_full_name = holder_by_employee.get(row.id, '')
            request_state = request_state_by_employee.get(row.id)
            row.request_status_label = request_state['label'] if request_state else 'Sin solicitar'
            row.request_requested_at = request_state['at'] if request_state else None
            row.deliver_loan_id = deliver_loan_by_employee.get(row.id)
            row.validate_loan_id = validate_loan_by_employee.get(row.id)

        context['manual_loan_form'] = ArchiveManualLoanForm()
        return context


class EmployeeArchiveDetailView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'employee_archive/employee_archive_detail.html'
    permission_required = 'employee_archive.view_employeearchivedocument'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(
            Employee.objects.select_related('person', 'area', 'institutional_data'),
            pk=self.kwargs['employee_id']
        )

        docs_map = _ensure_base_archive_documents(employee, self.request.user)
        _sync_employee_scan_tasks(employee, self.request.user, docs_map)

        # Garantiza que todos los tipos documentales activos tengan su contenedor en el empleado,
        # permitiendo crear tabs incluso si aun no tienen archivos cargados.
        active_types = EmployeeDocumentType.objects.filter(is_active=True).order_by('name')
        for document_type in active_types:
            EmployeeArchiveDocument.objects.get_or_create(
                employee=employee,
                document_type=document_type,
                defaults={
                    'status': EmployeeArchiveDocument.Status.PENDING,
                    'notes': 'Creado automaticamente para habilitar el tab del tipo documental.',
                    'created_by': self.request.user,
                    'updated_by': self.request.user,
                },
            )

        archive_documents = EmployeeArchiveDocument.objects.filter(
            employee=employee,
            is_active=True,
            document_type__is_active=True,
        ).select_related('document_type').prefetch_related(
            Prefetch('versions', queryset=EmployeeArchiveVersion.objects.order_by('-version_number', '-created_at'))
        ).order_by('document_type__name')

        scan_tasks = EmployeeArchiveScanTask.objects.filter(employee=employee, is_active=True).select_related(
            'document_type', 'scanned_by', 'version'
        ).order_by('-source_date', '-created_at')
        contract_scan_tasks = scan_tasks.filter(source_type=EmployeeArchiveScanTask.SourceType.CONTRACT)
        action_scan_tasks = scan_tasks.filter(source_type=EmployeeArchiveScanTask.SourceType.PERSONNEL_ACTION)

        current_loan = EmployeeArchiveLoan.objects.filter(
            employee=employee,
            status__in=[EmployeeArchiveLoan.Status.REQUESTED, EmployeeArchiveLoan.Status.ON_LOAN, EmployeeArchiveLoan.Status.RETURN_REPORTED]
        ).select_related('borrower_user', 'requested_by', 'delivered_by').first()

        loan_history = EmployeeArchiveLoan.objects.filter(employee=employee).select_related(
            'borrower_user', 'requested_by', 'delivered_by'
        )[:10]

        access_logs = list(EmployeeArchiveAccessLog.objects.filter(employee=employee).select_related(
            'user', 'archive_document__document_type', 'version'
        )[:30])

        expediente_reference = _expediente_number(employee)
        for log in access_logs:
            document_type = getattr(getattr(log.archive_document, 'document_type', None), 'name', None)
            log.document_type_label = document_type or 'General'

            reference_parts = [f'Exp. {expediente_reference}']
            if document_type:
                reference_parts.append(document_type)
            if log.version_id:
                reference_parts.append(f'v{log.version.version_number}')
                file_name = (log.version.file.name.rsplit('/', 1)[-1] if log.version and log.version.file else '')
                if file_name:
                    reference_parts.append(file_name)
            log.reference_label = ' · '.join(reference_parts)

        _log_access(
            user=self.request.user,
            employee=employee,
            action=EmployeeArchiveAccessLog.Action.VIEW_EMPLOYEE_ARCHIVE,
            ip_address=_client_ip(self.request),
        )

        context['employee'] = employee
        context['expediente_number'] = _expediente_number(employee)
        context['archive_documents'] = archive_documents
        context['document_form'] = EmployeeArchiveDocumentForm()
        context['version_form'] = EmployeeArchiveVersionForm()
        context['loan_request_form'] = ArchiveLoanRequestForm()
        context['manual_loan_form'] = ArchiveManualLoanForm()
        context['loan_deliver_form'] = ArchiveLoanDeliverForm()
        context['loan_return_form'] = ArchiveLoanReturnReportForm()
        context['loan_validate_form'] = ArchiveLoanReturnValidationForm()
        context['active_loan'] = current_loan
        context['loan_history'] = loan_history
        context['access_logs'] = access_logs
        context['type_choices'] = EmployeeDocumentType.objects.filter(is_active=True).order_by('name')
        context['scan_tasks'] = scan_tasks
        context['contract_scan_tasks'] = contract_scan_tasks
        context['action_scan_tasks'] = action_scan_tasks
        return context


class EmployeeArchiveDocumentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = EmployeeArchiveDocument
    form_class = EmployeeArchiveDocumentForm
    permission_required = 'employee_archive.add_employeearchivedocument'

    def dispatch(self, request, *args, **kwargs):
        self.employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.employee = self.employee
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user

        exists = EmployeeArchiveDocument.objects.filter(
            employee=self.employee,
            document_type=form.instance.document_type,
            is_active=True
        ).exists()
        if exists:
            form.add_error('document_type', 'Este tipo ya existe para el empleado.')
            return self.form_invalid(form)

        self.object = form.save()
        messages.success(self.request, 'Documento de archivo creado correctamente.')
        return redirect('employee_archive:employee_detail', employee_id=self.employee.id)

    def form_invalid(self, form):
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(self.request, error)
        return redirect('employee_archive:employee_detail', employee_id=self.employee.id)


@permission_required('employee_archive.add_employeearchiveversion', raise_exception=True)
@require_POST
def upload_archive_version(request, archive_id):
    archive = get_object_or_404(EmployeeArchiveDocument, pk=archive_id, is_active=True)
    version_instance = EmployeeArchiveVersion(
        archive=archive,
        uploaded_by=request.user,
        created_by=request.user,
        updated_by=request.user,
    )
    form = EmployeeArchiveVersionForm(request.POST, request.FILES, instance=version_instance)

    if not form.is_valid():
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
        return HttpResponseRedirect(reverse('employee_archive:employee_detail', kwargs={'employee_id': archive.employee_id}))

    last_version = archive.versions.order_by('-version_number').first()
    next_version = (last_version.version_number + 1) if last_version else 1

    version = form.save(commit=False)
    version.version_number = next_version
    version.save()

    _log_access(
        user=request.user,
        employee=archive.employee,
        archive_document=archive,
        version=version,
        action=EmployeeArchiveAccessLog.Action.UPLOAD_PDF,
        ip_address=_client_ip(request),
    )

    messages.success(request, 'Nueva version cargada correctamente.')
    return HttpResponseRedirect(reverse('employee_archive:employee_detail', kwargs={'employee_id': archive.employee_id}))


@permission_required('employee_archive.add_employeearchiveversion', raise_exception=True)
@require_POST
def upload_scan_task_version(request, task_id):
    task = get_object_or_404(
        EmployeeArchiveScanTask.objects.select_related('employee', 'document_type'),
        pk=task_id,
        is_active=True,
    )
    archive_document, _ = EmployeeArchiveDocument.objects.get_or_create(
        employee=task.employee,
        document_type=task.document_type,
        defaults={
            'status': EmployeeArchiveDocument.Status.PENDING,
            'notes': 'Creado automaticamente desde tarea de digitalizacion.',
            'created_by': request.user,
            'updated_by': request.user,
        },
    )

    version_instance = EmployeeArchiveVersion(
        archive=archive_document,
        uploaded_by=request.user,
        created_by=request.user,
        updated_by=request.user,
    )
    form = EmployeeArchiveVersionForm(request.POST, request.FILES, instance=version_instance)
    if not form.is_valid():
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
        return HttpResponseRedirect(reverse('employee_archive:employee_detail', kwargs={'employee_id': task.employee_id}))

    last_version = archive_document.versions.order_by('-version_number').first()
    next_version = (last_version.version_number + 1) if last_version else 1

    version = form.save(commit=False)
    version.version_number = next_version
    version.save()

    task.is_scanned = True
    task.scanned_at = timezone.now()
    task.scanned_by = request.user
    task.archive_document = archive_document
    task.version = version
    task.updated_by = request.user
    task.save()

    _log_access(
        user=request.user,
        employee=task.employee,
        archive_document=archive_document,
        version=version,
        action=EmployeeArchiveAccessLog.Action.UPLOAD_PDF,
        ip_address=_client_ip(request),
    )

    messages.success(request, 'Documento de la tarea digitalizado correctamente.')
    return HttpResponseRedirect(reverse('employee_archive:employee_detail', kwargs={'employee_id': task.employee_id}))


@login_required
@permission_required('employee_archive.view_employeearchivedocument', raise_exception=True)
def open_archive_version(request, version_id):
    version = get_object_or_404(
        EmployeeArchiveVersion.objects.select_related('archive', 'archive__employee'),
        pk=version_id,
        is_active=True,
    )
    _log_access(
        user=request.user,
        employee=version.archive.employee,
        archive_document=version.archive,
        version=version,
        action=EmployeeArchiveAccessLog.Action.VIEW_PDF,
        ip_address=_client_ip(request),
    )
    return redirect(version.file.url)


@require_POST
@permission_required('employee_archive.view_employeearchivedocument', raise_exception=True)
def request_archive_loan(request, employee_id):
    employee = get_object_or_404(Employee, pk=employee_id)
    list_url = reverse('employee_archive:employee_list')
    form = ArchiveLoanRequestForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect(list_url)

    active_exists = EmployeeArchiveLoan.objects.filter(
        employee=employee,
        status__in=[EmployeeArchiveLoan.Status.REQUESTED, EmployeeArchiveLoan.Status.ON_LOAN, EmployeeArchiveLoan.Status.RETURN_REPORTED]
    ).exists()
    if active_exists:
        messages.error(request, 'Ya existe un prestamo activo para este expediente.')
        return redirect(list_url)

    loan = EmployeeArchiveLoan.objects.create(
        employee=employee,
        expediente_number=_expediente_number(employee),
        borrower_user=request.user,
        requested_by=request.user,
        status=EmployeeArchiveLoan.Status.REQUESTED,
        request_observation=form.cleaned_data.get('request_observation', ''),
        created_by=request.user,
        updated_by=request.user,
    )

    _log_loan_action(loan, 'REQUESTED', request.user, _client_ip(request), loan.request_observation)

    detail_url = reverse('employee_archive:employee_detail', kwargs={'employee_id': employee.id})
    for archive_user in _archive_staff_users():
        _create_notification(
            recipient=archive_user,
            title='Nueva solicitud de expediente fisico',
            message=f'Se solicito el expediente {loan.expediente_number} de {employee.person.full_name}.',
            url=detail_url,
        )

    messages.success(request, 'Solicitud de expediente registrada correctamente.')
    return redirect(list_url)


@require_POST
def create_manual_archive_loan(request, employee_id):
    if not _can_create_manual_archive_loan(request.user):
        messages.error(request, 'No tiene permisos para registrar prestamos manuales.')
        return redirect(reverse('employee_archive:employee_list'))

    employee = get_object_or_404(Employee, pk=employee_id)
    default_redirect_url = reverse('employee_archive:employee_detail', kwargs={'employee_id': employee.id})
    requested_next = request.POST.get('next', '')
    redirect_url = default_redirect_url
    if requested_next and url_has_allowed_host_and_scheme(requested_next, allowed_hosts={request.get_host()}):
        redirect_url = requested_next

    form = ArchiveManualLoanForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect(redirect_url)

    active_exists = EmployeeArchiveLoan.objects.filter(
        employee=employee,
        status__in=[EmployeeArchiveLoan.Status.REQUESTED, EmployeeArchiveLoan.Status.ON_LOAN, EmployeeArchiveLoan.Status.RETURN_REPORTED]
    ).exists()
    if active_exists:
        messages.error(request, 'Ya existe un prestamo activo para este expediente.')
        return redirect(redirect_url)

    loan = EmployeeArchiveLoan.objects.create(
        employee=employee,
        expediente_number=_expediente_number(employee),
        borrower_user=form.cleaned_data['borrower_user'],
        requested_by=request.user,
        delivered_by=request.user,
        status=EmployeeArchiveLoan.Status.ON_LOAN,
        delivered_at=timezone.now(),
        delivery_observation=form.cleaned_data.get('delivery_observation', ''),
        created_by=request.user,
        updated_by=request.user,
    )

    _log_loan_action(loan, 'MANUAL_LOAN', request.user, _client_ip(request), loan.delivery_observation)
    _create_notification(
        recipient=loan.borrower_user,
        title='Expediente fisico en su poder',
        message=f'El expediente {loan.expediente_number} ha sido entregado y consta en su poder hasta su devolucion.',
        url=reverse('employee_archive:employee_detail', kwargs={'employee_id': employee.id}),
    )

    messages.success(request, 'Prestamo manual registrado correctamente.')
    return redirect(redirect_url)


@require_POST
@permission_required('employee_archive.can_manage_archive_loans', raise_exception=True)
def deliver_archive_loan(request, loan_id):
    loan = get_object_or_404(EmployeeArchiveLoan, pk=loan_id, is_active=True)
    loan_list_url = reverse('employee_archive:loan_list')
    form = ArchiveLoanDeliverForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect(loan_list_url)

    if loan.status != EmployeeArchiveLoan.Status.REQUESTED:
        messages.error(request, 'Solo se pueden entregar prestamos en estado solicitado.')
        return redirect(loan_list_url)

    loan.status = EmployeeArchiveLoan.Status.ON_LOAN
    loan.delivered_by = request.user
    loan.delivered_at = timezone.now()
    loan.delivery_observation = form.cleaned_data.get('delivery_observation', '')
    loan.updated_by = request.user
    loan.save()

    _log_loan_action(loan, 'DELIVERED', request.user, _client_ip(request), loan.delivery_observation)
    _create_notification(
        recipient=loan.borrower_user,
        title='Expediente fisico en su poder',
        message=f'El expediente {loan.expediente_number} consta en su poder hasta que registre su devolucion.',
        url=reverse('employee_archive:employee_detail', kwargs={'employee_id': loan.employee_id}),
    )

    messages.success(request, 'Entrega de expediente registrada correctamente.')
    return redirect(loan_list_url)


@require_POST
@login_required
def report_archive_return(request, loan_id):
    loan = get_object_or_404(EmployeeArchiveLoan, pk=loan_id, is_active=True)
    default_redirect_url = reverse('employee_archive:employee_detail', kwargs={'employee_id': loan.employee_id})
    requested_next = request.POST.get('next', '')
    redirect_url = default_redirect_url
    if requested_next and url_has_allowed_host_and_scheme(requested_next, allowed_hosts={request.get_host()}):
        redirect_url = requested_next

    if loan.status != EmployeeArchiveLoan.Status.ON_LOAN:
        messages.error(request, 'El expediente no esta en estado de prestamo activo.')
        return redirect(redirect_url)

    if request.user != loan.borrower_user and not request.user.has_perm('employee_archive.can_manage_archive_loans'):
        messages.error(request, 'No tiene permisos para reportar esta devolucion.')
        return redirect(redirect_url)

    form = ArchiveLoanReturnReportForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect(redirect_url)

    loan.status = EmployeeArchiveLoan.Status.RETURN_REPORTED
    loan.return_reported_at = timezone.now()
    loan.return_observation = form.cleaned_data.get('return_observation', '')
    loan.updated_by = request.user
    loan.save()

    _log_loan_action(loan, 'RETURN_REPORTED', request.user, _client_ip(request), loan.return_observation)

    for archive_user in _archive_staff_users():
        _create_notification(
            recipient=archive_user,
            title='Devolucion reportada pendiente de validacion',
            message=f'Se reporto devolucion del expediente {loan.expediente_number}. Valide la entrega fisica.',
            url=reverse('employee_archive:employee_detail', kwargs={'employee_id': loan.employee_id}),
        )

    messages.success(request, 'Devolucion reportada. Pendiente validacion del responsable de archivo.')
    return redirect(redirect_url)


@require_POST
def validate_archive_return(request, loan_id):
    if not _can_validate_archive_return(request.user):
        messages.error(request, 'No tiene permisos para validar devoluciones.')
        return redirect(reverse('employee_archive:employee_list'))

    loan = get_object_or_404(EmployeeArchiveLoan, pk=loan_id, is_active=True)
    default_redirect_url = reverse('employee_archive:employee_list')
    requested_next = request.POST.get('next', '')
    redirect_url = default_redirect_url
    if requested_next and url_has_allowed_host_and_scheme(requested_next, allowed_hosts={request.get_host()}):
        redirect_url = requested_next

    if loan.status not in [EmployeeArchiveLoan.Status.RETURN_REPORTED, EmployeeArchiveLoan.Status.ON_LOAN]:
        messages.error(request, 'Solo puede validar expedientes en prestamo activo o con devolucion reportada.')
        return redirect(redirect_url)

    form = ArchiveLoanReturnValidationForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect(redirect_url)

    loan.status = EmployeeArchiveLoan.Status.RETURN_VALIDATED
    loan.returned_at = timezone.now()
    loan.validation_observation = form.cleaned_data.get('validation_observation', '')
    loan.updated_by = request.user
    loan.save()

    _log_loan_action(loan, 'RETURN_VALIDATED', request.user, _client_ip(request), loan.validation_observation)
    _create_notification(
        recipient=loan.borrower_user,
        title='Devolucion validada',
        message=f'Se valido la devolucion del expediente {loan.expediente_number}.',
        url=reverse('employee_archive:employee_detail', kwargs={'employee_id': loan.employee_id}),
    )

    messages.success(request, 'Devolucion validada correctamente.')
    return redirect(redirect_url)


class EmployeeArchiveLoanListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = EmployeeArchiveLoan
    template_name = 'employee_archive/loan_list.html'
    context_object_name = 'loans'
    paginate_by = 20
    permission_required = 'employee_archive.view_employeearchiveloan'

    def get_queryset(self):
        queryset = EmployeeArchiveLoan.objects.select_related(
            'employee', 'employee__person', 'borrower_user', 'requested_by', 'delivered_by'
        )
        query = self.request.GET.get('q')
        status = self.request.GET.get('status')
        if query:
            queryset = queryset.filter(
                Q(expediente_number__icontains=query)
                | Q(employee__person__first_name__icontains=query)
                | Q(employee__person__last_name__icontains=query)
                | Q(borrower_user__username__icontains=query)
            )
        if status:
            queryset = queryset.filter(status=status)

        if self.request.user.has_perm('employee_archive.can_manage_archive_loans') or _can_create_manual_archive_loan(
            self.request.user
        ):
            return queryset
        return queryset.filter(Q(borrower_user=self.request.user) | Q(requested_by=self.request.user))


class EmployeeArchiveNotificationListView(LoginRequiredMixin, ListView):
    model = EmployeeArchiveNotification
    template_name = 'employee_archive/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 25

    def get_queryset(self):
        qs = EmployeeArchiveNotification.objects.filter(recipient=self.request.user).order_by('-created_at')
        unread_ids = list(qs.filter(is_read=False).values_list('id', flat=True))
        if unread_ids:
            EmployeeArchiveNotification.objects.filter(id__in=unread_ids).update(is_read=True, read_at=timezone.now())
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pending_return_loans = EmployeeArchiveLoan.objects.filter(
            borrower_user=self.request.user,
            status=EmployeeArchiveLoan.Status.ON_LOAN,
            is_active=True,
        ).select_related('employee', 'employee__person').order_by('-delivered_at', '-requested_at')
        context['pending_return_loans'] = pending_return_loans
        context['pending_return_loans_count'] = pending_return_loans.count()
        return context


@login_required
def user_search_json(request):
    if not _can_create_manual_archive_loan(request.user):
        return JsonResponse({'results': [], 'detail': 'No tiene permisos para buscar usuarios.'}, status=403)

    term = request.GET.get('term', '').strip()
    users = User.objects.filter(is_active=True)
    if term:
        users = users.filter(
            Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(username__icontains=term)
            | Q(email__icontains=term)
        )

    users = users.order_by('first_name', 'last_name', 'username')[:20]
    results = []
    for user in users:
        full_name = f'{user.first_name or ""} {user.last_name or ""}'.strip()
        label = full_name if full_name else user.username
        results.append({'id': str(user.id), 'text': f'{label} ({user.username})'})

    return JsonResponse({'results': results})


class EmployeeDocumentTypeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = EmployeeDocumentType
    template_name = 'employee_archive/document_type_list.html'
    context_object_name = 'types'
    paginate_by = 15
    permission_required = 'employee_archive.view_employeedocumenttype'

    def get_queryset(self):
        queryset = EmployeeDocumentType.objects.all()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(code__icontains=query))
        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = EmployeeDocumentTypeForm()
        return context


class EmployeeDocumentTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = EmployeeDocumentType
    form_class = EmployeeDocumentTypeForm
    permission_required = 'employee_archive.add_employeedocumenttype'
    success_url = reverse_lazy('employee_archive:archive_type_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, 'Tipo documental creado correctamente.')
        return super().form_valid(form)

    def form_invalid(self, form):
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(self.request, error)
        return redirect('employee_archive:archive_type_list')


class EmployeeDocumentTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = EmployeeDocumentType
    form_class = EmployeeDocumentTypeForm
    template_name = 'employee_archive/document_type_form.html'
    permission_required = 'employee_archive.change_employeedocumenttype'
    success_url = reverse_lazy('employee_archive:archive_type_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, 'Tipo documental actualizado correctamente.')
        return super().form_valid(form)

    def form_invalid(self, form):
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(self.request, error)
        return self.render_to_response(self.get_context_data(form=form))
