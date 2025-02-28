from django.contrib import admin
from .models import DockerEngine,UserContainer
from django.utils.html import format_html

from django import forms



@admin.register(DockerEngine)
class DockerEngineAdmin(admin.ModelAdmin):
    list_display = ('name', 'host_type', 'host_info', 'resource_limits', 
                    'tls_status', 'is_active', 'created_at')
    list_filter = ('host_type', 'tls_enabled', 'is_active')
    search_fields = ('name', 'host', 'domain')
    readonly_fields = ('created_at', 'updated_at')

    def get_fieldsets(self, request, obj=None):
        """根据主机类型动态调整字段集"""
        if obj and obj.host_type == 'LOCAL':
            return (
                ('基本信息', {
                    'fields': (
                        'name', 
                        'host_type',
                        'host',
                        'is_active'
                    )
                }),
                ('资源限制', {
                    'fields': (
                        'memory_limit',
                        'cpu_limit',
                    )
                }),
                ('时间信息', {
                    'classes': ('collapse',),
                    'fields': (
                        'created_at',
                        'updated_at',
                    )
                }),
            )
        return (
            ('基本信息', {
                'fields': (
                    'name', 
                    'host_type',
                    'host',
                    'port',
                    'domain',
                    'is_active'
                )
            }),
            ('TLS配置', {
                'classes': ('collapse',),
                'fields': (
                    'tls_enabled',
                    'ca_cert',
                    'client_cert',
                    'client_key',
                )
            }),
            ('资源限制', {
                'fields': (
                    'memory_limit',
                    'cpu_limit',
                )
            }),
            ('时间信息', {
                'classes': ('collapse',),
                'fields': (
                    'created_at',
                    'updated_at',
                )
            }),
        )

    def host_info(self, obj):
        """显示主机信息"""
        if obj.host_type == 'LOCAL':
            return 'Unix Socket'
        return format_html(
            '{} : {}',
            obj.host,
            obj.port
        )
    host_info.short_description = '主机信息'

    def resource_limits(self, obj):
        """显示资源限制"""
        return format_html(
            'CPU: {}核 / 内存: {}MB',
            obj.cpu_limit,
            obj.memory_limit
        )
    resource_limits.short_description = '资源限制'

    def tls_status(self, obj):
        """显示TLS状态"""
        if not obj.tls_enabled:
            return format_html(
                '<span style="color: gray;">未启用</span>'
            )
        if obj.ca_cert and obj.client_cert and obj.client_key:
            return format_html(
                '<span style="color: green;">配置完整</span>'
            )
        return format_html(
            '<span style="color: red;">配置不完整</span>'
        )
    tls_status.short_description = 'TLS状态'

    def save_model(self, request, obj, form, change):
        """保存模型时的额外处理"""
        if not obj.tls_enabled:
            # 如果禁用TLS，清除证书字段
            obj.ca_cert = None
            obj.client_cert = None
            obj.client_key = None
        super().save_model(request, obj, form, change)
    
@admin.register(UserContainer)
class UserContainerAdmin(admin.ModelAdmin):
    list_display = ('user', 'challenge', 'docker_engine', 'ip_address', 'port', 'domain', 'created_at', 'expires_at')
    list_filter = ('docker_engine', 'created_at', 'expires_at')
    search_fields = ('user__username', 'challenge__title', 'container_id')
    readonly_fields = ('created_at',)