from django.core.cache import cache
from django_redis import get_redis_connection
from django.db.models import Count, F, Q, Avg, FloatField
from datetime import timedelta
import json
from competition.models import Competition, Registration, ScoreTeam, ScoreUser, Submission
from challenge.models import Challenge

class DashboardService:
    def __init__(self, competition_id):
        self.competition_id = competition_id
        self.redis_conn = get_redis_connection("default")
        self.prefix = f"ctf:dashboard:{competition_id}:"
        self.competition = Competition.objects.get(id=competition_id)
    
    def calculate_stats(self):
        """计算基础统计数据"""
        # 使用缓存
        cache_key = f"{self.prefix}stats"
        stats = self.redis_conn.get(cache_key)
        
        if stats:
            return json.loads(stats)
        stats = {
            'participant_count': Registration.objects.filter(
                competition=self.competition
            ).count(),
            'submission_count': Submission.objects.filter(
                competition=self.competition
            ).count(),
            'solved_rate': round(
                Submission.objects.filter(
                    competition=self.competition,
                    status='correct'  # 只计算正确的提交
                ).count() / 
                max(Submission.objects.filter(
                    competition=self.competition
                ).count(), 1),  # 总提交次数，避免除以零
                2  # 保留两位小数
            ),
            'total_challenges': self.competition.challenges.count()
        }
     
        # 缓存5分钟
        self.redis_conn.setex(cache_key, 300, json.dumps(stats))
        return stats
    
    def calculate_leaderboard(self):
        """计算排行榜数据"""
        cache_key = f"{self.prefix}leaderboard"
        leaderboard = self.redis_conn.get(cache_key)
        
        if leaderboard:
            return json.loads(leaderboard)
            
        if self.competition.competition_type == 'team':
            scores = ScoreTeam.objects.filter(
                competition=self.competition
            ).select_related('team').order_by('score')[:10]
            
            leaderboard = [{
                'name': score.team.name,
                'score': score.score,
                'rank': idx + 1,
                'solved_count': score.solved_challenges.count(),
                'last_solved': Submission.objects.filter(
                    team=score.team,
                    status='correct'
                ).order_by('-created_at').first().created_at.strftime('%H:%M:%S') if Submission.objects.filter(
                    team=score.team,
                    status='correct'
                ).exists() else None
            } for idx, score in enumerate(scores)]
        else:
            scores = ScoreUser.objects.filter(
                competition=self.competition
            ).select_related('user').order_by('points')[:10]
            
            leaderboard = [{
                'name': score.user.username,
                'score': score.points,
                'rank': idx + 1,
                'solved_count': score.solved_challenges.count(),
                'last_solved': Submission.objects.filter(
                    user=score.user,
                    status='correct'
                ).order_by('-created_at').first().created_at.strftime('%H:%M:%S') if Submission.objects.filter(
                    user=score.user,
                    status='correct'
                ).exists() else None
            } for idx, score in enumerate(scores)]
        
        # 缓存2分钟
        self.redis_conn.setex(cache_key, 120, json.dumps(leaderboard))
        return leaderboard
    
    def calculate_category_stats(self):
        """计算分类完成情况"""
        cache_key = f"{self.prefix}category_stats"
        stats = self.redis_conn.get(cache_key)
        
        if stats:
            return json.loads(stats)
            
        challenges = self.competition.challenges.all()
        category_stats = []
        
        # 获取所有分类的统计数据
        category_counts = challenges.values('category').annotate(
            total=Count('id'),
            solved=Count('submissions', filter=Q(submissions__status='correct'), distinct=True)
        )
        
        for cat in category_counts:
            if cat['total'] > 0:
                category_stats.append({
                    'category': cat['category'],
                    'total': cat['total'],
                    'solved': cat['solved'],
                    'percent': round(cat['solved'] / cat['total'] * 100, 1)
                })
        
        # 缓存5分钟
        self.redis_conn.setex(cache_key, 300, json.dumps(category_stats))
        return category_stats
    
    def get_recent_submissions(self):
        """获取最近提交记录"""
        cache_key = f"{self.prefix}recent_submissions"
        submissions = self.redis_conn.get(cache_key)
        
        if submissions:
            return json.loads(submissions)
            
        submissions = Submission.objects.filter(
            challenge__in=self.competition.challenges.all()
        ).select_related(
            'team', 'user', 'challenge'
        ).order_by('-created_at')[:20]
        
        recent_submissions = []
        for sub in submissions:
            recent_submissions.append({
                'team': sub.team.name if sub.team else sub.user.username,
                'status': 'success' if sub.status == 'correct' else 'wrong',
                'challenge': sub.challenge.title,
                'category': sub.challenge.get_category_display(),  # 获取可读的分类名称
                'time': sub.created_at.strftime('%H:%M:%S'),
                'points': sub.points_earned if sub.status == 'correct' else 0,
                'is_first_blood': sub.is_first_blood()
            })
        
        # 缓存30秒
        self.redis_conn.setex(cache_key, 30, json.dumps(recent_submissions))
        return recent_submissions

    def get_score_trends(self):
        """获取得分趋势数据"""
        cache_key = f"{self.prefix}score_trends"
        trends = self.redis_conn.get(cache_key)
        
        if trends:
            return json.loads(trends)
            
        # 获取前10名的队伍/用户
        if self.competition.competition_type == 'team':
            top_scores = ScoreTeam.objects.filter(
                competition=self.competition
            ).select_related('team').order_by('-score')[:10]
        else:
            top_scores = ScoreUser.objects.filter(
                competition=self.competition
            ).select_related('user').order_by('-points')[:10]
        
        series_data = []
        # 扩展为10种颜色
        colors = [
            '#00f2fe', '#4facfe', '#00c6fb', '#005bea', '#0099ff',
            '#00e5ff', '#0066ff', '#00d4ff', '#0088ff', '#00bbff'
        ]
        
        # 获取比赛开始时间
        start_time = self.competition.start_time
        
        for idx, score in enumerate(top_scores):
            filter_kwargs = {
                'status': 'correct',
                'challenge__in': self.competition.challenges.all()
            }
            
            if self.competition.competition_type == 'team':
                filter_kwargs['team'] = score.team
            else:
                filter_kwargs['user'] = score.user
            
            submissions = Submission.objects.filter(
                **filter_kwargs
            ).order_by('created_at')
            
            data_points = []
            current_score = 0
            
            # 添加起始点
            data_points.append([
                start_time.strftime('%Y-%m-%d %H:%M:%S'),
                0
            ])
            
            for sub in submissions:
                current_score += sub.points_earned
                data_points.append([
                    sub.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    current_score
                ])
            
            if len(data_points) > 1:
                series_data.append({
                    'name': score.team.name if self.competition.competition_type == 'team' else score.user.username,
                    'type': 'line',
                    'data': data_points,
                    'smooth': True,
                    'symbol': 'none',
                    'lineStyle': {
                        'width': 2,
                        'color': colors[idx]
                    },
                    'areaStyle': {
                        'opacity': 0.1,
                        'color': colors[idx]
                    }
                })
        
        if series_data:
            self.redis_conn.setex(cache_key, 60, json.dumps(series_data))
        
        return series_data