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

    # --- ITEMS ---
    path('settings/items/list/<int:catalog_id>/', views.item_list_json, name='item_list'),
    path('settings/items/create/', views.CatalogItemCreateView.as_view(), name='item_create'),
    path('settings/items/detail/<int:pk>/', views.item_detail_json, name='item_detail'),
    path('settings/items/update/<int:pk>/', views.CatalogItemUpdateView.as_view(), name='item_update'),
    path('settings/items/toggle/<int:pk>/', views.item_toggle_status, name='item_toggle'),

    # --- Locations ---
    path('settings/locations/', views.LocationListView.as_view(), name='location_list'),
    path('settings/locations/create/', views.LocationCreateView.as_view(), name='location_create'),
    path('settings/locations/detail/<int:pk>/', views.location_detail_json, name='location_detail'),
    path('settings/locations/update/<int:pk>/', views.LocationUpdateView.as_view(), name='location_update'),
    path('settings/locations/toggle/<int:pk>/', views.location_toggle_status, name='location_toggle'),
]
