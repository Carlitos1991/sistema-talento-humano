from django.urls import path
from . import views

app_name = 'personnel_actions'

urlpatterns = [
    path('', views.PersonnelActionListView.as_view(), name='action_list'),
    path('create/', views.PersonnelActionCreateView.as_view(), name='action_create'),

    path('types/', views.ActionTypeListView.as_view(), name='type_list'),
    path('types/create/', views.ActionTypeCreateView.as_view(), name='type_create'),
    path('types/update/<int:pk>/', views.ActionTypeUpdateView.as_view(), name='type_update'),
    path('types/toggle/<int:pk>/', views.ActionTypeToggleStatusView.as_view(), name='type_toggle'),
]
