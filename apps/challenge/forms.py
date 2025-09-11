from django import forms
from .models import Challenge

class ChallengeForm(forms.ModelForm):
    class Meta:
        model = Challenge
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 如果是编辑（而非创建），禁用 initial_points, minimum_points, points 字段
        if self.instance and self.instance.pk:
            self.fields['initial_points'].disabled = True
            self.fields['minimum_points'].disabled = True
            

    def clean_initial_points(self):
        initial_points = self.cleaned_data.get('initial_points')
        minimum_points = self.cleaned_data.get('minimum_points')
        if initial_points:
            if int(initial_points) < 100 or int(initial_points) > 1000:
                raise forms.ValidationError("初始分数必须在100到1000之间。")
            return int(initial_points)
        return int(initial_points)

    def clean_minimum_points(self):
        initial_points = self.cleaned_data.get('initial_points')
        minimum_points = self.cleaned_data.get('minimum_points')
        if minimum_points and initial_points:
            if int(minimum_points) >= int(initial_points):
                raise forms.ValidationError("最低分数必须小于初始分数。")
            return int(minimum_points)
        return int(minimum_points)

   
