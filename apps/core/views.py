from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView
from django.views.generic import TemplateView, ListView, UpdateView
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .forms import CatalogForm, CatalogItemForm, LocationForm, SystemLetterheadForm, \
    SystemConfigurationSetupForm
from .forms import UserProfileForm
from .models import Catalog, CatalogItem, Location, SystemConfiguration
from .models import User
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.views.generic import View
from django.contrib.auth.decorators import permission_required
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)


def _safe_related(instance, attr_name, default=None):
    """Acceso seguro a relaciones opcionales para evitar 500 por registros faltantes."""
    if instance is None:
        return default
    try:
        return getattr(instance, attr_name)
    except ObjectDoesNotExist:
        return default
    except Exception:
        return default


# --- 1. LOGIN & AUTH ---
class CustomLoginView(LoginView):
    template_name = 'core/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        # Si el usuario nunca se había logueado antes (last_login is None), marcar en sesión
        try:
            user_obj = form.get_user()
            if getattr(user_obj, 'last_login', None) is None:
                self.request.session['force_change_on_login'] = True
        except Exception:
            pass

        response = super().form_valid(form)

        # --- Aprovisionamiento hacia Keycloak (perezoso, no bloqueante) ---
        # El usuario local YA existe (así fue que se autenticó, vía
        # ModelBackend como respaldo -> ver AUTHENTICATION_BACKENDS). Este
        # bloque migra la cuenta a Keycloak usando el MISMO username y la
        # MISMA contraseña que el usuario acaba de escribir en el form, para
        # que su PRÓXIMO login ya sea validado directamente por
        # KeycloakPasswordBackend (ROPC) sin que el usuario note nada.
        #
        # Es clave usar la contraseña en texto plano de ESTE request: Django
        # solo guarda el hash local, así que esta es la única oportunidad de
        # conocerla y reutilizarla en Keycloak.
        try:
            person = _safe_related(self.request.user, 'person', None)
            if person is not None:
                plain_password = form.cleaned_data.get('password')
                from .keycloak_service import ensure_keycloak_account
                result = ensure_keycloak_account(person, self.request.user, plain_password)
                if result.get('status') == 'created':
                    logger.info(
                        "[KEYCLOAK][PROVISION] Usuario %s migrado a Keycloak con su mismo username/contraseña.",
                        self.request.user.username,
                    )
        except Exception:
            logger.exception(
                "[KEYCLOAK][PROVISION] Fallo inesperado aprovisionando a %s en Keycloak.",
                getattr(self.request.user, 'username', '?'),
            )

        current_session_key = self.request.session.session_key
        user_id = str(self.request.user.id)

        # Mantiene la sesión actual y elimina cualquier otra sesión activa del mismo usuario.
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
        sessions_to_delete = []

        for session in active_sessions:
            data = session.get_decoded()
            if data.get('_auth_user_id') == user_id and session.session_key != current_session_key:
                sessions_to_delete.append(session.session_key)

        if sessions_to_delete:
            Session.objects.filter(session_key__in=sessions_to_delete).delete()

        return response

    def get_success_url(self):
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url
        return reverse_lazy('core:dashboard')

    def form_invalid(self, form):
        messages.error(self.request, "Credenciales incorrectas. Intente nuevamente.")
        return super().form_invalid(form)


class CustomLogoutView(auth_views.LogoutView):
    def get_next_page(self):
        next_url = self.request.POST.get(self.redirect_field_name) or self.request.GET.get(self.redirect_field_name)
        if next_url:
            return f"{reverse('core:login')}?{urlencode({self.redirect_field_name: next_url})}"
        return reverse_lazy('core:login')


class ForgotPasswordView(TemplateView):
    template_name = 'core/forgot_password.html'

    def post(self, request, *args, **kwargs):
        from django.contrib.auth import get_user_model
        from django.db.models import Q
        from django.urls import reverse  # Importación necesaria para construir la URL

        identificador = (request.POST.get('identificador') or '').strip()
        birth_date_raw = (request.POST.get('birth_date') or '').strip()

        if not identificador or not birth_date_raw:
            return JsonResponse(
                {'status': 'error', 'message': 'Debe ingresar su usuario o correo y la fecha de nacimiento.'})

        User = get_user_model()

        # 1. Buscar en la BD local si existe el usuario o correo
        user = User.objects.filter(Q(username=identificador) | Q(email=identificador)).first()

        if not user or not hasattr(user, 'person'):
            return JsonResponse(
                {'status': 'error', 'message': 'No se encontró un registro asociado a este usuario o correo.'})

        person = user.person

        # 2. Validar la fecha de nacimiento como factor de seguridad
        if not person.birth_date or str(person.birth_date) != birth_date_raw:
            return JsonResponse(
                {'status': 'error', 'message': 'La fecha de nacimiento no coincide con nuestros registros.'})

        from .keycloak_service import find_keycloak_user_by_username, send_keycloak_reset_password_email

        # 3. Verificar existencia en Keycloak usando el USERNAME exacto
        try:
            kc_user = find_keycloak_user_by_username(user.username)
        except Exception as e:
            logger.exception("[KEYCLOAK][RESET] Error conectando a Keycloak al buscar %s", user.username)
            return JsonResponse(
                {'status': 'error', 'message': 'Error de conexión con el servidor de identidades. Intente más tarde.'})

        if not kc_user:
            return JsonResponse({
                'status': 'error',
                'message': 'Su cuenta no ha sido migrada a Keycloak. Contacte a Talento Humano.'
            })

        # Construir la URL absoluta a la que volverá el usuario tras cambiar la clave
        redirect_to = request.build_absolute_uri(reverse('core:login'))

        # 4. Ordenar a Keycloak que envíe el correo con el enlace de recuperación y contexto de redirección
        try:
            send_keycloak_reset_password_email(kc_user['id'], redirect_to)
        except Exception as e:
            logger.exception("[KEYCLOAK][RESET] Error solicitando correo a Keycloak para %s", user.username)
            return JsonResponse(
                {'status': 'error', 'message': 'Keycloak no pudo procesar el envío del correo. Intente más tarde.'})

        # 5. Enmascarar correo para el mensaje de éxito
        institutional_email = kc_user.get('email')
        if not institutional_email:
            return JsonResponse({'status': 'error',
                                 'message': 'El usuario en Keycloak no tiene un correo configurado para recibir el enlace.'})

        masked_email = institutional_email
        if '@' in institutional_email:
            parts = institutional_email.split('@')
            name_part = parts[0]
            masked_name = f"{name_part[:2]}{'*' * (len(name_part) - 4)}{name_part[-2:]}" if len(
                name_part) > 4 else name_part
            masked_email = f"{masked_name}@{parts[1]}"

        return JsonResponse({
            'status': 'success',
            'message': f'Se ha enviado un enlace seguro de recuperación al correo {masked_email}'
        })


