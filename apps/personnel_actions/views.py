from django.db.models import Q
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction

from .models import PersonnelAction, ActionMovement, ActionType
from .forms import PersonnelActionForm, ActionMovementForm, ActionTypeForm


class PersonnelActionListView(LoginRequiredMixin, ListView):
    model = PersonnelAction
    template_name = 'personnel_action/personnel_action_list.html'
    context_object_name = 'actions'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().select_related('employee', 'action_type')
        query = self.request.GET.get('q')
        if query:
            qs = qs.filter(employee__first_name__icontains=query) | qs.filter(number__icontains=query)
        return qs

    def get_template_names(self):
        # Si es una petición AJAX (HTMX o fetch), devuelve solo la tabla
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['personnel_actions/partial_personnel_action_list.html']
        return [self.template_name]


class PersonnelActionCreateView(LoginRequiredMixin, CreateView):
    model = PersonnelAction
    form_class = PersonnelActionForm
    template_name = 'personnel_action/modals/modal_personnel_action_form.html'

    def form_valid(self, form):
        # Lógica transaccional para guardar Cabecera + Detalle
        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.created_by = self.request.user
            self.object.save()

            # Crear detalle vacío o procesar segundo form aquí si se envía junto
            ActionMovement.objects.create(
                personnel_action=self.object,
                previous_remuneration=0  # Aquí podrías buscar datos actuales del empleado
            )

        return render(self.request, 'personnel_action/partials/partial_personnel_action_list.html', {
            'actions': PersonnelAction.objects.select_related('employee', 'action_type').all().order_by('-date_issue')[
                       :10]
        })


class ActionTypeListView(LoginRequiredMixin, ListView):
    model = ActionType
    template_name = 'personnel_action/action_type_list.html'
    context_object_name = 'types'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.GET.get('q')
        status = self.request.GET.get('status')

        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(code__icontains=query))

        if status == 'true':
            qs = qs.filter(is_active=True)
        elif status == 'false':
            qs = qs.filter(is_active=False)

        return qs.order_by('name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Estadísticas Globales
        ctx['stats_total'] = ActionType.objects.count()
        ctx['stats_active'] = ActionType.objects.filter(is_active=True).count()
        ctx['stats_inactive'] = ActionType.objects.filter(is_active=False).count()
        return ctx

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['personnel_action/partials/partial_action_type_list.html']
        return [self.template_name]


class ActionTypeCreateOrUpdateView(LoginRequiredMixin, View):
    """Maneja Crear (POST sin ID) y Actualizar (POST con ID)"""

    def post(self, request, pk=None):
        if pk:
            instance = get_object_or_404(ActionType, pk=pk)
            form = ActionTypeForm(request.POST, instance=instance)
        else:
            form = ActionTypeForm(request.POST)

        if form.is_valid():
            form.save()
            # Renderizamos la tabla actualizada para devolverla
            types = ActionType.objects.all().order_by('name')
            html_table = render_to_string(
                'personnel_action/partials/partial_action_type_list.html',
                {'types': types},
                request=request
            )
            return JsonResponse({'success': True, 'html': html_table})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

class ActionTypeDetailJsonView(LoginRequiredMixin, View):
    """Devuelve los datos de un registro en JSON para cargarlos en Vue"""
    def get(self, request, pk):
        obj = get_object_or_404(ActionType, pk=pk)
        data = {
            'id': obj.pk,
            'name': obj.name,
            'code': obj.code,
            'is_active': obj.is_active
        }
        return JsonResponse(data)

class ActionTypeDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(ActionType, pk=pk)
        obj.delete()
        types = ActionType.objects.all().order_by('name')
        html_table = render_to_string(
            'personnel_action/partials/partial_action_type_list.html',
            {'types': types},
            request=request
        )
        return JsonResponse({'success': True, 'html': html_table})


class ActionTypeCreateView(LoginRequiredMixin, CreateView):
    model = ActionType
    form_class = ActionTypeForm
    template_name = 'personnel_action/modals/modal_action_type_form.html'

    def form_valid(self, form):
        form.save()
        return render(self.request, 'personnel_action/partials/partial_action_type_list.html', {
            'types': ActionType.objects.all().order_by('name')
        })


class ActionTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = ActionType
    form_class = ActionTypeForm
    template_name = 'personnel_action/modals/modal_action_type_form.html'

    def form_valid(self, form):
        form.save()
        return render(self.request, 'personnel_action/partials/partial_action_type_list.html', {
            'types': ActionType.objects.all().order_by('name')
        })


# Vista especial para cambiar estado (Toggle) vía AJAX
class ActionTypeToggleStatusView(LoginRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(ActionType, pk=pk)
        obj.is_active = not obj.is_active
        obj.save()
        types = ActionType.objects.all().order_by('name')
        html_table = render_to_string(
            'personnel_action/partials/partial_action_type_list.html',
            {'types': types},
            request=request
        )
        return JsonResponse({'success': True, 'html': html_table})
