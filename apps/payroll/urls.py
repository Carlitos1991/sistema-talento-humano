from django.urls import path
from .views import (
    PeriodListView, PeriodCreateView, GeneratePayrollView,
    GeneratePayrollUIView, GeneratePayrollSelectedView,
    ConstantListView, ConstantCreateView, ConstantUpdateView, ConstantDeleteView,
    PayrollListView, PayslipListView, PayslipDetailView,
    FondosReservaListView,
    InstitutionalReportView, NoveltyMassLoadView, ParseNoveltyExcelView,
    SaveNoveltiesView, GetNoveltiesView, GroupedPayrollReportView, PayslipToggleWithholdView, PayslipItemUpdateAPIView,
    MarkPeriodAsPaidAPIView,
    GenerateMissingPayrollView, BankTransferReportView, PeriodUpdateView, api_calculate_working_days,
    RecalculatePayslipsView, export_negative_balances_report, MassUpdateReserveFundsView, PrintablePayslipView,
    SendPayslipEmailView, PublicPayslipValidationView, RubricListView, RubricCreateView, RubricUpdateView
)

app_name = 'payroll'

urlpatterns = [
    # Periodos y Generación
    path('periods/', PeriodListView.as_view(), name='period_list'),
    path('periods/create/', PeriodCreateView.as_view(), name='period_create'),
    path('generate/', GeneratePayrollView.as_view(), name='generate'),
    path('generate/ui/', GeneratePayrollUIView.as_view(), name='generate_ui'),
    path('generate/selected/', GeneratePayrollSelectedView.as_view(), name='generate_selected'),

    # Constantes (CRUD)
    path('constants/', ConstantListView.as_view(), name='constant_list'),
    path('constants/create/', ConstantCreateView.as_view(), name='constant_create'),
    path('constants/update/<int:pk>/', ConstantUpdateView.as_view(), name='constant_update'),
    path('constants/delete/<int:pk>/', ConstantDeleteView.as_view(), name='constant_delete'),
    path('payslips/list/', PayrollListView.as_view(), name='payslip_list'),
    path('payslips/', PayslipListView.as_view(), name='payslip_list'),
    path('payslips/detail/<int:pk>/', PayslipDetailView.as_view(), name='payslip_detail'),
    # Mapeos contables para rubros

    path('reports/institutional/<int:period_id>/', InstitutionalReportView.as_view(), name='report_institutional'),
    path('reports/grouped/<int:pk>/', GroupedPayrollReportView.as_view(), name='grouped_report'),
    # --- NOVEDADES DE NÓMINA ---
    path('novelties/mass-load/', NoveltyMassLoadView.as_view(), name='novelty_mass_load'),
    path('novelties/parse-excel/', ParseNoveltyExcelView.as_view(), name='parse_novelty_excel'),
    path('novelties/save/', SaveNoveltiesView.as_view(), name='save_novelties'),
    path('novelties/get-existing/', GetNoveltiesView.as_view(), name='get_novelties'),

    path('rubrics/', RubricListView.as_view(), name='rubric_list'),
    path('rubrics/create/', RubricCreateView.as_view(), name='rubric_create'),
    path('rubrics/<int:pk>/edit/', RubricUpdateView.as_view(), name='rubric_edit'),
    # API para Retener/Liberar el pago
    path('payslip/<int:pk>/toggle-withhold/', PayslipToggleWithholdView.as_view(),
         name='payslip_toggle_withhold'),

    # API para Modificar un rubro individual manualmente
    path('payslip-item/<int:item_id>/update/', PayslipItemUpdateAPIView.as_view(), name='payslip_item_update'),
    path('payslips/recalculate/', RecalculatePayslipsView.as_view(), name='payslip_recalculate'),
    path('reserve-funds/', FondosReservaListView.as_view(), name='reserve_funds'),
    path('period/<int:period_id>/mark-paid/', MarkPeriodAsPaidAPIView.as_view(), name='period_mark_paid'),
    path('generate/missing/', GenerateMissingPayrollView.as_view(), name='generate_missing'),
    # Reporte exclusivo para el Banco (Reporte 4)
    path('reports/bank/<int:pk>/', BankTransferReportView.as_view(), name='report_bank_transfer'),
    path('period/edit/<int:pk>/', PeriodUpdateView.as_view(), name='period_edit'),
    path('api/calculate-working-days/', api_calculate_working_days, name='api_calculate_working_days'),
    path('reports/negative-balances/<int:period_id>/', export_negative_balances_report,
         name='report_negative_balances'),
    path('reserve-funds/mass-update/', MassUpdateReserveFundsView.as_view(), name='reserve_funds_mass_update'),
    path('payslips/<int:pk>/print/', PrintablePayslipView.as_view(), name='payslip_print'),
    path('payslips/validate/<str:token>/', PublicPayslipValidationView.as_view(), name='payslip_public_validate'),
    path('payslips/<int:pk>/send-email/', SendPayslipEmailView.as_view(), name='payslip_send_email'),
]