class ChangePasswordView(LoginRequiredMixin, View):
    """
    "Cambiar Contraseña" para un usuario YA autenticado en el sistema
    (ver navbar.html -> openChangePasswordModal()).

    A diferencia de ForgotPasswordView (que es para alguien SIN sesión que
    olvidó su clave), aquí el usuario confirma su contraseña ACTUAL y
    Keycloak la valida antes de permitir el cambio. La contraseña nueva
    también se guarda únicamente en Keycloak; localmente el password sigue
    quedando "unusable".
    """

    def post(self, request, *args, **kwargs):
        current_password = request.POST.get('current_password') or ''
        new_password = request.POST.get('new_password') or ''
        confirm_password = request.POST.get('confirm_password') or ''

        if not current_password or not new_password or not confirm_password:
            return JsonResponse({'status': 'error', 'message': 'Debe completar todos los campos.'})

        if new_password != confirm_password:
            return JsonResponse({'status': 'error', 'message': 'La nueva contraseña y su confirmación no coinciden.'})

        if new_password == current_password:
            return JsonResponse(
                {'status': 'error', 'message': 'La nueva contraseña debe ser distinta a la actual.'})

        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_password(new_password, user=request.user)
        except DjangoValidationError as e:
            return JsonResponse({'status': 'error', 'message': ' '.join(e.messages)})

        person = _safe_related(request.user, 'person', None)
        document_number = getattr(person, 'document_number', None)
        if not document_number:
            return JsonResponse({
                'status': 'error',
                'message': 'Su usuario no está vinculado a una persona con cédula registrada.'
            })

        from .keycloak_service import change_password_by_document
        result = change_password_by_document(
            document_number=document_number,
            current_password=current_password,
            username=request.user.username,
            new_password=new_password,
        )

        if result.get('status') == 'invalid_current_password':
            return JsonResponse({'status': 'error', 'message': 'La contraseña actual no es correcta.'})
        if result.get('status') == 'not_found':
            return JsonResponse({
                'status': 'error',
                'message': 'No existe una cuenta en Keycloak asociada a su usuario. Contacte a Talento Humano.'
            })
        if result.get('status') == 'error':
            return JsonResponse({
                'status': 'error', 'message': 'No se pudo actualizar la contraseña en este momento. Intente más tarde.'
            })

        # Sincronizamos el local: sigue sin password utilizable, Keycloak
        # es la fuente de verdad (se deja explícito por si algún flujo
        # legado hubiera dejado un hash usable).
        request.user.set_unusable_password()
        request.user.save(update_fields=['password'])

        return JsonResponse({'status': 'success', 'message': 'Contraseña actualizada correctamente.'})


