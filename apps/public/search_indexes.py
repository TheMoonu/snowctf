from haystack import indexes
from challenge.models import Challenge
from competition.models import Competition

class ChallengeIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField(model_attr='title')
    category = indexes.CharField(model_attr='category')
    difficulty = indexes.CharField(model_attr='difficulty')

    def get_model(self):
        return Challenge

    def index_queryset(self, using=None):
        return self.get_model().objects.filter(is_disable=True)

class CompetitionIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField(model_attr='title')
    description = indexes.CharField(model_attr='description', null=True)
    competition_type = indexes.CharField(model_attr='competition_type')
    
    def get_model(self):
        return Competition
    
    def index_queryset(self, using=None):
        return self.get_model().objects.all()