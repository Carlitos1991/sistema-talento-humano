from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.template.loader import render_to_string
from .models import BiometricDevice


class BiometricMixin:
    model = BiometricDevice
    success_url = reverse_lazy('biometric:biometric_list')


class BiometricListView(BiometricMixin, ListView):
    template_name = 'biometric/biometric_list.html'
    context_object_name = 'devices'

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(ip_address__icontains=q)
        return qs

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            html = render_to_string('biometric/partials/partial_biometric_table.html', {'devices': self.object_list})
            return JsonResponse({'html': html})
        return super().get(request, *args, **kwargs)


class BiometricCreateView(BiometricMixin, CreateView):
    fields = ['name', 'ip_address', 'port', 'location', 'serial_number', 'model_name']

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        self.object = form.save()
        return JsonResponse({'status': 'success', 'message': 'Dispositivo registrado correctamente'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)