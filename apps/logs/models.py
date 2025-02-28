from django.db import models
from django.conf import settings
# Create your models here.
class Log(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,verbose_name="用户ID")  
    message = models.TextField('日志信息')  # 日志信息
    timestamp = models.DateTimeField('日志创建时间',auto_now_add=True)  # 日志创建时间
    log_type = models.CharField('日志类型',max_length=50, choices=[('info', '信息'), ('error', '错误'), ('warning', '警告')])   # 日志类型

    class Meta:
        verbose_name = "系统日志"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.team.name} - {self.log_type}: {self.message}"