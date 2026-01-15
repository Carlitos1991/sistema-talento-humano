# apps/person/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.generic import ListView, CreateView, UpdateView
from .models import Person
from .forms import PersonForm


class PersonListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Person
    template_name = 'person/person_list.html'
    context_object_name = 'people'
    paginate_by = 10
    permission_required = 'person.view_person'

    def get_queryset(self):
        qs = Person.objects.select_related(
            'document_type',
            'user',
            'employee_profile__area',
            'employee_profile__employment_status'
        ).all().order_by('last_name')

        query = self.request.GET.get('q')
        if query:
            qs = qs.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(document_number__icontains=query)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PersonForm()  # Para renderizar el modal vacío
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return render(request, 'person/partials/partial_person_table.html', context)
        return super().get(request, *args, **kwargs)


class PersonCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Person
    form_class = PersonForm
    template_name = 'person/modals/modal_person_form.html'
    permission_required = 'person.create_person'

    def post(self, request, *args, **kwargs):
        # Nota: request.FILES es necesario para la foto
        form = PersonForm(request.POST, request.FILES)
        if form.is_valid():
            person = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Persona registrada correctamente.',
                # Devolvemos datos útiles por si quieres actualizar la tabla via JS sin recargar
                'data': {'id': person.id, 'full_name': person.full_name}
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class PersonUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Person
    form_class = PersonForm
    template_name = 'person/modals/modal_person_form.html'
    permission_required = 'change.view_person'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = PersonForm(request.POST, request.FILES, instance=self.object)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Datos actualizados correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


def person_detail_json(request, pk):
    p = get_object_or_404(Person, pk=pk)
    data = {
        'id': p.id,
        'document_type': p.document_type_id,
        'document_number': p.document_number,
        'first_name': p.first_name,
        'last_name': p.last_name,
        'email': p.email,
        'birth_date': p.birth_date.isoformat() if p.birth_date else None,
        'gender': p.gender_id,
        'marital_status': p.marital_status_id,
        'blood_type': p.blood_type_id,
        'country': p.country_id,
        'province': p.province_id,
        'canton': p.canton_id,
        'parish': p.parish_id,
        'address_reference': p.address_reference,
        'phone_number': p.phone_number,
        'photo_url': p.photo.url if p.photo else None,
        # --- CAMPOS DE SALUD E INCLUSIÓN ---
        'has_disability': p.has_disability,
        'disability_type': p.disability_type_id,
        'disability_percentage': p.disability_percentage,
        'has_catastrophic_illness': p.has_catastrophic_illness,
        'catastrophic_illness_description': p.catastrophic_illness_description,
        'is_substitute': p.is_substitute,
        'substitute_family_member_id': p.substitute_family_member_id,
        'substitute_family_member_name': p.substitute_family_member_name,
        'substitute_family_member_relationship': p.substitute_family_member_relationship_id,
        'substitute_family_member_disability_type': p.substitute_family_member_disability_type_id,
        'substitute_family_member_disability_percentage': p.substitute_family_member_disability_percentage,
        # --- EMERGENCIA ---
        'emergency_contact_name': p.emergency_contact_name,
        'emergency_contact_phone': p.emergency_contact_phone,
        'emergency_contact_relationship': p.emergency_contact_relationship_id,
    }
    return JsonResponse({'success': True, 'data': data})


def person_quick_view_partial(request, pk):
    """
    Retorna un fragmento HTML con la información resumida de una persona.
    """
    person = get_object_or_404(
        Person.objects.select_related(
            'document_type',
            'gender',
            'employee_profile__area',
            'employee_profile__employment_status'
        ),
        pk=pk
    )
    return render(request, 'person/partials/partial_person_quick_view.html', {
        'person': person
    })
