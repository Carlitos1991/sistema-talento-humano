"""
Capa de servicios del módulo Core.
Encapsula lógica de negocio, transacciones multi-modelo, cálculos de métricas
y operaciones de aprovisionamiento de cuentas.
"""
import logging
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from .auth import generate_keycloak_username
from .keycloak_service import (
    create_keycloak_user,
    ensure_keycloak_account,
    find_keycloak_user_by_document,
    find_keycloak_user_by_email,
    find_keycloak_user_by_username,
    provision_and_send_password_reset,
    send_keycloak_reset_password_email,
    set_keycloak_password,
    update_keycloak_user,
)
from .models import SystemConfiguration

logger = logging.getLogger(__name__)

LOCAL_PASSWORD_RESET_SALT = 'core.local-password-reset'
LOCAL_PASSWORD_RESET_MAX_AGE = 3600


def safe_related(instance, attr_name, default=None):
    """Obtiene relaciones opcionales de forma segura sin lanzar ObjectDoesNotExist."""
    if instance is None:
        return default
    try:
        return getattr(instance, attr_name)
    except ObjectDoesNotExist:
        return default
    except Exception:
        return default


def mask_email(email: str) -> str:
    """Enmascara parcialmente la parte local de un correo electrónico."""
    if '@' not in email:
        return email
    local_part, domain = email.split('@', 1)
    if len(local_part) > 4:
        masked_local = f"{local_part[:2]}{'*' * (len(local_part) - 4)}{local_part[-2:]}"
    else:
        masked_local = local_part
    return f"{masked_local}@{domain}"


