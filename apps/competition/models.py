from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from imagekit.models import ProcessedImageField
from challenge.models import Challenge
from imagekit.processors import ResizeToFill
import random
import string
from django.db.models import JSONField 
from django.contrib.auth.models import User 
from public.utils import clear_ranking_cache
from django.core.cache import cache

from django.db.models.signals import post_save
from django.dispatch import receiver




class Competition(models.Model):
    INDIVIDUAL = 'individual'
    TEAM = 'team'
    COMPETITION_TYPE_CHOICES = [
        (INDIVIDUAL, '个人赛'),
        (TEAM, '团体赛'),
    ]

    title = models.CharField('比赛标题', max_length=255)
    description = models.TextField('比赛描述')
    img_link = ProcessedImageField(
        upload_to='competition/upload/%Y/%m/%d/',
        default='public/default/default.png',
        verbose_name='封面图',
        processors=[ResizeToFill(250, 150)],
        blank=True,
        help_text='上传图片大小建议使用5:3的宽高比，为了清晰度原始图片宽度应该超过250px'
    )
    start_time = models.DateTimeField('比赛开始时间')
    end_time = models.DateTimeField('比赛结束时间')
    is_active = models.BooleanField('比赛是否正在进行', default=True)
    slug = models.SlugField('路由', unique=True, blank=True, null=True)
    re_slug = models.SlugField('报名路由', unique=True, blank=True, null=True)
    challenges = models.ManyToManyField(
        'challenge.Challenge',
        blank=True,
        verbose_name='题目',
        help_text='选择与此比赛相关的题目'
    )
    competition_type = models.CharField(
        max_length=10,
        choices=COMPETITION_TYPE_CHOICES,
        default=TEAM,
        verbose_name='比赛类型',
        help_text='选择比赛类型：个人赛或团体赛'
    )

    class Meta:
        verbose_name = "竞赛配置"
        verbose_name_plural = verbose_name
        ordering = ['-start_time']  # 按开始时间倒序排序

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def status(self):
        """获取比赛状态"""
        now = timezone.now()
        if now < self.start_time:
            return 'pending'  # 未开始
        elif now > self.end_time:
            return 'ended'    # 已结束
        else:
            return 'running'  # 进行中

    def get_status_display(self):
        """获取状态的显示文本"""
        status_map = {
            'pending': '未开始',
            'running': '进行中',
            'ended': '已结束'
        }
        return status_map.get(self.status, '未知状态')

    def save(self, *args, **kwargs):
        # 检查开始时间和结束时间的合法性
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValueError("结束时间必须晚于开始时间")

        # 更新活动状态
        now = timezone.now()
        self.is_active = self.start_time <= now <= self.end_time

        # 处理slug
        if not self.re_slug:
            self.re_slug = self.generate_random_slug()

        if self.slug and not self.slug.isalnum():
            raise ValueError('只能是数字及字母组成')

        # 先保存对象
        super().save(*args, **kwargs)
    
        # 更新Redis缓存
        cache_key = f'competition_time_data_{self.id}'
        
        # 清除旧缓存
        cache.delete(cache_key)
        
        # 创建新的缓存数据
        competition_data = {
            'id': self.id,
            'name': self.title,  # 修正这里，使用 title 而不是 name
            'slug': self.slug,
            'start_time': self.start_time,
            'end_time': self.end_time,
        }
        
        # 计算缓存时间
        now = timezone.now()  # 使用已导入的 timezone
        cache_timeout = None
        if self.end_time > now:
            cache_timeout = int((self.end_time - now).total_seconds()) + 86400
        
        # 设置新缓存
        cache.set(cache_key, competition_data, timeout=cache_timeout)

    def generate_random_slug(self):
        """生成随机slug"""
        return ''.join(random.choices(string.ascii_letters, k=10))

    def get_competition_url(self):
        """生成比赛的页面URL"""
        return reverse('competition_detail', args=[self.slug])

    def get_registration_url(self):
        """生成报名页面URL"""
        return reverse('competition_registration', args=[self.slug])
    
    def get_challenge_types(self):
        """获取与比赛相关的所有题目的类型"""
        return ', '.join([challenge.category for challenge in self.challenges.all()])

    def is_started(self):
        """检查比赛是否已开始"""
        return timezone.now() >= self.start_time

    def is_ended(self):
        """检查比赛是否已结束"""
        return timezone.now() > self.end_time

    def is_running(self):
        """检查比赛是否正在进行中"""
        now = timezone.now()
        return self.start_time <= now <= self.end_time

    def time_until_start(self):
        """获取距离比赛开始还有多长时间"""
        if self.is_started():
            return None
        return self.start_time - timezone.now()

    def time_until_end(self):
        """获取距离比赛结束还有多长时间"""
        if self.is_ended():
            return None
        return self.end_time - timezone.now()

