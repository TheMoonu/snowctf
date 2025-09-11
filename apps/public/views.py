from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from .utils import sanitize_html,validate_docker_compose,escape_xss,unescape_content,create_captcha_for_registration
from django.db import transaction
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from datetime import timedelta
from challenge.models import Challenge,Tag,DockerCompose
from container.models import UserContainer, DockerEngine
from competition.models import Competition, ScoreUser, ScoreTeam, Team,CheatingLog,Registration,Submission
from .docker_service import DockerService, DockerServiceException
from .flag_generator import get_or_generate_flag, verify_flag as verify_flag_func
from .redis_cache import UserContainerCache
from django.db.models import Count, Exists, OuterRef
from django.conf import settings
from django.views import generic
import time
from django.views.generic import TemplateView
from datetime import datetime
from django.db.models import F
from easytask.tasks import cleanup_container
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef, Q
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from urllib3.exceptions import NewConnectionError, MaxRetryError
from requests.exceptions import ConnectionError, ReadTimeout
from haystack.query import SearchQuerySet
import docker
import json
import requests
import uuid
import random
import math
from docker.errors import APIError,DockerException
from .view_api import create_container_api
from celery import current_app
from django.views.generic import CreateView, FormView
from django.urls import reverse_lazy
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from functools import wraps
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
import re
from .services import DashboardService
import yaml
from django.utils.functional import cached_property
import hashlib
from django.views.generic import ListView
from django.urls import reverse
from .forms import TeamSelectionForm, PersonalInfoForm
from django.views.decorators.cache import cache_page

