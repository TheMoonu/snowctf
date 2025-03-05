from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ScoreUser, ScoreTeam
from public.utils import clear_ranking_cache

@receiver(post_save, sender=ScoreUser)
def clear_user_ranking_cache(sender, instance, **kwargs):
    clear_ranking_cache(instance.competition_id if instance.competition else None)

@receiver(post_save, sender=ScoreTeam)
def clear_team_ranking_cache(sender, instance, **kwargs):
    clear_ranking_cache(instance.competition_id if instance.competition else None)