class Team(models.Model):
    name = models.CharField('队伍名称', max_length=255)  # 队伍名称
    member_count = models.IntegerField('队伍成员最大数量', default=4)  # 队伍成员数量
    leader = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='led_teams', on_delete=models.CASCADE, verbose_name="队长")  # 队长
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='teams', verbose_name="队员")  # 队员，可以是多个用户
    competition = models.ForeignKey('Competition', related_name='competition_teams', on_delete=models.CASCADE, default=None, blank=True,verbose_name="所属比赛")  # 添加比赛字段

    class Meta:
        verbose_name = "队伍"
        verbose_name_plural = verbose_name
        unique_together = ('name', 'competition')  # 确保队伍名称在同一比赛中唯一

    def __str__(self):
        return self.name


class ScoreTeam(models.Model):
    team = models.ForeignKey('Team', related_name='score_team_scores', on_delete=models.CASCADE)
    competition = models.ForeignKey('Competition', related_name='score_team_scores', on_delete=models.CASCADE)
    score = models.IntegerField('队伍得分')
    time = models.DateTimeField('最近得分时间', auto_now_add=True)
    rank = models.IntegerField(default=0, verbose_name="队伍排名")
    solved_challenges = models.ManyToManyField('challenge.Challenge', default=None, blank=True, verbose_name="全队已解决的挑战")

    class Meta:
        verbose_name = "队伍计分"
        verbose_name_plural = verbose_name

    def update_score(self, points_to_add):
        self.score += points_to_add
        self.time = timezone.now() 
        self.save()
        self.update_rank()

    def update_rank(self):
        all_teams = ScoreTeam.objects.filter(competition=self.competition).order_by('-score')
        for index, team in enumerate(all_teams, 1):
            team.rank = index
            team.save()

    def __str__(self):
        return f"{self.team.name} - {self.score} points"


class ScoreUser(models.Model):
    team = models.ForeignKey('Team', related_name='score_uuser_scores', on_delete=models.CASCADE, default=None, null=True, blank=True, verbose_name="所属队伍")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='scores', on_delete=models.CASCADE, verbose_name="用户")
    points = models.IntegerField('得分', default=0)
    competition = models.ForeignKey('Competition', related_name='score_uuser_scores', on_delete=models.CASCADE, default=None, blank=True, verbose_name="所属比赛")
    rank = models.IntegerField(default=0, verbose_name="用户排名")
    solved_challenges = models.ManyToManyField('challenge.Challenge', default=None,blank=True, verbose_name="已解决的题目")
    created_at = models.DateTimeField('得分时间', auto_now_add=True)

    class Meta:
        verbose_name = "个人计分"
        verbose_name_plural = verbose_name
        unique_together = ('team', 'user', 'competition')

    def update_score(self, points_to_add):
        self.points += points_to_add
        self.created_at = timezone.now() 
        self.save()
        self.update_rank()

    def update_rank(self):
        all_users = ScoreUser.objects.filter(competition=self.competition).order_by('-points')
        for index, user in enumerate(all_users, 1):
            user.rank = index
            user.save()

    def __str__(self):
        return f"{self.user.username} - {self.team.name} - {self.points} points"



