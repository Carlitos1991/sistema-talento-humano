from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    #  Usuarios
    path('users/list/', views.UserListView.as_view(), name='user_list'),
    path('users/control/', views.UserControlListView.as_view(), name='user_control_list'),

    # Roles
    path('roles/list/', views.RoleListView.as_view(), name='role_list'),
    path('roles/create/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/update/<int:pk>/', views.RoleUpdateView.as_view(), name='role_update'),

    # Ayuda / Mensajería
    path('help/messages/', views.HelpMessageListView.as_view(), name='help_message_list'),
    path('help/messages/create/', views.HelpMessageCreateView.as_view(), name='help_message_create'),
    path('help/messages/<int:pk>/mark-read/', views.HelpMessageMarkReadView.as_view(), name='help_message_mark_read'),
    path('help/messages/<int:pk>/reply/', views.HelpMessageReplyView.as_view(), name='help_message_reply'),
    path('help/messages/<int:pk>/correction/', views.HelpMessageCorrectionView.as_view(), name='help_message_correction'),
    path('help/messages/<int:pk>/sumilla/', views.HelpMessageSumillaView.as_view(), name='help_message_sumilla'),
    path('help/messages/<int:pk>/mark-attended/', views.HelpMessageMarkAttendedView.as_view(), name='help_message_mark_attended'),
    path('help/messages/<int:pk>/finalize/', views.HelpMessageFinalizeByInitiatorView.as_view(), name='help_message_finalize'),

    # Credenciales
    path('users/create-credentials/<int:person_id>/', views.CreateUserForPersonView.as_view(),
         name='user_create_credentials'),
    path('users/toggle/<int:pk>/', views.UserToggleStatusView.as_view(), name='user_toggle_status'),
    
    # API
    path('api/update-session-info/', views.UpdateSessionInfoView.as_view(), name='update_session_info'),
]
