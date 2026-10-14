import logging
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.views import LoginView
from django.contrib.sessions.models import Session
from django.core.exceptions import ObjectDoesNotExist
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import View, TemplateView, ListView, UpdateView

from .forms import (
    SystemLetterheadForm,
    SystemConfigurationSetupForm, UserProfileForm
)
from .models import Catalog, CatalogItem, Location, SystemConfiguration, User

logger = logging.getLogger(__name__)

LOCAL_PASSWORD_RESET_SALT = 'core.local-password-reset'
LOCAL_PASSWORD_RESET_MAX_AGE = 3600


def _build_local_password_reset_token(user):
    return signing.dumps(
        {'user_id': user.pk, 'password_marker': user.password},
        salt=LOCAL_PASSWORD_RESET_SALT,
    )


def _send_local_password_reset_email(user, email, request):
    token = _build_local_password_reset_token(user)
    reset_url = request.build_absolute_uri(
        reverse('core:local_password_reset', kwargs={'token': token})
    )
    context = {
        'nombre': user.get_full_name() or user.username,
        'reset_url': reset_url,
    }
    html_content = render_to_string('core/emails/local_password_reset.html', context)
    message = EmailMultiAlternatives(
        subject='Recuperación de contraseña - SIGETH',
        body=strip_tags(html_content),
        from_email=None,
        to=[email],
    )
    message.attach_alternative(html_content, 'text/html')
    message.send(fail_silently=False)


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


# =====================================================================
# 1. LOGIN & AUTH
# =====================================================================
class CustomLoginView(LoginView):
    template_name = 'core/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        try:
            user_obj = form.get_user()
            if getattr(user_obj, 'last_login', None) is None:
                self.request.session['force_change_on_login'] = True
        except Exception:
            pass

        response = super().form_valid(form)

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
        from django.db.models import Q
        from person.models import Person
        from core.auth import generate_keycloak_username
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType

        identificador = (request.POST.get('identificador') or '').strip()
        birth_date_raw = (request.POST.get('birth_date') or '').strip()

        if not identificador or not birth_date_raw:
            return JsonResponse(
                {'status': 'error', 'message': 'Debe ingresar su usuario o correo y la fecha de nacimiento.'})

        UserModel = get_user_model()
        user = UserModel.objects.filter(Q(username=identificador) | Q(email=identificador)).first()

        person = getattr(user, 'person', None) if user else None
        if person is None:
            person = Person.objects.filter(
                employee_profile__institutional_data__institutional_email__iexact=identificador
            ).select_related('employee_profile__institutional_data').first()
            user = getattr(person, 'user', None) if person else None

        if person is None:
            return JsonResponse(
                {'status': 'error', 'message': 'No se encontró un registro asociado a este usuario o correo.'})

        if not person.birth_date or str(person.birth_date) != birth_date_raw:
            return JsonResponse(
                {'status': 'error', 'message': 'La fecha de nacimiento no coincide con nuestros registros.'})

        institutional_email = getattr(
            getattr(getattr(person, 'employee_profile', None), 'institutional_data', None),
            'institutional_email', None
        )
        if not institutional_email:
            return JsonResponse(
                {'status': 'error', 'message': 'No existe un correo institucional registrado para esta persona.'})

        if user is None:
            username = generate_keycloak_username(person.first_name, person.last_name)
            if UserModel.objects.filter(username=username).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'No se pudo asociar la cuenta local. Contacte a Talento Humano.'
                })
            user = UserModel.objects.create_user(
                username=username,
                email=institutional_email.lower(),
                first_name=person.first_name,
                last_name=person.last_name,
                is_active=True,
            )
            user.set_unusable_password()
            user.save(update_fields=['password', 'email'])
            person.user = user
            person.save(update_fields=['user'])

            normal_group, _ = Group.objects.get_or_create(name='USUARIO_NORMAL')
            user.groups.add(normal_group)
            content_type = ContentType.objects.get_for_model(Group)
            dashboard_perm, _ = Permission.objects.get_or_create(
                codename='dashboard_empleado',
                content_type=content_type,
                defaults={'name': 'Acceso dashboard empleado'},
            )
            user.user_permissions.add(dashboard_perm)
        elif user.email != institutional_email:
            user.email = institutional_email.lower()
            user.save(update_fields=['email'])

        from .keycloak_service import provision_and_send_password_reset
        redirect_to = request.build_absolute_uri(reverse('core:login'))
        reset_result = provision_and_send_password_reset(person, user, redirect_to)
        if reset_result['status'] != 'ok':
            if reset_result.get('reason') == 'sin email':
                return JsonResponse({'status': 'error',
                                     'message': 'El usuario no tiene un correo configurado para recibir el enlace.'})
            try:
                _send_local_password_reset_email(user, institutional_email.lower(), request)
                logger.warning(
                    "[AUTH][RESET] Keycloak no disponible; se envió recuperación local para user_id=%s",
                    user.pk,
                )
                email = institutional_email.lower()
                masked_email = email
                if '@' in email:
                    parts = email.split('@')
                    name_part = parts[0]
                    masked_name = (
                        f"{name_part[:2]}{'*' * (len(name_part) - 4)}{name_part[-2:]}"
                        if len(name_part) > 4 else name_part
                    )
                    masked_email = f"{masked_name}@{parts[1]}"
                return JsonResponse({
                    'status': 'success',
                    'message': f'Se ha enviado un enlace seguro de recuperación al correo {masked_email}',
                })
            except Exception:
                logger.exception(
                    "[AUTH][RESET] Falló también la recuperación local para user_id=%s", user.pk
                )
                return JsonResponse({
                    'status': 'error',
                    'message': 'No se pudo enviar el correo de recuperación. Intente más tarde.',
                })

        email = reset_result['email']
        masked_email = email
        if '@' in email:
            parts = email.split('@')
            name_part = parts[0]
            masked_name = f"{name_part[:2]}{'*' * (len(name_part) - 4)}{name_part[-2:]}" if len(
                name_part) > 4 else name_part
            masked_email = f"{masked_name}@{parts[1]}"

        return JsonResponse({
            'status': 'success',
            'message': f'Se ha enviado un enlace seguro de recuperación al correo {masked_email}'
        })


