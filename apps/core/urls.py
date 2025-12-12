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
    path('settings/catalogs/create/', views.CatalogCreateView.as_view(), name='catalog_create'),
    path('settings/catalogs/detail/<int:pk>/', views.catalog_detail_json, name='catalog_detail'),
    path('settings/catalogs/update/<int:pk>/', views.CatalogUpdateView.as_view(), name='catalog_update'),
    path('settings/catalogs/toggle/<int:pk>/', views.catalog_toggle_status, name='catalog_toggle'),

    #     items
    path('settings/items/create/', views.CatalogItemCreateView.as_view(), name='item_create'),
]
