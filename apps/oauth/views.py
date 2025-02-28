from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .forms import ProfileForm
from django.contrib import messages
from django.shortcuts import render, get_object_or_404
from .models import Ouser
from django.http import JsonResponse
import os
import random
import string
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from competition.models import Team


# Create your views here.

@login_required
def profile_view(request):
    return render(request, 'oauth/profile.html')


@login_required
def change_profile_view(request):
    if request.method == 'POST':
        # 如果没有上传新头像，使用当前头像
        if 'avatar' not in request.FILES and request.user.avatar:
            form = ProfileForm(request.POST, instance=request.user)
        else:
            old_avatar_file = request.user.avatar.path
            old_avatar_url = request.user.avatar.url
            form = ProfileForm(request.POST, request.FILES, instance=request.user)

        if form.is_valid():
            # 只在使用默认头像且没有上传新头像时验证
            if 'default.png' in request.user.avatar.url and 'avatar' not in request.FILES:
                form.add_error('avatar', '请上传头像')
                return render(request, 'oauth/change_profile.html', {'form': form})

            # 如果上传了新头像，且旧头像不是默认头像，则删除旧头像
            if 'avatar' in request.FILES and 'default' not in old_avatar_url:
                try:
                    if os.path.exists(old_avatar_file):
                        os.remove(old_avatar_file)
                except Exception as e:
                    print(f"删除旧头像失败: {e}")

            form.save()
            messages.success(request, '个人信息更新成功！')
            return redirect('oauth:profile')
    else:
        form = ProfileForm(instance=request.user)
    
    return render(request, 'oauth/change_profile.html', {'form': form})


@login_required
def dissolve_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    if team.leader != request.user:
        return JsonResponse({'success': False, 'message': '只有队长可以解散队伍'})
    
    team.delete()
    return JsonResponse({'success': True})

@login_required
def leave_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    if team.leader == request.user:
        return JsonResponse({'success': False, 'message': '队长不能退出队伍'})
    
    team.members.remove(request.user)
    return JsonResponse({'success': True})


