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


# --- 1. GESTIÓN DE USUARIOS (PERSONAS) ---
class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Person
    template_name = 'security/users/user_list.html'
    context_object_name = 'persons'
    paginate_by = 10
    # CORREGIDO: El modelo Person está en la app 'person', no 'security'
    permission_required = 'person.view_person'

    def get_queryset(self):
        qs = Person.objects.select_related('user').prefetch_related('user__groups').all().order_by('last_name')
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

        all_persons = Person.objects.all()
        context['stats_total'] = User.objects.count()
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
    # CORREGIDO: auth.add_group
    permission_required = 'auth.add_group'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            role = form.save()
            perm_ids = request.POST.getlist('permissions[]')
            if perm_ids:
                role.permissions.set([int(pid) for pid in perm_ids])

            return JsonResponse({'success': True, 'message': 'Rol creado correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


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
                'permissions': list(self.object.permissions.values_list('id', flat=True))
            }
            return JsonResponse({'success': True, 'data': data})
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            role = form.save()
            perm_ids = request.POST.getlist('permissions[]')
            role.permissions.set([int(pid) for pid in perm_ids])

            return JsonResponse({'success': True, 'message': 'Rol actualizado correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


# --- 3. GESTIÓN DE CREDENCIALES ---
class CreateUserForPersonView(LoginRequiredMixin, PermissionRequiredMixin, View):
    # CORREGIDO: Faltaba definir el permiso aquí.
    # Usamos change_user porque permite crear o editar credenciales.
    permission_required = 'core.change_user'

    def post(self, request, person_id):
        from .forms import CredentialCreationForm

        try:
            form = CredentialCreationForm(person_id, request.POST)
            if form.is_valid():
                form.save()
                return JsonResponse({'success': True, 'message': 'Credenciales generadas y asignadas.'})
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
# Nota: Aquí usamos el Mixin en la clase, no el decorador en la clase para evitar el error de as_view()
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

        stats = {
            'total': Person.objects.count(),
            'active': Person.objects.filter(user__is_active=True).count(),
            'inactive': Person.objects.filter(user__isnull=False, user__is_active=False).count(),
        }

        action_verb = "activado" if user.is_active else "desactivado"

        return JsonResponse({
            'success': True,
            'message': f'Usuario {action_verb} correctamente.',
            'new_stats': stats
        })