from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    # 1. Configuración de usuario y firma
    path('settings/profile/', views.update_user_settings, name='update_user_settings'),
    path('settings/signature/', views.upload_signature_certificate, name='upload_signature_certificate'),

    # 2. Oficina Virtual y Despacho Drag & Drop (ESTA ES LA RUTA QUE FALTA)
    path('virtual-office/', views.virtual_office_view, name='virtual_office'),
    path('delegate/modal/', views.modal_delegate_task, name='modal_delegate_task'),
    path('delegate/process/', views.process_delegate_task, name='process_delegate_task'),

    # 3. Documentos existentes
    path('list/', views.DocumentListView.as_view(), name='document_list'),
    path('create/', views.DocumentCreateView.as_view(), name='document_create'),
    path('create-multiple/', views.create_multiple_documents, name='document_create_multiple'),
    path('next-code/<int:category_id>/', views.next_filing_code, name='next_filing_code'),
    path('detail/<int:pk>/', views.document_detail, name='document_detail'),
    path('update/<int:pk>/', views.DocumentUpdateView.as_view(), name='document_update'),
    path('upload-file/<int:pk>/', views.upload_document_file, name='document_upload_file'),
    path('delete-file/<int:pk>/', views.delete_document_file, name='document_delete_file'),
    # Recepción / Ventanilla de Trámites
    path('reception/', views.ProcedureReceptionListView.as_view(), name='procedure_reception_list'),
    path('reception/create/', views.procedure_reception_create, name='procedure_reception_create'),

    # 4. Tipos de documento
    path('types/', views.DocumentTypeListView.as_view(), name='doc_type_list'),
    path('types/create/', views.DocumentTypeCreateView.as_view(), name='doc_type_create'),
    path('types/update/<int:pk>/', views.DocumentTypeUpdateView.as_view(), name='doc_type_update'),
    path('types/status/<int:pk>/', views.change_type_status, name='doc_type_status'),
    path('types/detail/<int:pk>/', views.document_type_detail, name='doc_type_detail'),
    path('reception/update/<int:pk>/', views.procedure_reception_update, name='procedure_reception_update'),
    path('reception/cancel/<int:pk>/', views.procedure_cancel_or_delete, name='procedure_cancel_or_delete'),
    path('reception/trace/<int:pk>/', views.procedure_trace_modal, name='procedure_trace_modal'),
    # Remitir a Despacho (Modal y Proceso)
    path('reception/pass-modal/<int:pk>/', views.pass_to_secretariat_modal, name='pass_to_secretariat_modal'),
    path('reception/pass-process/<int:pk>/', views.process_pass_to_secretariat, name='process_pass_to_secretariat'),

    # Visor de PDF en Modal Grande
    path('reception/view-pdf/<int:pk>/', views.procedure_view_pdf_modal, name='procedure_view_pdf_modal'),
    path('reception/pdf-stream/<int:pk>/', views.serve_procedure_pdf, name='serve_procedure_pdf'),
    path('procedure/response/<int:pk>/', views.procedure_create_response_modal, name='procedure_create_response_modal'),
    # Guardar respuesta generada (Firma digital o física)
    path('procedure/response/save/<int:pk>/', views.save_response_document, name='save_response_document'),

    # Legalización de Sumilla (PDF físico o Firma electrónica)
    path('task/sumilla/print/<int:task_id>/', views.print_sumilla_dispositions, name='print_sumilla_dispositions'),
    path('task/sumilla/sign/<int:task_id>/', views.sign_sumilla_electronically, name='sign_sumilla_electronically'),
]
