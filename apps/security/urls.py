# apps/security/urls.py
from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    # Roles
    path('roles/create/', views.RoleCreateView.as_view(), name='role_create'),

    # Credenciales (Ojo al nombre para usarlo en el JS de person)
    path('users/create-credentials/<int:person_id>/', views.CreateUserForPersonView.as_view(),
         name='user_create_credentials'),
]
