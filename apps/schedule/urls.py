from django.urls import path
from . import views

app_name = 'schedule'

urlpatterns = [
    path('list/', views.ScheduleListView.as_view(), name='schedule_list'),
    path('partial-table/', views.ScheduleTablePartialView.as_view(), name='schedule_partial_table'),
    path('detail/<int:pk>/', views.ScheduleDetailAPIView.as_view(), name='schedule_detail_api'),
    path('create/', views.ScheduleCreateView.as_view(), name='schedule_create'),
    path('update/<int:pk>/', views.ScheduleUpdateView.as_view(), name='schedule_update'),
    path('activate/<int:pk>/', views.ScheduleActivateView.as_view(), name='schedule_activate'),
    path('deactivate/<int:pk>/', views.ScheduleDeactivateView.as_view(), name='schedule_deactivate'),
    path('observations/', views.ObservationListView.as_view(), name='observation_list'),
    path('observations/partial-table/', views.ObservationTablePartialView.as_view(), name='observation_partial_table'),
    path('observations/create/', views.ObservationCreateView.as_view(), name='observation_create'),
    path('observations/detail/<int:pk>/', views.ObservationDetailAPIView.as_view(), name='observation_detail_api'),
    path('observations/toggle-status/<int:pk>/', views.ObservationToggleStatusView.as_view(),
         name='observation_toggle_status'),
]