class LocalPasswordResetView(View):
    template_name = 'core/local_password_reset.html'

    def _get_user(self, token):
        try:
            payload = signing.loads(
                token,
                salt=LOCAL_PASSWORD_RESET_SALT,
                max_age=LOCAL_PASSWORD_RESET_MAX_AGE,
            )
            user = get_user_model().objects.get(pk=payload['user_id'], is_active=True)
            if payload.get('password_marker') != user.password:
                return None
            return user
        except (signing.BadSignature, signing.SignatureExpired, KeyError,
                get_user_model().DoesNotExist):
            return None

    def get(self, request, token):
        user = self._get_user(token)
        if user is None:
            return render(request, self.template_name, {
                'invalid_token': True,
                'error': 'El enlace no es válido o ya expiró.',
            }, status=400)
        return render(request, self.template_name, {'token': token})

    def post(self, request, token):
        user = self._get_user(token)
        if user is None:
            return render(request, self.template_name, {
                'invalid_token': True,
                'error': 'El enlace no es válido o ya expiró.',
            }, status=400)

        password = request.POST.get('password') or ''
        confirm_password = request.POST.get('confirm_password') or ''
        if password != confirm_password:
            return render(request, self.template_name, {
                'token': token,
                'error': 'Las contraseñas no coinciden.',
            }, status=400)
        try:
            validate_password(password, user)
        except Exception as exc:
            return render(request, self.template_name, {
                'token': token,
                'error': ' '.join(exc.messages),
            }, status=400)

        user.set_password(password)
        user.save(update_fields=['password'])
        return render(request, self.template_name, {'completed': True})


# Servicio o helper que verifica si existe en Keycloak
def check_user_in_keycloak(username):
    try:
        from core.keycloak_service import KeycloakAdminService  # o tu servicio existente
        kc = KeycloakAdminService()
        return kc.get_user_by_username(username) is not None
    except Exception:
        return False


