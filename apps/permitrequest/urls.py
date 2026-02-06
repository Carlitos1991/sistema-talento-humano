from django.urls import path
from . import views

app_name = 'permissions'

urlpatterns = [
    # --- Tipos de Permiso (Configuración) ---
    path('types/', views.PermitTypeListView.as_view(), name='type_list'),
    path('types/create/', views.PermitTypeCreateView.as_view(), name='type_create'),
    path('types/update/<int:pk>/', views.PermitTypeUpdateView.as_view(), name='type_update'),
    path('types/delete/<int:pk>/', views.PermitTypeDeleteView.as_view(), name='type_delete'),

    # --- Solicitudes de Permiso (Gestión Diaria) ---
    path('requests/', views.PermitRequestListView.as_view(), name='permit_list'),
    path('requests/generate/', views.PermitRequestCreateView.as_view(), name='permit_create'),
    path('requests/update/<int:pk>/', views.PermitRequestUpdateView.as_view(), name='permit_update'),
    path('api/type/<int:pk>/', views.permit_type_detail_api, name='api_type_details'),
]
