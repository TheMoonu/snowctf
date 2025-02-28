from django.shortcuts import render

from challenge.models import Challenge
from .models import ChallengeComment, Notification, SystemNotification
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from datetime import datetime
from django.shortcuts import get_object_or_404
from .utils import sanitize_content

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
    if request.is_ajax() and request.method == "POST":
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
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.method == "POST":
        try:
            data = request.POST
            new_user = request.user
            new_content = data.get('content')
            new_content = sanitize_content(new_content)
            Challenge_uuid = data.get('challenge_id')
            rep_id = data.get('rep_id')
            the_article =  Challenge.objects.get(uuid=Challenge_uuid)
            if len(new_content) > 1048:
                return JsonResponse({'msg': '你的评论字数超过1048，无法保存。'})

            if not rep_id:
                new_comment =  ChallengeComment(author=new_user, content=new_content, belong=the_article,
                                            parent=None,
                                            rep_to=None)
            else:
                new_rep_to =  ChallengeComment.objects.get(id=rep_id)
                new_parent = new_rep_to.parent if new_rep_to.parent else new_rep_to
                new_comment =  ChallengeComment(author=new_user, content=new_content, belong=the_article,
                                            parent=new_parent,
                                            rep_to=new_rep_to)
            new_comment.save()
            new_point = '#com-' + str(new_comment.id)
            return JsonResponse({'msg': '评论提交成功！', 'new_point': new_point})
        except Exception as e:
            print(e)
    return JsonResponse({'msg': '评论失败！'})