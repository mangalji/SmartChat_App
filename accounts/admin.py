from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, OTP


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering         = ['email']
    list_display     = ['email', 'full_name', 'phone', 'is_verified', 'is_staff', 'date_joined']
    list_filter      = ['is_verified', 'is_staff', 'is_active']
    search_fields    = ['email', 'full_name', 'phone']
    readonly_fields  = ['date_joined', 'last_login']

    fieldsets = (
        (None,         {'fields': ('email', 'password')}),
        ('Personal',   {'fields': ('full_name', 'phone', 'avatar')}),
        ('Status',     {'fields': ('is_verified', 'is_active', 'is_staff', 'is_superuser')}),
        ('Permissions',{'fields': ('groups', 'user_permissions')}),
        ('Dates',      {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields':  ('email', 'full_name', 'password1', 'password2', 'is_verified'),
        }),
    )


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display  = ['user', 'code', 'purpose', 'is_used', 'created_at']
    list_filter   = ['purpose', 'is_used']
    search_fields = ['user__email', 'code']
    readonly_fields = ['created_at']