class AuthService:
    """Servicio de gestión de sesiones, contraseñas y cuentas de usuario."""

    @staticmethod
    def handle_post_login(request, user, plain_password: str | None) -> None:
        """Aprovisiona cuenta en Keycloak y cierra sesiones previas del usuario."""
        try:
            person = safe_related(user, 'person', None)
            if person is not None:
                result = ensure_keycloak_account(person, user, plain_password)
                if result.get('status') == 'created':
                    logger.info(
                        "[KEYCLOAK][PROVISION] Usuario %s aprovisionado tras login local.",
                        user.username,
                    )
        except Exception:
            logger.exception(
                "[KEYCLOAK][PROVISION] Error inesperado aprovisionando a %s.",
                getattr(user, 'username', '?'),
            )

        current_session_key = request.session.session_key
        user_id = str(user.id)
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
        sessions_to_delete = [
            session.session_key
            for session in active_sessions
            if session.get_decoded().get('_auth_user_id') == user_id
               and session.session_key != current_session_key
        ]
        if sessions_to_delete:
            Session.objects.filter(session_key__in=sessions_to_delete).delete()

    @staticmethod
    def _assign_default_employee_permissions(user) -> None:
        """Asigna el grupo y permiso base de acceso al panel de empleado."""
        normal_group, _ = Group.objects.get_or_create(name='USUARIO_NORMAL')
        user.groups.add(normal_group)
        content_type = ContentType.objects.get_for_model(Group)
        dashboard_perm, _ = Permission.objects.get_or_create(
            codename='dashboard_empleado',
            content_type=content_type,
            defaults={'name': 'Acceso dashboard empleado'},
        )
        user.user_permissions.add(dashboard_perm)

    @classmethod
    def _get_or_create_local_employee_user(cls, person, institutional_email: str):
        """Obtiene o crea la cuenta local de Django vinculada a la persona."""
        user_model = get_user_model()
        user = safe_related(person, 'user', None)
        if user is not None:
            if user.email != institutional_email.lower():
                user.email = institutional_email.lower()
                user.save(update_fields=['email'])
            return user, None

        username = generate_keycloak_username(person.first_name, person.last_name)
        if user_model.objects.filter(username=username).exists():
            return None, 'No se pudo asociar la cuenta local. Contacte a Talento Humano.'

        with transaction.atomic():
            user = user_model.objects.create_user(
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
            cls._assign_default_employee_permissions(user)

        return user, None

    @staticmethod
    def _send_local_password_reset_email(user, email: str, request) -> None:
        """Envía enlace firmado localmente cuando Keycloak no está disponible."""
        token = signing.dumps(
            {'user_id': user.pk, 'password_marker': user.password},
            salt=LOCAL_PASSWORD_RESET_SALT,
        )
        reset_url = request.build_absolute_uri(
            reverse('core:local_password_reset', kwargs={'token': token})
        )
        full_name = user.get_full_name() or user.username

        plain_text_body = (
            f"Estimado/a {full_name},\n\n"
            "Hemos recibido una solicitud para restablecer la contraseña de su cuenta en SIGETH.\n"
            "Para definir una nueva contraseña, ingrese al siguiente enlace seguro:\n\n"
            f"{reset_url}\n\n"
            "Si usted no solicitó este cambio, puede ignorar este mensaje.\n\n"
            "Atentamente,\n"
            "Dirección de Talento Humano - Municipio de Loja"
        )

        html_content = render_to_string(
            'core/emails/local_password_reset.html',
            {'nombre': full_name, 'reset_url': reset_url},
        )
        message = EmailMultiAlternatives(
            subject='Recuperación de contraseña - SIGETH',
            body=plain_text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        message.attach_alternative(html_content, 'text/html')
        if message.send(fail_silently=False) != 1:
            raise RuntimeError('El servidor SMTP no confirmó el envío del correo.')

    @classmethod
    def request_password_recovery(cls, request, identifier: str, birth_date_raw: str) -> dict:
        """Valida identidad del servidor y dispara el correo de recuperación."""
        from datetime import date
        from employee.models import Employee
        from person.models import Person

        try:
            parsed_birth_date = date.fromisoformat(birth_date_raw.strip())
        except ValueError:
            return {'status': 'error', 'message': 'El formato de la fecha de nacimiento no es válido.'}

        user_model = get_user_model()
        identifier_clean = identifier.strip()
        identifier_lower = identifier_clean.casefold()

        user = user_model.objects.filter(
            Q(username__iexact=identifier_clean) | Q(email__iexact=identifier_lower)
        ).first()
        person = safe_related(user, 'person', None) if user else None

        if person is None:
            person = Person.objects.filter(
                employee_profile__institutional_data__institutional_email__iexact=identifier_clean
            ).select_related('user', 'employee_profile__institutional_data').first()
            user = safe_related(person, 'user', None) if person else None

        if person is None:
            employee = Employee.objects.filter(
                institutional_data__institutional_email__iexact=identifier_lower
            ).select_related('person__user', 'institutional_data').first()
            person = safe_related(employee, 'person', None) if employee else None
            user = safe_related(person, 'user', None) if person else None

        if person is None:
            return {'status': 'error', 'message': 'No se encontró un registro asociado a este usuario o correo.'}

        if not person.birth_date or person.birth_date != parsed_birth_date:
            return {'status': 'error', 'message': 'La fecha de nacimiento no coincide con nuestros registros.'}

        institutional_data = safe_related(safe_related(person, 'employee_profile', None), 'institutional_data', None)
        institutional_email = getattr(institutional_data, 'institutional_email', None)
        if not institutional_email:
            return {'status': 'error', 'message': 'No existe un correo institucional registrado para esta persona.'}

        user, error_msg = cls._get_or_create_local_employee_user(person, institutional_email)
        if error_msg:
            return {'status': 'error', 'message': error_msg}

        redirect_to = request.build_absolute_uri(reverse('core:login'))
        reset_result = provision_and_send_password_reset(person, user, redirect_to)

        if reset_result['status'] != 'ok':
            if reset_result.get('reason') == 'sin email':
                return {
                    'status': 'error',
                    'message': 'El usuario no tiene un correo configurado para recibir el enlace.',
                }
            try:
                cls._send_local_password_reset_email(user, institutional_email.lower(), request)
                logger.warning("[AUTH][RESET] Fallback local utilizado para user_id=%s", user.pk)
                return {
                    'status': 'success',
                    'message': f'Se ha enviado un enlace seguro de recuperación al correo {mask_email(institutional_email.lower())}',
                }
            except Exception:
                logger.exception("[AUTH][RESET] Error en recuperación local para user_id=%s", user.pk)
                return {
                    'status': 'error',
                    'message': 'No se pudo enviar el correo de recuperación. Intente más tarde.',
                }

        return {
            'status': 'success',
            'message': f"Se ha enviado un enlace seguro de recuperación al correo {mask_email(reset_result['email'])}",
        }

    @staticmethod
    def validate_local_reset_token(token: str):
        """Decodifica el token de recuperación y verifica que la contraseña no haya cambiado."""
        user_model = get_user_model()
        try:
            payload = signing.loads(
                token,
                salt=LOCAL_PASSWORD_RESET_SALT,
                max_age=LOCAL_PASSWORD_RESET_MAX_AGE,
            )
            user = user_model.objects.get(pk=payload['user_id'], is_active=True)
            if payload.get('password_marker') != user.password:
                return None
            return user
        except (signing.BadSignature, signing.SignatureExpired, KeyError, user_model.DoesNotExist):
            return None

    @staticmethod
    def apply_local_password_reset(user, new_password: str) -> None:
        """Sincroniza la nueva contraseña en Keycloak (si existe) y en Django."""
        person = safe_related(user, 'person', None)
        keycloak_user = None
        if person and person.document_number:
            keycloak_user = find_keycloak_user_by_document(person.document_number)
        if not keycloak_user and user.email:
            keycloak_user = find_keycloak_user_by_email(user.email)
        if not keycloak_user:
            keycloak_user = find_keycloak_user_by_username(user.username)

        if keycloak_user:
            set_keycloak_password(keycloak_user['id'], new_password, temporary=False)

        user.set_password(new_password)
        user.save(update_fields=['password'])

    @staticmethod
    def change_authenticated_password(user, new_password: str) -> tuple[bool, str, int]:
        """Actualiza o crea la credencial del usuario autenticado en Keycloak."""
        person = safe_related(user, 'person', None)
        document_number = getattr(person, 'document_number', None)
        institutional_data = safe_related(
            safe_related(person, 'employee_profile', None),
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
            return False, 'No existe información institucional suficiente para sincronizar la cuenta.', 400

        try:
            keycloak_user = (
                    find_keycloak_user_by_document(document_number)
                    or find_keycloak_user_by_email(institutional_email)
                    or find_keycloak_user_by_username(user.username)
            )
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
            logger.exception("[KEYCLOAK][CAMBIO_PASSWORD] Error sincronizando cuenta para %s.", user.username)
            return False, 'No se pudo sincronizar la contraseña con Keycloak. Intente más tarde.', 502

        user.set_unusable_password()
        user.save(update_fields=['password'])
        return True, 'Contraseña actualizada y sincronizada correctamente.', 200

    @classmethod
    def self_register_employee(cls, request, document_number: str) -> dict:
        """Crea o vincula la cuenta de acceso de un servidor activo por número de cédula."""
        from person.models import Person

        person = Person.objects.filter(
            document_number=document_number
        ).select_related(
            'user',
            'employee_profile__institutional_data',
            'employee_profile__employment_status',
        ).first()

        if not person:
            return {'status': 'error', 'message': 'No se encontró una persona registrada con esa cédula.'}

        existing_user = safe_related(person, 'user', None)
        if existing_user and existing_user.is_active:
            return {
                'status': 'error',
                'message': (
                    f'Ya existe una cuenta registrada para esta cédula (usuario: {existing_user.username}). '
                    'Si no recuerda su clave, utilice la opción "¿Olvidaste tu contraseña?".'
                ),
            }

        employee_profile = safe_related(person, 'employee_profile', None)
        if not employee_profile or not employee_profile.is_active:
            return {
                'status': 'error',
                'message': 'Para crear usuario debe estar registrado como empleado o trabajador de la institución.',
            }

        employment_code = (getattr(getattr(employee_profile, 'employment_status', None), 'code', '') or '').upper()
        if employment_code not in {'EMPLEADO', 'TRABAJADOR'}:
            return {
                'status': 'error',
                'message': 'Solo se pueden crear usuarios para registros con estado laboral EMPLEADO o TRABAJADOR.',
            }

        institutional_data = safe_related(employee_profile, 'institutional_data', None)
        institutional_email = getattr(institutional_data, 'institutional_email', None)
        if not institutional_email:
            return {'status': 'error', 'message': 'No existe un correo institucional registrado para esta persona.'}

        username = generate_keycloak_username(person.first_name, person.last_name)
        redirect_to = request.build_absolute_uri(reverse('core:login'))

        try:
            existing_kc_user = (
                    find_keycloak_user_by_username(username)
                    or find_keycloak_user_by_email(institutional_email)
                    or find_keycloak_user_by_document(document_number)
            )
        except Exception:
            logger.exception("[KEYCLOAK][REGISTRO] Error consultando Keycloak para cédula=%s", document_number)
            return {'status': 'error', 'message': 'No se pudo verificar la cuenta en Keycloak. Intente más tarde.'}

        try:
            if existing_kc_user:
                kc_user_id = existing_kc_user.get('id')
                update_keycloak_user(
                    keycloak_user_id=kc_user_id,
                    username=username,
                    email=institutional_email,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    document_number=document_number,
                )
            else:
                kc_user_id, _ = create_keycloak_user(
                    username=username,
                    email=institutional_email,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    document_number=document_number,
                    temporary=True,
                )
        except Exception:
            logger.exception("[KEYCLOAK][REGISTRO] Error aprovisionando Keycloak para username=%s", username)
            return {'status': 'error', 'message': 'No se pudo configurar la cuenta en el servidor. Intente más tarde.'}

        user_model = get_user_model()
        user = existing_user
        if user is None:
            with transaction.atomic():
                user = user_model.objects.filter(username=username).first()
                if user is None:
                    user = user_model.objects.create_user(
                        username=username,
                        email=institutional_email,
                        first_name=person.first_name,
                        last_name=person.last_name,
                        is_active=True,
                    )
                user.set_unusable_password()
                user.save(update_fields=['password'])
                person.user = user
                person.save(update_fields=['user', 'updated_at'])
                cls._assign_default_employee_permissions(user)

        if kc_user_id:
            try:
                send_keycloak_reset_password_email(kc_user_id, redirect_to)
            except Exception:
                logger.warning("[KEYCLOAK][REGISTRO] Falló envío Keycloak para %s, intentando fallback local.",
                               username)
                try:
                    cls._send_local_password_reset_email(user, institutional_email.lower(), request)
                except Exception:
                    logger.exception("[AUTH][REGISTRO] Error en envío de correo local para %s", username)
                    return {
                        'status': 'error',
                        'message': 'La cuenta fue creada pero no se pudo enviar el correo de activación. Use "¿Olvidaste tu contraseña?".',
                    }

        return {
            'status': 'success',
            'message': f'Se ha configurado su cuenta (usuario: {username}) y enviado un enlace de acceso al correo {mask_email(institutional_email)}',
        }


class DashboardService:
    """Servicio de agregación de indicadores para el panel principal."""

    @classmethod
    def build_dashboard_context(cls, user, force_boss_view: bool) -> dict:
        """Compila estadísticas institucionales, de jefatura y del servidor."""
        from budget.models import BudgetLine
        from documents.models import Document, ProcedureTask
        from employee.models import Employee

        context = {'system_config': SystemConfiguration.get_current()}

        has_boss_dashboard = user.has_perm('auth.dashboard_jefe')
        has_hr_dashboard = user.has_perm('auth.dashboard_talento_humano')
        can_use_boss_view = has_boss_dashboard or has_hr_dashboard

        if has_hr_dashboard and has_boss_dashboard:
            context['show_boss_dashboard'] = force_boss_view
        elif has_boss_dashboard:
            context['show_boss_dashboard'] = True
        else:
            context['show_boss_dashboard'] = force_boss_view and can_use_boss_view

        active_employees = Employee.objects.filter(is_active=True)
        employee_stats = active_employees.values('employment_status__code').annotate(total=Count('id'))
        stats_dict = {
            item['employment_status__code']: item['total']
            for item in employee_stats
            if item['employment_status__code']
        }

        context['total_employees'] = active_employees.count()
        context['empleados'] = stats_dict.get('EMPLEADO', 0)
        context['trabajadores'] = stats_dict.get('TRABAJADOR', 0)
        context['contratados'] = stats_dict.get('CONTRATADO', 0)
        context['profesionales'] = stats_dict.get('PROFESIONAL', 0)

        active_budgets = BudgetLine.objects.exclude(status_item__code='INACTIVA')
        budget_stats = active_budgets.values('status_item__code').annotate(total=Count('id'))
        budget_dict = {
            item['status_item__code']: item['total']
            for item in budget_stats
            if item['status_item__code']
        }

        total_lines = active_budgets.count()
        occupied_lines = budget_dict.get('OCUPADA', 0)
        context['total_partidas'] = total_lines
        context['partidas_ocupadas'] = occupied_lines
        context['partidas_libres'] = budget_dict.get('LIBRE', 0)
        context['partidas_concurso'] = budget_dict.get('CONCURSO', 0)
        context['partidas_litigio'] = budget_dict.get('LITIGIO', 0)
        context['porcentaje_ocupacion'] = round((occupied_lines / total_lines) * 100, 1) if total_lines > 0 else 0

        gender_stats = active_employees.values('person__gender__name').annotate(total=Count('id'))
        male_count = 0
        female_count = 0
        for stat in gender_stats:
            raw_gender = (stat['person__gender__name'] or '').upper()
            if 'MASCULINO' in raw_gender or 'HOMBRE' in raw_gender:
                male_count = stat['total']
            elif 'FEMENINO' in raw_gender or 'MUJER' in raw_gender:
                female_count = stat['total']

        context['empleados_masculino'] = male_count
        context['empleados_femenino'] = female_count

        try:
            levels = ['TERCER_NIVEL', 'CUARTO_NIVEL', 'TECNOLOGO']
            context['empleados_con_titulo'] = Employee.objects.filter(
                is_active=True,
                person__curriculum__academic_titles__education_level__code__in=levels,
            ).values_list('person_id', flat=True).distinct().count()
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
                context['profesionales'],
            ],
        }
        context['budget_chart_data'] = {
            'labels': ['Libres', 'Ocupadas', 'Litigio', 'Concurso'],
            'values': [
                context['partidas_libres'],
                context['partidas_ocupadas'],
                context['partidas_litigio'],
                context['partidas_concurso'],
            ],
        }
        context['gender_chart_data'] = {
            'labels': ['Masculino', 'Femenino'],
            'values': [male_count, female_count],
        }

        context.update(cls._build_boss_context(user, context['show_boss_dashboard']))

        context['employee_pending_tasks_count'] = ProcedureTask.objects.filter(
            assigned_to=user,
            status__in=[ProcedureTask.TaskStatus.PENDING, ProcedureTask.TaskStatus.IN_PROCESS],
        ).count()
        context['employee_docs_count'] = Document.objects.filter(
            created_by=user,
            is_active=True,
        ).count()

        try:
            from permitrequest.models import PermitRequest
            context['employee_permits_count'] = PermitRequest.objects.filter(
                employee__person__user=user,
                created_at__year=timezone.now().year,
            ).count()
        except Exception:
            context['employee_permits_count'] = 0

        return context

    @staticmethod
    def _build_boss_context(user, show_boss_dashboard: bool) -> dict:
        """Calcula indicadores operativos de la unidad administrativa dirigida."""
        boss_data = {
            'boss_unit': None,
            'boss_unit_detail_url': '',
            'boss_total_personal': 0,
            'boss_pending_permits_count': 0,
            'boss_pending_tramites_count': 0,
            'boss_pending_permits': [],
            'boss_can_manage_permits': user.has_perm('permitrequest.change_permitrequest'),
        }
        if not show_boss_dashboard:
            return boss_data

        try:
            from documents.models import ProcedureTask
            from employee.models import Employee
            from institution.models import AdministrativeUnit
            from permitrequest.models import PermitRequest
            from person.models import Person

            user_person = safe_related(user, 'person', None)
            employee_profile = safe_related(user_person, 'employee_profile', None)

            if not employee_profile:
                person_by_doc = Person.objects.filter(
                    document_number=user.username
                ).select_related('employee_profile').first()
                employee_profile = safe_related(person_by_doc, 'employee_profile', None)

            if not employee_profile:
                return boss_data

            managed_unit = AdministrativeUnit.objects.filter(
                boss=employee_profile,
                is_active=True,
            ).select_related('level').order_by('level__level_order', 'name').first()

            if not managed_unit and safe_related(employee_profile, 'person', None):
                managed_unit = AdministrativeUnit.objects.filter(
                    boss__person__document_number=employee_profile.person.document_number,
                    is_active=True,
                ).select_related('level').order_by('level__level_order', 'name').first()

            if not managed_unit and employee_profile.is_boss and employee_profile.area_id:
                managed_unit = employee_profile.area

            if not managed_unit:
                return boss_data

            scoped_unit_ids = [managed_unit.id]
            frontier = [managed_unit.id]
            while frontier:
                children_ids = list(
                    AdministrativeUnit.objects.filter(
                        parent_id__in=frontier,
                        is_active=True,
                    ).values_list('id', flat=True)
                )
                if not children_ids:
                    break
                scoped_unit_ids.extend(children_ids)
                frontier = children_ids

            unit_permits_qs = PermitRequest.objects.select_related(
                'employee__person', 'permit_type'
            ).filter(
                Q(permit_type_id=1) | Q(permit_type__parent_id=1),
                employee__area_id__in=scoped_unit_ids,
                employee__is_active=True,
                status__in=['REQUESTED', 'APPROVED', 'REJECTED'],
            ).order_by('-created_at')

            pending_permits = unit_permits_qs.filter(status='REQUESTED')

            boss_data['boss_unit'] = managed_unit
            boss_data['boss_unit_detail_url'] = reverse('institution:unit_detail', args=[managed_unit.id])
            boss_data['boss_total_personal'] = Employee.objects.filter(
                is_active=True,
                area_id__in=scoped_unit_ids,
            ).count()
            boss_data['boss_pending_permits_count'] = pending_permits.count()
            boss_data['boss_pending_permits'] = pending_permits
            boss_data['boss_pending_tramites_count'] = ProcedureTask.objects.filter(
                unit=managed_unit,
                status__in=[ProcedureTask.TaskStatus.PENDING, ProcedureTask.TaskStatus.IN_PROCESS],
            ).count()
        except Exception:
            logger.exception("[DASHBOARD][BOSS] Error obteniendo métricas de jefatura para %s.", user.username)

        return boss_data
