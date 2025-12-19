from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import CreateView, View, ListView, UpdateView
from django.contrib.auth import get_user_model

from apps.person.models import Person
from .forms import RoleForm, CredentialCreationForm


# --- 1. GESTIÓN DE USUARIOS (PERSONAS) ---
class UserListView(LoginRequiredMixin, ListView):
    model = Person
    template_name = 'security/users/user_list.html'
    context_object_name = 'persons'

    def get_queryset(self):
        qs = Person.objects.select_related('user', 'person_status').all().order_by('-id')
        query = self.request.GET.get('q')
        if query:
            qs = qs.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(document_number__icontains=query) |
                Q(email__icontains=query) |
                Q(user__username__icontains=query)
            )
        status = self.request.GET.get('status')
        if status == 'active':
            qs = qs.filter(user__is_active=True)
        elif status == 'inactive':
            qs = qs.filter(user__is_active=False)
        elif status == 'no_account':
            qs = qs.filter(user__isnull=True)

        return qs[:200]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['creds_form'] = CredentialCreationForm()
        context['stats_total'] = Person.objects.count()
        # Activos (Tienen usuario y is_active=True)
        context['stats_active'] = Person.objects.filter(user__is_active=True).count()
        # Inactivos (Tienen usuario y is_active=False)
        context['stats_inactive'] = Person.objects.filter(user__is_active=False).count()

        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            # Renderiza la tabla de USUARIOS
            return render(request, 'security/users/partials/partial_user_table.html', context)
        return super().get(request, *args, **kwargs)


# --- 2. GESTIÓN DE ROLES (GRUPOS) ---
class RoleListView(LoginRequiredMixin, ListView):
    model = Group
    template_name = 'security/groups/group_list.html'
    context_object_name = 'roles'

    def get_queryset(self):
        # Lógica para buscar Grupos
        qs = Group.objects.prefetch_related('user_set').all().order_by('name')
        query = self.request.GET.get('q')
        if query:
            qs = qs.filter(name__icontains=query)
        return qs[:200]

    # --- AQUÍ ES DONDE DEBE IR EL CONTEXTO PARA EL MODAL DE ROLES ---
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Inyectamos RoleForm para que el modal "Crear Nuevo Perfil" funcione
        context['form'] = RoleForm()
        context['stats_total'] = Group.objects.count()
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            # Renderiza la tabla de ROLES
            return render(request, 'security/groups/partials/partial_group_table.html', context)
        return super().get(request, *args, **kwargs)


class RoleCreateView(LoginRequiredMixin, CreateView):
    model = Group
    form_class = RoleForm
    template_name = 'security/groups/modals/modal_role_matrix.html'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            role = form.save()
            perm_ids = request.POST.getlist('permissions[]')
            if perm_ids:
                role.permissions.set([int(pid) for pid in perm_ids])

            return JsonResponse({'success': True, 'message': 'Rol creado correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class RoleUpdateView(LoginRequiredMixin, UpdateView):
    model = Group
    form_class = RoleForm
    template_name = 'security/groups/modals/modal_role_matrix.html'

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
class CreateUserForPersonView(LoginRequiredMixin, View):

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
