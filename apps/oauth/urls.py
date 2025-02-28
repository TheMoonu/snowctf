# -*- coding: utf-8 -*-
from django.urls import path
from .views import profile_view, change_profile_view, dissolve_team, leave_team

urlpatterns = [
    path('profile/',profile_view,name='profile'),
    path('profile/change/',change_profile_view,name='change_profile'),
    path('api/v1/team/<int:team_id>/dissolve/', dissolve_team, name='dissolve_team'),
    path('api/v1/team/<int:team_id>/leave/', leave_team, name='leave_team'),
]