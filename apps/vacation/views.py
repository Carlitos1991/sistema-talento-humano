from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

# Importamos los nuevos modelos refactorizados
from .models import VacationRequest, VacationPeriod

class VacationRequestListView(LoginRequiredMixin, ListView):
    """
    Vista para 'Administrar Solicitudes' (equivalente a tu Administrar Permisos).
    Renderizará la tabla parcial luego.
    """
    model = VacationRequest
    template_name = 'vacation/vacation_request_list.html'
    context_object_name = 'vacations'

    def get_queryset(self):
        # Retornamos vacío por ahora para que no falle si no hay datos
        return VacationRequest.objects.none()

class VacationCreateView(LoginRequiredMixin, TemplateView):
    """
    Vista para 'Generar Solicitud'.
    Usamos TemplateView por ahora, luego la cambiaremos a CreateView con Ajax.
    """
    template_name = 'vacation/modals/modal_vacation_form.html'

class PeriodListView(LoginRequiredMixin, ListView):
    """
    Vista para 'Administrar Periodos/Saldos'.
    """
    model = VacationPeriod
    template_name = 'vacation/period_list.html'
    context_object_name = 'periods'