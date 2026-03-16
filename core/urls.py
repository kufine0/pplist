from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('', views.dashboard, name='dashboard'),

    path('cache/', views.cache_management, name='cache_management'),
    path('logs/', views.log_viewer, name='log_viewer'),

    path('clerk/login/', views.clerk_login, name='clerk_login'),
    path('clerk/logout/', views.clerk_logout, name='clerk_logout'),
    path('clerk/', views.clerk_dashboard, name='clerk_dashboard'),
    path('clerk/purchase/', views.clerk_create_purchase, name='clerk_create_purchase'),
    path('clerk/ajax/search-products/', views.clerk_search_products, name='clerk_search_products'),
    path('clerk/ajax/api-status/', views.clerk_api_status, name='clerk_api_status'),
]
