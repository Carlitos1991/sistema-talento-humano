from django.urls import path
from . import views
from .views import UserSearchAjaxView

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
    path('notification-types/create/', views.SanctionNotificationTypeCreateView.as_view(),
         name='notification_type_create'),
    path('notification-types/update/<int:pk>/', views.SanctionNotificationTypeUpdateView.as_view(),
         name='notification_type_update'),
    path('notification-types/toggle/<int:pk>/', views.SanctionNotificationTypeToggleView.as_view(),
         name='notification_type_toggle'),
    path('notification-types/preview/<int:pk>/', views.SanctionNotificationTypePreviewView.as_view(),
         name='notification_type_preview'),
    path('notification-types/help/', views.SanctionNotificationTypeHelpView.as_view(), name='notification_type_help'),
    path('notifications/generate/', views.GenerateSanctionNotificationView.as_view(), name='generate_notification'),
    path('notifications/preview/', views.SanctionNotificationPreviewView.as_view(), name='notification_preview'),
    path('notifications/list/', views.SanctionNotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/pdf/', views.SanctionNotificationPdfView.as_view(), name='notification_pdf'),

    # --- Employee List to Generate Sanctions ---
    path('employees/', views.EmployeeSanctionListView.as_view(), name='sanction_employee_list'),
    # --- Sanction History ---
    path('history/', views.SanctionHistoryListView.as_view(), name='sanction_history'),

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
    path('personnel-action/<int:pk>/edit/', views.EditSanctionPersonnelActionView.as_view(), name='edit_sanction_personnel_action'),

    # --- Template Editor (Dynamic Templates) ---
    path('templates/create/<int:type_id>/<int:regime_id>/', views.TemplateEditorCreateView.as_view(),
         name='template_editor_create'),
    path('templates/editor/<int:pk>/', views.TemplateEditorDetailView.as_view(), name='template_editor_detail'),
    path('templates/<int:template_id>/sections/create/', views.TemplateSectionCreateAjaxView.as_view(),
         name='template_section_create'),
    path('templates/sections/<int:section_id>/update/', views.TemplateSectionUpdateAjaxView.as_view(),
         name='template_section_update'),
    path('templates/sections/<int:section_id>/delete/', views.TemplateSectionDeleteAjaxView.as_view(),
         name='template_section_delete'),
    path('templates/<int:template_id>/sections/reorder/', views.TemplateSectionReorderAjaxView.as_view(),
         name='template_section_reorder'),
    path('templates/<int:template_id>/preview/', views.TemplatePreviewAjaxView.as_view(), name='template_preview'),
    path('notifications/<int:pk>/toggle-response/', views.SanctionNotificationToggleResponseView.as_view(),
         name='notification_toggle_response'),
    path('users/search/', UserSearchAjaxView.as_view(), name='user_search_ajax'),
    path('notifications/assign/', views.AssignNotificationAjaxView.as_view(), name='assign_notification_bulk'),
    path('assign-ajax/', views.AssignNotificationAjaxView.as_view(), name='assign_notification_ajax'),
    path('notifications/massive-return/', views.MassiveReturnNotificationView.as_view(),
         name='massive_return_notifications'),
    path('notifications/<int:pk>/archive/', views.ArchiveNotificationView.as_view(), name='notification_archive'),
    path('notifications/<int:pk>/route/', views.NotificationRouteHistoryAjaxView.as_view(),
         name='notification_route_history'),
    
    # --- History AJAX Views ---
    path('history/sanction-ajax/', views.SanctionHistoryAjaxView.as_view(), name='sanction_history_ajax'),
    path('history/actions-ajax/', views.ActionsHistoryAjaxView.as_view(), name='actions_history_ajax'),
     path('history/notifications-ajax/', views.NotificationHistoryAjaxView.as_view(), name='notification_history_ajax'),
]
