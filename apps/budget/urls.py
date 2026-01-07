from django.urls import path
from . import views

app_name = 'budget'

urlpatterns = [
    path('list/', views.BudgetListView.as_view(), name='budget_list'),
    path('create/', views.BudgetCreateView.as_view(), name='budget_create'),
    path('update/<int:pk>/', views.BudgetUpdateView.as_view(), name='budget_update'),

    # API para cascada
    path('api/hierarchy/', views.HierarchyOptionsJsonView.as_view(), name='api_hierarchy'),
    # --- Estructura ---
    path('programs/', views.ProgramListView.as_view(), name='program_list'),
    path('program/<int:program_id>/subprograms/', views.SubprogramListView.as_view(), name='subprogram_list'),
    path('subprogram/<int:subprogram_id>/projects/', views.ProjectListView.as_view(), name='project_list'),
    path('project/<int:project_id>/activities/', views.ActivityListView.as_view(), name='activity_list'),

    # --- CRUD Genérico para los niveles (vía AJAX) ---
    path('structure/create/<str:model_type>/<int:parent_id>/', views.StructureCreateView.as_view(),
         name='structure_create'),
    path('structure/edit/<str:model_type>/<int:pk>/', views.StructureUpdateView.as_view(), name='structure_edit'),
    path('structure/toggle/<str:model_type>/<int:pk>/', views.StructureToggleView.as_view(), name='structure_toggle'),
    path('assign-number/<int:pk>/', views.AssignIndividualNumberView.as_view(), name='assign_individual_number'),
    path('assign-employee/<int:pk>/', views.BudgetAssignEmployeeView.as_view(), name='budget_assign_employee'),
    path('release/<int:pk>/', views.BudgetReleaseView.as_view(), name='budget_release'),
    path('change-status/<int:pk>/', views.BudgetChangeStatusView.as_view(), name='budget_change_status'),
    path('detail/<int:pk>/', views.BudgetDetailView.as_view(), name='budget_detail'),
    path('history/changes/<int:pk>/', views.BudgetChangesHistoryView.as_view(), name='history_changes'),
    path('history/occupants/<int:pk>/', views.BudgetOccupantsHistoryView.as_view(), name='history_occupants'),

]
