import random
import string
import hashlib
from django.core.cache import cache
from competition.models import CheatingLog, Team
from django.utils import timezone

def generate_flag(challenge, user):
    """生成动态flag
    
    Args:
        challenge: 题目对象
        user: 用户对象
        
    Returns:
        str: 生成的flag
        
    Flag格式: flag{challenge_id_user_hash_prefix_hash}
    """
    # 基础信息
    challenge_uuid = str(challenge.uuid)[:8]
    user_id = str(user.id)
    username_hash = hashlib.md5(user.username.encode()).hexdigest()[:8]
    
    # 随机前缀
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    
    # 生成完整性校验hash
    unique_data = f"{challenge_uuid}_{user_id}_{username_hash}_{prefix}"
    unique_hash = hashlib.sha256(unique_data.encode()).hexdigest()[:12]
    
    if challenge.flag_type == 'STATIC':
        flag = challenge.flag_template
    else:
        # 默认flag模板
        default_template = 'flag{{{uuid}_{user}_{prefix}_{hash}}}'
        flag_template = challenge.flag_template or default_template
        
        # 填充模板
        flag = flag_template.format(
            uuid=challenge_uuid,      
            user=username_hash,       
            prefix=prefix,           
            hash=unique_hash        
        )
    
    # 缓存flag信息
    cache_key = f"flags:{challenge.uuid}:{user.id}"
    flag_info = {
        'flag': flag,
        'user_id': user_id,
        'username': user.username,
        'generated_at': str(timezone.now())
    }
    
    cache.set(cache_key, flag_info, 3600*2)  # 缓存1小时
    return flag

def get_or_generate_flag(challenge, user):
    """获取或生成flag"""
    cache_key = f"flags:{challenge.uuid}:{user.id}"
    # 尝试从缓存获取 flag
    flag_info = cache.get(cache_key)
    if flag_info is None:
        # 如果缓存中没有，生成新的 flag
        flag = generate_flag(challenge, user)
    else:
        flag = flag_info['flag']
    
    return flag

def verify_flag(submitted_flag, challenge, user):
    """验证提交的flag并记录可疑行为
    
    Args:
        submitted_flag: 用户提交的flag
        challenge: 题目对象
        user: 提交用户
    
    Returns:
        tuple: (是否正确, 错误信息)
    """
    cache_key = f"flags:{challenge.uuid}:{user.id}"
    flag_info = cache.get(cache_key)
    
    if challenge.flag_type == 'STATIC':
        return submitted_flag == challenge.flag_template, None
    if not flag_info:
        correct_flag = generate_flag(challenge, user)
    else:
        correct_flag = flag_info['flag']
    
    if '_' in submitted_flag:
        try:
            if not submitted_flag.startswith('flag{') or not submitted_flag.endswith('}'):
                return False, "Flag格式错误"
                
            # 解析flag内容
            flag_content = submitted_flag[5:-1] 
            parts = flag_content.split('_')
            

            if len(parts) != 4:  # uuid_user_prefix_hash
                return False, "Flag不正确，请重新提交"
                
            if len(parts[0]) != 8:  # challenge_uuid的前8位
                return False, "Flag不正确，请重新提交"
            if len(parts[1]) != 8:  # username_hash的前8位
                return False, "Flag不正确，请重新提交"
                
            submitted_user_hash = parts[1]
            current_user_hash = hashlib.md5(user.username.encode()).hexdigest()[:8]
            if submitted_user_hash != current_user_hash:
                # 获取用户所在的队伍
                team = Team.objects.filter(
                    members=user,
                    competition__in=challenge.competition_set.all()
                ).first()
                
                competition = challenge.competition_set.first()
                
                # 记录作弊行为
                if team and competition:
                    CheatingLog.objects.create(
                        team=team,
                        competition=competition,
                        cheating_type='manual',
                        description=f"用户 {user.username} 在题目 {challenge.title} 中使用了其他用户的flag。"
                                  f"提交的flag: {submitted_flag}",
                        detected_by="System"
                    )
                return False, "请使用自己的flag，不要使用其他用户的flag"
                
        except Exception as e:
            return False, "Flag不正确，请重新提交"
    
    # 检查提交频率（防止暴力破解）
    rate_limit_key = f"flag_submit_rate:{user.id}:{challenge.id}"
    submit_times = cache.get(rate_limit_key, 0)
    
    if submit_times > 10:  # 假设1分钟内允许10次提交
        # 获取用户所在的队伍和比赛
        team = Team.objects.filter(
            members=user,
            competition__in=challenge.competition_set.all()
        ).first()
        competition = challenge.competition_set.first()
        
        if team and competition:
            CheatingLog.objects.create(
                team=team,
                competition=competition,
                cheating_type='timing',
                description=f"用户 {user.username} 在题目 {challenge.title} 中频繁提交flag。"
                          f"1分钟内提交次数: {submit_times}",
                detected_by="System"
            )
        return False, "提交过于频繁，请稍后再试"
    
    # 更新提交频率计数
    cache.set(rate_limit_key, submit_times + 1, 60)  # 60秒过期
    
    # 验证flag是否正确
    result = (submitted_flag == correct_flag)
    
    # 如果flag正确，从缓存中删除
    if result:
        cache.delete(cache_key)
        return True, None
    
    if submit_times > 10:  
        team = Team.objects.filter(
            members=user,
            competition__in=challenge.competition_set.all()
        ).first()
        competition = challenge.competition_set.first()
        
        if team and competition:
            CheatingLog.objects.create(
                team=team,
                competition=competition,
                cheating_type='exploit',
                description=f"用户 {user.username} 在题目 {challenge.title} 中多次提交错误flag。"
                          f"提交的flag: {submitted_flag}",
                detected_by="System"
            )
    
    return False, "Flag不正确，请重新提交"

def is_suspicious_activity(user, challenge):
    """检查是否存在可疑活动"""
    # 获取用户所在的队伍和比赛
    team = Team.objects.filter(
        members=user,
        competition__in=challenge.competition_set.all()
    ).first()
    competition = challenge.competition_set.first()
    
    if team and competition:
        # 获取最近的提交记录
        recent_logs = CheatingLog.objects.filter(
            team=team,
            competition=competition,
            timestamp__gte=timezone.now() - timezone.timedelta(minutes=30)
        ).count()
        
        return recent_logs >= 3  # 如果30分钟内有3次以上可疑记录，返回True
    return False

def reset_flag(challenge, user):
    """重置用户的 flag"""
    if challenge.flag_type != 'STATIC':
        cache_key = f"flag:{challenge.uuid}:{user.id}"
        cache.delete(cache_key)
        return generate_flag(challenge, user)
    return challenge.flag_template  # 对于静态 flag，直接返回模板