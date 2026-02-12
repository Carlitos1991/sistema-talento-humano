from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('list/', views.DocumentListView.as_view(), name='document_list'),
    path('create/', views.DocumentCreateView.as_view(), name='document_create'),
    # path('update/<int:pk>/', ...),
    # path('delete/<int:pk>/', ...),
    # --- RUTAS PARA TIPOS DE DOCUMENTO ---
    path('types/', views.DocumentTypeListView.as_view(), name='type_list'),
    path('types/create/', views.DocumentTypeCreateView.as_view(), name='type_create'),
    path('types/update/<int:pk>/', views.DocumentTypeUpdateView.as_view(), name='type_update'),
    path('types/status/<int:pk>/', views.change_type_status, name='type_status'),
    path('types/detail/<int:pk>/', views.document_type_detail, name='type_detail'),
]