class ChangePasswordView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not new_password or new_password != confirm_password:
            return JsonResponse({'success': False, 'message': 'Las contraseñas no coinciden.'}, status=400)

        if len(new_password) < 8:
            return JsonResponse({'success': False, 'message': 'La contraseña debe tener al menos 8 caracteres.'},
                                status=400)

        try:
            from .keycloak_service import (
                create_keycloak_user,
                find_keycloak_user_by_document,
                find_keycloak_user_by_email,
                find_keycloak_user_by_username,
                set_keycloak_password,
                update_keycloak_user,
            )
            person = _safe_related(user, 'person', None)
            document_number = getattr(person, 'document_number', None)
            institutional_data = _safe_related(
                _safe_related(person, 'employee_profile', None),
                'institutional_data',
                None,
            )
            institutional_email = (
                getattr(institutional_data, 'institutional_email', None)
                or user.email
                or getattr(person, 'email', None)
                or ''
            ).strip().lower()
            if not person or not document_number or not institutional_email:
                return JsonResponse({
                    'success': False,
                    'message': 'No existe información institucional suficiente para sincronizar la cuenta.'
                }, status=400)

            keycloak_user = find_keycloak_user_by_document(document_number)
            if not keycloak_user:
                keycloak_user = find_keycloak_user_by_email(institutional_email)
            if not keycloak_user:
                keycloak_user = find_keycloak_user_by_username(user.username)

            if keycloak_user:
                update_keycloak_user(
                    keycloak_user_id=keycloak_user['id'],
                    username=user.username,
                    email=institutional_email,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    document_number=document_number,
                )
                set_keycloak_password(keycloak_user['id'], new_password, temporary=False)
            else:
                create_keycloak_user(
                    username=user.username,
                    email=institutional_email,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    document_number=document_number,
                    password=new_password,
                    temporary=False,
                )
        except Exception:
            logger.exception("[KEYCLOAK][CAMBIO_PASSWORD] No se pudo crear o actualizar la cuenta.")
            return JsonResponse({
                'success': False,
                'message': 'No se pudo sincronizar la contraseña con Keycloak. Intente más tarde.'
            }, status=502)

        # Keycloak es la fuente de verdad de la contraseña.
        user.set_unusable_password()
        user.save(update_fields=['password'])
        update_session_auth_hash(request, user)

        # 3. Liberar forzado de cambio
        if 'force_change_on_login' in request.session:
            del request.session['force_change_on_login']

        return JsonResponse({
            'success': True,
            'message': 'Contraseña actualizada y sincronizada correctamente.'
        })


class SyncKeycloakPasswordView(LoginRequiredMixin, View):
    """
    Si el usuario ya está en Keycloak, solo confirma y retira el flag
    sin obligarlo a crear una contraseña nueva.
    """

    def post(self, request):
        if 'force_change_on_login' in request.session:
            del request.session['force_change_on_login']
            request.session.modified = True

        messages.success(request, 'Cuenta vinculada exitosamente con el sistema institucional.')
        return redirect('dashboard')


