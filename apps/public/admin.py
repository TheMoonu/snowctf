from django.contrib import admin
from django.conf import settings
# Register your models here.
admin.site.site_header = f'{settings.SITE_LOGO_NAME}后台管理'  # 设置header
admin.site.site_title = f'{settings.SITE_LOGO_NAME}后台管理'   # 设置title
admin.site.index_title = f'{settings.SITE_LOGO_NAME}后台管理'
