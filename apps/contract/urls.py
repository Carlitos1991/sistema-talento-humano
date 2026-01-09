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
]
