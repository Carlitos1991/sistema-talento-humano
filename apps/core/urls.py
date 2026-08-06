from django.contrib.auth import views as auth_views
from django.urls import path, include

from . import views

app_name = 'core'

urlpatterns = [
    # Login propio (formulario local que valida contra Keycloak vía ROPC)
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('create-user/', views.CreateUserFromLoginView.as_view(), name='create_user_from_login'),

    # Login SSO por redirect a Keycloak (flujo aparte, sigue disponible en /oidc/)
    path('oidc/', include('mozilla_django_oidc.urls')),

    # Logout
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),

    # Dashboard (Home)
    path('', views.DashboardView.as_view(), name='dashboard'),

    # Perfil de Usuario
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
    path('api/locations/', views.LocationJsonView.as_view(), name='location_list_json'),
    # --- System Configuration ---
    path('settings/letterhead/', views.SystemLetterheadView.as_view(), name='system_letterhead'),
]
