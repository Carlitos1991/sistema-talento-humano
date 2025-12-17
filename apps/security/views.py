# apps/security/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.generic import CreateView, View

from apps.person.models import Person
# OJO AQUÍ: Importamos los formularios correctos que acabamos de crear
from .forms import RoleForm, CredentialCreationForm


# --- GESTIÓN DE ROLES ---
class RoleCreateView(LoginRequiredMixin, CreateView):
    model = Group
    form_class = RoleForm
    template_name = 'security/roles/modals/modal_role_matrix.html'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            role = form.save()

            # Guardar permisos de la matriz (vienen como array de IDs)
            perm_ids = request.POST.getlist('permissions[]')
            if perm_ids:
                role.permissions.set(perm_ids)

            return JsonResponse({'success': True, 'message': 'Rol creado correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


# --- GESTIÓN DE CREDENCIALES (Usuario para Persona) ---
class CreateUserForPersonView(LoginRequiredMixin, View):

    def post(self, request, person_id):
        # Instanciamos el form con el ID de la persona
        form = CredentialCreationForm(person_id, request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Credenciales generadas y asignadas.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)