from django.contrib import admin
from .models import Competition, Team, ScoreTeam, ScoreUser, CheatingLog,Registration,Submission
from challenge.models import Challenge
from django import forms
from django.contrib.sites.models import Site
from django.utils.html import format_html
from django.urls import reverse
from public.utils import site_full_url
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
User = get_user_model()
class RegistrationForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = '__all__'  # 或者列出您想要的字段

    def clean(self):
        cleaned_data = super().clean()
        registration_type = cleaned_data.get('registration_type')
        team_name = cleaned_data.get('team_name')
        competition = cleaned_data.get('competition')

        # 验证个人报名时不填写队伍名称
        if registration_type == Registration.INDIVIDUAL and team_name is not None:
            self.add_error('team_name', '个人报名不需要填写队伍名称')

        # 验证团队报名时必须填写队伍名称
        if registration_type == Registration.TEAM and team_name is None:
            self.add_error('team_name', '团队报名需要填写队伍名称')

        # 确保比赛类型与报名类型一致
        if competition:
            if competition.competition_type == 'team' and registration_type == Registration.INDIVIDUAL:
                raise forms.ValidationError('团队赛不允许个人报名')
            elif competition.competition_type == 'individual' and registration_type == Registration.TEAM:
                raise forms.ValidationError('个人赛不允许团队报名')

        return cleaned_data

@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = (
        'title', 
        'start_time', 
        'end_time', 
        'is_active', 
        'competition_type_display', 
        'get_challenge_types', 
        'competition_link',  # 添加比赛链接
        'registration_link'   # 添加报名链接
    )
    search_fields = ('title',)
    filter_horizontal = ('challenges', )
    prepopulated_fields = {'slug': ('title',)}

    def competition_type_display(self, obj):
        return dict(Competition.COMPETITION_TYPE_CHOICES).get(obj.competition_type, '未知类型')
    competition_type_display.short_description = '比赛类型'  # 自定义列标题

    def get_challenge_types(self, obj):
        return obj.get_challenge_types()
    get_challenge_types.short_description = '题目类型'  # 自定义列标题

    def competition_link(self, obj):
        # 获取当前站点的域名
        site = Site.objects.get_current()
       
        url = f"{site_full_url()}{reverse('public:competition_detail', args=[obj.slug])}"
        
        return format_html('<a href="{}" target="_blank">查看比赛</a>', url)
    competition_link.short_description = '比赛链接'  # 自定义列标题

    def registration_link(self, obj):
        # 获取当前站点的域名
        site = Site.objects.get_current()
        url = f"{site_full_url()}{reverse('competition:registration_detail', args=[obj.slug, obj.re_slug])}"
        return format_html('<a href="{}" target="_blank">报名链接</a>', url)
    registration_link.short_description = '报名链接'  # 自定义列标题

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "challenges":
            # 根据题目类型过滤题目
            kwargs["queryset"] = Challenge.objects.filter(is_active=True)  # 例如，只显示激活的题目
        return super().formfield_for_manytomany(db_field, request, **kwargs)

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'competition', 'leader', 'get_members', 'member_count', 'get_current_members')
    list_filter = ('competition',)  # 添加按比赛筛选
    search_fields = ('name', 'leader__username', 'competition__title')  # 扩展搜索字段
    raw_id_fields = ('leader', 'members')  # 使用 raw_id 选择用户

    def get_members(self, obj):
        # 返回队员名称的字符串
        return ", ".join([member.username for member in obj.members.all()])
    get_members.short_description = '队员名称'

    def get_current_members(self, obj):
        # 返回当前队员数量
        return obj.members.count()
    get_current_members.short_description = '当前队员数量'

    def save_model(self, request, obj, form, change):
        if not change:  # 如果是新建队伍
            obj.save()  # 先保存以获取 ID
            obj.members.add(obj.leader)  # 自动将队长添加为队员
        
        # 检查队伍成员数量
        if obj.members.count() > obj.member_count:
            raise ValidationError(f'队伍成员数量不能超过 {obj.member_count} 人')
        
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
    # 在选择队长时，过滤掉已经是其他队伍队长的用户
        if db_field.name == "leader":
            competition_id = request.GET.get('competition')
            if competition_id:
                # 如果有指定比赛，只排除该比赛中已经是队长的用户
                kwargs["queryset"] = User.objects.exclude(
                    led_teams__competition_id=competition_id
                )
            # 如果没有指定比赛，不做特殊过滤
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None:  # 新建队伍时
            form.base_fields['member_count'].initial = 4  # 设置默认成员数量
        return form
    

