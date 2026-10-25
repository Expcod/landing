from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'panel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='panel/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/panel/login/'), name='logout'),
    path('password/', views.password, name='password'),

    path('leads/', views.leads, name='leads'),
    path('leads/export.csv', views.leads_csv, name='leads_csv'),
    path('leads/<int:pk>/', views.lead_detail, name='lead'),
    path('leads/<int:pk>/status/', views.lead_status, name='lead_status'),

    path('reports/', views.reports, name='reports'),

    path('content/<slug:kind>/', views.content_list, name='content'),
    path('content/<slug:kind>/new/', views.content_edit, name='content_new'),
    path('content/<slug:kind>/reorder/', views.content_reorder, name='content_reorder'),
    path('content/<slug:kind>/<int:pk>/', views.content_edit, name='content_edit'),
    path('content/<slug:kind>/<int:pk>/delete/', views.content_delete, name='content_delete'),
    path('content/<slug:kind>/<int:pk>/toggle/', views.content_toggle, name='content_toggle'),

    path('telegram/', views.telegram, name='telegram'),
    path('settings/', views.settings_view, name='settings'),
    path('users/', views.users, name='users'),
    path('users/new/', views.user_edit, name='user_new'),
    path('users/<int:pk>/', views.user_edit, name='user'),
]
