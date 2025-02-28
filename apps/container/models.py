from django.db import models, transaction
from django.urls import reverse
import uuid
from django.conf import settings
from django.contrib.auth.models import User
from .utils import sanitize_html,escape_xss
import math
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import FileExtensionValidator,RegexValidator
from docker.tls import TLSConfig
import time
from django.db.models import F
import os
from django.utils import timezone

def certificate_upload_path(instance, filename):
    # 使用时间戳生成唯一文件名
    timestamp = int(time.time())
    return f'certificates/{timestamp}_{filename}'

class DockerEngine(models.Model):
    HOST_CHOICES = [
        ('LOCAL', '本地模式'),
        ('REMOTE', '远程模式'),
    ]
    
    name = models.CharField("引擎名称", max_length=100)
    host_type = models.CharField("主机类型", max_length=6, choices=HOST_CHOICES, default='LOCAL')
    host = models.CharField("主机地址", max_length=200,  blank=True, null=True,default="localhost")
    port = models.IntegerField("端口", blank=True, null=True, default=None, help_text="本地模式不需要填写" )
    tls_enabled = models.BooleanField("启用TLS", default=False, help_text="本地模式不需要填写" )
    domain = models.CharField("域名", max_length=255, default=None, blank=True, null=True)  
    ca_cert = models.FileField(
        "CA证书",
        upload_to=certificate_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['pem', 'crt'])],
        blank=True,
        null=True
    )
    client_cert = models.FileField(
        "客户端证书",
        upload_to=certificate_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['pem', 'crt'])],
        blank=True,
        null=True
    )
    client_key = models.FileField(
        "客户端密钥",
        upload_to=certificate_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['pem', 'key'])],
        blank=True,
        null=True
    )
    memory_limit = models.IntegerField("内存限制(MB)")
    cpu_limit = models.FloatField("CPU限制")
    is_active = models.BooleanField("是否激活", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "Docker引擎"
        verbose_name_plural = "Docker引擎"

    def get_docker_url(self):
        if self.host_type == 'LOCAL':
            return "unix:///var/run/docker.sock"
        else:
            return f"tcp://{self.host}:{self.port}"

    def __str__(self):
        return self.name
    
    

    @property
    def url(self):
        protocol = "https" if self.needs_tls else "http"
        return f"{protocol}://{self.host}:{self.port}"

    @property
    def needs_tls(self):
        return self.host_type == 'REMOTE' and self.tls_enabled
    
    def get_cert_path(self, cert_field):
        if cert_field and cert_field.name:
            return cert_field.path
        return None

    @property
    def ca_cert_path(self):
        return self.get_cert_path(self.ca_cert)

    @property
    def client_cert_path(self):
        return self.get_cert_path(self.client_cert)

    @property
    def client_key_path(self):
        return self.get_cert_path(self.client_key)
    
    def get_tls_config(self):
        if self.tls_enabled:
            return TLSConfig(
                ca_cert=self.ca_cert_path,
                client_cert=(self.client_cert_path, self.client_key_path),
                verify=True
            )
        return None
    
class UserContainer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="用户")
    challenge = models.ForeignKey('challenge.Challenge', on_delete=models.CASCADE, verbose_name="题目")
    challenge_uuid = models.UUIDField("挑战UUID", default=uuid.uuid4, editable=False)
    docker_engine = models.ForeignKey(DockerEngine, on_delete=models.CASCADE, verbose_name="Docker引擎")
    container_id = models.CharField("容器ID", max_length=64)
    ip_address = models.GenericIPAddressField("IP地址", null=True, blank=True)
    domain = models.CharField("域名", max_length=255, default=None, blank=True, null=True) 
    port = models.TextField("端口", blank=True, null=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    expires_at = models.DateTimeField("过期时间")
    
    def get_expiration_time(self):
        lifecycle_duration = timedelta(hours=2)  # 可以根据实际情况调整生命周期
        return self.created_at + lifecycle_duration

    def is_expired(self):
        # 检查容器是否过期
        return timezone.now() > self.get_expiration_time()

    class Meta:
        verbose_name = "容器日志"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} - {self.challenge.title} - {self.container_id}"