class CreateUserFromLoginView(TemplateView):
    template_name = 'core/create_user_from_login.html'

    def post(self, request, *args, **kwargs):
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType
        from person.models import Person
        from core.auth import generate_keycloak_username
        from django.urls import reverse

        cedula = (request.POST.get('cedula') or '').strip()
        if not cedula:
            return JsonResponse({'status': 'error', 'message': 'Debe ingresar la cédula para continuar.'})

        person = Person.objects.filter(
            document_number=cedula
        ).select_related('user', 'employee_profile__institutional_data', 'employee_profile__employment_status').first()

        if not person:
            return JsonResponse({'status': 'error', 'message': 'No se encontró una persona registrada con esa cédula.'})

        employee_profile = getattr(person, 'employee_profile', None)
        if not employee_profile or not employee_profile.is_active:
            return JsonResponse({'status': 'error',
                                 'message': 'Para crear usuario debe estar registrado como empleado o trabajador de la institución.'})

        employment_code = (getattr(getattr(employee_profile, 'employment_status', None), 'code', '') or '').upper()
        if employment_code not in ['EMPLEADO', 'TRABAJADOR']:
            return JsonResponse({'status': 'error',
                                 'message': 'Solo se pueden crear usuarios para registros con estado laboral EMPLEADO o TRABAJADOR.'})

        institutional_data = getattr(employee_profile, 'institutional_data', None)
        institutional_email = getattr(institutional_data, 'institutional_email', None)
        if not institutional_email:
            return JsonResponse(
                {'status': 'error', 'message': 'No existe un correo institucional registrado para esta persona.'})

        # 1. Generamos el username según la regla
        username = generate_keycloak_username(person.first_name, person.last_name)

        user_model = get_user_model()
        user = getattr(person, 'user', None)

        from .keycloak_service import find_keycloak_user_by_username, create_keycloak_user, \
            send_keycloak_reset_password_email

        redirect_to = request.build_absolute_uri(reverse('core:login'))
        kc_user_id = None

        # 2. Validar si existe en Keycloak por USERNAME
        try:
            existing_kc_user = find_keycloak_user_by_username(username)
        except Exception as e:
            logger.exception("[KEYCLOAK][REGISTRO] Error consultando Keycloak para username=%s", username)
            return JsonResponse(
                {'status': 'error', 'message': 'No se pudo verificar la cuenta en Keycloak. Intente más tarde.'})

        if existing_kc_user:
            # 3. SI EXISTE: Tomamos su ID
            kc_user_id = existing_kc_user.get('id')
            logger.info(
                "[KEYCLOAK][REGISTRO] El usuario %s ya existe en Keycloak (id=%s). Se solicitará correo de actualización.",
                username, kc_user_id)
        else:
            # 4. SI NO EXISTE: Lo creamos en Keycloak (Keycloak le asignará clave interna, la reemplazaremos con el link)
            logger.info("[KEYCLOAK][REGISTRO] Creando nuevo usuario %s en Keycloak.", username)
            try:
                # Al no pasar 'password', create_keycloak_user genera una aleatoria interna
                new_kc_user_id, _ = create_keycloak_user(
                    username=username,
                    email=institutional_email,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    document_number=cedula,
                    temporary=True,
                )
                kc_user_id = new_kc_user_id
            except Exception as e:
                logger.exception("[KEYCLOAK][REGISTRO] Error creando usuario en Keycloak para username=%s", username)
                return JsonResponse(
                    {'status': 'error', 'message': 'No se pudo crear la cuenta en el servidor. Intente más tarde.'})

        # 5. Ordenar a Keycloak que envíe el correo de configuración inicial / reseteo
        if kc_user_id:
            try:
                send_keycloak_reset_password_email(kc_user_id, redirect_to)
            except Exception as e:
                logger.exception("[KEYCLOAK][REGISTRO] Error solicitando correo a Keycloak para %s", username)
                return JsonResponse(
                    {'status': 'error',
                     'message': 'La cuenta está lista pero Keycloak no pudo procesar el envío del correo. Intente más tarde.'})

        # 6. Lógica del Usuario Local (Django)
        if user is None:
            if user_model.objects.filter(username=username).exists():
                user = user_model.objects.get(username=username)
            else:
                user = user_model.objects.create_user(
                    username=username,
                    email=institutional_email,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    is_active=True
                )

            # La contraseña local es inutilizable porque Keycloak manda
            user.set_unusable_password()
            user.save()
            person.user = user
            person.save(update_fields=['user', 'updated_at'])

            # Asignación de grupos y permisos locales
            normal_group, _ = Group.objects.get_or_create(name='USUARIO_NORMAL')
            user.groups.add(normal_group)
            ct = ContentType.objects.get_for_model(Group)
            dashboard_perm, _ = Permission.objects.get_or_create(
                codename='dashboard_empleado',
                content_type=ct,
                defaults={'name': 'Acceso dashboard empleado'}
            )
            user.user_permissions.add(dashboard_perm)

        # 7. Enmascarar correo para el mensaje de éxito
        masked_email = institutional_email
        if '@' in institutional_email:
            parts = institutional_email.split('@')
            name_part = parts[0]
            masked_name = f"{name_part[:2]}{'*' * (len(name_part) - 4)}{name_part[-2:]}" if len(
                name_part) > 4 else name_part
            masked_email = f"{masked_name}@{parts[1]}"

        return JsonResponse({
            'status': 'success',
            'message': f'Se ha configurado su cuenta y enviado un enlace seguro de acceso al correo {masked_email}'
        })


