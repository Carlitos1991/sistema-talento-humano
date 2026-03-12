from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.views import View

from .models import Account
from .models import Journal, JournalItem
from django.views.generic import DetailView
from django.http import HttpResponse
import csv


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


class AccountCreateView(CreateView):
    model = Account
    fields = ['code', 'name', 'is_active']
    template_name = 'accounting/account_form.html'
    success_url = reverse_lazy('accounting:account_list')


class AccountUpdateView(UpdateView):
    model = Account
    fields = ['code', 'name', 'is_active']
    template_name = 'accounting/account_form.html'
    success_url = reverse_lazy('accounting:account_list')


class AccountDeleteView(DeleteView):
    model = Account
    template_name = 'accounting/account_confirm_delete.html'
    success_url = reverse_lazy('accounting:account_list')
