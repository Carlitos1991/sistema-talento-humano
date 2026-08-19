import csv

from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .forms import AccountForm
from .models import Account, Journal
from django.db.models import F


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
        writer.writerow(
            ['account_code', 'account_name', 'debit', 'credit', 'budget_line_code', 'budget_line_number', 'reference'])
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

        if show_inactive is not None and show_inactive.lower() in ['true', '1']:
            qs = qs.filter(is_active=False)
        else:
            qs = qs.filter(is_active=True)
        return qs


class AccountCreateView(CreateView):
    model = Account
    form_class = AccountForm
    template_name = 'accounting/account_form.html'
    success_url = reverse_lazy('accounting:account_list')

    def get_template_names(self):
        # Si la petición es AJAX, devolvemos la plantilla modal
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['accounting/modal_account_form.html']
        return [self.template_name]

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'status': 'success', 'message': 'Cuenta creada correctamente'})
        return response

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class AccountUpdateView(UpdateView):
    model = Account
    form_class = AccountForm
    template_name = 'accounting/account_form.html'
    success_url = reverse_lazy('accounting:account_list')

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['accounting/modal_account_form.html']
        return [self.template_name]

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'status': 'success', 'message': 'Cuenta actualizada correctamente'})
        return response

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class AccountDeleteView(DeleteView):
    model = Account
    template_name = 'accounting/account_confirm_delete.html'
    success_url = reverse_lazy('accounting:account_list')