# --- 2. DASHBOARD ---
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            has_employee_dashboard = request.user.has_perm('auth.dashboard_empleado')
            has_hr_dashboard = request.user.has_perm('auth.dashboard_talento_humano')
            has_boss_dashboard = request.user.has_perm('auth.dashboard_jefe')

            if has_employee_dashboard and not has_hr_dashboard and not has_boss_dashboard:
                return redirect('employee:self_dashboard')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from employee.models import Employee
        from budget.models import BudgetLine
        from person.models import Person
        from function_manual.models import JobProfile
        from core.models import CatalogItem
        from django.db.models import Count, Q, Avg, Sum
        from datetime import date, timedelta
        from django.utils import timezone

        force_boss_view = self.request.GET.get('view') == 'jefe'
        has_boss_dashboard = self.request.user.has_perm('auth.dashboard_jefe')
        has_hr_dashboard = self.request.user.has_perm('auth.dashboard_talento_humano')
        can_use_boss_view = (
                self.request.user.has_perm('auth.dashboard_jefe') or
                self.request.user.has_perm('auth.dashboard_talento_humano')
        )

        # Lógica mejorada: Si el usuario es admin (tiene ambos permisos), mostrar el de Talento Humano por defecto
        # Solo mostrar dashboard de Jefe si ESPECÍFICAMENTE se solicita o si SOLO tiene ese permiso
        if has_hr_dashboard and has_boss_dashboard:
            # Admin con ambos permisos: mostrar Talento Humano por defecto, a menos que pida jefe
            context['show_boss_dashboard'] = force_boss_view
        elif has_boss_dashboard and not has_hr_dashboard:
            # Solo jefe: mostrar siempre dashboard de jefe
            context['show_boss_dashboard'] = True
        else:
            # Solo admin o solo con un permiso
            context['show_boss_dashboard'] = force_boss_view and can_use_boss_view

        # === ESTADÍSTICAS DE EMPLEADOS (SOLO ACTIVOS) ===
        active_employees = Employee.objects.filter(is_active=True)

        employee_stats = active_employees.values(
            'employment_status__code',
            'employment_status__name'
        ).annotate(total=Count('id'))

        stats_dict = {stat['employment_status__code']: stat['total'] for stat in employee_stats if
                      stat['employment_status__code']}

        context['total_employees'] = active_employees.count()
        context['empleados'] = stats_dict.get('EMPLEADO', 0)
        context['trabajadores'] = stats_dict.get('TRABAJADOR', 0)
        context['contratados'] = stats_dict.get('CONTRATADO', 0)
        context['profesionales'] = stats_dict.get('PROFESIONAL', 0)

        # === ESTADÍSTICAS DE PARTIDAS (SOLO ACTIVAS) ===
        active_budgets = BudgetLine.objects.exclude(status_item__code='INACTIVA')
        budget_stats = active_budgets.values(
            'status_item__code',
            'status_item__name'
        ).annotate(total=Count('id'))

        budget_dict = {stat['status_item__code']: stat['total'] for stat in budget_stats if stat['status_item__code']}

        context['total_partidas'] = active_budgets.count()
        context['partidas_ocupadas'] = budget_dict.get('OCUPADA', 0)
        context['partidas_libres'] = budget_dict.get('LIBRE', 0)
        context['partidas_concurso'] = budget_dict.get('CONCURSO', 0)
        context['partidas_litigio'] = budget_dict.get('LITIGIO', 0)

        # === ESTADÍSTICAS ADICIONALES ===
        # Porcentaje de ocupación
        if context['total_partidas'] > 0:
            context['porcentaje_ocupacion'] = round((context['partidas_ocupadas'] / context['total_partidas']) * 100, 1)
        else:
            context['porcentaje_ocupacion'] = 0

        # Género
        gender_stats = active_employees.values(
            'person__gender__name'
        ).annotate(total=Count('id'))

        context['empleados_masculino'] = 0
        context['empleados_femenino'] = 0

        for stat in gender_stats:
            if stat['person__gender__name']:
                gender_name = stat['person__gender__name'].upper()
                if 'MASCULINO' in gender_name or 'HOMBRE' in gender_name:
                    context['empleados_masculino'] = stat['total']
                elif 'FEMENINO' in gender_name or 'MUJER' in gender_name:
                    context['empleados_femenino'] = stat['total']

        # Empleados con título universitario (sumar TERCER_NIVEL, CUARTO_NIVEL y TECNOLOGO)
        try:
            levels = ['TERCER_NIVEL', 'CUARTO_NIVEL', 'TECNOLOGO']
            # Personas únicas (deduplicadas) que tengan al menos un título en cualquiera de los niveles indicados
            person_ids = Employee.objects.filter(
                is_active=True,
                person__curriculum__academic_titles__education_level__code__in=levels
            ).values_list('person_id', flat=True).distinct()
            context['empleados_con_titulo'] = person_ids.count()

            # Mantener desglose por código por si se necesita mostrar por separado
            context['empleados_cuarto_nivel'] = Employee.objects.filter(
                is_active=True,
                person__curriculum__academic_titles__education_level__code='CUARTO_NIVEL'
            ).values_list('person_id', flat=True).distinct().count()

            context['empleados_tecnologo'] = Employee.objects.filter(
                is_active=True,
                person__curriculum__academic_titles__education_level__code='TECNOLOGO'
            ).values_list('person_id', flat=True).distinct().count()
        except Exception:
            context['empleados_con_titulo'] = 0
            context['empleados_cuarto_nivel'] = 0
            context['empleados_tecnologo'] = 0

        # Empleados con discapacidad
        context['empleados_con_discapacidad'] = active_employees.filter(
            person__has_disability=True
        ).count()

        # Empleados sustitutos
        context['empleados_sustitutos'] = active_employees.filter(
            person__is_substitute=True
        ).count()

        # Próximos jubilados (mayores de 60 años)
        fecha_jubilacion = date.today() - timedelta(days=365 * 60)
        context['proximos_jubilados'] = active_employees.filter(
            person__birth_date__lte=fecha_jubilacion
        ).count()

        # Áreas con más empleados
        top_areas = active_employees.values(
            'area__name'
        ).annotate(
            total=Count('id')
        ).order_by('-total')[:5]

        context['top_areas'] = [
            {'name': area['area__name'] or 'Sin área', 'total': area['total']}
            for area in top_areas
        ]

        # === DATOS PARA GRÁFICOS ===
        context['employee_chart_data'] = {
            'labels': ['Empleados', 'Trabajadores', 'Contratados', 'Profesionales'],
            'values': [
                context['empleados'],
                context['trabajadores'],
                context['contratados'],
                context['profesionales']
            ]
        }

        context['budget_chart_data'] = {
            'labels': ['Libres', 'Ocupadas', 'Litigio', 'Concurso'],
            'values': [
                context['partidas_libres'],
                context['partidas_ocupadas'],
                context['partidas_litigio'],
                context['partidas_concurso']
            ]
        }

        context['gender_chart_data'] = {
            'labels': ['Masculino', 'Femenino'],
            'values': [context['empleados_masculino'], context['empleados_femenino']]
        }

        # === ESTADÍSTICAS DE PERFILES (JobProfile) ===
        try:
            qs_profiles = JobProfile.objects.all()
            context['profiles_total'] = qs_profiles.count()

            # Contar solo aquellos que realmente están legalizados.
            # Requerimos que los tres authority fields existan y además que exista el documento legalizado.
            profiles_legalized = 0
            for p in qs_profiles.only('prepared_by_id', 'reviewed_by_id', 'approved_by_id', 'legalized_document'):
                if p.prepared_by_id and p.reviewed_by_id and p.approved_by_id and p.legalized_document:
                    profiles_legalized += 1

            context['profiles_legalized'] = profiles_legalized
            context['profiles_pending'] = context['profiles_total'] - context['profiles_legalized']
        except Exception:
            context['profiles_total'] = 0
            context['profiles_legalized'] = 0
            context['profiles_pending'] = 0

        # === DASHBOARD DE JEFE ===
        context['boss_unit'] = None
        context['boss_unit_detail_url'] = ''
        context['boss_total_personal'] = 0
        context['boss_pending_permits_count'] = 0
        context['boss_pending_permits'] = []
        context['boss_can_manage_permits'] = self.request.user.has_perm('permitrequest.change_permitrequest')

        try:
            if context['show_boss_dashboard']:
                from institution.models import AdministrativeUnit
                from permitrequest.models import PermitRequest
                from person.models import Person

                user_person = _safe_related(self.request.user, 'person', None)
                employee_profile = _safe_related(user_person, 'employee_profile', None) if user_person else None

                # Fallback 1: buscar persona por cédula (username suele ser la cédula)
                if not employee_profile:
                    person_by_document = Person.objects.filter(
                        document_number=self.request.user.username
                    ).select_related('employee_profile').first()
                    if person_by_document:
                        employee_profile = getattr(person_by_document, 'employee_profile', None)

                # Fallback 2: buscar por email del usuario
                if not employee_profile and self.request.user.email:
                    person_by_email = Person.objects.filter(
                        email__iexact=self.request.user.email
                    ).select_related('employee_profile').first()
                    if person_by_email:
                        employee_profile = getattr(person_by_email, 'employee_profile', None)

                managed_unit = None

                if employee_profile:
                    managed_unit = AdministrativeUnit.objects.filter(
                        boss=employee_profile,
                        is_active=True
                    ).select_related('level').order_by('level__level_order', 'name').first()

                    # Fallback 3: buscar unidad por cédula del jefe asignado
                    if not managed_unit and _safe_related(employee_profile, 'person', None):
                        managed_unit = AdministrativeUnit.objects.filter(
                            boss__person__document_number=employee_profile.person.document_number,
                            is_active=True
                        ).select_related('level').order_by('level__level_order', 'name').first()

                    # Fallback: si no tiene unidad gestionada pero su perfil esta marcado como jefe,
                    # usar su unidad actual para no dejar el dashboard vacio.
                    if not managed_unit and employee_profile.is_boss and employee_profile.area_id:
                        managed_unit = employee_profile.area

                if managed_unit:
                    def collect_unit_tree_ids(root_unit):
                        """Devuelve IDs de la unidad raiz y todas sus dependencias hijas."""
                        collected = [root_unit.id]
                        frontier = [root_unit.id]

                        while frontier:
                            children_ids = list(
                                AdministrativeUnit.objects.filter(
                                    parent_id__in=frontier,
                                    is_active=True
                                ).values_list('id', flat=True)
                            )
                            if not children_ids:
                                break
                            collected.extend(children_ids)
                            frontier = children_ids

                        return collected

                    scoped_unit_ids = collect_unit_tree_ids(managed_unit)

                    unit_employees = Employee.objects.filter(
                        is_active=True,
                        area_id__in=scoped_unit_ids
                    ).select_related('person', 'area')

                    # Filtrar directamente por el área del empleado en la consulta para evitar
                    # discrepancias por instancias en memoria. Además, dejar claro que la
                    # lista de pendientes mostrada en el dashboard del jefe debe incluir
                    # únicamente solicitudes con estado REQUESTED.
                    unit_permits_qs = PermitRequest.objects.select_related(
                        'employee__person', 'permit_type'
                    ).filter(
                        Q(permit_type_id=1) | Q(permit_type__parent_id=1),
                        employee__area_id__in=scoped_unit_ids,
                        employee__is_active=True,
                        status__in=['REQUESTED', 'APPROVED', 'REJECTED']
                    ).order_by('-created_at')

                    pending_permits_count = unit_permits_qs.filter(status='REQUESTED').count()

                    context['boss_unit'] = managed_unit
                    context['boss_unit_detail_url'] = reverse('institution:unit_detail', args=[managed_unit.id])
                    context['boss_total_personal'] = Employee.objects.filter(is_active=True,
                                                                             area_id__in=scoped_unit_ids).count()
                    context['boss_pending_permits_count'] = pending_permits_count
                    # Para la vista principal del dashboard mostramos únicamente los pendientes (REQUESTED)
                    context['boss_pending_permits'] = unit_permits_qs.filter(status='REQUESTED')
        except Exception:
            context['boss_unit'] = None
            context['boss_unit_detail_url'] = ''
            context['boss_total_personal'] = 0
            context['boss_pending_permits_count'] = 0
            context['boss_pending_permits'] = []

        return context


