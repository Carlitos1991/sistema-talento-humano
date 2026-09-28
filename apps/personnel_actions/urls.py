from django.urls import path
from . import views

app_name = 'personnel_actions'

urlpatterns = [
    # Lista Principal
    path('', views.PersonnelActionListView.as_view(), name='action_list'),
    path('create/', views.PersonnelActionCreateView.as_view(), name='action_create'),

    # Generar Acción (Lista de Empleados)
    path('employees/', views.EmployeeActionListView.as_view(), name='action_employee_list'),

    # Historial de Acciones por Empleado
    path('history/<int:employee_id>/', views.ActionHistoryView.as_view(), name='action_history'),
    path('<int:pk>/inactivate/', views.ActionInactivateView.as_view(), name='action_inactivate'),

    # Detalle, Editar, Registrar, PDF
    path('<int:pk>/detail/', views.ActionDetailView.as_view(), name='action_detail'),
    path('<int:pk>/edit/', views.ActionUpdateView.as_view(), name='action_update'),
    path('<int:pk>/register/', views.ActionRegisterView.as_view(), name='action_register'),
    path('<int:pk>/pdf/', views.ActionPDFView.as_view(), name='action_pdf'),

    # =========================================================================
    # TIPOS DE ACCIÓN (CRUD ESTÁNDAR DJANGO + MAIN.JS MODALS)
    # =========================================================================
    path('types/', views.ActionTypeListView.as_view(), name='action_type_list'),
    path('types/create/', views.ActionTypeCreateView.as_view(), name='action_type_create'),
    path('types/<int:pk>/edit/', views.ActionTypeUpdateView.as_view(), name='action_type_edit'),
    path('types/<int:pk>/delete/', views.ActionTypeDeleteView.as_view(), name='action_type_delete'),

    # APIs para Formularios y Select2 Dinámicos
    path('api/unit-children/', views.AdministrativeUnitChildrenJsonView.as_view(), name='api_unit_children'),
    path('api/search-budget-lines/', views.SearchBudgetLinesJsonView.as_view(), name='api_search_budget_lines'),
    path('api/users/search/', views.user_search_json, name='api_user_search'),
]
