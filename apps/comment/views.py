from django.shortcuts import render

from challenge.models import Challenge
from competition.models import Competition
from .models import ChallengeComment, Notification, SystemNotification
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from datetime import datetime
from django.shortcuts import get_object_or_404
from .utils import sanitize_content
from django.contrib import messages
from django.shortcuts import redirect
from django.core.cache import cache

user_model = settings.AUTH_USER_MODEL





@login_required
def NotificationView(request, is_read=None):
    """展示提示消息列表"""
    now_date = datetime.now()
    return render(request, 'comment/notification.html',
                  context={'is_read': is_read, 'now_date': now_date})


@login_required
@require_POST
def mark_to_read(request):
    """将一个消息标记为已读"""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.method == "POST":
        data = request.POST
        user = request.user
        _id = data.get('id')
        _tag = data.get('tag')
        if _tag == 'comment':
            info = get_object_or_404(Notification, get_p=user, id=_id)
        elif _tag == 'system':
            info = get_object_or_404(SystemNotification, get_p=user, id=_id)
        else:
            return JsonResponse({'msg': 'bad tag', 'code': 1})
        info.mark_to_read()
        return JsonResponse({'msg': 'mark success', 'code': 0})
    return JsonResponse({'msg': 'miss', 'code': 1})


@login_required
@require_POST
def mark_to_delete(request):
    """将一个消息删除"""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.method == "POST":
        data = request.POST
        user = request.user
        _id = data.get('id')
        _tag = data.get('tag')
        if _tag == 'comment':
            info = get_object_or_404(Notification, get_p=user, id=_id)
        elif _tag == 'system':
            info = get_object_or_404(SystemNotification, get_p=user, id=_id)
        else:
            return JsonResponse({'msg': 'bad tag', 'code': 1})
        info.delete()
        return JsonResponse({'msg': 'delete success', 'code': 0})
    return JsonResponse({'msg': 'miss', 'code': 1})



@login_required
@require_POST
def AddChallengeCommentView(request):
    """添加评论"""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'error'})
    # 检查是否有前端传递的错误消息
    try:
        data = request.POST
        new_user = request.user
        new_content = data.get('content')
        
        # 检查评论内容是否为空
        if not new_content or new_content.strip() == '':
            messages.error(request, '评论内容不能为空！')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # 使用缓存检查评论时间间隔
        cache_key = f'comment_cooldown_{new_user.id}'
        
        # 如果缓存键存在，说明用户在短时间内已经评论过
        if cache.get(cache_key):
            # 获取剩余冷却时间
            ttl = cache.ttl(cache_key)  # 获取键的剩余生存时间（秒）
            if ttl > 0:
                
                messages.error(request, f'评论过于频繁，请等待{ttl}秒后再试')

                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error'})
                
        
        new_content = sanitize_content(new_content)
        challenge_uuid = data.get('challenge_id')
        competition_id = data.get('competition_id')
        rep_id = data.get('rep_id')
        
        # 检查评论长度
        if len(new_content) > 1048:
            messages.error(request, '你的评论字数超过1048，无法保存。')
            
            return JsonResponse({'status': 'error'})
        
        # 获取题目对象
        try:
            the_challenge = Challenge.objects.get(uuid=challenge_uuid)
        except Challenge.DoesNotExist:
            messages.error(request, '题目不存在！')
            
            return JsonResponse({'status': 'error'})
        
        # 获取竞赛对象
        the_competition = None
        if competition_id:
            try:
                the_competition = Competition.objects.get(id=competition_id)
                
                # 判断题目是否在竞赛中
                if the_challenge not in the_competition.challenges.all():
                    messages.error(request, '该题目不属于指定的比赛！')
                    return JsonResponse({'status': 'error'})
                
            except Competition.DoesNotExist:
                messages.error(request, '指定的比赛不存在！')
                return JsonResponse({'status': 'error'})
        
        if not rep_id:
            new_comment = ChallengeComment(
                author=new_user, 
                content=new_content, 
                belong=the_challenge,
                competition=the_competition,  
                parent=None,
                rep_to=None
            )
        else:
            try:
                new_rep_to = ChallengeComment.objects.get(id=rep_id)
                
                # 确保回复的评论属于同一个题目和比赛
                if new_rep_to.belong != the_challenge:
                    messages.error(request, '不能回复其他题目的评论！')
                    return JsonResponse({'status': 'error'})
                
                if the_competition and new_rep_to.competition != the_competition:
                    messages.error(request, '不能回复其他比赛的评论！')
                    return JsonResponse({'status': 'error'})
                
                new_parent = new_rep_to.parent if new_rep_to.parent else new_rep_to
                new_comment = ChallengeComment(
                    author=new_user, 
                    content=new_content, 
                    belong=the_challenge,
                    competition=the_competition,
                    parent=new_parent,
                    rep_to=new_rep_to
                )
            except ChallengeComment.DoesNotExist:
                messages.error(request, '回复的评论不存在！')
                return JsonResponse({'status': 'error'})
        
        # 保存评论
        new_comment.save()
        
        # 设置评论冷却时间（40秒）
        cache.set(cache_key, True, 40)
        
        new_point = '#com-' + str(new_comment.id)
        
        # 添加成功消息
        messages.success(request, '评论提交成功！')
        
        # 对于 AJAX 请求，返回锚点信息
        
        return JsonResponse({'status': 'success', 'new_point': new_point})
        
        # 对于非 AJAX 请求，重定向回原页面
    
    except Exception as e:
        return JsonResponse({'status': 'error'})