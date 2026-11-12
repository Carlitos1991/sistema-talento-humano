from django.urls import path
from . import views

app_name = 'licenses'

urlpatterns = [
    # Medical Licenses
    path('', views.MedicalLicenseListView.as_view(), name='list'),
    path('subsidios/modal/', views.LicenseSubsidyReportModalView.as_view(), name='subsidy_report_modal'),
    path('subsidios/exportar/', views.LicenseSubsidyReportExportView.as_view(), name='subsidy_report_export'),
    path('crear/', views.MedicalLicenseCreateView.as_view(), name='create'),
    path('<int:pk>/accion-modal/', views.MedicalLicenseActionModalView.as_view(), name='action_modal'),
    path('<int:pk>/accion-guardar/', views.MedicalLicenseActionSaveView.as_view(), name='action_save'),
    path('<int:pk>/devolver-recepcion/', views.MedicalLicenseReturnReceptionView.as_view(), name='return_reception'),
    path('<int:pk>/devolver-recepcion-modal/', views.MedicalLicenseReturnReceptionModalView.as_view(),
         name='return_reception_modal'),

    # License Types
    path('tipos/', views.LicenseTypeListView.as_view(), name='type_list'),
    path('tipos/crear/', views.LicenseTypeCreateView.as_view(), name='type_create'),
    path('tipos/<int:pk>/editar/', views.LicenseTypeUpdateView.as_view(), name='type_update'),

    # Requirements
    path('requisitos/crear-modal/', views.RequirementCreateModalView.as_view(), name='requirement_create_modal'),
    path('requisitos/guardar/', views.RequirementSaveAjaxView.as_view(), name='requirement_save_ajax'),

    # Document Reception
    path('recepcion/', views.LicenseReceptionListView.as_view(), name='reception_list'),
    path('recepcion/crear-modal/', views.LicenseReceptionCreateModalView.as_view(), name='reception_create_modal'),
    path('recepcion/obtener-requisitos/<int:type_id>/', views.LicenseTypeRequirementsView.as_view(),
         name='get_type_requirements'),
    path('recepcion/guardar/', views.LicenseReceptionSaveView.as_view(), name='reception_save'),
    path('recepcion/<int:pk>/estado/', views.LicenseReceptionToggleStatusView.as_view(),
         name='reception_toggle_status'),

    # Reception Workflow & Reports
    path('recepcion/<int:pk>/validar-modal/', views.LicenseReceptionValidateModalView.as_view(),
         name='reception_validate_modal'),
    path('recepcion/<int:pk>/validar-guardar/', views.LicenseReceptionValidateSaveView.as_view(),
         name='reception_validate_save'),
    path('recepcion/<int:pk>/entregar-modal/', views.LicenseReceptionDeliverModalView.as_view(),
         name='reception_deliver_modal'),
    path('recepcion/<int:pk>/entregar-guardar/', views.LicenseReceptionDeliverSaveView.as_view(),
         name='reception_deliver_save'),
    path('recepcion/remitir-modal/', views.LicenseReceptionBulkDeliverModalView.as_view(),
         name='reception_bulk_deliver_modal'),
    path('recepcion/remitir-guardar/', views.LicenseReceptionBulkDeliverSaveView.as_view(),
         name='reception_bulk_deliver_save'),
    path('recepcion/<int:pk>/detalle-modal/', views.LicenseReceptionDetailModalView.as_view(),
         name='reception_detail_modal'),
    path('recepcion/reporte/', views.LicenseReceptionReportView.as_view(), name='reception_report'),
    path('recepcion/<int:pk>/pdf/', views.LicenseReceptionPdfReportView.as_view(), name='reception_pdf_report'),
]
