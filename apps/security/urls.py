# apps/security/urls.py
from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    #  Usuarios
    path('users/list/', views.UserListView.as_view(), name='user_list'),

    # Roles
    path('roles/list/', views.RoleListView.as_view(), name='role_list'),
    path('roles/create/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/update/<int:pk>/', views.RoleUpdateView.as_view(), name='role_update'),

    # Credenciales
    path('users/create-credentials/<int:person_id>/', views.CreateUserForPersonView.as_view(),
         name='user_create_credentials'),
    path('users/toggle/<int:pk>/', views.UserToggleStatusView.as_view(), name='user_toggle_status'),
]
