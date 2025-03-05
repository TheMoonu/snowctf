from django import template
from ..models import emoji_info

# 创建了新的tags标签文件后必须重启服务器
register = template.Library()


@register.simple_tag
def get_notifications(user, f=None):
    """获取一个用户的对应条件下的提示信息"""
    if f == 'true':
        # 获取所有已读通知
        lis = []
        lis.extend(user.notification_get.filter(is_read=True))
        lis.extend(user.systemnotification_recipient.filter(is_read=True))
    elif f == 'false':
        # 获取所有未读通知
        lis = []
        lis.extend(user.notification_get.filter(is_read=False))
        lis.extend(user.systemnotification_recipient.filter(is_read=False))
    else:
        # 获取所有通知
        lis = []
        lis.extend(user.notification_get.all())
        lis.extend(user.systemnotification_recipient.all())

    # 按照 create_date 字段进行汇总后重新排序
    lis = sorted(lis, key=lambda x: x.create_date, reverse=True)
    #print(lis)
    return lis[:50]


@register.simple_tag
def get_notifications_count(user, f=None):
    """获取一个用户的对应条件下的提示信息总数"""
    if f == 'true':
        num = 0
        num += user.notification_get.filter(is_read=True).count()
        num += user.systemnotification_recipient.filter(is_read=True).count()
    elif f == 'false':
        num = 0
        num += user.notification_get.filter(is_read=False).count()
        num += user.systemnotification_recipient.filter(is_read=False).count()
    else:
        num = 0
        num += user.notification_get.all().count()
        num += user.systemnotification_recipient.all().count()
    return num


@register.simple_tag
def get_emoji_imgs():
    """
    返回一个列表，包含表情信息
    :return:
    """
    return emoji_info


@register.filter(is_safe=True)
def emoji_to_url(value):
    """
    将emoji表情的名称转换成图片地址
    """
    emoji_static_url = 'comment/weibo/{}.png'
    return emoji_static_url.format(value)




@register.simple_tag
def get_challenge_comment_count(entry, competition=None):
    """获取评论总数
    
    Args:
        entry: Challenge对象
        competition: Competition对象，如果提供则只统计该竞赛中的评论
        
    Returns:
        int: 评论数
    """
    # 如果指定了竞赛则过滤
    if competition:
        return entry.challenge_comments.filter(competition=competition).count()
    else:
        return entry.challenge_comments.count()


@register.simple_tag(takes_context=True)
def get_challenge_parent_comments(context, entry, competition=None):
    """获取一个文章的父评论列表，逆序只选取后面的20个评论
    
    Args:
        context: 模板上下文
        entry: Challenge对象
        competition: Competition对象，如果提供则只返回该竞赛中的评论
        
    Returns:
        QuerySet: 父评论列表
    """
    # 如果没有明确指定竞赛，尝试从上下文中获取
    if not competition and 'competition' in context:
        competition = context['competition']
    
    # 基本查询：获取父评论（parent=None）
    query = entry.challenge_comments.filter(parent=None)
    
    # 如果指定了竞赛则进一步过滤
    if competition:
        query = query.filter(competition=competition)
    
    # 按ID逆序排序并限制数量
    return query.order_by("-id")[:20]


@register.simple_tag
def get_challenge_child_comments(com):
    """获取一个父评论的子平路列表"""
    lis = com.challengecomment_child_comments.all()
    return lis


@register.simple_tag
def get_challenge_comment_user_count(entry, competition=None):
    """获取评论人总数
    
    Args:
        entry: Challenge对象
        competition: Competition对象，如果提供则只统计该竞赛中的评论
        
    Returns:
        int: 评论人数
    """
    p = []
    # 获取评论列表，如果指定了竞赛则过滤
    if competition:
        lis = entry.challenge_comments.filter(competition=competition)
    else:
        lis = entry.challenge_comments.all()
    
    for each in lis:
        if each.author not in p:
            p.append(each.author)
    return len(p)