class CreateUserFromLoginView(TemplateView):
    template_name = 'core/create_user_from_login.html'

    def post(self, request, *args, **kwargs):
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType
        from person.models import Person
        from core.auth import generate_keycloak_username

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

        username = generate_keycloak_username(person.first_name, person.last_name)
        user_model = get_user_model()
        user = getattr(person, 'user', None)

        from .keycloak_service import (
            find_keycloak_user_by_document,
            find_keycloak_user_by_email,
            find_keycloak_user_by_username,
            create_keycloak_user,
            update_keycloak_user,
            send_keycloak_reset_password_email,
        )

        redirect_to = request.build_absolute_uri(reverse('core:login'))

        try:
            existing_kc_user = find_keycloak_user_by_document(cedula)
            if not existing_kc_user:
                existing_kc_user = find_keycloak_user_by_email(institutional_email)
            if not existing_kc_user:
                existing_kc_user = find_keycloak_user_by_username(username)
        except Exception:
            logger.exception("[KEYCLOAK][REGISTRO] Error consultando Keycloak para cedula=%s", cedula)
            return JsonResponse(
                {'status': 'error', 'message': 'No se pudo verificar la cuenta en Keycloak. Intente más tarde.'})

        if existing_kc_user:
            kc_user_id = existing_kc_user.get('id')
            logger.info(
                "[KEYCLOAK][REGISTRO] El usuario de %s ya existe en Keycloak (id=%s). Se actualizarán sus datos.",
                cedula,
                kc_user_id)
            try:
                update_keycloak_user(
                    keycloak_user_id=kc_user_id,
                    username=username,
                    email=institutional_email,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    document_number=cedula,
                )
            except Exception:
                logger.exception("[KEYCLOAK][REGISTRO] Error actualizando usuario de Keycloak para cedula=%s",
                                 cedula)
                return JsonResponse({
                    'status': 'error',
                    'message': 'No se pudo actualizar la cuenta en el servidor. Intente más tarde.'
                })
        else:
            logger.info("[KEYCLOAK][REGISTRO] Creando nuevo usuario %s en Keycloak.", username)
            try:
                new_kc_user_id, _ = create_keycloak_user(
                    username=username,
                    email=institutional_email,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    document_number=cedula,
                    temporary=True,
                )
                kc_user_id = new_kc_user_id
            except Exception:
                logger.exception("[KEYCLOAK][REGISTRO] Error creando usuario en Keycloak para username=%s", username)
                return JsonResponse(
                    {'status': 'error', 'message': 'No se pudo crear la cuenta en el servidor. Intente más tarde.'})

        if kc_user_id:
            try:
                send_keycloak_reset_password_email(kc_user_id, redirect_to)
            except Exception:
                logger.exception("[KEYCLOAK][REGISTRO] Error solicitando correo a Keycloak para %s", username)
                return JsonResponse(
                    {'status': 'error',
                     'message': 'La cuenta está lista pero Keycloak no pudo procesar el envío del correo. Intente más tarde.'})

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

            user.set_unusable_password()
            user.save()
            person.user = user
            person.save(update_fields=['user', 'updated_at'])

            normal_group, _ = Group.objects.get_or_create(name='USUARIO_NORMAL')
            user.groups.add(normal_group)
            ct = ContentType.objects.get_for_model(Group)
            dashboard_perm, _ = Permission.objects.get_or_create(
                codename='dashboard_empleado',
                content_type=ct,
                defaults={'name': 'Acceso dashboard empleado'}
            )
            user.user_permissions.add(dashboard_perm)

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


