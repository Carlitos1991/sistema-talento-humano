# apps/core/urls.py
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'core'

urlpatterns = [
    # Login Personalizado
    path('login/', views.CustomLoginView.as_view(), name='login'),

    # Logout
    path('logout/', auth_views.LogoutView.as_view(next_page='core:login'), name='logout'),

    # Dashboard (Home)
    path('', views.DashboardView.as_view(), name='dashboard'),

    # Perfil de Usuario (NUEVO)
    path('profile/', views.ProfileView.as_view(), name='profile'),
    # --- Catalogs ---
    path('settings/catalogs/', views.CatalogListView.as_view(), name='catalog_list'),
]
