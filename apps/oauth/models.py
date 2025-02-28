import os
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill
from django.core.validators import FileExtensionValidator
from django.conf import settings
from django.utils.html import strip_tags
import random
import bleach
import string
from django.utils import timezone 
from datetime import timedelta,datetime
from django.contrib.sessions.models import Session

class Ouser(AbstractUser):
    email = models.EmailField(unique=True, verbose_name='电子邮件', blank=False)
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='用户组',
        blank=True,
        help_text='用户所属的组',
        related_name='custom_user_set',  
        related_query_name='custom_user'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='用户权限',
        blank=True,
        help_text='用户的特定权限',
        related_name='custom_user_set', 
        related_query_name='custom_user'
    )
    
    link = models.URLField('个人网址', blank=True, help_text='提示：网址必须填写以http开头的完整形式')
    avatar = ProcessedImageField(upload_to='avatar/upload/%Y/%m/%d/%H-%M-%S',
                                 default='avatar/default/default.png',
                                 verbose_name='头像',
                                 processors=[ResizeToFill(80, 80)],
                                 validators=[
                                        FileExtensionValidator(
                                            allowed_extensions=['jpg', 'jpeg', 'png', 'gif'],
                                            message='只支持jpg、jpeg、png、gif格式的图片'
                                        )
                                ],
                                )
    uuid = models.UUIDField('UUID', default=uuid.uuid4, editable=False, unique=True)
    phones = models.CharField('手机号', max_length=11, blank=True, null=True)
    profile = models.TextField('个人简介', blank=True, null=True, max_length=100,help_text='提示：个人简介字数限制在100字以内')

    

    
    

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = verbose_name
        ordering = ['-id']

    def __str__(self):
        return self.username


    def clean_profile(self):
        """清理个人简介内容"""
        if self.profile:
            # 首先去除所有HTML标签
            cleaned_text = strip_tags(self.profile)
            
            # 使用bleach清理内容，只允许基本的HTML标签
            allowed_tags = []  # 不允许任何HTML标签
            allowed_attributes = {}  # 不允许任何属性
            allowed_protocols = ['http', 'https', 'mailto']  # 允许的URL协议
            
            cleaned_text = bleach.clean(
                cleaned_text,
                tags=allowed_tags,
                attributes=allowed_attributes,
                protocols=allowed_protocols,
                strip=True,
                strip_comments=True
            )
            
            # 截断到最大长度
            if len(cleaned_text) > 100:
                cleaned_text = cleaned_text[:100]
            
            return cleaned_text
        return ''

    def save(self, *args, **kwargs):
        # 清理个人简介
        self.profile = self.clean_profile()           
        super().save(*args, **kwargs)
    