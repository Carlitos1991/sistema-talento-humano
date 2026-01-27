from django.urls import path
from . import views

app_name = 'personnel_actions'

urlpatterns = [
    path('', views.PersonnelActionListView.as_view(), name='action_list'),
    path('create/', views.PersonnelActionCreateView.as_view(), name='action_create'),
    # path('update/<int:pk>/', ...),
]