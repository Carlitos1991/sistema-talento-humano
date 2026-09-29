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

    path('catalogs/', views.CatalogListView.as_view(), name='catalog_list'),
    path('catalogs/modal/form/', views.CatalogModalFormView.as_view(), name='catalog_modal_create'),
    path('catalogs/modal/form/<int:pk>/', views.CatalogModalFormView.as_view(), name='catalog_modal_update'),
    path('catalogs/create/', views.CatalogCreateView.as_view(), name='catalog_create'),
    path('catalogs/update/<int:pk>/', views.CatalogUpdateView.as_view(), name='catalog_update'),
    path('catalogs/toggle/<int:pk>/', views.CatalogToggleStatusView.as_view(), name='catalog_toggle'),

    # Ítems
    path('catalogs/<int:catalog_id>/items/modal/', views.CatalogItemListModalView.as_view(),
         name='catalog_items_modal_list'),
    path('catalogs/<int:catalog_id>/items/form/', views.CatalogItemModalFormView.as_view(),
         name='catalog_item_modal_create'),
    path('catalogs/<int:catalog_id>/items/form/<int:pk>/', views.CatalogItemModalFormView.as_view(),
         name='catalog_item_modal_update'),
    path('catalogs/<int:catalog_id>/items/create/', views.CatalogItemCreateView.as_view(), name='catalog_item_create'),
    path('catalogs/items/update/<int:pk>/', views.CatalogItemUpdateView.as_view(), name='catalog_item_update'),
    path('catalogs/items/toggle/<int:pk>/', views.CatalogItemToggleStatusView.as_view(), name='catalog_item_toggle'),

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
