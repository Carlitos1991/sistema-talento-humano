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


@login_required
def search_employee_by_cedula(request):
    cedula = request.GET.get('q', '').strip()

    if not cedula:
        return JsonResponse({'success': False, 'message': 'Cédula no proporcionada.'})

    try:
        # Buscamos el Empleado a través de su relación con Persona
        # Nota: El campo en tu modelo Person es 'document_number'
        emp = Employee.objects.select_related('person').get(
            person__document_number=cedula,
            is_active=True
        )

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
        return JsonResponse({
            'success': False,
            'message': 'No se encontró un registro de Empleado con esa cédula. Asegúrese de que la Persona esté registrada y tenga un perfil de Empleado activo.'
        })


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

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
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

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
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
        data = {'id': item.id, 'education_level': item.education_level_id, 'title_obtained': item.title_obtained,
                'educational_institution': item.educational_institution, 'graduation_year': item.graduation_year}
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
        current_budget = employee.current_budget_line.first() # Reverse relation
        regime_name = current_budget.regime_item.name if (current_budget and current_budget.regime_item) else 'Sin definir'
        position_name = current_budget.position_item.name if (current_budget and current_budget.position_item) else 'Sin definir'

        data = {
            'area': employee.area.id if employee.area else None,
            'area_name': employee.area.name if employee.area else 'Sin Asignar',
            'employment_status': employee.employment_status.id if employee.employment_status else None,
            'employment_status_name': employee.employment_status.name if employee.employment_status else 'Sin Definir',
            'regime_name': regime_name,
            'position': position_name,
            
            # Campos Editables de InstitutionalData
            'file_number': inst_data.file_number or '',
            'biometric_id': inst_data.biometric_id or '',
            'institutional_email': inst_data.institutional_email or '',
            'observations': inst_data.observations or ''
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
            inst_data.institutional_email = request.POST.get('institutional_email')
            inst_data.observations = request.POST.get('observations')
            
            inst_data.save()
            
            return JsonResponse({'success': True, 'message': 'Datos institucionales actualizados correctamente'})
        except Exception as e:
             return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)


@login_required
def get_areas_list_api(request):
    """Retorna todas las unidades administrativas activas para select2"""
    from apps.institution.models import AdministrativeUnit
    areas = AdministrativeUnit.objects.filter(is_active=True).values('id', 'name', 'code')
    return JsonResponse({'success': True, 'data': list(areas)})


@login_required
def get_employment_statuses_api(request):
    """Retorna los estados laborales activos para select2"""
    from apps.core.models import CatalogItem
    statuses = CatalogItem.objects.filter(
        catalog__code='EMPLOYMENT_STATUS', 
        is_active=True
    ).values('id', 'name')
    return JsonResponse({'success': True, 'data': list(statuses)})
