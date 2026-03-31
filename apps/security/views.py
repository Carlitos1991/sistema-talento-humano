from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, View, ListView, UpdateView
from person.models import Person
from .forms import RoleForm, UserFilterForm, CredentialCreationForm
from django.contrib.sessions.models import Session
from django.utils import timezone
from .models import UserSession


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

        return qs

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
        context['form'] = RoleForm()
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
                'username': '', 'role': '', 'is_active': True, 'is_staff': False
            }
        }

        if user:
            data['has_user'] = True
            group = user.groups.first()
            data['form_data'] = {
                'username': user.username,
                'role': group.id if group else '',
                'is_active': user.is_active,
                'is_staff': user.is_staff
            }
        else:
            username_suggestion = f"{person.first_name.split()[0]}{person.last_name.split()[0]}".lower()
            data['form_data']['username'] = username_suggestion

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
        
        # Get all active sessions
        sessions = Session.objects.filter(expire_date__gte=timezone.now())
        
        # Get user IDs from active sessions
        user_ids = []
        for session in sessions:
            data = session.get_decoded()
            user_id = data.get('_auth_user_id')
            if user_id:
                user_ids.append(user_id)

        # Get active users
        active_users = get_user_model().objects.filter(id__in=user_ids)
        
        # Get last login details
        user_sessions = UserSession.objects.order_by('user', '-created_at').distinct('user')
        
        user_data = []
        for user in self.get_queryset():
            is_online = user in active_users
            last_session = next((s for s in user_sessions if s.user == user), None)
            user_data.append({
                'user': user,
                'is_online': is_online,
                'ip_address': last_session.ip_address if last_session else 'N/A',
            })
            
        context['user_data'] = user_data
        return context