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
from .forms import AcademicTitleForm, WorkExperienceForm
from .models import Employee, Curriculum
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


from .models import EconomicData, BankAccount
from .forms import BankAccountForm


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


@transaction.atomic
def add_work_experience_api(request, person_id):
    person = get_object_or_404(Person, pk=person_id)
    curriculum, _ = Curriculum.objects.get_or_create(person=person)
    form = WorkExperienceForm(request.POST)
    if form.is_valid():
        exp = form.save(commit=False)
        exp.curriculum = curriculum
        exp.save()
        return JsonResponse({'success': True, 'message': 'Experiencia registrada correctamente'})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)