# --- 3. PERFIL DE USUARIO ---
class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'core/profile.html'
    success_url = reverse_lazy('core:profile')

    def get_object(self):
        # Forzamos a que el objeto a editar sea SIEMPRE el usuario logueado
        return self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "¡Tu perfil ha sido actualizado correctamente!")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Error al actualizar. Revisa los campos.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasamos la Person si existe
        if hasattr(self.request.user, 'person'):
            context['person'] = self.request.user.person
        return context


# --- 4. CATÁLOGOS ---
# --- 4.1 LISTA DE CATÁLOGOS ---
def get_catalog_stats_dict():
    """Retorna un diccionario con las estadísticas actuales de Catálogos."""
    return {
        'total': Catalog.objects.count(),
        'active': Catalog.objects.filter(is_active=True).count(),
        'inactive': Catalog.objects.filter(is_active=False).count(),
    }


class CatalogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Catalog
    template_name = 'core/catalogs/catalog_list.html'
    context_object_name = 'catalogs'
    permission_required = 'core.view_catalog'

    # paginate_by = 10

    def get_queryset(self):
        query = self.request.GET.get('q')
        qs = Catalog.objects.all()

        if query:
            qs = qs.filter(name__icontains=query)
        return qs.order_by('-created_at')[:200]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = CatalogForm()
        stats = get_catalog_stats_dict()
        context['stats_total'] = stats['total']
        context['stats_active'] = stats['active']
        context['stats_inactive'] = stats['inactive']
        return context


