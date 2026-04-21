from django.contrib.auth import get_user_model
from django.contrib import messages as django_messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, View, ListView, UpdateView
from person.models import Person
from .forms import RoleForm, UserFilterForm, CredentialCreationForm, HelpMessageForm, HelpMessageReplyForm, HelpMessageSumillaForm, HelpMessageCloseForm
from django.contrib.sessions.models import Session
from django.utils import timezone
from .models import UserSession, HelpMessage


# --- 1. GESTIÓN DE USUARIOS (PERSONAS) ---
class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Person
    template_name = 'security/users/user_list.html'
    context_object_name = 'persons'
    paginate_by = 10
    permission_required = 'person.view_person'

    def get_queryset(self):
        # En la gestión de usuarios solo se listan personas activas.
        qs = Person.objects.filter(is_active=True).select_related('user').prefetch_related('user__groups').order_by('last_name')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(document_number__icontains=q)
            )
            # También permitir buscar por rol (nombre del Group)
            qs = qs.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(document_number__icontains=q) |
                Q(user__groups__name__icontains=q)
            )

        cedula = self.request.GET.get('cedula')
        first_name = self.request.GET.get('first_name')
        last_name = self.request.GET.get('last_name')
        role_id = self.request.GET.get('role')
        status = self.request.GET.get('status')

        if cedula:
            qs = qs.filter(document_number__icontains=cedula)
        if first_name:
            qs = qs.filter(first_name__icontains=first_name)
        if last_name:
            qs = qs.filter(last_name__icontains=last_name)

        if role_id:
            qs = qs.filter(user__groups__id=role_id)

        if status == 'active':
            qs = qs.filter(user__is_active=True)
        elif status == 'inactive':
            qs = qs.filter(user__isnull=False, user__is_active=False)
        elif status == 'no_account':
            qs = qs.filter(user__isnull=True)

        # Evitar duplicados cuando se hace join con grupos
        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        User = get_user_model()

        context['filter_form'] = UserFilterForm(self.request.GET)
        context['creds_form'] = CredentialCreationForm()

        all_persons = Person.objects.filter(is_active=True)
        context['stats_total'] = all_persons.count()
        context['stats_active'] = all_persons.filter(user__is_active=True).count()
        context['stats_inactive'] = all_persons.filter(user__is_active=False).count()

        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return render(request, 'security/users/partials/partial_user_table.html', context)
        return super().get(request, *args, **kwargs)


# --- 2. GESTIÓN DE ROLES (GRUPOS) ---
class RoleListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Group
    template_name = 'security/groups/group_list.html'
    context_object_name = 'roles'
    # CORREGIDO: El modelo Group pertenece a la app 'auth'
    permission_required = 'auth.view_group'

    def get_queryset(self):
        qs = Group.objects.prefetch_related('user_set').all().order_by('name')
        query = self.request.GET.get('q')
        if query:
            qs = qs.filter(name__icontains=query)
        return qs[:200]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = RoleForm(current_user=self.request.user)
        context['stats_total'] = Group.objects.count()
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return render(request, 'security/groups/partials/partial_group_table.html', context)
        return super().get(request, *args, **kwargs)


class RoleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Group
    form_class = RoleForm
    template_name = 'security/groups/modals/modal_role_matrix.html'
    permission_required = 'auth.add_group'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_user'] = self.request.user
        return kwargs

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            role = form.save()
            perm_ids = request.POST.getlist('permissions[]')
            if perm_ids:
                perm_ids_with_admin = self._add_can_admin_permissions(perm_ids)
                role.permissions.set([int(pid) for pid in perm_ids_with_admin])

            # Guardar tipo de dashboard como permiso especializado
            dashboard_type = request.POST.get('dashboard_type')
            if dashboard_type:
                self._set_dashboard_permission(role, dashboard_type)

            return JsonResponse({'success': True, 'message': 'Rol creado correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    
    def _add_can_admin_permissions(self, perm_ids):
        """Agrega automáticamente can_admin si se marcaron todos los permisos de un modelo"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        perm_ids = [int(pid) for pid in perm_ids]
        permissions = Permission.objects.filter(id__in=perm_ids).select_related('content_type')
        
        # Agrupar permisos por content_type
        perms_by_model = {}
        for perm in permissions:
            ct_id = perm.content_type_id
            if ct_id not in perms_by_model:
                perms_by_model[ct_id] = []
            perms_by_model[ct_id].append(perm.codename)
        
        # Verificar si tienen los 4 permisos básicos y agregar can_admin
        for ct_id, codenames in perms_by_model.items():
            # Buscar el modelo name para construir los codenames correctos
            ct = ContentType.objects.get(id=ct_id)
            model_name = ct.model
            
            expected_perms = [
                f'view_{model_name}',
                f'add_{model_name}',
                f'change_{model_name}',
                f'delete_{model_name}'
            ]
            
            has_all = all(p in codenames for p in expected_perms)
            if has_all:
                # Buscar el permiso can_admin para este content_type
                can_admin_perm = Permission.objects.filter(
                    content_type_id=ct_id,
                    codename='can_admin'
                ).first()
                if can_admin_perm and can_admin_perm.id not in perm_ids:
                    perm_ids.append(can_admin_perm.id)
        
        return perm_ids

    def _set_dashboard_permission(self, role, dashboard_type):
        """Asigna un permiso especial al Group que indica el tipo de dashboard.
        Se crean los permisos si no existen y se garantiza que solo uno esté presente.
        """
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(Group)
        mapping = {
            'talento_humano': 'dashboard_talento_humano',
            'jefe': 'dashboard_jefe',
            'empleado': 'dashboard_empleado'
        }

        # Validar tipo
        if dashboard_type not in mapping:
            return

        # Crear permisos si no existen
        for key, codename in mapping.items():
            Permission.objects.get_or_create(
                codename=codename,
                content_type=ct,
                defaults={'name': f'Acceso dashboard {key}'}
            )

        # Eliminar permisos de dashboard previos
        perms_to_remove = Permission.objects.filter(content_type=ct, codename__in=list(mapping.values()))
        role.permissions.remove(*perms_to_remove)

        # Añadir el permiso seleccionado
        sel_codename = mapping[dashboard_type]
        sel_perm = Permission.objects.get(content_type=ct, codename=sel_codename)
        role.permissions.add(sel_perm)


class RoleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Group
    form_class = RoleForm
    template_name = 'security/groups/modals/modal_role_matrix.html'
    # CORREGIDO: auth.change_group
    permission_required = 'auth.change_group'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_user'] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            data = {
                'id': self.object.id,
                'name': self.object.name,
                'permissions': list(self.object.permissions.values_list('id', flat=True)),
                'dashboard_type': self._get_dashboard_type(self.object)
            }
            return JsonResponse({'success': True, 'data': data})
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            role = form.save()
            perm_ids = request.POST.getlist('permissions[]')
            # Agregar permisos can_admin automáticamente
            perm_ids_with_admin = self._add_can_admin_permissions(perm_ids)

            # Preservar permisos can_admin que ya existían en el rol
            try:
                existing_can_admin_ids = list(self.object.permissions.filter(codename='can_admin').values_list('id', flat=True))
            except Exception:
                existing_can_admin_ids = []

            for cid in existing_can_admin_ids:
                if cid not in perm_ids_with_admin:
                    perm_ids_with_admin.append(cid)

            role.permissions.set([int(pid) for pid in perm_ids_with_admin])

            # Guardar tipo de dashboard como permiso especializado
            dashboard_type = request.POST.get('dashboard_type')
            if dashboard_type:
                self._set_dashboard_permission(role, dashboard_type)

            return JsonResponse({'success': True, 'message': 'Rol actualizado correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    
    def _add_can_admin_permissions(self, perm_ids):
        """Agrega automáticamente can_admin si se marcaron todos los permisos de un modelo"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        perm_ids = [int(pid) for pid in perm_ids]
        permissions = Permission.objects.filter(id__in=perm_ids).select_related('content_type')
        
        # Agrupar permisos por content_type
        perms_by_model = {}
        for perm in permissions:
            ct_id = perm.content_type_id
            if ct_id not in perms_by_model:
                perms_by_model[ct_id] = []
            perms_by_model[ct_id].append(perm.codename)
        
        # Verificar si tienen los 4 permisos básicos y agregar can_admin
        for ct_id, codenames in perms_by_model.items():
            # Buscar el modelo name para construir los codenames correctos
            ct = ContentType.objects.get(id=ct_id)
            model_name = ct.model
            
            expected_perms = [
                f'view_{model_name}',
                f'add_{model_name}',
                f'change_{model_name}',
                f'delete_{model_name}'
            ]
            
            has_all = all(p in codenames for p in expected_perms)
            if has_all:
                # Buscar el permiso can_admin para este content_type
                can_admin_perm = Permission.objects.filter(
                    content_type_id=ct_id,
                    codename='can_admin'
                ).first()
                if can_admin_perm and can_admin_perm.id not in perm_ids:
                    perm_ids.append(can_admin_perm.id)
        
        return perm_ids

    def _set_dashboard_permission(self, role, dashboard_type):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(Group)
        mapping = {
            'talento_humano': 'dashboard_talento_humano',
            'jefe': 'dashboard_jefe',
            'empleado': 'dashboard_empleado'
        }

        if dashboard_type not in mapping:
            return

        for key, codename in mapping.items():
            Permission.objects.get_or_create(
                codename=codename,
                content_type=ct,
                defaults={'name': f'Acceso dashboard {key}'}
            )

        perms_to_remove = Permission.objects.filter(content_type=ct, codename__in=list(mapping.values()))
        role.permissions.remove(*perms_to_remove)

        sel_codename = mapping[dashboard_type]
        sel_perm = Permission.objects.get(content_type=ct, codename=sel_codename)
        role.permissions.add(sel_perm)

    def _get_dashboard_type(self, role):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(Group)
        mapping = {
            'talento_humano': 'dashboard_talento_humano',
            'jefe': 'dashboard_jefe',
            'empleado': 'dashboard_empleado'
        }

        perms = role.permissions.filter(content_type=ct).values_list('codename', flat=True)
        for key, codename in mapping.items():
            if codename in perms:
                return key
        return None


# --- 3. GESTIÓN DE CREDENCIALES ---
class CreateUserForPersonView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_user'

    def post(self, request, person_id):
        from .forms import CredentialCreationForm

        try:
            form = CredentialCreationForm(person_id, request.POST)
            if form.is_valid():
                user_updated = form.save()
                message_text = 'Credenciales generadas y asignadas.'
                require_logout = False
                
                # Si el usuario cambia su propia contraseña y es válida, debe reiniciar sesión pero avisamos al frontend.
                if user_updated and form.cleaned_data.get('password'):
                    if request.user == user_updated:
                        require_logout = True
                        message_text = 'Contraseña actualizada. Deberá iniciar sesión nuevamente.'
                        
                return JsonResponse({'success': True, 'message': message_text, 'require_logout': require_logout})
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'errors': {'__all__': [f'Error del servidor: {str(e)}']}
            }, status=500)

    def get(self, request, person_id):
        person = get_object_or_404(Person, pk=person_id)
        user = person.user

        data = {
            'success': True,
            'person_name': f"{person.first_name} {person.last_name}",
            'has_user': False,
            'form_data': {
                'username': '',
                'role': '',
                'is_active': True,
                'is_staff': False,
                'custom_name': '',
                'custom_position': ''
            }
        }

        if user:
            data['has_user'] = True
            group = user.groups.first()
            data['form_data'] = {
                'username': user.username,
                'role': group.id if group else '',
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'custom_name': user.custom_name or user.get_default_signature_name(),
                'custom_position': user.custom_position or user.get_default_signature_position(),
            }
        else:
            # Sugerir la cédula como nombre de usuario para nuevos usuarios
            username_suggestion = (person.document_number or '').strip()
            data['form_data']['username'] = username_suggestion
            data['form_data']['custom_name'] = person.full_name.upper()

            employee = getattr(person, 'employee_profile', None)
            budget_line = employee.current_budget_line.select_related('position_item').first() if employee else None
            data['form_data']['custom_position'] = (
                (budget_line.position_item.name or '').upper()
                if budget_line and budget_line.position_item
                else ''
            )

        return JsonResponse(data)