@admin.register(ScoreTeam)
class ScoreTeamAdmin(admin.ModelAdmin):
    list_display = ('team', 'competition', 'rank','score', 'time')
    list_filter = ('competition','rank',)



@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    form = RegistrationForm
    list_display = ('user', 'name','student_id','role','competition', 'registration_type', 'phone','team_name', 'created_at')
    list_filter = ('competition', 'registration_type')
    search_fields = ('user__username', 'team_name__name', 'competition__title')

    def get_queryset(self, request):
        # 只显示当前用户的报名记录
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    

    

@admin.register(ScoreUser)
class ScoreUserAdmin(admin.ModelAdmin):
    list_display = ('team', 'user', 'points', 'rank','competition', 'created_at')
    list_filter = ('competition','rank',)

@admin.register(CheatingLog)
class CheatingLogAdmin(admin.ModelAdmin):
    list_display = ('team', 'competition', 'cheating_type', 'timestamp')
    list_filter = ('competition', 'cheating_type')



@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'challenge_title', 
        'user_info', 
        'team_name', 
        'status_badge', 
        'points_earned',
        'ip_address', 
        'created_at',
        'competition'
    ]
    
    list_filter = [
        'status',
        ('challenge', admin.RelatedOnlyFieldListFilter),
        'created_at',
        ('team', admin.RelatedOnlyFieldListFilter),
        ('competition', admin.RelatedOnlyFieldListFilter),
    ]
    
    search_fields = [
        'user__username',
        'team__name',
        'challenge__title',
        'flag',
        'ip'
    ]
    
    readonly_fields = [
        'created_at',
        'points_earned',
        'is_first_blood_display'
    ]
    
    ordering = ['-created_at']
    list_per_page = 20
    
    fieldsets = (
        ('基本信息', {
            'fields': (
                'challenge',
                'user',
                'team',
                'status',
                'points_earned',
                'created_at',
                'competition'
            )
        }),
        ('提交详情', {
            'fields': (
                'flag',
                'ip',
                'is_first_blood_display',
           
            )
        }),
    )
    
    def challenge_title(self, obj):
        return format_html(
            '{} <span style="color: #666;">[{}]</span>',
            obj.challenge.title,
            obj.challenge.get_category_display()
        )
    challenge_title.short_description = '题目'
    
    def user_info(self, obj):
        return format_html(
            '{}<br/><span style="color: #666;">{}</span>',
            obj.user.username,
            obj.user.email
        )
    user_info.short_description = '用户'
    
    def team_name(self, obj):
        if obj.team:
            return obj.team.name
        return format_html('<span style="color: #999;">个人参赛</span>')
    team_name.short_description = '队伍'
    
    def status_badge(self, obj):
        colors = {
            'correct': '#52c41a',
            'wrong': '#ff4d4f',
            'pending': '#faad14'
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status, '#666'),
            obj.get_status_display()
        )
    status_badge.short_description = '状态'
    
    def ip_address(self, obj):
        return obj.ip or '未记录'
    ip_address.short_description = 'IP地址'
    
    def is_first_blood_display(self, obj):
        if obj.is_first_blood():
            return format_html(
                '<span style="color: #ff4d4f;">✓ 一血</span>'
            )
        return '否'
    is_first_blood_display.short_description = '是否一血'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'challenge',
            'user',
            'team',
            'competition'
        )



