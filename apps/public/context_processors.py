# -*- coding: utf-8 -*-
import datetime
import json
from django.conf import settings



# 自定义上下文管理器
def settings_info(request):
    return {
        'this_year': datetime.datetime.now().year,
        'site_logo_name': settings.SITE_LOGO_NAME,
        'site_end_title': settings.SITE_END_TITLE,
        'site_description': settings.SITE_DESCRIPTION,
        'site_keywords': settings.SITE_KEYWORDS,
    }
