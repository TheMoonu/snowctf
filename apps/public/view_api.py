from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import json
import time
import uuid
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.db.models import Count
from docker.errors import APIError, DockerException
from requests.exceptions import ConnectionError, ReadTimeout
import docker
from challenge.models import Challenge, DockerCompose
from container.models import UserContainer, DockerEngine
from .redis_cache import UserContainerCache
from .docker_service import DockerService, DockerServiceException
from .flag_generator import get_or_generate_flag, verify_flag as verify_flag_func
from easytask.tasks import cleanup_container
from celery.exceptions import MaxRetriesExceededError
import requests
from requests.exceptions import RequestException
from urllib.parse import urlparse
from django.conf import settings

class ContainerManager:
    def __init__(self, user, challenge_uuid):
        self.user = user
        self.challenge_uuid = challenge_uuid
        self.challenge = get_object_or_404(Challenge, uuid=challenge_uuid)
        self.cache_key = f"{user.id}_{challenge_uuid}"
        self.docker_engine = None
        self.docker_url = None
        self.tls_config = None

    def check_existing_container(self) -> Optional[Dict]:
        """检查已存在的容器"""
        cached_container = UserContainerCache.get(self.user.id, self.challenge_uuid)
        if not cached_container:
            return None

        if cached_container['challenge_uuid'] != str(self.challenge.uuid):
            raise ValueError("一个用户只能启动一个容器")
            
        if datetime.fromisoformat(cached_container['expires_at']) < timezone.now():
            raise ValueError("容器已过期，请重新启动")


    def check_prerequisites(self):
        """检查创建容器的前置条件"""
        if not self.challenge.is_active:
            raise ValueError("该题目当前未启用，暂时无法访问")
        
        active_container = UserContainer.objects.filter(
            user=self.user,
            expires_at__gt=timezone.now()
        ).first()
        
        if active_container:
            raise ValueError(f"您已有一个正在运行的题目环境，请先关闭后再重新启动 (题目标题: {active_container.challenge.title})")

        if cache.get(self.cache_key):
            raise ValueError("一分钟内禁止重复创建容器")

    def _get_docker_engine(self):
        """获取负载最小的Docker引擎"""
        active_engines = list(DockerEngine.objects.filter(is_active=True))
        if not active_engines:
            raise ValueError("没有可用的Docker引擎")
        
        engine_loads = UserContainer.objects.values('docker_engine').annotate(
            container_count=Count('id')
        )
        engine_loads_dict = {
            load['docker_engine']: load['container_count'] 
            for load in engine_loads
        }

        docker_engine = min(
            active_engines, 
            key=lambda engine: engine_loads_dict.get(engine.id, 0)
        )

        if docker_engine.tls_enabled:
            tls_config = docker.tls.TLSConfig(
                client_cert=(
                    docker_engine.client_cert_path, 
                    docker_engine.client_key_path
                ),
                ca_cert=docker_engine.ca_cert_path,
                verify=True
            )
        else:
            tls_config = None

        if docker_engine.host_type == 'LOCAL':
            docker_url = "unix:///var/run/docker.sock"
        else:
            docker_url = f"tcp://{docker_engine.host}:{docker_engine.port}"

        self.docker_engine = docker_engine
        self.docker_url = docker_url
        self.tls_config = tls_config

        return docker_engine

    def _get_docker_service(self, docker_engine):
        """创建Docker服务实例"""
        return DockerService(
            url=self.docker_url,
            tls_config=self.tls_config
        )

    def _create_user_container(self, container, docker_engine, expires_at):
        """创建用户容器记录"""
        return UserContainer.objects.create(
            user=self.user,
            challenge=self.challenge,
            challenge_uuid=self.challenge_uuid,
            docker_engine=docker_engine,
            container_id=container['id'],
            ip_address=docker_engine.host,
            domain=docker_engine.domain,
            port=json.dumps(container['ports']),
            expires_at=expires_at
        )

    def _schedule_cleanup(self, container, docker_engine, expires_at):
        """调度容器清理任务"""
        try:
            # 获取是否需要调整时区的设置
            adjust_timezone = getattr(settings, 'CELERY_ADJUST_TIMEZONE', False)
            
            # 根据设置决定是否调整时区
            eta_time = expires_at
            if adjust_timezone:
                # 减去8小时
                eta_time = expires_at - timedelta(hours=8)
            task = cleanup_container.apply_async(
                args=[
                    container['id'],
                    self.user.id,
                    docker_engine.id
                ],
                eta=eta_time  # 使用可能调整过的时间
            )
            
        except Exception as e:
             # 打印更详细的错误信息
            raise ValueError(f"未能调度清理任务: {e}")
        # 保存任务 ID 到缓存或数据库
        cache.set(f"cleanup_task_{container['id']}", task.id, timeout=3600*2)

    def _cleanup_on_error(self):
        """错误发生时清理资源"""
        UserContainerCache.delete(self.user.id, self.challenge_uuid)
        cache.delete(self.cache_key)
        cache.delete(f"flags:{self.challenge.uuid}:{self.user.id}")
        
        user_containers = UserContainer.objects.filter(user=self.user)
        for container in user_containers:
            container.delete()

    def create_container(self) -> Dict:
        """创建容器"""
        try:
            # 检查前置条件
            self.check_prerequisites()
            
            cache.set(self.cache_key, True, timeout=60)
            docker_engine = self._get_docker_engine()
            docker_service = self._get_docker_service(docker_engine)
            
            containers_info, web_container_info = docker_service.create_containers(
                challenge=self.challenge,
                user=self.user,
                flag=get_or_generate_flag(self.challenge, self.user),
                memory_limit=docker_engine.memory_limit,
                cpu_limit=docker_engine.cpu_limit
            )
            
            return self._handle_container_creation(
                containers_info, 
                web_container_info, 
                docker_engine
            )
        
        except (DockerServiceException, APIError, ConnectionError, ReadTimeout, DockerException) as e:
            self._cleanup_on_error()
            raise
        except Exception as e:
            raise
    def check_container_url(self, url, max_retries=120, timeout=4):
        """
        检查容器URL是否可访问
        """
        for _ in range(max_retries):
            try:
                #print(url)
                response = requests.get(url, timeout=timeout)
                if response.status_code == 200:
                    return True
            except RequestException:
                pass
            time.sleep(1)
        return False

    def _handle_container_creation(self, containers_info, web_container_info, docker_engine) -> Dict:
        """处理容器创建结果"""
        expiry_hours = getattr(settings, 'CONTAINER_EXPIRY_HOURS', 2)
        expires_at = timezone.now() + timedelta(hours=expiry_hours)
        try:
            # 创建容器记录
            user_container = None
            for container in containers_info:
                user_container = self._create_user_container(
                    container, docker_engine, expires_at
                )   
            if not user_container:
                self._cleanup_on_error()
                raise ValueError("没有成功创建任何容器")
            
            UserContainerCache.set(user_container)
            
            self._schedule_cleanup(containers_info[-1], docker_engine, expires_at)

            if web_container_info:
               
                # 返回容器URL
                ports = web_container_info['ports'].values()
                container_urls = []

                # 生成所有URL
                random_prefix = uuid.uuid4().hex[:8]  # 对于域名方式使用相同的随机前缀
                for port in ports:
                    if docker_engine.domain:
                        url = f"http://{random_prefix}.{docker_engine.domain}:{port}"
                    else:
                        url = f"http://{docker_engine.host}:{port}"
                    container_urls.append(url)

                return {
                    "container_urls": container_urls,  # 返回URL列表
                    "expires_at": expires_at
                }
        except Exception as e:
            #
            raise ValueError(f"未能创建 web 容器{e}")

def create_container_api(challenge_uuid, user) -> Tuple[Dict, Optional[str]]:
    """
    创建容器API
    
    Args:
        challenge_uuid: 挑战的UUID
        user: 用户对象
        
    Returns:
        Tuple[Dict, Optional[str]]: (结果数据, 错误信息)
    """
    try:
        container_manager = ContainerManager(user, challenge_uuid)
        existing_container = container_manager.check_existing_container()
        if existing_container:
            return existing_container, None
        result = container_manager.create_container()
        return result, None
        
    except ValueError as e:
        return None, str(e)
    except Exception as e:
        return None, f"题目环境创建失败请稍后再试{e}"