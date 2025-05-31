# urls.py
from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Inscription et vérification
    path('register/', views.register, name='register'),
    path('verify-phone/', views.verify_phone, name='verify_phone'),
    path('resend-code/', views.resend_code, name='resend_code'),
    
    # Gestion du code PIN
    path('create-pin/', views.create_pin, name='create_pin'),
    path('verify-pin/', views.verify_pin, name='verify_pin'),
    
    # Authentification
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    
    # Profil utilisateur
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('auth-status/', views.auth_status, name='auth_status'),
    path('update-background-time/', views.update_background_time, name='update_background_time'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('testblacklist/', views.test_blacklist, name='test_blacklist'),
]