# =====================================================================
# 2. DASHBOARD
# =====================================================================
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        """
        if request.user.is_authenticated:
            has_employee_dashboard = request.user.has_perm('auth.dashboard_empleado')
            has_hr_dashboard = request.user.has_perm('auth.dashboard_talento_humano')
            has_boss_dashboard = request.user.has_perm('auth.dashboard_jefe')

            if has_employee_dashboard and not has_hr_dashboard and not has_boss_dashboard:
                return redirect('employee:self_dashboard')
        """
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from employee.models import Employee
        from budget.models import BudgetLine
        from function_manual.models import JobProfile
        from django.db.models import Count, Q
        from datetime import date, timedelta

        # -------------------------------------------------------------
        # Contexto Institucional (Logo y datos institucionales)
        # -------------------------------------------------------------
        context['system_config'] = SystemConfiguration.get_current()

        force_boss_view = self.request.GET.get('view') == 'jefe'
        has_boss_dashboard = self.request.user.has_perm('auth.dashboard_jefe')
        has_hr_dashboard = self.request.user.has_perm('auth.dashboard_talento_humano')
        can_use_boss_view = (has_boss_dashboard or has_hr_dashboard)

        if has_hr_dashboard and has_boss_dashboard:
            context['show_boss_dashboard'] = force_boss_view
        elif has_boss_dashboard and not has_hr_dashboard:
            context['show_boss_dashboard'] = True
        else:
            context['show_boss_dashboard'] = force_boss_view and can_use_boss_view

        # Estadísticas de Talento Humano
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

        if context['total_partidas'] > 0:
            context['porcentaje_ocupacion'] = round((context['partidas_ocupadas'] / context['total_partidas']) * 100, 1)
        else:
            context['porcentaje_ocupacion'] = 0

        gender_stats = active_employees.values('person__gender__name').annotate(total=Count('id'))
        context['empleados_masculino'] = 0
        context['empleados_femenino'] = 0

        for stat in gender_stats:
            if stat['person__gender__name']:
                gender_name = stat['person__gender__name'].upper()
                if 'MASCULINO' in gender_name or 'HOMBRE' in gender_name:
                    context['empleados_masculino'] = stat['total']
                elif 'FEMENINO' in gender_name or 'MUJER' in gender_name:
                    context['empleados_femenino'] = stat['total']

        try:
            levels = ['TERCER_NIVEL', 'CUARTO_NIVEL', 'TECNOLOGO']
            person_ids = Employee.objects.filter(
                is_active=True,
                person__curriculum__academic_titles__education_level__code__in=levels
            ).values_list('person_id', flat=True).distinct()
            context['empleados_con_titulo'] = person_ids.count()
        except Exception:
            context['empleados_con_titulo'] = 0

        context['empleados_con_discapacidad'] = active_employees.filter(person__has_disability=True).count()
        context['empleados_sustitutos'] = active_employees.filter(person__is_substitute=True).count()

        top_areas = active_employees.values('area__name').annotate(total=Count('id')).order_by('-total')[:5]
        context['top_areas'] = [
            {'name': area['area__name'] or 'Sin área', 'total': area['total']}
            for area in top_areas
        ]

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

        # Lógica de Jefatura
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

                if not employee_profile:
                    person_by_document = Person.objects.filter(
                        document_number=self.request.user.username
                    ).select_related('employee_profile').first()
                    if person_by_document:
                        employee_profile = getattr(person_by_document, 'employee_profile', None)

                managed_unit = None
                if employee_profile:
                    managed_unit = AdministrativeUnit.objects.filter(
                        boss=employee_profile,
                        is_active=True
                    ).select_related('level').order_by('level__level_order', 'name').first()

                    if not managed_unit and _safe_related(employee_profile, 'person', None):
                        managed_unit = AdministrativeUnit.objects.filter(
                            boss__person__document_number=employee_profile.person.document_number,
                            is_active=True
                        ).select_related('level').order_by('level__level_order', 'name').first()

                    if not managed_unit and employee_profile.is_boss and employee_profile.area_id:
                        managed_unit = employee_profile.area

                if managed_unit:
                    def collect_unit_tree_ids(root_unit):
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
                    context['boss_pending_permits'] = unit_permits_qs.filter(status='REQUESTED')
        except Exception:
            context['boss_unit'] = None
            context['boss_unit_detail_url'] = ''
            context['boss_total_personal'] = 0
            context['boss_pending_permits_count'] = 0
            context['boss_pending_permits'] = []

        return context


# =====================================================================
# 3. PERFIL DE USUARIO
# =====================================================================
class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'core/profile.html'
    success_url = reverse_lazy('core:profile')

    def get_object(self):
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
        if hasattr(self.request.user, 'person'):
            context['person'] = self.request.user.person
        return context


