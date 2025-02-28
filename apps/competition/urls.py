# -*- coding: utf-8 -*-
from django.urls import path
from public.views import registrationView
urlpatterns = [
    path('<slug:slug>/<slug:re_slug>/', registrationView, name='registration_detail'),
]