from django.urls import path
from . import views

app_name = 'sanctions'

urlpatterns = [
    # --- Sanction Types (Configuration) ---
    path('types/', views.SanctionTypeListView.as_view(), name='sanction_type_list'),
    path('types/create/', views.SanctionTypeCreateView.as_view(), name='sanction_type_create'),
    path('types/update/<int:pk>/', views.SanctionTypeUpdateView.as_view(), name='sanction_type_update'),
    path('types/delete/<int:pk>/', views.SanctionTypeDeleteView.as_view(), name='sanction_type_delete'),
    path('types/toggle/<int:pk>/', views.SanctionTypeToggleView.as_view(), name='sanction_type_toggle'),

    # --- Notification Types (Configuration) ---
    path('notification-types/', views.SanctionNotificationTypeListView.as_view(), name='notification_type_list'),
    path('notification-types/create/', views.SanctionNotificationTypeCreateView.as_view(), name='notification_type_create'),
    path('notification-types/update/<int:pk>/', views.SanctionNotificationTypeUpdateView.as_view(), name='notification_type_update'),
    path('notification-types/toggle/<int:pk>/', views.SanctionNotificationTypeToggleView.as_view(), name='notification_type_toggle'),
    path('notification-types/preview/<int:pk>/', views.SanctionNotificationTypePreviewView.as_view(), name='notification_type_preview'),
    path('notification-types/help/', views.SanctionNotificationTypeHelpView.as_view(), name='notification_type_help'),
    path('notification-types/template/<int:link_id>/download/', views.SanctionNotificationTypeTemplateDownloadView.as_view(), name='notification_type_template_download'),
    path('notifications/generate/', views.GenerateSanctionNotificationView.as_view(), name='generate_notification'),
    path('notifications/preview/', views.SanctionNotificationPreviewView.as_view(), name='notification_preview'),
    path('notifications/list/', views.SanctionNotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/pdf/', views.SanctionNotificationPdfView.as_view(), name='notification_pdf'),

    # --- Employee List to Generate Sanctions ---
    path('employees/', views.EmployeeSanctionListView.as_view(), name='sanction_employee_list'),

    # --- Sanction Creation ---
    path('generate/', views.GenerateSanctionFormView.as_view(), name='generate_sanction'),
    
    # --- Sanction Administration ---
    path('admin/', views.SanctionAdminListView.as_view(), name='sanction_admin'),
    path('admin/employee/<int:employee_id>/', views.SanctionAdminListView.as_view(), name='sanction_admin_by_employee'),
    path('admin/<int:pk>/detail/', views.SanctionDetailView.as_view(), name='sanction_detail'),
    path('admin/<int:pk>/update-status/', views.SanctionUpdateStatusView.as_view(), name='sanction_update_status'),
    path('admin/<int:pk>/edit/', views.EditSanctionView.as_view(), name='sanction_edit'),
    path('admin/<int:pk>/register/', views.RegisterSanctionView.as_view(), name='sanction_register'),
    path('admin/<int:pk>/pdf/', views.SanctionPDFView.as_view(), name='sanction_pdf'),

    # --- Template Editor (Dynamic Templates) ---
    path('templates/editor/<int:pk>/', views.TemplateEditorDetailView.as_view(), name='template_editor_detail'),
    path('templates/<int:template_id>/sections/create/', views.TemplateSectionCreateAjaxView.as_view(), name='template_section_create'),
    path('templates/sections/<int:section_id>/update/', views.TemplateSectionUpdateAjaxView.as_view(), name='template_section_update'),
    path('templates/sections/<int:section_id>/delete/', views.TemplateSectionDeleteAjaxView.as_view(), name='template_section_delete'),
    path('templates/<int:template_id>/sections/reorder/', views.TemplateSectionReorderAjaxView.as_view(), name='template_section_reorder'),
    path('templates/<int:template_id>/preview/', views.TemplatePreviewAjaxView.as_view(), name='template_preview'),
]
