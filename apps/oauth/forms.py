# -*- coding: utf-8 -*-
from django import forms
from .models import Ouser
from allauth.account.forms import LoginForm
from allauth.account.forms import AddEmailForm
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError
from allauth.account.adapter import DefaultAccountAdapter
from django.core.mail import EmailMessage
from smtplib import SMTPRecipientsRefused
from django.contrib import messages
from allauth.account.forms import AddEmailForm, SignupForm

class ProfileForm(forms.ModelForm):

    avatar = forms.ImageField(
        label='头像',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control-file',
            'accept': 'image/*',  # 只接受图片文件
            'data-max-size': '10240',  # 最大文件大小（KB）
            'id': 'avatar-upload'
        }),
        help_text='支持jpg、png、gif格式，文件小于10MB'
    )
    class Meta:
        model = Ouser
        fields = ['link','profile','avatar']










