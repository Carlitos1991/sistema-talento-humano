import csv
from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from .forms import AccountForm
from .models import Account, Journal


class JournalListView(ListView):
    model = Journal
    template_name = 'accounting/journal_list.html'
    context_object_name = 'journals'


class JournalDetailView(DetailView):
    model = Journal
    template_name = 'accounting/journal_detail.html'
    context_object_name = 'journal'


class JournalExportView(View):
    def get(self, request, pk):
        journal = Journal.objects.prefetch_related('items__account', 'items__budget_line').get(pk=pk)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=journal_{pk}.csv'
        writer = csv.writer(response)
        writer.writerow([
            'account_code', 'account_name', 'debit', 'credit',
            'budget_line_code', 'budget_line_number', 'reference'
        ])
        for it in journal.items.all():
            writer.writerow([
                it.account.code,
                it.account.name,
                f"{it.debit}",
                f"{it.credit}",
                it.budget_line.code if it.budget_line else '',
                it.budget_line.number_individual if it.budget_line else '',
                it.reference or ''
            ])
        return response


class AccountListView(ListView):
    model = Account
    template_name = 'accounting/account_list.html'
    context_object_name = 'accounts'

    def get_queryset(self):
        qs = Account.objects.all().order_by(F('order').asc(nulls_last=True), 'code')
        show_inactive = self.request.GET.get('show_inactive')

        if show_inactive is not None and str(show_inactive).lower() in ['true', '1', 'on']:
            return qs.filter(is_active=False)
        return qs.filter(is_active=True)

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            html = render_to_string('accounting/partials/partial_account_table.html', context, request=request)
            return JsonResponse({'html': html})
        return super().get(request, *args, **kwargs)


class AccountCreateView(CreateView):
    model = Account
    form_class = AccountForm
    template_name = 'accounting/account_form.html'
    success_url = reverse_lazy('accounting:account_list')

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['accounting/modals/modal_account_form.html']
        return [self.template_name]

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': 'Cuenta creada correctamente.'})
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class AccountUpdateView(UpdateView):
    model = Account
    form_class = AccountForm
    template_name = 'accounting/account_form.html'
    success_url = reverse_lazy('accounting:account_list')

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['accounting/modals/modal_account_form.html']
        return [self.template_name]

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': 'Cuenta actualizada correctamente.'})
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class AccountToggleView(View):
    """Alterna el estado is_active sin eliminar la cuenta físicamente."""

    def post(self, request, pk):
        account = get_object_or_404(Account, pk=pk)
        account.is_active = not account.is_active
        # save() dispara la lógica de asignación/liberación de 'order' de models.py
        account.save()

        action_word = "activada" if account.is_active else "desactivada"
        return JsonResponse({
            'success': True,
            'message': f'La cuenta {account.name} ha sido {action_word} correctamente.',
            'is_active': account.is_active
        })
