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
from django.apps import apps
# Create your models here.



def file_upload_path(instance, filename):

    today = timezone.now().strftime('%Y/%m/%d')
    ext = filename.split('.')[-1]
    new_filename = f"{instance.id}_{timezone.now().strftime('%H%M%S')}.{ext}"
    return os.path.join('uploads', today, new_filename)

def challenge_file_upload_path(instance, filename):
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    return f'challenge_files/{instance.__class__.__name__.lower()}/{timestamp}_{filename}'


class StaticFile(models.Model):
    """静态文件模型"""
    name = models.CharField("文件名称", max_length=255)
    file = models.FileField(
        upload_to=challenge_file_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['zip', 'rar', '7z', 'tar', 'gz'])],
        verbose_name="静态文件",
        help_text="支持的压缩包格式：zip, rar, 7z, tar, gz"
    )
    description = models.TextField("文件描述", blank=True, null=True)
    file_size = models.BigIntegerField("文件大小", default=0)  # 以字节为单位
    upload_time = models.DateTimeField("上传时间", auto_now_add=True)
    download_count = models.IntegerField("下载次数", default=0)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="创建者",
        null=True,
        blank=True,
        default=None
    )


    def get_file_url(self):
        if self.file:
            return self.file.url

        return None
    
    class Meta:
        verbose_name = "题目附件管理"
        verbose_name_plural = verbose_name
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)

class DockerCompose(models.Model):
    """Docker Compose配置模型"""
    COMPOSE_TYPE_CHOICES = [
        ('MANUAL', '在线编写'),
        ('FILE', '手动上传'),
    ]
    
    name = models.CharField("名称", max_length=255)
    compose_type = models.CharField(
        "配置类型",
        max_length=10,
        choices=COMPOSE_TYPE_CHOICES,
        default='MANUAL'
    )
    compose_content = models.TextField(
        "Compose内容",
        blank=True,
        null=True,
        help_text="手动编写时填写docker-compose.yml的内容"
    )
    compose_file = models.FileField(
        upload_to=challenge_file_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['zip'])],
        blank=True,
        null=True,
        verbose_name="Compose文件",
        help_text="上传包含docker-compose.yml的zip文件"
    )
    parsed_compose = models.TextField(
        "解析后的Compose内容",
        blank=True,
        null=True,
        help_text="从上传文件解析出的docker-compose.yml内容"
    )
    flag_script = models.TextField(
        "Flag脚本命令",
        blank=True,
        null=True,
        help_text="用于生成动态flag的shell命令，例如: sh /flag.sh {flag} 或 bash -c 'echo {flag} > /flag'"
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="创建者",
        null=True,
        blank=True,
        default=None
    )
    
    class Meta:
        verbose_name = "容器镜像管理"
        verbose_name_plural = verbose_name
        
    def __str__(self):
        return f"{self.name} ({self.get_compose_type_display()})"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.compose_type == 'FILE' and self.compose_file:
            try:
                self.parsed_compose = self.parse_compose_file()
                super().save(update_fields=['parsed_compose'])
            except Exception as e:
                from django.contrib import messages
                messages.error(None, f'解析文件失败: {str(e)}')
    
    def parse_compose_file(self):
        """解析上传的compose文件"""
        import zipfile
        import yaml
        import os
        from django.core.files.storage import default_storage
        
        try:
            file_path = default_storage.path(self.compose_file.name)
            temp_dir = os.path.join(os.path.dirname(file_path), 'temp_' + os.path.basename(file_path))
            os.makedirs(temp_dir, exist_ok=True)
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            compose_file_path = None
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.lower() in ['docker-compose.yml', 'docker-compose.yaml']:
                        compose_file_path = os.path.join(root, file)
                        break
            
            if not compose_file_path:
                raise FileNotFoundError('未找到docker-compose.yml文件')
            with open(compose_file_path, 'r', encoding='utf-8') as f:
                compose_content = f.read()
                yaml.safe_load(compose_content)
                
                return compose_content
                
        except zipfile.BadZipFile:
            raise ValueError('无效的ZIP文件')
        except yaml.YAMLError:
            raise ValueError('无效的YAML格式')
        except Exception as e:
            raise ValueError(f'解析文件时发生错误: {str(e)}')
        finally:
            # 清理临时目录
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)

