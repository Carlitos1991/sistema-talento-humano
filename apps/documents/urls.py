from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('list/', views.DocumentListView.as_view(), name='document_list'),
    path('create/', views.DocumentCreateView.as_view(), name='document_create'),
    path('create-multiple/', views.create_multiple_documents, name='document_create_multiple'),
    path('next-code/<int:category_id>/', views.next_filing_code, name='next_filing_code'),
    path('detail/<int:pk>/', views.document_detail, name='document_detail'),
    path('update/<int:pk>/', views.DocumentUpdateView.as_view(), name='document_update'),
    path('upload-file/<int:pk>/', views.upload_document_file, name='document_upload_file'),
    path('delete-file/<int:pk>/', views.delete_document_file, name='document_delete_file'),
    # path('delete/<int:pk>/', ...),
    # --- RUTAS PARA TIPOS DE DOCUMENTO ---
    path('types/', views.DocumentTypeListView.as_view(), name='doc_type_list'),
    path('types/create/', views.DocumentTypeCreateView.as_view(), name='doc_type_create'),
    path('types/update/<int:pk>/', views.DocumentTypeUpdateView.as_view(), name='doc_type_update'),
    path('types/status/<int:pk>/', views.change_type_status, name='doc_type_status'),
    path('types/detail/<int:pk>/', views.document_type_detail, name='doc_type_detail'),
]