# --- 4.2 CREAR CATÁLOGOS ---
class CatalogCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Catalog
    form_class = CatalogForm
    template_name = 'core/catalogs/modals/modal_catalog_form.html'  # Solo renderiza el form si es GET
    permission_required = 'core.add_catalog'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            catalog = form.save()
            stats = get_catalog_stats_dict()
            return JsonResponse({
                'success': True,
                'message': 'Catálogo creado correctamente.',
                'data': {'id': catalog.id, 'name': catalog.name, 'new_stats': stats}
                # Para actualizar lista sin recargar
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


# --- 4.3 Vista para OBTENER datos (JSON) ---
def catalog_detail_json(request, pk):
    """Retorna los datos de un catálogo específico para editar"""
    catalog = get_object_or_404(Catalog, pk=pk)
    return JsonResponse({
        'success': True,
        'data': {
            'id': catalog.id,
            'name': catalog.name,
            'code': catalog.code,
            'is_active': catalog.is_active
        }
    })


# --- 4.4 EDITAR CATÁLOGOS ---
class CatalogUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Catalog
    form_class = CatalogForm
    template_name = 'core/catalogs/modals/modal_catalog_form.html'
    permission_required = 'core.change_catalog'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()  # Obtener la instancia a editar
        form = self.get_form()

        if form.is_valid():
            catalog = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Catálogo actualizado correctamente.',
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


# --- 4.5 cambiar estado ---
@require_POST  # Por seguridad, solo permitimos POST
@permission_required('core.change_catalog', raise_exception=True)
def catalog_toggle_status(request, pk):
    """Alterna el estado (Activo/Inactivo) de un catálogo"""
    # Verificamos que el usuario esté logueado (puedes usar decorador login_required también)
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'No autorizado'}, status=403)

    catalog = get_object_or_404(Catalog, pk=pk)

    # Usamos el método de tu modelo BaseModel
    catalog.toggle_status()

    status_label = "activado" if catalog.is_active else "desactivado"
    stats = get_catalog_stats_dict()
    return JsonResponse({
        'success': True,
        'message': f'El catálogo "{catalog.name}" ha sido {status_label} correctamente.',
        'new_stats': stats
    })


# --- 5. ITEMS DE CATÁLOGO  ---
# --- 5.1 CREAR ITEMS ---
class CatalogItemCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = CatalogItem
    form_class = CatalogItemForm
    template_name = 'core/catalogs/modals/modal_item_form.html'  # Solo renderiza el form si es GET
    permission_required = 'core.add_catalogitem'

    def post(self, request, *args, **kwargs):
        catalog_id = request.POST.get('catalog_id')
        if not catalog_id:
            return JsonResponse({'success': False, 'message': 'Falta el ID del catálogo.'}, status=400)
        catalog = get_object_or_404(Catalog, pk=catalog_id)
        form = self.get_form()
        if form.is_valid():
            code = form.cleaned_data.get('code')
            if CatalogItem.objects.filter(catalog=catalog, code=code).exists():
                return JsonResponse({
                    'success': False,
                    'errors': {'code': ['Ya existe un item con este código en este catálogo.']}
                }, status=400)

            try:
                # 3. Guardado con asignación del padre
                item = form.save(commit=False)
                item.catalog = catalog
                item.save()

                return JsonResponse({
                    'success': True,
                    'message': f'Item creado en "{catalog.name}".',
                    'data': {'id': item.id, 'name': item.name}
                })
            except Exception as e:
                return JsonResponse({'success': False, 'message': str(e)}, status=500)
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


