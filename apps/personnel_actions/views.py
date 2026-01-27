from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction

from .models import PersonnelAction, ActionMovement
from .forms import PersonnelActionForm, ActionMovementForm


class PersonnelActionListView(LoginRequiredMixin, ListView):
    model = PersonnelAction
    template_name = 'personnel_actions/personnel_action_list.html'
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
    template_name = 'personnel_actions/modal_personnel_action_form.html'

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

        return render(self.request, 'personnel_actions/partial_personnel_action_list.html', {
            'actions': PersonnelAction.objects.select_related('employee', 'action_type').all().order_by('-date_issue')[
                       :10]
        })