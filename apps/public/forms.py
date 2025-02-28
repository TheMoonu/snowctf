from django import forms
import re
from django.core.exceptions import ValidationError
from django.utils import timezone
from competition.models import Registration
from django.core.cache import cache

class TeamSelectionForm(forms.Form):
    """创建或加入队伍"""
    TEAM_CHOICES = [
        ('create', '创建新队伍'),
        ('join', '加入现有队伍')
    ]
    team_action = forms.ChoiceField(
        choices=TEAM_CHOICES,
        widget=forms.RadioSelect,
        label='队伍选择'
    )
    team_name = forms.CharField(
        max_length=255,
        required=True,
        label='队伍名称',
        help_text='如果创建新队伍，请输入队伍名称；如果加入现有队伍，请输入要加入的队伍名称'
    )
    captcha = forms.CharField(
        max_length=6, 
        required=True,
        label='验证码',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '请输入验证码'
        }),
        help_text='请输入右侧图片中的验证码'
    )

    def clean_team_name(self):
        team_name = self.cleaned_data['team_name']
        
        # 检查长度
        if len(team_name) < 2 or len(team_name) > 20:
            raise ValidationError('队伍名称长度必须在2-20个字符之间')
            
        # 只允许中文、英文、数字和下划线
        if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_]+$', team_name):
            raise ValidationError('队伍名称只能包含中文、英文、数字和下划线')
            
        # 检查特殊字符
        dangerous_chars = ['<', '>', '&', '"', "'", ';', '--', '/*', '*/']
        for char in dangerous_chars:
            if char in team_name:
                raise ValidationError('队伍名称包含非法字符')
                
        return team_name
        
    def clean_captcha(self):
        captcha = self.cleaned_data['captcha'].strip().lower()
        captcha_key = self.data.get('captcha_key')
        
        if not captcha_key:
            raise ValidationError('验证码已过期，请刷新页面')
        
        # 从Redis获取正确的验证码
        correct_captcha = cache.get(f'registration_captcha_{captcha_key}')
        
        if not correct_captcha:
            raise ValidationError('验证码已过期，请刷新页面')
        
        if captcha != correct_captcha.lower():
            raise ValidationError('验证码错误，请重新输入')
        
        # 验证成功后删除缓存中的验证码，防止重复使用
        cache.delete(f'registration_captcha_{captcha_key}')
        
        return captcha

class PersonalInfoForm(forms.ModelForm):
    """填写个人信息"""
    captcha = forms.CharField(
        max_length=6, 
        required=True,
        label='验证码',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '请输入验证码'
        }),
        help_text='请输入右侧图片中的验证码'
    )
    
    class Meta:
        model = Registration
        fields = ['student_id', 'name', 'role', 'phone']
        widgets = {
            'student_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入学号或身份证号'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入姓名'}),
            'role': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入所属单位或学院'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入联系方式'}),
        }

    def clean_student_id(self):
        student_id = self.cleaned_data['student_id']
        if not re.match(r'^[0-9A-Za-z]+$', student_id):
            raise ValidationError('学号/身份证号只能包含数字和字母')
        return student_id

    def clean_name(self):
        name = self.cleaned_data['name']
        if not re.match(r'^[\u4e00-\u9fa5a-zA-Z]+$', name):
            raise ValidationError('姓名只能包含中文和英文字母')
        return name

    def clean_role(self):
        role = self.cleaned_data['role']
        if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9\s_()-]+$', role):
            raise ValidationError('所属单位只能包含中文、英文、数字、空格和常用符号')
        return role

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if not re.match(r'^[0-9-]+$', phone):
            raise ValidationError('联系方式只能包含数字和连字符')
        return phone
        
    def clean_captcha(self):
        captcha = self.cleaned_data['captcha'].strip().lower()
        captcha_key = self.data.get('captcha_key')
        
        if not captcha_key:
            raise ValidationError('验证码已过期，请刷新页面')
        
        # 从Redis获取正确的验证码
        correct_captcha = cache.get(f'registration_captcha_{captcha_key}')
        
        if not correct_captcha:
            raise ValidationError('验证码已过期，请刷新页面')
        
        if captcha != correct_captcha.lower():
            raise ValidationError('验证码错误，请重新输入')
        
        # 验证成功后删除缓存中的验证码，防止重复使用
        cache.delete(f'registration_captcha_{captcha_key}')
        
        return captcha