def prevent_duplicate_submission(timeout=5):
    """
    防重复提交装饰器
    timeout: 限制时间(秒)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # 生成用户特定的缓存key
            cache_key = f"submit_lock:{request.user.id}:{self.__class__.__name__}"
            
            # 检查是否存在锁
            if cache.get(cache_key):
                return JsonResponse({
                    'status': 'error',
                    'message': f'请等待{timeout}秒后再次提交'
                }, status=429)
                
            # 设置锁
            cache.set(cache_key, True, timeout)
            
            try:
                return func(self, request, *args, **kwargs)
            finally:
                # 操作完成后删除锁
                cache.delete(cache_key)
                
        return wrapper
    return decorator

@login_required
@require_http_methods(["GET"])
def check_container_status(request):
    try:
        challenge_uuid = request.GET.get('challenge_uuid')
        if not challenge_uuid:
            return JsonResponse({"error": "缺少挑战 UUID"}, status=400)

        cached_container = UserContainerCache.get(request.user.id, challenge_uuid)
        if cached_container:
            ports = json.loads(cached_container['port'])
            container_urls = []
            
            # 如果有域名，使用相同的随机前缀
            random_prefix = uuid.uuid4().hex[:8] if cached_container['domain'] else None
            
            # 为每个端口生成URL
            for port in ports.values():
                if cached_container['domain']:
                    url = f"http://{random_prefix}.{cached_container['domain']}:{port}"
                else:
                    url = f"http://{cached_container['ip_address']}:{port}"
                container_urls.append(url)
                
            return JsonResponse({
                "status": "active",
                "container_urls": container_urls,
                "expires_at": cached_container['expires_at']
            })
        else:
            # 用户没有创建容器
            return JsonResponse({"status": "inactive"})
    except Exception as e:
        return JsonResponse({"error": "请求错误"}, status=500)

   
@require_http_methods(["POST"])
def create_web_container(request, slug):
    try:
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest' and not request.method == "POST":
            return JsonResponse({"error": "请求错误"}, status=500)
        if not request.user.is_authenticated:
            return JsonResponse({"error": "请先登录"}, status=500)
        if not request.POST.get('challenge_uuid'):
            return JsonResponse({"error": "缺少挑战 UUID"}, status=400)
        challenge_uuid = request.POST.get('challenge_uuid')
        competition_slug = slug
        challenge = Challenge.objects.get(uuid=challenge_uuid)

        competition = get_object_or_404(Competition, slug=competition_slug)
        super_user = request.user.is_superuser or request.user.is_staff

        if challenge not in competition.challenges.all():
            return JsonResponse({
                'error': '该题目不属于当前比赛'
            }, status=400)
        if competition:  
            registration = Registration.objects.filter(
                competition=competition,
                user=request.user
            ).first()
           
            if not registration and not super_user:
                return JsonResponse({
                    "error": "您还未报名该比赛，请先报名后再尝试"
                }, status=403)

            if not super_user:
            # 如果是团队赛，检查用户是否在队伍中
                if competition.competition_type == Competition.TEAM and not registration.team_name:
                    return JsonResponse({
                        "error": "团队赛需要加入队伍后才能参与"
                    }, status=403)

        cached_container = UserContainerCache.get(request.user.id, challenge_uuid)
        if cached_container:
            ports = json.loads(cached_container['port'])
            container_urls = []
            
            # 如果有域名，使用相同的随机前缀
            random_prefix = uuid.uuid4().hex[:8] if cached_container['domain'] else None
            
            # 为每个端口生成URL
            for port in ports.values():
                if cached_container['domain']:
                    url = f"http://{random_prefix}.{cached_container['domain']}:{port}"
                else:
                    url = f"http://{cached_container['ip_address']}:{port}"
                container_urls.append(url)
                
            return JsonResponse({
                "status": "active",
                "container_urls": container_urls,
                "expires_at": cached_container['expires_at']
            })
        
        result, error = create_container_api(challenge_uuid, request.user)
        if error:
            return JsonResponse({"error": error}, status=400)
            cache_key = f'user_ctf_stats_{request.user.id}' 
            cache.delete(cache_key)
        if result:
            time.sleep(10)
            return JsonResponse(result, status=200)
        else:
            return JsonResponse({"error": "创建容器失败"}, status=500)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    

@login_required
@require_http_methods(["DELETE"])
def remove_container(request, container_id):
    container = get_object_or_404(UserContainer, container_id=container_id, user=request.user)
    docker_engine = container.docker_engine
    

    if docker_engine.tls_enabled:
        tls_configs = docker_engine.get_tls_config()
    else:
        tls_configs = None 
    docker_service = DockerService(
        url=container.docker_engine.url,
        tls_config=tls_configs
    )
    
    try:
        docker_service.remove_container(container_id)
        container.delete()
        return JsonResponse({"message": "容器已成功移除"})
    except Exception as e:
        return JsonResponse({"error": f"移除容器失败: {str(e)}"}, status=500)


@login_required
@require_http_methods(["POST"])
def verify_flag(request, slug):
    """验证flag提交接口"""
    # 请求方法检查
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method != "POST":
        return JsonResponse({"status": "error", "message": "请求错误"}, status=500)
    
    # 获取参数
    challenge_uuid = request.POST.get('challenge_uuid')
    submitted_flag = request.POST.get('flag')
    
    if not all([challenge_uuid, submitted_flag]):
        return JsonResponse({'status': 'error', 'message': '缺少必要参数'}, status=400)
    
    # 获取比赛和题目
    competition = get_object_or_404(Competition, slug=slug)
    challenge = get_object_or_404(Challenge, uuid=challenge_uuid)
    super_user = request.user.is_superuser or request.user.is_staff
    user = request.user
    
    # 检查题目是否属于比赛
    if challenge not in competition.challenges.all():
        return JsonResponse({
            'status': 'error',
            'message': '该题目不属于当前比赛'
        }, status=400)
    
    # 检查用户是否报名
    if super_user:
        is_correct, error_msg = verify_flag_func(submitted_flag, challenge, user)
        if is_correct:
            return JsonResponse({
                        'status': 'success',
                        'message': f'恭喜！Flag 正确，您测试成功'
                    })
        else:
            return JsonResponse({
                        'status': 'error',
                        'message': f'Flag 不正确，请再试一次'
                    })


    registration = Registration.objects.filter(
        competition=competition,
        user=user
    ).first()
    
    if not registration:
        return JsonResponse({
            'status': 'error',
            'message': '您还未报名该比赛，请先报名后再尝试'
        }, status=403)
    
    # 检查题目和比赛状态
    if not challenge.is_active:
        return JsonResponse({'status': 'error', 'message': '该题目当前未启用'}, status=400)
    
    now = timezone.now()
    if now < competition.start_time:
        return JsonResponse({'status': 'error', 'message': '比赛尚未开始'}, status=400)
    if now > competition.end_time:
        return JsonResponse({'status': 'error', 'message': '比赛已经结束'}, status=400)
    
    # 检查容器题目
    is_docker = False
    if challenge.docker_compose:
        is_docker = True
        cached_container = UserContainerCache.get(user.id, challenge_uuid)
        if not cached_container or \
           datetime.fromisoformat(cached_container['expires_at']) < timezone.now() or \
           cached_container['challenge_uuid'] != str(challenge_uuid):
            return JsonResponse({'status': 'error', 'message': '题目环境未创建或环境已过期'}, status=400)
    
    try:
        with transaction.atomic():
            # 获取用户IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

            # 获取用户所在队伍（如果是团队赛）
            team = None
            if competition.competition_type == Competition.TEAM:
                team = Team.objects.filter(
                    members=user,
                    competition=competition
                ).first()
                
                if not team:
                    return JsonResponse({
                        'status': 'error', 
                        'message': '团队赛需要加入队伍后才能参与'
                    }, status=400)

            # 检查是否已解决
            if competition.competition_type == Competition.TEAM:

                score_team = ScoreTeam.objects.filter(
                    team=team, 
                    competition=competition
                ).first()
                if score_team and challenge in score_team.solved_challenges.all():
                    return JsonResponse({
                        'status': 'error', 
                        'message': '您的队伍已经解决了这道题目'
                    }, status=400)
            else:

                score_user = ScoreUser.objects.filter(
                    user=user,
                    competition=competition
                ).first()
                if score_user and challenge in score_user.solved_challenges.all():
                    return JsonResponse({
                        'status': 'error', 
                        'message': '您已经解决了这道题目'
                    }, status=400)
            
            # 验证flag

            is_correct, error_msg = verify_flag_func(submitted_flag, challenge, user)

            # 创建提交记录
   
            # 团队赛 - 包含team
            submission = Submission.objects.create(
                challenge=challenge,
                user=user,
                competition=competition,
                team=team,
                flag=submitted_flag,
                status='correct' if is_correct else 'wrong',
                ip=ip,
                points_earned=0
            )

            if error_msg:
                return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
            if is_correct:
                points_earned = challenge.points
                # 更新题目解题次数和动态分数
                challenge.add_solve()
                challenge.refresh_from_db()  # 确保从数据库获取最新数据
                
                # 获取最新的动态分数
                points_earned = challenge.points
                

                competition_duration = (competition.end_time - competition.start_time).total_seconds()
                time_elapsed = (now - competition.start_time).total_seconds()
                
                # 计算最大奖励分数（题目初始分数的10%）
                max_bonus = int(challenge.initial_points * 0.1)
                
                # 分段函数实现前期快速衰减
                time_ratio = max(0, min(1, time_elapsed / competition_duration))
                if time_ratio < 0.25:
                    bonus_ratio = 1.0 - (0.7 * time_ratio / 0.25)
                else:
                    # 剩余时间从30%降到0%
                    bonus_ratio = 0.3 * (1.0 - (time_ratio - 0.25) / 0.75)
                time_bonus = int(max_bonus * bonus_ratio)
                # 基于解题数量的奖励
                solve_count = challenge.solves
                
                # 设置顺序奖励
                # 首个解题：额外奖励等于最大奖励
                # 第二个解题：额外奖励为最大奖励的50%
                # 第三个解题：额外奖励为最大奖励的30%
                if solve_count == 0:  # 这是第一个解出的
                    order_bonus = max_bonus 
                elif solve_count == 1:  # 第二个解出
                    order_bonus = int(max_bonus * 0.6)
                elif solve_count == 2:  # 第三个解出
                    order_bonus = int(max_bonus * 0.3)
                elif 3 <= solve_count < 10: # 前10名还有少量奖励 
                    order_bonus = int(max_bonus * 0.1)
                else:
                    order_bonus = 0
                total_bonus = time_bonus + order_bonus
                total_points = points_earned + total_bonus
                # 更新提交记录的得分
                submission.points_earned = total_points
                submission.save()
                
                score_user, _ = ScoreUser.objects.get_or_create(
                    user=user,
                    team=team,
                    competition=competition,
                    defaults={'points': 0}
                )
                 
                score_user.update_score(total_points)
                score_user.solved_challenges.add(challenge)
    
                cache_key = f'user_ctf_stats:{user.id}:{competition.id}'
                cache.delete(cache_key)
                # 如果是团队赛，更新团队分数
                if competition.competition_type == Competition.TEAM:
                    score_team, _ = ScoreTeam.objects.get_or_create(
                        team=team,
                        competition=competition,
                        defaults={'score': 0}
                    )
                    score_team.update_score(total_points)
                    score_team.solved_challenges.add(challenge)
                    
                    # 更新一血信息
                    
                    return JsonResponse({
                        'status': 'success',
                        'is_docker': is_docker,
                        'message': f'恭喜！Flag 正确，您的队伍题目剩余 {points_earned} 分, 解题速度奖励 {total_bonus} 分, 总得分 {total_points} 分'
                    })
                else:
                    # 更新一血信息
                    return JsonResponse({
                        'status': 'success',
                        'is_docker': is_docker,
                        'message': f'恭喜！Flag 正确，获得 {points_earned} 分, 解题速度奖励 {total_bonus} 分, 总得分 {total_points} 分'
                    })
            
            # flag验证失败
            return JsonResponse({'status': 'error', 'message': 'Flag 不正确，请再试一次'})
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"验证flag时发生错误: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)   


# 更新 create_web_container_view 函数
def create_web_container_view(request):
    return CTFChallengeListView.as_view()(request)

@login_required
def challenge_detail(request, slug, uuid):
    # 获取对应的比赛
    competition = get_object_or_404(Competition, slug=slug)
    
    # 获取特定的挑战
    challenge = get_object_or_404(competition.challenges.all(), uuid=uuid)

    super_user = request.user.is_superuser or request.user.is_staff
    if super_user:
        messages.info(request, "您是管理员，可以对题目进行测试")
    if challenge not in competition.challenges.all():
        messages.warning(request, "该题目不属于当前比赛")
        return redirect('public:competition_detail', slug=slug)
    if competition:  
        registration = Registration.objects.filter(
            competition=competition,
            user=request.user
        ).first()

        
        if not registration and not super_user:
            messages.warning(request, "您还未报名该比赛，请先报名后再尝试")
            return redirect('public:competition_detail', slug=slug)
        
        

    # 检查访问权限
    if not competition.is_running() and not super_user:
        if competition.status == 'pending':
            messages.warning(request, f"比赛尚未开始，将于 {competition.start_time.strftime('%Y-%m-%d %H:%M')} 开始")
            
        else:  # ended
            messages.warning(request, f"比赛已于 {competition.end_time.strftime('%Y-%m-%d %H:%M')} 结束")
        return redirect('public:competition_detail', slug=slug)
    if not challenge.is_active:
        messages.warning(request, "该题目当前未启用，暂时无法访问")
        return redirect('public:competition_detail', slug=slug)


    file_url = None
    if challenge.static_files and (competition.is_running() or super_user):
        file_url = challenge.static_files.get_file_url()

    context = {
        'challenge': challenge,
        'competition': competition,
        'file_url': file_url,
        'super_user': super_user,
    }
    return render(request, 'public/tags/challenge_detail.html', context)


@login_required
@require_http_methods(["POST"])
def destroy_web_container(request):
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({"error": "请求错误"}, status=400)
    
    user = request.user
    challenge_uuid = request.POST.get('challenge_uuid')
    
    try:
        challenge = get_object_or_404(Challenge, uuid=challenge_uuid)
        user_containers = UserContainer.objects.filter(user=user, challenge=challenge)
        
        if not user_containers.exists():
            if UserContainerCache.get(user.id, challenge_uuid):
                UserContainerCache.delete(user.id, challenge_uuid)
            if cache.get(f"flags:{challenge.uuid}:{user.id}"):
                cache.delete(f"flags:{challenge.uuid}:{user.id}")
            
            return JsonResponse({'status': 'success', 'message': '容器已被摧毁'}, status=200)

        
        docker_services = {}
        for user_container in user_containers:
            try:
                docker_engine = user_container.docker_engine
                if docker_engine.id not in docker_services:
                    # 获取或创建 DockerService 实例
                    if docker_engine.host_type == 'LOCAL':
                        docker_url = "unix:///var/run/docker.sock"
                    else:
                        docker_url = f"tcp://{docker_engine.host}:{docker_engine.port}"
                    tls_config = docker_engine.get_tls_config() if docker_engine.tls_enabled else None
                    docker_services[docker_engine.id] = DockerService(url=docker_url, tls_config=tls_config)
                
                docker_service = docker_services[docker_engine.id]
                
                # 停止并移除容器
                docker_service.stop_and_remove_container(user_container.container_id)

                task_id = cache.get(f"cleanup_task_{user_container.container_id}")
                if task_id:
                    
                    current_app.control.revoke(task_id, terminate=True)
                    cache.delete(f"cleanup_task_{user_container.container_id}")
                
                # 删除 UserContainer 记录
                user_container.delete()
                
            except Exception as e:
                error_msg = f"销毁容器 时发生错误{e}"
                return JsonResponse({'error': error_msg}, status=500)
        
        # 清除缓存
        UserContainerCache.delete(user.id, challenge_uuid)
        cache.delete(f"flags:{challenge.uuid}:{user.id}")
        return JsonResponse({'status': 'success', 'message': '所有相关容器已销毁'})
    
    except Challenge.DoesNotExist:
        return JsonResponse({'error': '找不到指定的题目'}, status=404)
    
    except Exception as e:
        error_msg = f"销毁容器时发生未知错误"
        return JsonResponse({'error': error_msg}, status=500)

    finally:
        if UserContainerCache.get(user.id, challenge_uuid):
            UserContainerCache.delete(user.id, challenge_uuid)
        if cache.get(f"flags:{challenge.uuid}:{user.id}"):
            cache.delete(f"flags:{challenge.uuid}:{user.id}")


@login_required
@require_http_methods(["POST"])
def delete_challenge(request):
    try:
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"error": "请求错误"}, status=400)
        
        user = request.user
        challenge_uuid = request.POST.get('challenge_uuid')

        try:
            challenge = get_object_or_404(Challenge, uuid=challenge_uuid)
            if not challenge.user_can_manage(user):
                return JsonResponse({
                    "error": "您没有权限删除此题目",
                    "redirect": reverse('ctf:challenge_detail', kwargs={'uuid': challenge_uuid})
                }, status=403)
            
            success, message = challenge.safe_delete(user)
            
            if success:
                messages.success(request, message)
                return JsonResponse({
                    "redirect": reverse('ctf:challenge_list')
                })
            else:
                messages.error(request, message)
                return JsonResponse({
                    "redirect": reverse('ctf:challenge_detail', kwargs={'uuid': challenge_uuid})
                }, status=400)
        
        except Challenge.DoesNotExist:
            return JsonResponse({"error": "题目不存在"}, status=404)
    except Exception as e:
        print(e)


def CompetitionViewList(request):
    # 获取所有比赛对象
    competitions = Competition.objects.all().order_by('-start_time')  # 按创建时间倒序

    # 获取搜索参数
    search_query = request.GET.get('q', '')
    
    # 应用搜索过滤
    if search_query:
        competitions = competitions.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query) |
            Q(slug__icontains=search_query)
        )

    # 获取筛选参数
    status_filter = request.GET.get('status')
    type_filter = request.GET.get('type')

    # 根据状态筛选
    if status_filter == 'upcoming':
        competitions = competitions.filter(start_time__gt=timezone.now())
    elif status_filter == 'ongoing':
        competitions = competitions.filter(start_time__lte=timezone.now(), end_time__gte=timezone.now())
    elif status_filter == 'ended':
        competitions = competitions.filter(end_time__lt=timezone.now())

    # 根据类型筛选
    if type_filter == 'individual':
        competitions = competitions.filter(competition_type='individual')
    elif type_filter == 'team':
        competitions = competitions.filter(competition_type='team')

    # 设置分页
    page = request.GET.get('page', 1)
    paginate_by = getattr(settings, 'COMPETITION_PER_PAGE', 8)  # 从settings获取每页显示数量，默认10
    paginator = Paginator(competitions, paginate_by, 
                         orphans=getattr(settings, 'BASE_ORPHANS', 0))  # orphans防止最后一页数量太少

    try:
        competitions = paginator.page(page)
    except PageNotAnInteger:
        competitions = paginator.page(1)
    except EmptyPage:
        competitions = paginator.page(paginator.num_pages)

    context = {
        'competitions': competitions,
        'now': timezone.now(),
        'paginator': paginator,
        'is_paginated': paginator.num_pages > 1,  # 是否需要分页
        'page_obj': competitions,  # 当前页对象
        'search_query': search_query,  # 将搜索词传递给模板
        'status_filter': status_filter,  # 将状态筛选传递给模板
        'type_filter': type_filter,  # 将类型筛选传递给模板
        'total_count': paginator.count,  # 总结果数
    }
    # 渲染模板并传递比赛对象列表和当前时间
    return render(request, 'public/competition.html', context)


class Competition_detail(ListView):
    model = Competition
    template_name = 'public/ctf_index.html'
    context_object_name = 'challenges'
    paginate_by = 28
    paginate_orphans = getattr(settings, 'BASE_ORPHANS', 0)

    @method_decorator(never_cache)
    @method_decorator(require_http_methods(["GET", "POST"]))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        """获取查询集，包含所有过滤条件"""
        # 基础查询集
        competition_slug = self.kwargs.get('slug')
        competition = get_object_or_404(Competition, slug=competition_slug)
        queryset = competition.challenges.filter(is_active=True)

        # 应用类型过滤
        challenge_type = self.request.GET.get('type')
        if challenge_type and challenge_type != 'ALL':
            queryset = queryset.filter(category=challenge_type)
        
        # 应用难度过滤
        difficulty = self.request.GET.get('difficulty')
        if difficulty and difficulty != 'ALL':
            queryset = queryset.filter(difficulty=difficulty)


        # 应用搜索过滤
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            # 将搜索词分割成单独的关键词
            keywords = search_query.split()
            search_results = SearchQuerySet().models(Challenge)
            
            # 对每个关键词进行搜索
            for keyword in keywords:
                search_results = search_results.filter(content__contains=keyword)
                    
            challenge_ids = [result.pk for result in search_results]
            if not challenge_ids:
                # 如果全文搜索没有结果，尝试使用数据库模糊搜索
                query = Q()
                for keyword in keywords:
                    query |= Q(title__icontains=keyword) | Q(description__icontains=keyword)
                queryset = queryset.filter(query)
            else:
                queryset = queryset.filter(id__in=challenge_ids)

        # 应用解决状态过滤
        if self.request.user.is_authenticated:
            if competition.competition_type == 'team':
                # 团队赛 - 检查用户所在队伍的解题记录
                team = Team.objects.filter(
                    members=self.request.user,
                    competition=competition
                ).first()
                
                if team:
                    solved_subquery = ScoreTeam.objects.filter(
                        team=team,
                        competition=competition,
                        solved_challenges=OuterRef('pk')
                    )
                else:
                    # 用户不在队伍中，显示所有题目为未解决
                    solved_subquery = ScoreTeam.objects.none()
            else:
                # 个人赛 - 检查用户个人的解题记录
                solved_subquery = ScoreUser.objects.filter(
                    user=self.request.user,
                    competition=competition,
                    solved_challenges=OuterRef('pk')
                )

            queryset = queryset.annotate(is_solved=Exists(solved_subquery))
            
            status = self.request.GET.get('status')
            if status == 'solved':
                queryset = queryset.filter(is_solved=True)
            elif status == 'unsolved':
                queryset = queryset.filter(is_solved=False)

        # 添加解题次数注解
        if competition.competition_type == 'team':
            # 团队赛 - 统计解决该题目的团队数
            queryset = queryset.annotate(
                solve_count=Count('scoreteam', filter=Q(scoreteam__competition=competition))
            )
        else:
            # 个人赛 - 统计解决该题目的用户数
            queryset = queryset.annotate(
                solve_count=Count('scoreuser', filter=Q(scoreuser__competition=competition))
            )

        # 应用排序
        sort_by = self.request.GET.get('sort_by', 'id')
        if sort_by == 'solve_count':
            queryset = queryset.order_by('-solve_count', 'id')
        elif sort_by == 'points':
            queryset = queryset.order_by('-points', 'id')
        else:
            queryset = queryset.order_by('-is_top', '-id')

        return queryset.distinct()

    def paginate_queryset(self, queryset, page_size):
        """重写分页方法，处理空页面情况"""
        paginator = self.get_paginator(
            queryset, 
            page_size,
            orphans=self.paginate_orphans,
            allow_empty_first_page=True
        )
        page_kwarg = self.page_kwarg
        page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or 1
        
        try:
            page_number = int(page)
            page = paginator.page(page_number)
        except (ValueError, EmptyPage):
            page = paginator.page(1)
            
        return (paginator, page, page.object_list, page.has_other_pages())

    def get(self, request, *args, **kwargs):
        """重写 get 方法，处理分页重定向"""
        try:
            return super().get(request, *args, **kwargs)
        except EmptyPage:
            url = request.path
            query = request.GET.copy()
            query['page'] = '1'
            if query:
                url += '?' + query.urlencode()
            return redirect(url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        competition_slug = self.kwargs.get('slug')
        competition = get_object_or_404(Competition, slug=competition_slug)

        # 获取挑战类型
        challenge_types_key = f"competition_{competition_slug}_challenge_types"
        challenge_types = cache.get(challenge_types_key)
        if challenge_types is None:
            challenge_types = list(competition.challenges.values_list('category', flat=True).distinct())
            cache.set(challenge_types_key, challenge_types, 60 * 60)
        context['challenge_types'] = challenge_types

        # 获取难度级别
        difficulties_key = f"competition_{competition_slug}_difficulties"
        difficulties = cache.get(difficulties_key)
        if difficulties is None:
            difficulties = list(competition.challenges.values_list('difficulty', flat=True).distinct())
            cache.set(difficulties_key, difficulties, 60 * 60)
        context['difficulties'] = difficulties

        # 添加比赛信息
        context.update({
            'competition_title': competition.title,
            'end_time': competition.end_time,
            'competition_slug': competition.slug,
            'competition': competition,
        })

        # 添加团队信息（如果是团队赛）
        if competition.competition_type == 'team' and self.request.user.is_authenticated:
            context['user_team'] = Team.objects.filter(
                members=self.request.user,
                competition=competition
            ).first()

        # 添加用户得分信息
        if self.request.user.is_authenticated:
            if competition.competition_type == 'team':
                team = context.get('user_team')
                if team:
                    score_info = ScoreTeam.objects.filter(
                        team=team,
                        competition=competition
                    ).first()
                    context['score_info'] = score_info
            else:
                score_info = ScoreUser.objects.filter(
                    user=self.request.user,
                    competition=competition
                ).first()
                context['score_info'] = score_info

        # 添加当前的查询参数到上下文
        context.update({
            'current_type': self.request.GET.get('type', 'ALL'),
            'current_difficulty': self.request.GET.get('difficulty', 'ALL'),
            'current_status': self.request.GET.get('status', 'ALL'),
            'current_sort': self.request.GET.get('sort_by', 'id'),
            'current_author': self.request.GET.get('author', 'all'),
            'current_tag': self.request.GET.get('tag', ''),
            'search_query': self.request.GET.get('q', ''),
            
            'sort_options': [
                ('id', '默认'),
                ('solve_count', '解题次数'),
                ('points', '分数')
            ],
            'author_options': [
                ('all', '所有题目'),
                ('me', '我的题目')
            ],
            'status_options': ['ALL', 'solved', 'unsolved'],
            'user_authenticated': self.request.user.is_authenticated,
        })

        return context

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)



@login_required
def registrationView(request, slug, re_slug):
    competition = get_object_or_404(Competition, slug=slug, re_slug=re_slug)
    current_step = request.session.get('registration_step', 1)
    
    # 检查是否已经报名
    if Registration.objects.filter(competition=competition, user=request.user).exists():
        messages.error(request, '您已经报名过该比赛')
        return redirect('public:competition_detail', slug=slug)
    
    # 检查用户是否已经在某个队伍中（针对团队赛）
    if competition.competition_type == Competition.TEAM:
        if Team.objects.filter(competition=competition, members=request.user).exists():
            team = Team.objects.filter(competition=competition, members=request.user).first()
            if current_step == 1:
                messages.success(request, f'您已经是队伍 "{team.name}" 的成员，请继续完成报名')
                request.session['team_id'] = team.id
                request.session['registration_step'] = 2
                
                return redirect('competition:registration_detail', slug=slug, re_slug=re_slug)
            elif 'team_id' not in request.session:
                request.session['team_id'] = team.id 
    now = timezone.now()
    if now >= competition.start_time:
        messages.error(request, '比赛已开始，无法报名')
        return redirect('public:competition_detail', slug=slug)
        
    # 检查比赛是否已结束
    if now >= competition.end_time:
        messages.error(request, '比赛已结束，无法报名')
        return redirect('public:competition_detail', slug=slug)

    # 生成验证码
    captcha_data = create_captcha_for_registration()

    if request.method == 'POST':
        if 'previous' in request.POST:
            current_step = max(1, current_step - 1)
            request.session['registration_step'] = current_step
            return redirect('competition:registration_detail', slug=slug, re_slug=re_slug)

        # 团队赛处理逻辑
        if competition.competition_type == Competition.TEAM:
            if current_step == 1:
                form = TeamSelectionForm(request.POST)
                if form.is_valid():
                    team_action = form.cleaned_data['team_action']
                    team_name = form.cleaned_data['team_name']
                    
                    # 检查用户是否已经在某个队伍中
                    if Team.objects.filter(competition=competition, members=request.user).exists():
                        existing_team = Team.objects.filter(competition=competition, members=request.user).first()
                        messages.error(request, f'您已经是队伍 "{existing_team.name}" 的成员，不能创建或加入其他队伍')
                        return redirect('competition:registration_detail', slug=slug, re_slug=re_slug)
                    
                    try:
                        if team_action == 'create':
                            # 检查队伍名称是否已存在
                            if Team.objects.filter(name=team_name, competition=competition).exists():
                                messages.error(request, '该队伍名称已存在')
                                return redirect('competition:registration_detail', slug=slug, re_slug=re_slug)
                            
                            team = Team.objects.create(
                                name=team_name,
                                leader=request.user,
                                competition=competition
                            )
                            team.members.add(request.user)
                        else:
                            team = Team.objects.get(name=team_name, competition=competition)
                            if team.members.count() >= team.member_count:
                                messages.error(request, '该队伍已满')
                                return redirect('competition:registration_detail', slug=slug, re_slug=re_slug)
                            team.members.add(request.user)
                        
                        request.session['team_id'] = team.id
                        current_step = 2
                        request.session['registration_step'] = current_step
                        return redirect('competition:registration_detail', slug=slug, re_slug=re_slug)
                    except Team.DoesNotExist:
                        messages.error(request, '未找到该队伍')
                        return redirect('competition:registration_detail', slug=slug, re_slug=re_slug)

            elif current_step == 2:
                form = PersonalInfoForm(request.POST)
                if form.is_valid():
                    registration = form.save(commit=False)
                    registration.user = request.user
                    registration.competition = competition
                    registration.registration_type = Competition.TEAM
                    registration.team_name = Team.objects.get(id=request.session.get('team_id'))
                    registration.save()
                    
                    # 清除session
                    del request.session['registration_step']
                    if 'team_id' in request.session:
                        del request.session['team_id']
                    
                    messages.success(request, '报名成功！')
                    return redirect('public:competition_detail', slug=slug)

        # 个人赛处理逻辑
        else:
            form = PersonalInfoForm(request.POST)
            if form.is_valid():
                registration = form.save(commit=False)
                registration.user = request.user
                registration.competition = competition
                registration.registration_type = Competition.INDIVIDUAL
                registration.save()
                
                messages.success(request, '报名成功！')
                return redirect('public:competition_detail', slug=slug)

    else:
        if competition.competition_type == Competition.TEAM:
            form = TeamSelectionForm() if current_step == 1 else PersonalInfoForm()
        else:
            form = PersonalInfoForm()

    context = {
        'form': form,
        'competition': competition,
        'current_step': current_step,
        'total_steps': 2 if competition.competition_type == Competition.TEAM else 1,
        'is_team_competition': competition.competition_type == Competition.TEAM,
        'captcha_key': captcha_data['captcha_key'],
        'captcha_image': captcha_data['captcha_image']
    }
    return render(request, 'public/registration.html', context)

def refresh_captcha(request):
    """刷新验证码的API端点"""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        captcha_data = create_captcha_for_registration()
        return JsonResponse({
            'success': True,
            'captcha_key': captcha_data['captcha_key'],
            'captcha_image': captcha_data['captcha_image']
        })
    return JsonResponse({'success': False, 'message': '非法请求'}, status=400)


class SubmissionDynamicView(TemplateView):
    """解题动态视图 - 表格形式展示解题情况"""
    template_name = 'public/submission_dynamic.html'

    @method_decorator(cache_page(10))  # 缓存10秒
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        slug = self.kwargs['slug']

        # 获取比赛
        competition = get_object_or_404(Competition, slug=slug)
        context['competition'] = competition

        # 获取所有正确的提交
        submissions = Submission.objects.filter(
            competition=competition,
            status='correct'
        ).select_related(
            'challenge',
            'user',
            'team'
        ).order_by('created_at')

        # 题目列表（横向表头）
        challenges = list(competition.challenges.all().order_by('id'))

        context['challenges'] = challenges

        # 队伍/个人列表（纵向表头）
        players = {}
        for s in submissions:
            team_name = s.team.name if s.team else s.user.username
            if team_name not in players:
                players[team_name] = {
                    'name': team_name,
                    'submissions': {}
                }

        # 计算每个题目的排名（谁是第 1、2、3 血）
        first_solves = {}  # {challenge_id: [user1, user2, user3]}
        for s in submissions:
            cid = s.challenge.id
            solver = s.team.name if s.team else s.user.username
            if cid not in first_solves:
                first_solves[cid] = []
            if solver not in first_solves[cid]:
                first_solves[cid].append(solver)

        # 填充表格数据
        for s in submissions:
            cid = s.challenge.id
            solver = s.team.name if s.team else s.user.username

            if cid in first_solves and solver in first_solves[cid]:
                rank = first_solves[cid].index(solver) + 1  # 1,2,3 血
                if rank == 1:
                    status = "一血"
                elif rank == 2:
                    status = "二血"
                elif rank == 3:
                    status = "三血"
                else:
                    status = "已解决"
            else:
                status = "已解决"

            players[solver]['submissions'][cid] = status

        context['players'] = players.values()
        return context



class SubmissionDynamicView_test(TemplateView):
    """解题动态视图 - 展示所有解题记录"""
    template_name = 'public/submission_dynamic.html'
    
    @method_decorator(cache_page(30))  # 缓存30秒
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        slug = self.kwargs['slug']
        
        competition = get_object_or_404(Competition, slug=slug)
        context['competition'] = competition
        
        # 获取解题动态数据
        submissions = Submission.objects.filter(
            competition=competition,
            status='correct'  # 只显示正确的提交
        ).select_related(
            'challenge', 
            'user', 
            'team'
        ).order_by('-created_at')[:100]  # 显示最近100条
        
        # 处理提交数据，添加是否一血信息
        submission_data = []
        for submission in submissions:
            # 检查是否是一血
            is_first_blood = not Submission.objects.filter(
                challenge=submission.challenge,
                competition=competition,
                status='correct',
                created_at__lt=submission.created_at
            ).exists()
            
            submission_data.append({
                'submission': submission,
                'is_first_blood': is_first_blood,
                'submission_time': submission.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'team_name': submission.team.name if submission.team else '个人参赛',
                'user_name': submission.user.username,
                'challenge_title': submission.challenge.title,
                'points_earned': submission.points_earned,
                'category': submission.challenge.category if hasattr(submission.challenge, 'category') else '其他'
            })
        
        context['submission_data'] = submission_data
        context['total_submissions'] = len(submission_data)
        print(context['submission_data'])
        return context


@method_decorator(cache_page(30), name='dispatch')
class SubmissionDynamicAPIView(generic.View):
    """解题动态API视图 - 提供JSON格式的解题数据"""
    
    def get(self, request, slug):
        """获取解题动态API数据"""
        competition = get_object_or_404(Competition, slug=slug)
        
        # 获取分页参数
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        
        # 计算偏移量
        offset = (page - 1) * page_size
        
        # 获取解题动态数据
        submissions = Submission.objects.filter(
            competition=competition,
            status='correct'
        ).select_related(
            'challenge', 
            'user', 
            'team'
        ).order_by('-created_at')[offset:offset + page_size]
        
        # 构建响应数据
        data = []
        for submission in submissions:
            is_first_blood = not Submission.objects.filter(
                challenge=submission.challenge,
                competition=competition,
                status='correct',
                created_at__lt=submission.created_at
            ).exists()
            
            data.append({
                'id': submission.id,
                'challenge': {
                    'id': submission.challenge.id,
                    'title': submission.challenge.title,
                    'category': submission.challenge.category if hasattr(submission.challenge, 'category') else '其他',
                    'points': submission.challenge.points
                },
                'user': {
                    'id': submission.user.id,
                    'username': submission.user.username,
                    'display_name': submission.user.get_full_name() or submission.user.username
                },
                'team': {
                    'id': submission.team.id if submission.team else None,
                    'name': submission.team.name if submission.team else '个人参赛'
                },
                'submission_time': submission.created_at.isoformat(),
                'formatted_time': submission.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'points_earned': submission.points_earned,
                'is_first_blood': is_first_blood,
                'relative_time': self.get_relative_time(submission.created_at)
            })
        
        # 获取总数用于分页
        total_count = Submission.objects.filter(
            competition=competition,
            status='correct'
        ).count()
        
        return JsonResponse({
            'data': data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total_count,
                'pages': (total_count + page_size - 1) // page_size
            }
        })
    
    def get_relative_time(self, dt):
        """获取相对时间描述"""
        now = timezone.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days}天前"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}小时前"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}分钟前"
        else:
            return "刚刚"


class RankingsView(TemplateView):
    template_name = 'public/rankings.html'
    
    @method_decorator(cache_page(60))  # 缓存整个页面1分钟
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        slug = self.kwargs['slug']
        ranking_type = self.kwargs['ranking_type']
        
        competition = get_object_or_404(Competition, slug=slug)
        context['competition'] = competition
        
        if ranking_type == 'individual':
            rankings = ScoreUser.objects.filter(
                competition=competition
            ).select_related('user', 'team').order_by('-points', 'created_at')
            context['ranking_title'] = '个人排行'
            context['is_individual'] = True
        else:
            rankings = ScoreTeam.objects.filter(
                competition=competition
            ).select_related('team').order_by('-score', 'time')
            context['ranking_title'] = '队伍排行'
            context['is_individual'] = False
            
        context['rankings'] = rankings
        context['ranking_type'] = ranking_type
        
        return context


@login_required
def competition_dashboard(request, slug):
    competition = get_object_or_404(Competition, slug=slug)
 
    if competition.competition_type == Competition.INDIVIDUAL:
        messages.warning(request, "该比赛为个人赛，无法查看比赛数据")
        return redirect('public:competition_detail', slug=slug)
    
    if competition:  
        registration = Registration.objects.filter(
            competition=competition,
            user=request.user
        ).first()
        
        if not registration and not request.user.is_superuser and not request.user.is_staff:
            messages.warning(request, "您还未报名该比赛，无法查看比赛数据")
            return redirect('public:competition_detail', slug=slug)
    context = {
        'competition': competition,
    }
    return render(request, 'public/dashboard.html', context)


@login_required
def get_dashboard_data(request, slug):
    """获取比赛大屏数据"""
    competition = get_object_or_404(Competition, slug=slug)
    service = DashboardService(competition.id)
    
    try:
        # 从Redis缓存获取数据
        redis_conn = service.redis_conn
        prefix = service.prefix
        
        # 使用pipeline批量获取数据
        pipeline = redis_conn.pipeline()
        pipeline.get(f"{prefix}stats")
        pipeline.get(f"{prefix}leaderboard")
        pipeline.get(f"{prefix}category_stats")
        pipeline.get(f"{prefix}recent_submissions")
        pipeline.get(f"{prefix}score_trends")
        
        # 执行pipeline
        stats, leaderboard, category_stats, recent_submissions, score_trends = pipeline.execute()
        
        # 如果缓存中没有数据，重新计算
        if not stats:
            stats = service.calculate_stats()
        else:
            stats = json.loads(stats)
            
        if not leaderboard:
            leaderboard = service.calculate_leaderboard()
        else:
            leaderboard = json.loads(leaderboard)
            
        if not category_stats:
            category_stats = service.calculate_category_stats()
        else:
            category_stats = json.loads(category_stats)
            
        if not recent_submissions:
            recent_submissions = service.get_recent_submissions()
        else:
            recent_submissions = json.loads(recent_submissions)
            
        if not score_trends:
            score_trends = service.get_score_trends()
        else:
            score_trends = json.loads(score_trends)
        
        # 获取时间线数据（从最近提交记录中提取）
        timeline_data = []
        for submission in recent_submissions:
            if submission['status'] == 'success':
                timeline_data.append({
                    'time': submission['time'],
                    'team': submission['team'],
                    'challenge': submission['challenge'],
                    'category': submission['category'],
                    'points': submission.get('points', 0)
                })
        
        return JsonResponse({
            'stats': stats,
            'leaderboard': leaderboard,
            'timeline_data': timeline_data,
            'series_data': score_trends,
            'recent_submissions': recent_submissions,
            'category_stats': category_stats
        })
        
    except Exception as e:
        print(e)
        # 如果发生错误，记录日志并返回错误信息
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"获取大屏数据失败: {str(e)}", exc_info=True)
        
        return JsonResponse({
            'error': '获取数据失败，请稍后重试',
        }, status=500)


def refresh_captcha(request):
    """刷新验证码的API端点"""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        captcha_data = create_captcha_for_registration()
        return JsonResponse({
            'success': True,
            'captcha_key': captcha_data['captcha_key'],
            'captcha_image': captcha_data['captcha_image']
        })
    return JsonResponse({'success': False, 'message': '非法请求'}, status=400)