class Challenge(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="唯一标识符")
    CATEGORY_CHOICES = [
        ('WEB', 'Web'),
        ('MISC', '杂项'),
        ('CRYPTO', '加密'),
        ('PWN', 'Pwn'),
        ('REV', '逆向'),
        ('IOT', 'IoT'),
        ('CVE', 'CVE复现'),
        ('签到', '签到'),
        ('OTHER', '其他'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('Easy', '简单'),
        ('Medium', '中等'),
        ('Hard', '困难'),
    ]
    
    FLAG_TYPE_CHOICES = [
        ('STATIC', '静态Flag'),
        ('DYNAMIC', '动态flag'),
    ]

   
    
    DEPLOYMENT_CHOICES = [
        ('STATIC', '静态文件部署'),
        ('COMPOSE', 'Docker Compose部署'),
    ]
    
    title = models.CharField(max_length=255, verbose_name="题目标题")
    description = models.TextField(verbose_name="题目描述")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='WEB', verbose_name="题目类型")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='Medium', verbose_name="难度")
    flag_type = models.CharField(max_length=20, choices=FLAG_TYPE_CHOICES, default='DYNAMIC', verbose_name="Flag类型")
    initial_points = models.IntegerField(default=500, verbose_name="初始分数")
    minimum_points = models.IntegerField(default=100, verbose_name="最低分数")
    points = models.IntegerField(default=500, verbose_name="当前分数")
    solves = models.IntegerField(default=0, verbose_name="解决次数")
    flag_template = models.CharField(max_length=255, verbose_name="Flag值", blank=True, null=True,help_text="静态的FLAG值的模板")
    static_files = models.ForeignKey(
        StaticFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="题目附件",
        help_text="选择要使用的题目附件"
    )
    
    docker_compose = models.ForeignKey(
        DockerCompose,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="容器配置",
        help_text="选择Docker容器配置"
    )
    hint = models.TextField(blank=True, null=True, verbose_name="提示")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    is_practice = models.BooleanField(default=True, verbose_name="是否允许评论")
    tags = models.ManyToManyField('Tag',blank=True,verbose_name='标签')
    is_top = models.BooleanField('置顶', default=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "题目管理"
        verbose_name_plural = "题目管理"

    def __str__(self):
        tag_names = ', '.join([tag.name for tag in self.tags.all()]) if self.tags.exists() else '无标签'
        return f"{self.title} ({self.category}) - [{tag_names}]"
    
    def get_absolute_url(self):
    # 获取与此挑战关联的第一个比赛
        competition = self.competition_set.first()
        
        if competition:
            return reverse('public:challenge_detail', kwargs={
                'slug': competition.slug,
                'uuid': self.uuid
            })
    
    # 如果没有关联的比赛，可以返回到挑战列表页面
        return reverse('public:challenge_list')  # 假设有这个URL

    def save(self, *args, **kwargs):
        self.description = escape_xss(self.description)
        #self.hint = sanitize_html(self.hint)
        super().save(*args, **kwargs)
    
    def calculate_dynamic_points(self):
        """
        计算动态分数
        公式: points = max(minimum_points, initial_points * (3 + min(solve_count, 1)) / (3 + solve_count))
        
        特点:
        1. 首个解题者获得100%的初始分数
        2. 随着解题人数增加，分数逐渐降低
        3. 分数不会低于最低分数
        4. 分数曲线平滑，避免陡降
        """
        if self.solves == 0:
            return self.initial_points
            
        points = int(self.initial_points * (3 + min(1, self.solves)) / (3 + self.solves))
        return max(self.minimum_points, points)
    
    def update_points(self):
        """更新题目分数并更新所有已解题用户/团队的分数（优化版）"""
        from django.db import transaction

        ScoreTeam = apps.get_model('competition', 'ScoreTeam')
        ScoreUser = apps.get_model('competition', 'ScoreUser')
        new_points = self.calculate_dynamic_points()
        point_difference = new_points - self.points  # 计算分数差值

        if point_difference == 0:  
            return
        self.points = new_points
        self.save(update_fields=['points'])
        competitions = self.competition_set.all()

        with transaction.atomic():  
            for competition in competitions:
                if competition.competition_type == 'team':
                    # 批量更新团队分数
                    ScoreTeam.objects.filter(
                        competition=competition,
                        solved_challenges=self
                    ).update(score=F('score') + point_difference)
                    
                    # 批量更新团队成员的个人分数
                    ScoreUser.objects.filter(
                        competition=competition,
                        team__in=ScoreTeam.objects.filter(
                            competition=competition,
                            solved_challenges=self
                        ).values('team'),
                        solved_challenges=self
                    ).update(points=F('points') + point_difference)
                    
                    # 批量更新团队排名
                    teams = ScoreTeam.objects.filter(competition=competition).order_by('-score')
                    teams_to_update = []
                    for i, team in enumerate(teams, 1):
                        team.rank = i
                        teams_to_update.append(team)
                    
                    if teams_to_update:
                        ScoreTeam.objects.bulk_update(teams_to_update, ['rank'])
                    
                    # 批量更新用户排名
                    users = ScoreUser.objects.filter(competition=competition).order_by('-points')
                    users_to_update = []
                    for i, user in enumerate(users, 1):
                        user.rank = i
                        users_to_update.append(user)
                    
                    if users_to_update:
                        ScoreUser.objects.bulk_update(users_to_update, ['rank'])
                else:
                    # 批量更新个人分数
                    ScoreUser.objects.filter(
                        competition=competition,
                        solved_challenges=self
                    ).update(points=F('points') + point_difference)
                    
                    # 批量更新用户排名
                    users = ScoreUser.objects.filter(competition=competition).order_by('-points')
                    users_to_update = []
                    for i, user in enumerate(users, 1):
                        user.rank = i
                        users_to_update.append(user)
                    
                    if users_to_update:
                        ScoreUser.objects.bulk_update(users_to_update, ['rank'])
    
    def add_solve(self):
        """增加解题次数并更新分数"""
        self.solves += 1
        self.update_points()
        self.save(update_fields=['solves'])

    def get_points_for_solve_count(self, solve_count):
        """获取指定解题次数时的分数（用于预览）"""
        if solve_count == 0:
            return self.initial_points
            
        points = int(self.initial_points * (3 + min(1, solve_count)) / (3 + solve_count))
        return max(self.minimum_points, points)

class Tag(models.Model):
    name = models.CharField('文章标签', max_length=20,unique=True)
    description = models.TextField('描述', max_length=240, default='标签描述',
                                   help_text='用来作为SEO中description,长度参考SEO标准')

    class Meta:
        verbose_name = '标签'
        verbose_name_plural = verbose_name
        ordering = ['id']

    def __str__(self):
        return self.name

    def get_Challenge_list(self):
        """"""
        return Challenge.objects.filter(tags=self, is_active=True)
    