@method_decorator(require_POST, name='dispatch')
class UserToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.change_user'
    raise_exception = True

    def post(self, request, pk):
        person = get_object_or_404(Person, pk=pk)

        if not person.user:
            return JsonResponse({
                'success': False,
                'message': 'Esta persona no tiene un usuario asociado.'
            }, status=400)

        if person.user == request.user:
            return JsonResponse({
                'success': False,
                'message': 'No puedes desactivar tu propia cuenta.'
            }, status=403)

        user = person.user
        user.is_active = not user.is_active
        user.save()

        active_persons = Person.objects.filter(is_active=True)
        stats = {
            'total': active_persons.count(),
            'active': active_persons.filter(user__is_active=True).count(),
            'inactive': active_persons.filter(user__isnull=False, user__is_active=False).count(),
        }

        action_verb = "activado" if user.is_active else "desactivado"

        return JsonResponse({
            'success': True,
            'message': f'Usuario {action_verb} correctamente.',
            'new_stats': stats
        })


# --- 4. CONTROL DE USUARIOS (LISTA DE USUARIOS CON ESTADO DE CONEXIÓN) ---
class UserControlListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = get_user_model()
    template_name = 'security/users/user_control_list.html'
    context_object_name = 'users'
    permission_required = 'auth.view_user'

    def get_queryset(self):
        return get_user_model().objects.filter(last_login__isnull=False).order_by('-last_login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from datetime import timedelta
        from django.db.models import Q
        
        user_data = []
        SESSION_TIMEOUT_HOURS = 12
        timeout_threshold = timezone.now() - timedelta(hours=SESSION_TIMEOUT_HOURS)
        
        # Obtener todas mis sesiones
        all_sessions = {obj.user_id: obj for obj in UserSession.objects.select_related('user').all()}
        
        for user in self.get_queryset():
            last_session = all_sessions.get(user.id)
            
            # Determinar si está en línea:
            # - Debe tener una sesión registrada
            # - La última actividad debe ser MAYOR o igual al threshold (dentro de 12 horas)
            is_online = False
            if last_session and last_session.last_activity:
                is_online = last_session.last_activity >= timeout_threshold
            
            user_data.append({
                'user': user,
                'is_online': is_online,
                'ip_address': last_session.ip_address if last_session else 'N/A',
                'mac_address': last_session.mac_address if last_session else 'N/A',
                'device_info': last_session.user_agent if last_session else 'N/A',
            })
            
        context['user_data'] = user_data
        return context


class UpdateSessionInfoView(LoginRequiredMixin, View):
    """API para actualizar información del dispositivo en la sesión de usuario"""
    
    def post(self, request):
        import json
        
        try:
            data = json.loads(request.body)
            mac_address = data.get('mac_address', '')
            device_info = data.get('device_info', '')
            
            # Actualizar la sesión actual del usuario con la información del dispositivo
            UserSession.objects.filter(user=request.user).update(
                mac_address=mac_address[:17] if mac_address else None,  # Limitar a longitud de MAC
                user_agent=device_info[:500] if device_info else None   # Limitar longitud
            )
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


class HelpMessageListView(LoginRequiredMixin, ListView):
    model = HelpMessage
    template_name = 'security/help_messages/message_list.html'
    context_object_name = 'help_messages'
    paginate_by = 10

    @staticmethod
    def _thread_participant_ids(root):
        participants = set([root.sender_user_id, root.recipient_user_id])
        thread_users = HelpMessage.objects.filter(
            Q(id=root.id) | Q(original_message=root)
        ).values_list('sender_user_id', 'recipient_user_id')
        for sender_id, recipient_id in thread_users:
            participants.add(sender_id)
            participants.add(recipient_id)
        return participants

    @staticmethod
    def _format_elapsed(delta):
        total_seconds = max(0, int(delta.total_seconds()))
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        return f'{days}d {hours}h {minutes}m'

    @staticmethod
    def _pending_turn_count(user):
        roots = list(
            HelpMessage.objects.filter(
                Q(sender_user=user) | Q(recipient_user=user)
            ).annotate(
                root_id=Coalesce('original_message_id', 'id')
            ).values_list('root_id', flat=True).distinct()
        )

        if not roots:
            return 0

        root_status_map = {
            item['id']: item['status']
            for item in HelpMessage.objects.filter(id__in=roots).values('id', 'status')
        }

        thread_messages = HelpMessage.objects.filter(
            Q(id__in=roots) | Q(original_message_id__in=roots)
        ).values('id', 'original_message_id', 'recipient_user_id', 'created_at').order_by('created_at')

        last_recipient_by_root = {}
        for item in thread_messages:
            root_id = item['original_message_id'] or item['id']
            last_recipient_by_root[root_id] = item['recipient_user_id']

        return sum(
            1
            for root_id, recipient_id in last_recipient_by_root.items()
            if recipient_id == user.id and root_status_map.get(root_id) != HelpMessage.Status.FINALIZED
        )

    def get_queryset(self):
        tab = self.request.GET.get('tab', 'received')
        user = self.request.user
        own_messages = HelpMessage.objects.filter(
            Q(recipient_user=user) | Q(sender_user=user)
        )

        root_ids = list(
            own_messages.annotate(
                root_id=Coalesce('original_message_id', 'id')
            ).values_list('root_id', flat=True).distinct()
        )

        qs = HelpMessage.objects.filter(
            id__in=root_ids,
            original_message__isnull=True
        ).select_related(
            'sender_user__person',
            'recipient_user__person'
        )

        if tab == 'sent':
            qs = qs.filter(sender_user=user)
        elif tab == 'received':
            qs = qs.exclude(sender_user=user)
        elif tab == 'attended':
            qs = qs.filter(status__in=[HelpMessage.Status.ATTENDED, HelpMessage.Status.FINALIZED])

        query = self.request.GET.get('q')
        if query:
            qs = qs.filter(
                Q(subject__icontains=query) |
                Q(detail__icontains=query) |
                Q(sender_user__username__icontains=query) |
                Q(recipient_user__username__icontains=query) |
                Q(sender_user__person__first_name__icontains=query) |
                Q(sender_user__person__last_name__icontains=query) |
                Q(recipient_user__person__first_name__icontains=query) |
                Q(recipient_user__person__last_name__icontains=query)
            )

        qs = qs.order_by('-updated_at', '-created_at')
        roots = list(qs)

        thread_messages = HelpMessage.objects.filter(
            Q(id__in=[root.id for root in roots]) | Q(original_message_id__in=[root.id for root in roots])
        ).select_related('sender_user__person', 'recipient_user__person').order_by('created_at')

        thread_map = {}
        for root in roots:
            thread_map[root.id] = []

        for item in thread_messages:
            root_id = item.original_message_id or item.id
            if root_id in thread_map:
                thread_map[root_id].append(item)

        for root in roots:
            root.thread_messages = thread_map.get(root.id, [root])
            root.last_message = root.thread_messages[-1] if root.thread_messages else root
            root.direction = 'sent' if root.sender_user_id == user.id else 'received'
            root.counterpart_name = root.recipient_name if root.direction == 'sent' else root.sender_name
            participants = self._thread_participant_ids(root)
            is_closed = root.status in [HelpMessage.Status.ATTENDED, HelpMessage.Status.FINALIZED]
            root.can_reply = (not is_closed) and (user.id in participants)
            root.can_sumilla = (not is_closed) and (root.direction == 'received') and (user.id in participants)
            root.can_initiator_attended_actions = (
                root.status == HelpMessage.Status.ATTENDED
                and root.sender_user_id == user.id
                and root.last_message.recipient_user_id == user.id
            )
            root.user_has_unread = any(
                m.recipient_user_id == user.id and m.status == HelpMessage.Status.SENT
                for m in root.thread_messages
            )
            root.is_user_turn = (not is_closed) and (root.last_message.recipient_user_id == user.id)
            root.actions_unlocked = root.is_user_turn and (not root.user_has_unread)
            end_time = root.attended_at if is_closed and root.attended_at else timezone.now()
            root.elapsed_label = self._format_elapsed(end_time - root.created_at)

        return roots

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        own_messages = HelpMessage.objects.filter(
            Q(recipient_user=self.request.user) | Q(sender_user=self.request.user)
        )
        context['create_form'] = HelpMessageForm()
        context['reply_form'] = HelpMessageReplyForm()
        context['sumilla_form'] = HelpMessageSumillaForm(current_user=self.request.user)
        context['close_form'] = HelpMessageCloseForm()
        context['active_tab'] = self.request.GET.get('tab', 'received')
        context['messages_total'] = own_messages.count()
        context['messages_sent'] = own_messages.filter(sender_user=self.request.user, original_message__isnull=True).count()
        context['messages_received'] = own_messages.filter(recipient_user=self.request.user, original_message__isnull=True).count()
        context['messages_unread'] = self._pending_turn_count(self.request.user)
        context['messages_read'] = HelpMessage.objects.filter(
            recipient_user=self.request.user,
            status=HelpMessage.Status.READ
        ).count()
        context['messages_attended'] = HelpMessage.objects.filter(
            recipient_user=self.request.user,
            status__in=[HelpMessage.Status.ATTENDED, HelpMessage.Status.FINALIZED]
        ).count()
        return context


class HelpMessageCreateView(LoginRequiredMixin, View):
    def post(self, request):
        form = HelpMessageForm(request.POST, request.FILES)
        if form.is_valid():
            recipient_person = form.cleaned_data['recipient_person']
            recipient_user = recipient_person.user
            HelpMessage.objects.create(
                sender_user=request.user,
                recipient_user=recipient_user,
                subject=form.cleaned_data['subject'],
                detail=form.cleaned_data['detail'],
                attachment=form.cleaned_data.get('attachment'),
                status=HelpMessage.Status.SENT,
                created_by=request.user,
                updated_by=request.user,
            )
            django_messages.success(request, 'Mensaje enviado correctamente.')
            return redirect('security:help_message_list')

        django_messages.error(request, 'No se pudo enviar el mensaje. Revisa los campos requeridos.')
        return redirect('security:help_message_list')


class HelpMessageMarkReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        root = get_object_or_404(HelpMessage, pk=pk, original_message__isnull=True)
        participants = HelpMessageListView._thread_participant_ids(root)
        if request.user.id not in participants:
            return JsonResponse({'success': False}, status=403)

        now = timezone.now()
        
        # Marcar como leído los mensajes SENT pendientes
        unread_qs = HelpMessage.objects.filter(
            Q(id=root.id) | Q(original_message=root),
            recipient_user=request.user,
            status=HelpMessage.Status.SENT
        )
        unread_qs.update(
            status=HelpMessage.Status.READ,
            read_at=now,
            updated_by=request.user,
            updated_at=now,
        )

        # Si el usuario es el iniciador y el hilo está ATTENDED,
        # marcar los mensajes de cierre como leídos también
        if root.status == HelpMessage.Status.ATTENDED and request.user.id == root.sender_user_id:
            attended_qs = HelpMessage.objects.filter(
                Q(id=root.id) | Q(original_message=root),
                recipient_user=request.user,
                status=HelpMessage.Status.ATTENDED
            )
            attended_qs.update(
                read_at=now,
                updated_by=request.user,
                updated_at=now,
            )

        if root.status not in [HelpMessage.Status.ATTENDED, HelpMessage.Status.FINALIZED]:
            root.status = HelpMessage.Status.READ
            root.updated_by = request.user
            root.save(update_fields=['status', 'updated_by', 'updated_at'])

        remaining_unread = HelpMessageListView._pending_turn_count(request.user)

        return JsonResponse({'success': True, 'status': root.status, 'remaining_unread': remaining_unread})


class HelpMessageReplyView(LoginRequiredMixin, View):
    def post(self, request, pk):
        original = get_object_or_404(HelpMessage, pk=pk, original_message__isnull=True)
        participants = HelpMessageListView._thread_participant_ids(original)
        if request.user.id not in participants:
            return redirect('security:help_message_list')

        if original.status in [HelpMessage.Status.ATTENDED, HelpMessage.Status.FINALIZED]:
            django_messages.warning(request, 'La conversación ya está atendida y no admite más respuestas.')
            return redirect('security:help_message_list')

        form = HelpMessageReplyForm(request.POST, request.FILES)
        if form.is_valid():
            reply_subject = f'Respuesta a mensaje: {original.subject}'
            thread_last = HelpMessage.objects.filter(
                Q(id=original.id) | Q(original_message=original)
            ).order_by('-created_at').first()
            if not thread_last:
                thread_last = original
            reply_recipient = thread_last.sender_user if thread_last.sender_user_id != request.user.id else thread_last.recipient_user
            HelpMessage.objects.create(
                sender_user=request.user,
                recipient_user=reply_recipient,
                subject=reply_subject,
                detail=form.cleaned_data['detail'],
                attachment=form.cleaned_data.get('attachment'),
                status=HelpMessage.Status.SENT,
                original_message=original,
                created_by=request.user,
                updated_by=request.user,
            )
            original.status = HelpMessage.Status.SENT
            original.updated_by = request.user
            original.save(update_fields=['status', 'updated_by', 'updated_at'])
            django_messages.success(request, 'Respuesta enviada correctamente.')
            return redirect('security:help_message_list')

        django_messages.error(request, 'No se pudo enviar la respuesta. Revisa los campos requeridos.')
        return redirect('security:help_message_list')


class HelpMessageMarkAttendedView(LoginRequiredMixin, View):
    def post(self, request, pk):
        root = get_object_or_404(HelpMessage, pk=pk, original_message__isnull=True)
        participants = HelpMessageListView._thread_participant_ids(root)
        if request.user.id not in participants:
            return redirect('security:help_message_list')

        if root.status in [HelpMessage.Status.ATTENDED, HelpMessage.Status.FINALIZED]:
            django_messages.warning(request, 'La conversación ya está atendida.')
            return redirect('security:help_message_list')

        close_form = HelpMessageCloseForm(request.POST, request.FILES)
        if not close_form.is_valid():
            django_messages.error(request, 'Debes escribir un mensaje final para cerrar el trámite.')
            return redirect('security:help_message_list')

        now = timezone.now()
        
        # Crear el mensaje final de cierre como parte del hilo
        # Este mensaje será visto por el iniciador cuando abra el detalle
        final_message = HelpMessage.objects.create(
            sender_user=request.user,
            recipient_user=root.sender_user,
            subject=f'Cierre de trámite: {root.subject}',
            detail=close_form.cleaned_data['detail'],
            attachment=close_form.cleaned_data.get('attachment'),
            status=HelpMessage.Status.ATTENDED,  # El mensaje de cierre es ATTENDED, no SENT
            original_message=root,
            created_by=request.user,
            updated_by=request.user,
        )

        # Marcar todo el hilo como ATTENDED (incluyendo el mensaje de cierre)
        HelpMessage.objects.filter(
            Q(id=root.id) | Q(original_message=root)
        ).update(
            status=HelpMessage.Status.ATTENDED,
            attended_at=now,
            updated_by=request.user,
            updated_at=now,
        )

        root.updated_by = request.user
        root.save(update_fields=['updated_by', 'updated_at'])
        django_messages.success(request, 'Trámite marcado como atendido. El iniciador puede verlo en su bandeja.')
        return redirect('security:help_message_list')


class HelpMessageSumillaView(LoginRequiredMixin, View):
    def post(self, request, pk):
        root = get_object_or_404(HelpMessage, pk=pk, original_message__isnull=True)
        participants = HelpMessageListView._thread_participant_ids(root)
        if request.user.id not in participants:
            return redirect('security:help_message_list')

        if root.status in [HelpMessage.Status.ATTENDED, HelpMessage.Status.FINALIZED]:
            django_messages.warning(request, 'La conversación está atendida. No se puede sumillar.')
            return redirect('security:help_message_list')

        form = HelpMessageSumillaForm(request.POST, request.FILES, current_user=request.user)
        if not form.is_valid():
            django_messages.error(request, 'No se pudo enviar la sumilla. Revisa los campos requeridos.')
            return redirect('security:help_message_list')

        recipient_person = form.cleaned_data['recipient_person']
        recipient_user = recipient_person.user

        if recipient_user.id in participants:
            django_messages.warning(request, 'Ese usuario ya participa en la conversación.')
            return redirect('security:help_message_list')

        sumilla_subject = f'Sumilla: {root.subject}'
        sumilla_detail = form.cleaned_data['detail']
        HelpMessage.objects.create(
            sender_user=request.user,
            recipient_user=recipient_user,
            subject=sumilla_subject,
            detail=sumilla_detail,
            attachment=form.cleaned_data.get('attachment'),
            status=HelpMessage.Status.SENT,
            original_message=root,
            created_by=request.user,
            updated_by=request.user,
        )

        root.status = HelpMessage.Status.SENT
        root.updated_by = request.user
        root.save(update_fields=['status', 'updated_by', 'updated_at'])

        django_messages.success(request, 'Sumilla enviada correctamente.')
        return redirect('security:help_message_list')


class HelpMessageFinalizeByInitiatorView(LoginRequiredMixin, View):
    def post(self, request, pk):
        root = get_object_or_404(HelpMessage, pk=pk, original_message__isnull=True)
        if request.user.id != root.sender_user_id:
            return redirect('security:help_message_list')

        if root.status != HelpMessage.Status.ATTENDED:
            django_messages.warning(request, 'Solo se puede finalizar cuando el trámite está atendido.')
            return redirect('security:help_message_list')

        now = timezone.now()
        thread_last = HelpMessage.objects.filter(
            Q(id=root.id) | Q(original_message=root)
        ).order_by('-created_at').first()

        if thread_last and thread_last.status in [HelpMessage.Status.SENT, HelpMessage.Status.READ, HelpMessage.Status.ATTENDED]:
            thread_last.status = HelpMessage.Status.FINALIZED
            if not thread_last.read_at and thread_last.recipient_user_id == request.user.id:
                thread_last.read_at = now
            thread_last.updated_by = request.user
            thread_last.save(update_fields=['status', 'read_at', 'updated_by', 'updated_at'])

        root.status = HelpMessage.Status.FINALIZED
        if not root.attended_at:
            root.attended_at = now
        root.updated_by = request.user
        root.save(update_fields=['status', 'attended_at', 'updated_by', 'updated_at'])

        django_messages.success(request, 'Trámite finalizado correctamente.')
        return redirect('security:help_message_list')


class HelpMessageCorrectionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        root = get_object_or_404(HelpMessage, pk=pk, original_message__isnull=True)
        if request.user.id != root.sender_user_id:
            return redirect('security:help_message_list')

        if root.status != HelpMessage.Status.ATTENDED:
            django_messages.warning(request, 'Solo puedes enviar alcance cuando el trámite está atendido.')
            return redirect('security:help_message_list')

        form = HelpMessageReplyForm(request.POST, request.FILES)
        if not form.is_valid():
            django_messages.error(request, 'No se pudo enviar el alcance. Revisa los campos requeridos.')
            return redirect('security:help_message_list')

        thread_last = HelpMessage.objects.filter(
            Q(id=root.id) | Q(original_message=root)
        ).order_by('-created_at').first()
        if not thread_last:
            thread_last = root

        reply_recipient = thread_last.sender_user if thread_last.sender_user_id != request.user.id else thread_last.recipient_user

        HelpMessage.objects.create(
            sender_user=request.user,
            recipient_user=reply_recipient,
            subject=f'Corrección/Alcance: {root.subject}',
            detail=form.cleaned_data['detail'],
            attachment=form.cleaned_data.get('attachment'),
            status=HelpMessage.Status.SENT,
            original_message=root,
            created_by=request.user,
            updated_by=request.user,
        )

        root.status = HelpMessage.Status.SENT
        root.updated_by = request.user
        root.save(update_fields=['status', 'updated_by', 'updated_at'])

        django_messages.success(request, 'Alcance enviado. El trámite vuelve a pendiente.')
        return redirect('security:help_message_list')
