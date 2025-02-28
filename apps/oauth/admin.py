from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Ouser

@admin.register(Ouser)
class OuserAdmin(UserAdmin):
    list_display = (
        'username', 
        'email',
        'phones',
        'is_staff', 
        'is_active', 
        'date_joined'
    )
    
    fieldsets = (
        ('基础信息', {
            'fields': (
                ('username', 'email'), 
                'profile',
                'link', 
                'avatar',
                'phones',
                'uuid'
            )
        }),
        ('权限信息', {
            'fields': (
                ('is_active', 'is_staff', 'is_superuser'),
                'groups', 
                'user_permissions'
            )
        }),
        ('重要日期', {
            'fields': (
                ('last_login', 'date_joined'),
            )
        }),
    )
    
    add_fieldsets = (
        ('用户信息', {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
            'description': '邮箱为必填项'
        }),
    )
    
    readonly_fields = ('uuid', 'last_login', 'date_joined')
    filter_horizontal = ('groups', 'user_permissions')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'email', 'phones')
    ordering = ('-date_joined',)

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return self.readonly_fields + ('is_staff', 'is_superuser', 'groups', 'user_permissions')
        return self.readonly_fields