# =====================================================================
# 4. GESTIÓN DE CATÁLOGOS (CATALOGS & CATALOG ITEMS)
# =====================================================================
def get_catalog_stats_dict():
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

    def get_queryset(self):
        qs = Catalog.objects.all().order_by('name')
        q = (self.request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                models.Q(code__icontains=q) |
                models.Q(name__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_cats = Catalog.objects.all()
        context['stats_total'] = all_cats.count()
        context['stats_active'] = all_cats.filter(is_active=True).count()
        context['stats_inactive'] = all_cats.filter(is_active=False).count()
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'core/catalogs/partials/partial_catalog_table.html',
                context,
                request=self.request
            )
            return JsonResponse({'html': html})
        return super().render_to_response(context, **response_kwargs)


class CatalogModalFormView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_catalog'

    def get(self, request, pk=None):
        if pk:
            catalog = get_object_or_404(Catalog, pk=pk)
            is_edit = True
            action_url = reverse('core:catalog_update', args=[pk])
        else:
            catalog = None
            is_edit = False
            action_url = reverse('core:catalog_create')

        html = render_to_string('core/catalogs/modals/modal_catalog_form.html', {
            'catalog': catalog,
            'is_edit': is_edit,
            'action_url': action_url,
        }, request=request)
        return HttpResponse(html)


class CatalogCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.add_catalog'

    def post(self, request):
        code = (request.POST.get('code') or '').strip().upper()
        name = (request.POST.get('name') or '').strip().upper()
        is_active = request.POST.get('is_active') in ['true', 'True', True, 'on', '1']

        errors = {}
        if not code:
            errors['code'] = ['El código es obligatorio.']
        elif Catalog.objects.filter(code=code).exists():
            errors['code'] = ['Ya existe un catálogo con este código.']

        if not name:
            errors['name'] = ['El nombre es obligatorio.']

        if errors:
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        Catalog.objects.create(
            code=code,
            name=name,
            is_active=is_active,
            created_by=request.user
        )
        return JsonResponse({'success': True, 'message': 'Catálogo creado exitosamente.'})


class CatalogUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_catalog'

    def post(self, request, pk):
        catalog = get_object_or_404(Catalog, pk=pk)
        name = (request.POST.get('name') or '').strip().upper()
        is_active = request.POST.get('is_active') in ['true', 'True', True, 'on', '1']

        errors = {}
        if not name:
            errors['name'] = ['El nombre es obligatorio.']

        if errors:
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        catalog.name = name
        catalog.is_active = is_active
        catalog.updated_by = request.user
        catalog.save()

        return JsonResponse({'success': True, 'message': 'Catálogo actualizado exitosamente.'})


class CatalogToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_catalog'

    def post(self, request, pk):
        instance = get_object_or_404(Catalog, pk=pk)
        instance.is_active = not instance.is_active
        instance.updated_by = request.user
        instance.save()
        return JsonResponse({
            'success': True,
            'message': f'Estado del catálogo actualizado a {"Activo" if instance.is_active else "Inactivo"}.'
        })


class CatalogItemListModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.view_catalogitem'

    def get(self, request, catalog_id):
        catalog = get_object_or_404(Catalog, pk=catalog_id)
        items = CatalogItem.objects.filter(catalog=catalog).order_by('code')
        html = render_to_string('core/catalogs/modals/modal_item_list.html', {
            'catalog': catalog,
            'items': items,
        }, request=request)
        return HttpResponse(html)


class CatalogItemModalFormView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_catalogitem'

    def get(self, request, catalog_id, pk=None):
        catalog = get_object_or_404(Catalog, pk=catalog_id)
        if pk:
            item = get_object_or_404(CatalogItem, pk=pk, catalog=catalog)
            is_edit = True
            action_url = reverse('core:catalog_item_update', args=[item.id])
        else:
            item = None
            is_edit = False
            action_url = reverse('core:catalog_item_create', args=[catalog.id])

        html = render_to_string('core/catalogs/modals/modal_item_form.html', {
            'catalog': catalog,
            'item': item,
            'is_edit': is_edit,
            'action_url': action_url,
        }, request=request)
        return HttpResponse(html)


class CatalogItemCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.add_catalogitem'

    def post(self, request, catalog_id):
        catalog = get_object_or_404(Catalog, pk=catalog_id)
        code = (request.POST.get('code') or '').strip().upper()
        name = (request.POST.get('name') or '').strip().upper()
        description = (request.POST.get('description') or '').strip()
        is_active = request.POST.get('is_active') in ['true', 'True', True, 'on', '1']

        errors = {}
        if not code:
            errors['code'] = ['El código del ítem es obligatorio.']
        elif CatalogItem.objects.filter(catalog=catalog, code=code).exists():
            errors['code'] = ['Ya existe un ítem con este código dentro del catálogo.']

        if not name:
            errors['name'] = ['El nombre es obligatorio.']

        if errors:
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        CatalogItem.objects.create(
            catalog=catalog,
            code=code,
            name=name,
            description=description,
            is_active=is_active,
            created_by=request.user
        )
        return JsonResponse({'success': True, 'message': 'Ítem registrado exitosamente.'})


class CatalogItemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_catalogitem'

    def post(self, request, pk):
        item = get_object_or_404(CatalogItem, pk=pk)
        name = (request.POST.get('name') or '').strip().upper()
        description = (request.POST.get('description') or '').strip()
        is_active = request.POST.get('is_active') in ['true', 'True', True, 'on', '1']

        errors = {}
        if not name:
            errors['name'] = ['El nombre es obligatorio.']

        if errors:
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        item.name = name
        item.description = description
        item.is_active = is_active
        item.updated_by = request.user
        item.save()

        return JsonResponse({'success': True, 'message': 'Ítem actualizado exitosamente.'})


class CatalogItemToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_catalogitem'

    def post(self, request, pk):
        item = get_object_or_404(CatalogItem, pk=pk)
        item.is_active = not item.is_active
        item.updated_by = request.user
        item.save()
        return JsonResponse({
            'success': True,
            'message': f'Estado del ítem actualizado a {"Activo" if item.is_active else "Inactivo"}.'
        })


# =====================================================================
# 5. UBICACIONES GEOGRÁFICAS (LOCATIONS)
# =====================================================================
def get_location_stats_dict():
    return {
        'country': Location.objects.filter(level=1, is_active=True).count(),
        'province': Location.objects.filter(level=2, is_active=True).count(),
        'city': Location.objects.filter(level=3, is_active=True).count(),
        'parish': Location.objects.filter(level=4, is_active=True).count(),
    }


class LocationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Location
    template_name = 'core/locations/location_list.html'
    context_object_name = 'locations'
    permission_required = 'core.view_location'

    def get_queryset(self):
        level = self.request.GET.get('level')
        parent_id = self.request.GET.get('parent_id')
        query = (self.request.GET.get('q') or '').strip()

        qs = Location.objects.all().select_related('parent').order_by('name')

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
        base_stats = Location.objects.filter(is_active=True)
        context['stats_country'] = base_stats.filter(level=1).count()
        context['stats_province'] = base_stats.filter(level=2).count()
        context['stats_city'] = base_stats.filter(level=3).count()
        context['stats_parish'] = base_stats.filter(level=4).count()

        parent_id = self.request.GET.get('parent_id')
        level = self.request.GET.get('level')
        current_display_level = '1'

        if parent_id:
            try:
                parent = Location.objects.get(pk=parent_id)
                current_display_level = str(min(parent.level + 1, 4))
            except Location.DoesNotExist:
                pass
        elif level and level != 'all':
            current_display_level = str(level)

        context['current_display_level'] = current_display_level
        return context

    def render_to_response(self, context, **response_kwargs):
        # Compatible con refreshCurrentTable de main.js
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'core/locations/partials/partial_location_table.html',
                context,
                request=self.request
            )
            return JsonResponse({
                'html': html,
                'current_display_level': context.get('current_display_level', '1'),
                'stats': get_location_stats_dict()
            })
        return super().render_to_response(context, **response_kwargs)


class LocationCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.create_location'
    template_name = 'core/locations/modals/modal_location_form.html'

    def get(self, request, *args, **kwargs):
        parent_id = request.GET.get('parent_id')
        parent_obj = None
        current_level = 1
        level_map = {1: 'País', 2: 'Provincia', 3: 'Ciudad', 4: 'Parroquia'}

        if parent_id and parent_id != 'null':
            try:
                parent_obj = Location.objects.filter(pk=parent_id).first()
                if parent_obj:
                    current_level = min(parent_obj.level + 1, 4)
            except (ValueError, TypeError):
                parent_obj = None

        modal_title = f"Nuevo {level_map.get(current_level, 'Ubicación')}"
        if parent_obj:
            modal_title += f" de {parent_obj.name}"

        context = {
            'action_url': reverse('core:location_create'),
            'is_edit': False,
            'current_level': current_level,
            'level_label': level_map.get(current_level, 'Ubicación'),
            'parent_id': parent_obj.id if parent_obj else '',
            'parent_name': parent_obj.name if parent_obj else '- Raíz -',
            'modal_title': modal_title,
        }

        html = render_to_string(self.template_name, context, request=request)
        return HttpResponse(html)

    def post(self, request, *args, **kwargs):
        name = (request.POST.get('name') or '').strip().title()
        level_raw = request.POST.get('level')
        parent_id = request.POST.get('parent')
        is_active = request.POST.get('is_active') in ['true', 'True', True, 'on', '1']

        errors = {}
        if not name:
            errors['name'] = ['El nombre de la ubicación es obligatorio.']

        try:
            level = int(level_raw) if level_raw else 1
        except (ValueError, TypeError):
            level = 1

        parent_obj = None
        if parent_id and parent_id != 'null' and parent_id.isdigit():
            parent_obj = Location.objects.filter(pk=int(parent_id)).first()

        # Validar duplicados en el mismo nivel y padre
        qs_dup = Location.objects.filter(name__iexact=name, level=level, parent=parent_obj)
        if qs_dup.exists():
            errors['name'] = [f'Ya existe una ubicación con el nombre "{name}" en este nivel.']

        if errors:
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        Location.objects.create(
            name=name,
            level=level,
            parent=parent_obj,
            is_active=is_active,
            created_by=request.user
        )

        return JsonResponse({
            'success': True,
            'message': 'Ubicación registrada exitosamente.',
            'new_stats': get_location_stats_dict()
        })


class LocationUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_location'
    template_name = 'core/locations/modals/modal_location_form.html'

    def get(self, request, pk, *args, **kwargs):
        location = get_object_or_404(Location, pk=pk)
        level_map = {1: 'País', 2: 'Provincia', 3: 'Ciudad', 4: 'Parroquia'}

        context = {
            'location': location,
            'action_url': reverse('core:location_update', args=[location.id]),
            'is_edit': True,
            'current_level': location.level,
            'level_label': level_map.get(location.level, 'Ubicación'),
            'parent_id': location.parent_id or '',
            'parent_name': location.parent.name if location.parent else '- Raíz -',
            'modal_title': f"Editar Ubicación: {location.name}",
        }

        html = render_to_string(self.template_name, context, request=request)
        return HttpResponse(html)

    def post(self, request, pk, response=JsonResponse(
        {'success': True, 'message': 'Ubicación actualizada exitosamente.', 'new_stats': get_location_stats_dict()}),
             *args, **kwargs):
        location = get_object_or_404(Location, pk=pk)
        name = (request.POST.get('name') or '').strip().title()
        is_active = request.POST.get('is_active') in ['true', 'True', True, 'on', '1']

        errors = {}
        if not name:
            errors['name'] = ['El nombre de la ubicación es obligatorio.']

        # Validar duplicados excluyendo la propia instancia
        qs_dup = Location.objects.filter(
            name__iexact=name,
            level=location.level,
            parent=location.parent
        ).exclude(pk=location.pk)

        if qs_dup.exists():
            errors['name'] = [f'Ya existe otra ubicación con el nombre "{name}" en este nivel.']

        if errors:
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        location.name = name
        location.is_active = is_active
        location.updated_by = request.user
        location.save()

        return response


@require_POST
@permission_required('core.change_location', raise_exception=True)
def location_toggle_status(request, pk):
    """
    Alterna el estado activo/inactivo de una ubicación geográfica y retorna
    respuesta JSON compatible con toggleStatusAjax() de main.js.
    """
    location = get_object_or_404(Location, pk=pk)
    location.is_active = not location.is_active
    location.updated_by = request.user
    location.save()

    status_label = "activada" if location.is_active else "desactivada"
    stats = get_location_stats_dict()

    return JsonResponse({
        'success': True,
        'message': f'La ubicación "{location.name}" ha sido {status_label} correctamente.',
        'new_stats': stats
    })


# =====================================================================
# 2. API JSON PARA SELECTORES EN CASCADA (PAÍS -> PROVINCIA -> CIUDAD)
# =====================================================================
class LocationJsonView(LoginRequiredMixin, View):
    """
    Retorna la lista de ubicaciones activas en formato JSON simple.
    Soporta filtrado por 'parent_id' o por defecto los países (level=1).
    Útil para selectores dependientes en formularios.
    """

    def get(self, request, *args, **kwargs):
        parent_id = request.GET.get('parent_id')

        if parent_id:
            qs = Location.objects.filter(parent_id=parent_id, is_active=True).order_by('name')
        else:
            qs = Location.objects.filter(level=1, is_active=True).order_by('name')

        data = [{'id': loc.id, 'name': loc.name} for loc in qs]
        return JsonResponse({
            'success': True,
            'data': data
        })


# =====================================================================
# 6. CONFIGURACIÓN DEL SISTEMA & HOJA MEMBRETADA
# =====================================================================
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


# =====================================================================
# 7. MANEJADORES DE ERROR HTTP
# =====================================================================
def custom_page_not_found(request, exception=None):
    return render(request, '404.html', status=404)


def custom_permission_denied(request, exception=None):
    return render(request, '403.html', status=403)


def custom_server_error(request, exception=None):
    return render(request, '500.html', status=500)
