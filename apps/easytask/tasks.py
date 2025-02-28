# -*- coding: utf-8 -*-
import time
from django.utils import timezone
from celery import shared_task
from django.core.management import call_command
from django.core.cache import cache
from datetime import timedelta
from .utils import TaskResponse

from django.db.models import Count


from container.models import UserContainer,DockerEngine
from public.redis_cache import UserContainerCache
import docker
from docker.errors import NotFound
import logging
logger = logging.getLogger(__name__)
# ... 保留原有的其他任务 ...


@shared_task
def cleanup_container(container_id, user_id, docker_engine_id):
    response = TaskResponse()
    try:
        # 获取 DockerEngine 实例
        docker_engine = DockerEngine.objects.get(id=docker_engine_id)
        
        # 使用DockerEngine的方法获取正确的URL
        docker_url = docker_engine.get_docker_url()
        
        # 构建 TLS 配置
        tls_config = None
        if docker_engine.tls_enabled:
            tls_config = docker_engine.get_tls_config()
        
        # 创建 Docker 客户端
        docker_client = docker.DockerClient(base_url=docker_url, tls=tls_config)
        
        try:
            container = docker_client.containers.get(container_id)
            # 获取容器的网络信息
            network_ids = [net_id for net_id in container.attrs['NetworkSettings']['Networks'].keys()]
            
            # 先处理网络连接
            for network_id in network_ids:
                try:
                    network = docker_client.networks.get(network_id)
                    # 断开网络上的所有容器连接
                    if 'Containers' in network.attrs:
                        for container_in_network in network.attrs['Containers'].keys():
                            try:
                                network.disconnect(container_in_network, force=True)
                            except Exception as e:
                                response.data['network_disconnect_errors'] = f"断开容器 {container_in_network} 的网络连接时出错: {str(e)}"
                except Exception as e:
                    response.data['network_errors'] = f"处理网络 {network_id} 时出错: {str(e)}"
            
            # 停止并删除容器
            container.stop(timeout=10)
            container.remove(force=True)
            response.data['container'] = f"容器 {container_id} 已停止并删除"
            
            # 清理相关网络
            removed_networks = []
            for network_id in network_ids:
                try:
                    network = docker_client.networks.get(network_id)
                    network.remove()
                    removed_networks.append(network_id)
                except docker.errors.NotFound:
                    continue
                except Exception as e:
                    response.data['network_errors'] = f"清理网络 {network_id} 时出错: {str(e)}"
            
            if removed_networks:
                response.data['networks'] = f"已清理网络: {', '.join(removed_networks)}"
            
        except docker.errors.NotFound:
            response.data['container'] = f"容器 {container_id} 未找到，可能已被删除"
        
        # 清理数据库和缓存
        UserContainer.objects.filter(container_id=container_id).delete()
        response.data['database'] = f"已清理容器 {container_id} 的数据库记录"
        
    except DockerEngine.DoesNotExist:
        response.error = f"Docker引擎 ID {docker_engine_id} 不存在"
    except Exception as e:
        response.error = f"清理容器 {container_id} 时发生错误: {str(e)}"
    finally:
        if 'docker_client' in locals():
            docker_client.close()
    
    return response.as_dict()
    # 清理数据库和缓存


@shared_task
def simple_task():
    print(111224234)
    return 1


@shared_task
def update_cache():
    """
    更新各种缓存
    @return:
    """
    response = TaskResponse()
    article_result = action_update_article_cache()
    response.data['article'] = article_result
    # 博客统计信息
    blog_info_result = get_blog_infos()
    response.data['blog_infos'] = blog_info_result
    return response.as_dict()




@shared_task

def destroy_expired_containers():
    # 获取当前时间
    now = timezone.now()

    # 查询所有过期的容器
    expired_containers = UserContainer.objects.filter(expires_at__lt=now, container_id__isnull=False)
    
    if expired_containers.exists():
        for container in expired_containers:
            docker_engine = container.docker_engine

            # 获取 Docker 引擎的连接 URL
            docker_url = docker_engine.get_docker_url()

            # 获取 TLS 配置
            tls_config = docker_engine.get_tls_config()

            # 创建 Docker 客户端
            try:
                if tls_config:
                    # 如果启用了 TLS，使用 TLS 配置
                    client = docker.DockerClient(base_url=docker_url, tls=tls_config)
                else:
                    # 否则，使用普通的 Docker 连接
                    client = docker.DockerClient(base_url=docker_url)

                # 尝试停止并删除容器
                docker_container = client.containers.get(container.container_id)
                network_ids = [net_id for net_id in docker_container.attrs['NetworkSettings']['Networks'].keys()]
            
            # 先处理网络连接
                for network_id in network_ids:
                    try:
                        network = client.networks.get(network_id)
                        # 断开网络上的所有容器连接
                        if 'Containers' in network.attrs:
                            for container_in_network in network.attrs['Containers'].keys():
                                try:
                                    network.disconnect(container_in_network, force=True)
                                except Exception as e:
                                    response.data['network_disconnect_errors'] = f"断开容器 {container_in_network} 的网络连接时出错: {str(e)}"
                    except Exception as e:
                        response.data['network_errors'] = f"处理网络 {network_id} 时出错: {str(e)}"
                    docker_container.stop()  # 停止容器
                    docker_container.remove()  # 删除容器
                
                # 删除数据库中的记录
                container.delete()
                print(f"容器 {container.container_id} 已删除")
            except docker.errors.NotFound:
                print(f"容器 {container.container_id} 未找到，可能已经被删除")
            except Exception as e:
                print(f"无法删除容器 {container.container_id}: {e}")
    else:
        print("没有过期的容器")



@shared_task
def update_dashboard_cache():
    """
    定时更新所有正在进行的比赛的数据大屏缓存
    """
    from django.utils import timezone
    from competition.models import Competition
    from public.services import DashboardService
    
    response = TaskResponse()
    now = timezone.now()
    
    try:
        # 获取所有正在进行的比赛
        active_competitions = Competition.objects.filter(
            start_time__lte=now,
            end_time__gte=now,
            is_active=True
        )
        
        for competition in active_competitions:
            service = DashboardService(competition.id)
            competition_data = {}
            
            # 根据比赛结束时间动态调整更新策略
            time_to_end = competition.end_time - now
            is_final_stage = time_to_end <= timedelta(hours=1)
            
            try:
                # 始终更新的数据
                competition_data['recent_submissions'] = service.get_recent_submissions()
                
                # 如果是最后一小时或者到了常规更新时间，更新其他数据
                if is_final_stage or not service.redis_conn.get(f"{service.prefix}stats"):
                    competition_data.update({
                        'stats': service.calculate_stats(),
                        'leaderboard': service.calculate_leaderboard(),
                        'category_stats': service.calculate_category_stats(),
                        'score_trends': service.get_score_trends()
                    })
                
                response.data[f'competition_{competition.id}'] = {
                    'status': 'success',
                    'updated_fields': list(competition_data.keys()),
                    'is_final_stage': is_final_stage
                }
                
            except Exception as e:
                response.data[f'competition_{competition.id}'] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        response.data['summary'] = f"已处理 {active_competitions.count()} 个比赛的数据"
        
    except Exception as e:
        response.error = f"更新大屏数据时发生错误: {str(e)}"
    
    return response.as_dict()