class Registration(models.Model):
    INDIVIDUAL = 'individual'
    TEAM = 'team'
    REGISTRATION_TYPE_CHOICES = [
        (INDIVIDUAL, '个人报名'),
        (TEAM, '团队报名'),
    ]

    competition = models.ForeignKey('Competition', on_delete=models.CASCADE, related_name='registrations',verbose_name="所属比赛")  # 关联比赛
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,verbose_name="用户ID")  # 报名用户
    team_name = models.ForeignKey('Team', related_name='队伍名称', on_delete=models.CASCADE,null=True, blank=True,verbose_name="所属队伍")  # 团队名称
    registration_type = models.CharField(
        max_length=10,
        choices=REGISTRATION_TYPE_CHOICES,
        default=INDIVIDUAL,
        verbose_name='报名类型',
        help_text='选择报名类型：个人报名或团队报名'
    )
    student_id = models.CharField('学号（身份证号）', max_length=100,null=True, blank=True)
    name = models.CharField('姓名', max_length=20,null=True, blank=True)
    role = models.CharField('所属单位（学院）', max_length=20,null=True, blank=True)
    phone = models.CharField('联系方式', max_length=20,null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)   # 报名时间

    class Meta:
        verbose_name = "报名信息"
        verbose_name_plural = "报名信息"

  

    def __str__(self):
        if self.registration_type == self.INDIVIDUAL:
            return f"{self.user.username} - {self.competition.title} (个人报名)"
        else:
            return f"{self.team_name} - {self.competition.title} (团队报名)"


class CheatingLog(models.Model):
    CHEATING_TYPES = [
        ('timing', 'Timing Cheating'),  # 比如不合理的提交频率
        ('exploit', 'Exploit'),         # 比如利用漏洞作弊
        ('bot', 'Bot Activity'),        # 比如机器人行为
        ('manual', 'Manual'),           # 比如手动作弊行为
    ]

    team = models.ForeignKey('Team', related_name='cheating_logs', on_delete=models.CASCADE)  # 关联队伍
    competition = models.ForeignKey('Competition', related_name='cheating_logs', on_delete=models.CASCADE)  # 关联比赛
    cheating_type = models.CharField('作弊类型',max_length=50, choices=CHEATING_TYPES)  # 作弊类型
    description = models.TextField('描述')  # 作弊行为描述
    timestamp = models.DateTimeField('记录时间',default=timezone.now)  # 记录时间
    detected_by = models.CharField('检测者',max_length=100, default="System")  # 检测者，可能是系统或管理员

    class Meta:
        verbose_name = "监控日志"
        verbose_name_plural =  "监控日志"

    def __str__(self):
        return f"{self.team.name} - {self.cheating_type} - {self.timestamp}"

    
class Submission(models.Model):
    STATUS_CHOICES = [
        ('correct', '正确'),
        ('wrong', '错误'),
        ('pending', '待判定'),
    ]

    challenge = models.ForeignKey('challenge.Challenge', on_delete=models.CASCADE, related_name='submissions', verbose_name="题目")
    competition = models.ForeignKey('Competition', on_delete=models.CASCADE, null=True, blank=True, related_name='submissions', verbose_name="所属比赛")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="提交用户")
    team = models.ForeignKey('Team', on_delete=models.CASCADE, null=True, blank=True, verbose_name="所属队伍")
    flag = models.CharField('提交的Flag', max_length=255)
    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default='pending')
    ip = models.GenericIPAddressField('提交IP', null=True, blank=True)
    created_at = models.DateTimeField('提交时间', auto_now_add=True)
    points_earned = models.IntegerField('获得分数', default=0)
    
    class Meta:
        verbose_name = "提交记录"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['challenge', 'user', 'status']),
            models.Index(fields=['challenge', 'team', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['competition']),
        ]

    def __str__(self):
        team_or_user = self.team.name if self.team else self.user.username
        return f"{team_or_user} - {self.challenge.title} - {self.get_status_display()}"

    def is_first_blood(self):
        """检查是否是一血"""
        query = Submission.objects.filter(
            challenge=self.challenge,
            status='correct',
            created_at__lt=self.created_at
        )
        
        # 如果有比赛信息，则限定在同一比赛内判断一血
        if self.competition:
            query = query.filter(competition=self.competition)
            
        return not query.exists()

    @property
    def submission_time(self):
        """返回格式化的提交时间"""
        return self.created_at.strftime('%Y-%m-%d %H:%M:%S')

    def get_user_team(self):
        """获取用户所属的队伍名称"""
        return self.team.name if self.team else "个人参赛"

    def is_first_blood(self):
        """检查是否是一血"""
        return not Submission.objects.filter(
            challenge=self.challenge,
            status='correct',
            created_at__lt=self.created_at
        ).exists()

