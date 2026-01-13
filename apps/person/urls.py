from django.urls import path
from . import views

app_name = 'person'

urlpatterns = [
    path('list/', views.PersonListView.as_view(), name='person_list'),
    path('create/', views.PersonCreateView.as_view(), name='person_create'),
    path('update/<int:pk>/', views.PersonUpdateView.as_view(), name='person_update'),
    path('detail/<int:pk>/', views.person_detail_json, name='person_detail'),
    path('quick-view/<int:pk>/', views.person_quick_view_partial, name='person_quick_view_partial'),
]
