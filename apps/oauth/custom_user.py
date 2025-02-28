# custom_user.py

from django.contrib.auth.models import AnonymousUser as DjangoAnonymousUser

class CustomAnonymousUser(DjangoAnonymousUser):
    @property
    def is_member(self):
        return False
