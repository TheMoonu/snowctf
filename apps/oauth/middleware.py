# middleware.py

from django.contrib.auth.middleware import AuthenticationMiddleware as DjangoAuthenticationMiddleware
from django.utils.deprecation import MiddlewareMixin
from .custom_user import CustomAnonymousUser

class CustomAuthenticationMiddleware(DjangoAuthenticationMiddleware, MiddlewareMixin):
    def process_request(self, request):
        super().process_request(request)
        if not hasattr(request, 'user') or request.user.is_anonymous:
            request.user = CustomAnonymousUser()
