from django.contrib import admin
from .models import CustomUser, PhoneVerification, UserSession
from django.contrib.auth.admin import UserAdmin


# Register your models here.
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('phone_number', 'full_name', 'is_phone_verified', 'has_pin_code', 'date_joined', 'is_active')
    list_filter = ('is_phone_verified', 'has_pin_code', 'is_active', 'date_joined')
    search_fields = ('phone_number', 'full_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Informations personnelles', {'fields': ('full_name', 'profile_picture')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Vérifications', {'fields': ('is_phone_verified', 'has_pin_code')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined', 'last_pin_entry')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'full_name', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login', 'last_pin_entry')

@admin.register(PhoneVerification)
class PhoneVerificationAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'full_name', 'verification_code', 'is_verified', 'created_at', 'expires_at', 'attempts')
    list_filter = ('is_verified', 'created_at', 'expires_at')
    search_fields = ('phone_number', 'full_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'expires_at', 'verification_code')
    
    def has_change_permission(self, request, obj=None):
        # Empêcher la modification des vérifications
        return False

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_active', 'created_at', 'last_activity')
    list_filter = ('is_active', 'created_at', 'last_activity')
    search_fields = ('user__phone_number', 'user__full_name')
    ordering = ('-last_activity',)
    readonly_fields = ('created_at', 'last_activity', 'jwt_token')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
