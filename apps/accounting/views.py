from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.views import View

from .models import Account
from .forms import AccountForm
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

    def get(self, request, *args, **kwargs):
        show_inactive = request.GET.get('show_inactive')
        qs = Account.objects.all().order_by('code')
        if show_inactive is None or show_inactive.lower() in ['false', '0', '']:
            qs = qs.filter(is_active=True)

        # Si es petición AJAX devolvemos solo las filas (tbody)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from django.template.loader import render_to_string
            html = render_to_string('accounting/_account_rows.html', {'accounts': qs})
            from django.http import HttpResponse
            return HttpResponse(html)

        self.object_list = qs
        context = self.get_context_data()
        return self.render_to_response(context)


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
