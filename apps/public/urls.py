# -*- coding: utf-8 -*-
from django.urls import path
from django.conf import settings
from .views import (challenge_detail,create_web_container,remove_container,
    verify_flag,destroy_web_container,check_container_status,delete_challenge,
    CompetitionViewList,Competition_detail,registrationView,RankingsView,competition_dashboard,get_dashboard_data,refresh_captcha)

urlpatterns = [
    path('',CompetitionViewList,name='CompetitionView'),  # 主页，自然排序
    path('<slug:slug>/<uuid:uuid>/', challenge_detail, name='challenge_detail'),
    path('<slug:slug>/dashboard/', competition_dashboard, name='competition_dashboard'),
    path('api/v1/<slug:slug>/create_web_container/', create_web_container, name='create_web_container'),
    path('remove_container/<str:container_id>/', remove_container, name='remove_container'),
    path('api/v1/<slug:slug>/verify-flag/', verify_flag, name='verify_flag'),
    path('api/v1/destroy_web_container/', destroy_web_container, name='destroy_web_container'),
    path('api/v1/check_container_status/', check_container_status, name='check_container_status'),

    path('api/v1/challenge/delete/', delete_challenge, name='challenge_delete'),
    path('api/v1/competition/<slug:slug>/dashboard-data/', get_dashboard_data, name='competition_dashboard_data'),
    path('api/v1/refresh-captcha/', refresh_captcha, name='refresh_captcha'),
    path('<slug:slug>/', Competition_detail.as_view(), name='competition_detail'),
    
    path('rankings/<int:competition_id>/<str:ranking_type>/', RankingsView.as_view(), name='rankings'),
]