def item_list_json(request, catalog_id):
    """Devuelve los items de un catálogo específico"""
    items = CatalogItem.objects.filter(catalog_id=catalog_id).order_by('code')
    data = []
    for item in items:
        data.append({
            'id': item.id,
            'code': item.code,
            'name': item.name,
            'is_active': item.is_active
        })
    return JsonResponse({'success': True, 'data': data})


def item_detail_json(request, pk):
    """Para cargar el formulario de edición de item"""
    item = get_object_or_404(CatalogItem, pk=pk)
    return JsonResponse({
        'success': True,
        'data': {
            'id': item.id,
            'catalog_id': item.catalog_id,
            'name': item.name,
            'code': item.code
        }
    })


# --- 5.2 ACTUALIZAR ITEMS ---
class CatalogItemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = CatalogItem
    form_class = CatalogItemForm
    template_name = 'core/catalogs/modals/modal_item_form.html'
    permission_required = 'security.change_catalogitem'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            item = form.save()
            return JsonResponse({'success': True, 'message': 'Item actualizado correctamente.'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)


# --- 5.3 CAMBIAR ESTADO ITEMS ---
@require_POST
@permission_required('core.change_catalogitem', raise_exception=True)
def item_toggle_status(request, pk):
    """Activar/Inactivar Item"""
    item = get_object_or_404(CatalogItem, pk=pk)
    item.toggle_status()
    return JsonResponse({
        'success': True,
        'message': f'Item "{item.name}" {"activado" if item.is_active else "desactivado"}.',
        'is_active': item.is_active
    })


# --- 6. UBICACIONES ---
def get_location_stats_dict():
    """Retorna un diccionario con las estadísticas actuales de Catálogos."""
    return {
        'country': Location.objects.filter(level=1, is_active=True).count(),
        'province': Location.objects.filter(level=2, is_active=True).count(),
        'city': Location.objects.filter(level=3, is_active=True).count(),
        'parish': Location.objects.filter(level=4, is_active=True).count(),
    }


# --- 6.1 LISTA DE UBICACIONES ---
class LocationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Location
    template_name = 'core/locations/location_list.html'
    context_object_name = 'locations'
    permission_required = 'core.view_location'

    def get_queryset(self):
        level = self.request.GET.get('level')
        parent_id = self.request.GET.get('parent_id')
        query = self.request.GET.get('q')

        qs = Location.objects.all().order_by('name')

        if parent_id:
            qs = qs.filter(parent_id=parent_id)
        elif level and level != 'all':
            qs = qs.filter(level=level)
        else:
            if not query:
                qs = qs.filter(level=1)

        if query:
            qs = qs.filter(name__icontains=query)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = LocationForm()

        # Stats
        base_stats = Location.objects.filter(is_active=True)
        context['stats_country'] = base_stats.filter(level=1).count()
        context['stats_province'] = base_stats.filter(level=2).count()
        context['stats_city'] = base_stats.filter(level=3).count()
        context['stats_parish'] = base_stats.filter(level=4).count()

        # --- LÓGICA DE NIVEL VISUAL (Para iluminar los stats) ---
        parent_id = self.request.GET.get('parent_id')
        level = self.request.GET.get('level')

        current_display_level = '1'  # Por defecto Paises

        if parent_id:
            # Si estamos filtrando por padre, estamos viendo el nivel de sus hijos.
            # Buscamos al padre para saber su nivel + 1
            try:
                parent = Location.objects.get(pk=parent_id)
                current_display_level = str(parent.level + 1)
            except Location.DoesNotExist:
                pass
        elif level and level != 'all':
            current_display_level = str(level)

        context['current_display_level'] = current_display_level

        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return render(request, 'core/locations/partials/partial_location_table.html', context)
        return super().get(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        """
        Sobrescribimos esto para devolver JSON si se solicita,
        usado por los selectores en cascada.
        """
        if self.request.GET.get('format') == 'json' or self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Solo si estamos pidiendo datos para selects (filtrado por padre)
            if self.request.GET.get('parent_id'):
                data = list(self.object_list.values('id', 'name'))
                return JsonResponse(data, safe=False)

        return super().render_to_response(context, **response_kwargs)


class LocationCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'core/locations/modals/modal_location_form.html'
    permission_required = 'core.create_location'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            location = form.save()
            stats = get_location_stats_dict()
            return JsonResponse({
                'success': True,
                'message': 'Ubicación creada correctamente.',
                'data': {'id': location.id, 'name': location.name, 'new_stats': stats}
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


class LocationUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'core/locations/modals/modal_location_form.html'
    permission_required = 'core.change_location'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()  # Obtener la instancia a editar
        form = self.get_form()

        if form.is_valid():
            location = form.save()
            stats = get_location_stats_dict()
            return JsonResponse({
                'success': True,
                'message': 'Ubicación actualizada correctamente.',
                'data': {'id': location.id, 'name': location.name, 'new_stats': stats}
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


def location_detail_json(request, pk):
    """
    Retorna los datos de una ubicación.
    Útil para editar y para calcular el nivel de una nueva ubicación hija.
    """
    location = get_object_or_404(Location, pk=pk)
    return JsonResponse({
        'success': True,
        'data': {
            'id': location.id,
            'name': location.name,
            'level': location.level,
            'parent': location.parent_id,
            'parent_name': location.parent.name if location.parent else None
        }
    })


@require_POST
@permission_required('core.change_location', raise_exception=True)
def location_toggle_status(request, pk):
    """Alterna el estado de una Ubicación"""
    location = get_object_or_404(Location, pk=pk)
    location.toggle_status()

    status_label = "activada" if location.is_active else "desactivada"

    # Recalculamos estadísticas para devolverlas si fuera necesario
    stats = get_location_stats_dict()

    return JsonResponse({
        'success': True,
        'message': f'La ubicación "{location.name}" ha sido {status_label} correctamente.',
        'new_stats': stats
    })


class LocationJsonView(View):
    """Retorna ubicaciones filtradas por padre para los selectores en cascada"""

    def get(self, request):
        parent_id = request.GET.get('parent_id')
        if parent_id:
            locations = Location.objects.filter(parent_id=parent_id, is_active=True).order_by('name')
        else:
            locations = Location.objects.filter(level=1, is_active=True).order_by('name')

        data = [{'id': loc.id, 'name': loc.name} for loc in locations]
        return JsonResponse({
            'success': True,
            'data': data
        })


# === MANEJADORES DE ERRORES PERSONALIZADOS ===
def custom_page_not_found(request, exception=None):
    """Manejador personalizado para error 404"""
    from django.shortcuts import render
    return render(request, '404.html', status=404)


# --- CAMBIO DE CONTRASEÑA ---
class ChangePasswordView(LoginRequiredMixin, View):
    """Vista para cambiar la contraseña del usuario"""

    def post(self, request):
        """Procesa el cambio de contraseña"""
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Petición inválida'}, status=400)

        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        # Validaciones
        if not new_password or not confirm_password:
            return JsonResponse({
                'success': False,
                'message': 'Los campos de contraseña no pueden estar vacíos.'
            })

        if new_password != confirm_password:
            return JsonResponse({
                'success': False,
                'message': 'Las contraseñas no coinciden.'
            })

        if len(new_password) < 8:
            return JsonResponse({
                'success': False,
                'message': 'La contraseña debe tener al menos 8 caracteres.'
            })

        # Verificar requisitos de contraseña
        import re
        if not re.search(r'[a-z]', new_password):
            return JsonResponse({
                'success': False,
                'message': 'La contraseña debe contener al menos una minúscula.'
            })

        if not re.search(r'[0-9]', new_password):
            return JsonResponse({
                'success': False,
                'message': 'La contraseña debe contener al menos un número.'
            })

        # Actualizar contraseña
        try:
            user = request.user
            user.set_password(new_password)
            user.save()
            # Limpiar marca en sesión si existe (para el flujo basado en first-login)
            try:
                if 'force_change_on_login' in request.session:
                    del request.session['force_change_on_login']
            except Exception:
                pass

            return JsonResponse({
                'success': True,
                'message': 'Tu contraseña ha sido cambiada exitosamente.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Ocurrió un error: {str(e)}'
            })


class SystemLetterheadView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.view_systemconfiguration'
    template_name = 'core/system_letterhead.html'

    def get_configuration(self):
        return SystemConfiguration.get_current() or SystemConfiguration.objects.order_by('-effective_date').first()

    def get(self, request):
        configuration = self.get_configuration()
        form = SystemLetterheadForm(instance=configuration)
        config_form = SystemConfigurationSetupForm(instance=configuration)
        return render(request, self.template_name, {
            'form': form,
            'config_form': config_form,
            'configuration': configuration,
        })

    def post(self, request):
        if not request.user.has_perm('core.change_systemconfiguration'):
            messages.error(request, 'No tiene permisos para modificar la hoja membretada.')
            return redirect('core:system_letterhead')

        configuration = self.get_configuration()
        action_type = request.POST.get('action_type', 'letterhead')

        if action_type == 'setup':
            config_form = SystemConfigurationSetupForm(request.POST, request.FILES, instance=configuration)
            form = SystemLetterheadForm(instance=configuration)

            if config_form.is_valid():
                config = config_form.save(commit=False)
                if configuration is None:
                    config.created_by = request.user
                config.updated_by = request.user
                config.save()
                messages.success(request, 'Configuración general guardada correctamente.')
                return redirect('core:system_letterhead')

            return render(request, self.template_name, {
                'form': form,
                'config_form': config_form,
                'configuration': configuration,
            })

        if configuration is None:
            messages.error(request, 'Debe registrar primero la configuración general del sistema.')
            form = SystemLetterheadForm()
            config_form = SystemConfigurationSetupForm(request.POST, request.FILES)
            return render(request, self.template_name, {
                'form': form,
                'config_form': config_form,
                'configuration': configuration,
            })

        form = SystemLetterheadForm(request.POST, request.FILES, instance=configuration)
        if form.is_valid():
            config = form.save(commit=False)
            config.updated_by = request.user
            config.save()
            messages.success(request, 'Hoja membretada actualizada correctamente.')
            return redirect('core:system_letterhead')

        config_form = SystemConfigurationSetupForm(instance=configuration)
        return render(request, self.template_name, {
            'form': form,
            'config_form': config_form,
            'configuration': configuration,
        })


def custom_page_not_found(request, exception=None):
    """Manejador personalizado para error 404"""
    from django.shortcuts import render
    return render(request, '404.html', status=404)


def custom_permission_denied(request, exception=None):
    """Manejador personalizado para error 403"""
    from django.shortcuts import render
    return render(request, '403.html', status=403)


def custom_server_error(request, exception=None):
    """Manejador personalizado para error 500"""
    from django.shortcuts import render
    return render(request, '500.html', status=500)
