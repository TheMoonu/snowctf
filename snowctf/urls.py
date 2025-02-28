"""
URL configuration for snowctf project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.views.generic import RedirectView

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='/static/public/img/favicon.ico')),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # allauth
    path('accounts/', include(('oauth.urls', 'oauth'), namespace='oauth')),
    path('', include(('public.urls', 'public'), namespace='public')),
    path('comment/', include(('comment.urls', 'comment'), namespace='comment')),
    path('ctf/', include(('competition.urls', 'competition'), namespace='competition')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
