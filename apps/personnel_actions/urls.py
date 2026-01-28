from django.urls import path
from . import views

app_name = 'personnel_actions'

urlpatterns = [
    # Lista Principal
    path('', views.PersonnelActionListView.as_view(), name='action_list'),
    path('create/', views.PersonnelActionCreateView.as_view(), name='action_create'),

    # --- TIPOS DE ACCIÓN (CRUD VUE) ---
    path('types/', views.ActionTypeListView.as_view(), name='type_list'),

    # API Endpoints para Vue
    path('types/api/save/', views.ActionTypeCreateOrUpdateView.as_view(), name='type_save'),
    path('types/api/save/<int:pk>/', views.ActionTypeCreateOrUpdateView.as_view(), name='type_update'),
    path('types/api/detail/<int:pk>/', views.ActionTypeDetailJsonView.as_view(), name='type_detail'),
    path('types/api/delete/<int:pk>/', views.ActionTypeDeleteView.as_view(), name='type_delete'),
    path('types/api/toggle/<int:pk>/', views.ActionTypeToggleStatusView.as_view(), name='type_toggle'),
]
