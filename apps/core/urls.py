from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'core'

urlpatterns = [
    # Login Personalizado
    path('login/', views.CustomLoginView.as_view(), name='login'),

    # Logout (Redirige al login)
    path('logout/', auth_views.LogoutView.as_view(next_page='core:login'), name='logout'),

    # Dashboard (Protegido)
    path('', views.DashboardView.as_view(), name='dashboard'),
]