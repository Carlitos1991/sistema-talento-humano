from django.urls import path
from . import views

app_name = 'contract'

urlpatterns = [
    # Régimen Laboral
    path('regimes/', views.LaborRegimeListView.as_view(), name='regime_list'),
    path('regimes/create/', views.LaborRegimeCreateView.as_view(), name='regime_create'),
    path('regimes/detail/<int:pk>/', views.LaborRegimeDetailAPIView.as_view(), name='regime_detail_api'),
    path('regimes/update/<int:pk>/', views.LaborRegimeUpdateView.as_view(), name='regime_update'),
    path('regimes/toggle-status/<int:pk>/', views.LaborRegimeToggleStatusView.as_view(), name='regime_toggle_status'),
    path('regimes/partial-table/', views.LaborRegimeTablePartialView.as_view(), name='regime_partial_table'),

    # Tipos de Contrato (Anidado)
    path('regimes/<int:regime_id>/contract-types/', views.ContractTypeListView.as_view(), name='contract_type_list'),
    path('contract-types/create/', views.ContractTypeCreateView.as_view(), name='contract_type_create'),
    path('contract-types/toggle-status/<int:pk>/', views.ContractTypeToggleStatusView.as_view(),
         name='contract_type_toggle_status'),
    path('contract-types/update/<int:pk>/', views.ContractTypeUpdateView.as_view(), name='contract_type_update'),

    # Inicios de Gestión
    path('periods/', views.ManagementPeriodListView.as_view(), name='period_list'),
    path('periods/partial-table/', views.ManagementPeriodTablePartialView.as_view(), name='period_partial_table'),
    path('periods/create/', views.ManagementPeriodCreateView.as_view(), name='period_create'),

    # APIs de búsqueda para el formulario
    path('api/validate-employee/<str:doc_number>/', views.ValidateEmployeeAPIView.as_view(),
         name='api_validate_employee'),
    path('api/budget-lines/<int:unit_id>/', views.GetAvailableBudgetLinesAPIView.as_view(), name='api_budget_lines'),
    path('periods/terminate/<int:pk>/', views.ManagementPeriodTerminateView.as_view(), name='period_terminate'),
    path('periods/sign/<int:pk>/', views.ManagementPeriodSignView.as_view(), name='period_sign'),
    path('periods/detail/<int:pk>/', views.ManagementPeriodDetailAPIView.as_view(), name='period_detail_api'),
    path('periods/update-partial/<int:pk>/', views.ManagementPeriodPartialUpdateView.as_view(),
         name='period_update_partial'),
]
