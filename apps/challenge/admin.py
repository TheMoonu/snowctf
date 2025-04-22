from django.contrib import admin
from .models import Challenge, Tag, StaticFile, DockerCompose
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count

@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'difficulty', 'points', 'solves', 
                   'is_practice', 'is_active', 'is_top', 'created_at', 'author')
    list_filter = ('category', 'difficulty','is_practice', 'is_active', 'is_top')
    search_fields = ('title', 'description')
    readonly_fields = ('uuid', 'solves', 'created_at', 'updated_at', 'first_blood_user', 'first_blood_time')
    filter_horizontal = ('tags', )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('基本信息', {
            'fields': ('title', 'description', 'category', 'difficulty', 'points', 'tags', 'is_top')
        }),
        ('Flag配置', {
            'fields': ('flag_type', 'flag_template')
        }),
        ('部署配置', {
            'fields': ('static_files', 'docker_compose')
        }),
        ('其他信息', {
            'fields': ('hint', 'is_active', 'is_practice','author')
        }),
        ('统计信息', {
            'fields': ('solves', 'initial_points','minimum_points','first_blood_user', 'first_blood_time'),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        if not change:  # 如果是新建，设置作者
            obj.author = request.user
        super().save_model(request, obj, form, change)



@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'get_challenge_count')
    search_fields = ('name', 'description')

    def get_challenge_count(self, obj):
        return obj.challenge_set.count()
    get_challenge_count.short_description = '关联题目数'

@admin.register(StaticFile)
class StaticFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'file_size_display', 'download_count', 
                   'upload_time', 'author')
    search_fields = ('name', 'description')
    readonly_fields = ('file_size', 'download_count', 'upload_time')
    
    def file_size_display(self, obj):
        """将文件大小转换为人类可读格式"""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
    file_size_display.short_description = '文件大小'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)

@admin.register(DockerCompose)
class DockerComposeAdmin(admin.ModelAdmin):
    list_display = ('name', 'compose_type', 'created_at', 'updated_at', 'author')
    list_filter = ('compose_type',)
    search_fields = ('name',)
    readonly_fields = ('parsed_compose', 'created_at', 'updated_at')
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'compose_type')
        }),
        ('配置内容', {
            'fields': ('compose_content', 'compose_file', 'flag_script')
        }),
        ('解析结果', {
            'fields': ('parsed_compose',),
            'classes': ('collapse',)
        }),
        ('其他信息', {
            'fields': ('author', 'created_at', 'updated_at')
        })
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)