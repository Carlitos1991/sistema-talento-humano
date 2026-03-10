from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('accounts/', views.AccountListView.as_view(), name='account_list'),
    path('accounts/add/', views.AccountCreateView.as_view(), name='account_add'),
    path('accounts/<int:pk>/edit/', views.AccountUpdateView.as_view(), name='account_edit'),
    path('accounts/<int:pk>/delete/', views.AccountDeleteView.as_view(), name='account_delete'),
    path('journals/', views.JournalListView.as_view(), name='journal_list'),
    path('journals/<int:pk>/', views.JournalDetailView.as_view(), name='journal_detail'),
    path('journals/<int:pk>/export/', views.JournalExportView.as_view(), name='journal_export'),
]
