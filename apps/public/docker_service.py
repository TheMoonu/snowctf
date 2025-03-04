import docker
from docker.errors import DockerException, NotFound, APIError
from django.conf import settings
from pypinyin import lazy_pinyin
from .flag_generator import generate_flag
import time
import io
from contextlib import closing, contextmanager
import tempfile
import os
import json
import yaml
import zipfile
import shutil
import uuid
import logging
import tarfile
import re
from .utils import sanitize_html,validate_docker_compose
logger = logging.getLogger(__name__)
class DockerService:
    def __init__(self, url, tls_config=None):
        self.url = url
        self.tls_config = tls_config
        self.network_name = "network"
        self.timeout = 300
        self.temp_dir = None
    
    @contextmanager
    def get_client(self):
        client = docker.DockerClient(base_url=self.url, tls=self.tls_config, timeout=300)
        try:
            yield client
        finally:
            client.close()

    def generate_container_name(self, challenge_title, username, container_type):
        title_pinyin = ''.join(lazy_pinyin(challenge_title))
        username_pinyin = ''.join(lazy_pinyin(username))
        
        # 清理非法字符
        sanitized_title = re.sub(r'[^a-zA-Z0-9_.-]', '_', title_pinyin)
        sanitized_username = re.sub(r'[^a-zA-Z0-9_.-]', '_', username_pinyin)
        return f"{sanitized_title}_{sanitized_username}_{container_type}".lower().replace(' ', '_')

    def create_containers(self, challenge, user, flag, memory_limit, cpu_limit):
        with closing(docker.DockerClient(base_url=self.url, tls=self.tls_config, timeout=300)) as client:
            if challenge.deployment_type == 'COMPOSE':
                return self._create_compose_containers(client, challenge, user, flag, memory_limit, cpu_limit)
            
            
            if challenge.deployment_type == 'STATIC':
                return ""


    def _create_compose_containers(self, client, challenge, user, flag, memory_limit, cpu_limit):
        temp_dir = None
        containers_info = []
        network = None
        
        try:
            compose_config = challenge.docker_compose
            if not compose_config:
                raise DockerServiceException("未找到 Docker Compose 配置")
            
            compose_content = (compose_config.compose_content 
                            if compose_config.compose_type == 'MANUAL' 
                            else compose_config.parsed_compose)
            
            if not compose_content:
                raise DockerServiceException("Docker Compose 配置内容为空")
            
            is_valid, error_message = validate_docker_compose(compose_content)
            if not is_valid:
                
                raise DockerServiceException(f"无效的 DockerCompose 配置: {error_message}")
            
            if compose_config.compose_type == 'FILE':
                temp_dir = self._extract_compose_files(compose_config.compose_file, user)
                self.temp_dir = temp_dir
            
            try:
                
                compose_data = yaml.safe_load(compose_content)
                if compose_config.compose_type == 'FILE':
                    compose_data = self._update_file_paths(compose_data, temp_dir)
                
                title_pinyin = ''.join(lazy_pinyin(challenge.title))
                username_pinyin = ''.join(lazy_pinyin(user.username))
    
                # 清理非法字符
                sanitized_title = re.sub(r'[^a-zA-Z0-9_.-]', '_', title_pinyin)
                sanitized_username = re.sub(r'[^a-zA-Z0-9_.-]', '_', username_pinyin)
                
                project_name = f"{sanitized_title}_{sanitized_username}_{uuid.uuid4().hex[:8]}".lower().replace(' ', '_')
                network_name = f"{project_name}_network"
                network = self._get_or_create_network(client, network_name)
                
                services = compose_data.get('services', {})
                service_order = self._get_service_deploy_order(services)
                
                web_container_info = None
                
                for service_name in service_order:
                    container_info = self._deploy_service(
                        client=client,
                        service_name=service_name,
                        service_config=services[service_name],
                        project_name=project_name,
                        network_name=network_name,
                        flag=flag,
                        flag_type=challenge.flag_type,
                        memory_limit=memory_limit,
                        cpu_limit=cpu_limit,
                        flag_script=compose_config.flag_script
                    )
                    logger.info(f"容器信息: {container_info}")
                    if container_info:
                        containers_info.append(container_info)
                        if service_name != 'db':
                            web_container_info = container_info
                
                return containers_info, web_container_info
                
            except Exception as e:
                raise DockerServiceException(f"部署服务失败: {str(e)}")
                
        except Exception as e:
            
            self._cleanup_compose_deployment(client, containers_info, network)
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise DockerServiceException(f"创建 Docker Compose 容器失败: {str(e)}")
        finally:
            if hasattr(self, 'temp_dir'):
                delattr(self, 'temp_dir')

    def _deploy_service(self, client, service_name, service_config, project_name, 
                       network_name, flag, flag_type, memory_limit, cpu_limit, flag_script):
        container_name = f"{project_name}_{service_name}"
        logger.info(f"部署服务: {container_name}")
        try:
            self._stop_and_remove_container_if_exists(client, container_name)
            
            environment = self._prepare_environment(
                service_name=service_name,
                service_config=service_config,
                flag=flag,
                flag_type=flag_type,
                project_name=project_name
            )
            
            ports = self._prepare_ports(service_config.get('ports', []))
            logger.info(f"环境变量: {environment}")
            logger.info(f"端口: {ports}")
            container = self._prepare_container_config(
                client=client,
                service_config=service_config,
                container_name=container_name,
                network_name=network_name,
                environment=environment,
                ports=ports,
                memory_limit=memory_limit,
                cpu_limit=cpu_limit,
                project_name=project_name
            )
            
            logger.info(f"容器: {container}")
            if flag_script:
                
                logger.info(f"执行flag脚本: {flag_script}")
                try:
                    container.exec_run(flag_script, user='root', privileged=True)
                except Exception as e:
                    raise DockerServiceException(f"执行flag脚本失败: 请联系管理员")

            if not self._wait_for_container(container):
                raise DockerServiceException(f"容器 {container_name} 启动失败")
            

            return self._create_container_info(
                container=container,
                service_name=service_name,
                container_name=container_name,
                ports=ports
            )
            
        except Exception as e:
            
            self._stop_and_remove_container_if_exists(client, container_name)
            raise DockerServiceException(f"部署服务 {service_name} 失败: {str(e)}")

    def _prepare_environment(self, service_name, service_config, flag, flag_type, project_name):
        environment = {
            'FLAG': flag
        }
        
        if 'environment' in service_config:
            env_config = service_config['environment']
            if isinstance(env_config, list):
                for env_item in env_config:
                    if '=' in env_item:
                        key, value = env_item.split('=', 1)
                        # 动态替换 _HOST 结尾的环境变量
                        if key.strip().endswith('_HOST'):
                            value = f"{project_name}_{value.strip()}"
                        # 检查值是否为 $SNOW_FLAG
                        if value.strip() == '$FLAG':
                            value = flag
                        environment[key.strip()] = value.strip()
            elif isinstance(env_config, dict):
                for key, value in env_config.items():
                    if key.endswith('_HOST'):
                        value = f"{project_name}_{value.strip()}"
                    # 检查值是否为 $SNOW_FLAG
                    if str(value).strip() == '$FLAG':
                        value = flag
                    environment[key] = value
        return environment

    def _prepare_ports(self, ports_config):
        ports = {}
        for port_mapping in ports_config:
            if isinstance(port_mapping, str):
                try:
                    if ':' in port_mapping:
                        parts = port_mapping.split(':')
                        container_port = parts[-1]
                    else:
                        container_port = port_mapping
                    container_port = container_port.strip()
                    ports[f'{container_port}/tcp'] = None
                except Exception as e:
                    print(f"解析端口映射失败: {port_mapping}, 错误: {str(e)}")
        return ports


    def wait_for_container_ready(self, container, max_retries=30, delay=2):
        """
        等待容器启动完成

        Args:
            container: Docker 容器对象
            max_retries: 最大重试次数
            delay: 每次重试的间隔时间(秒)

        Returns:
            bool: 容器是否成功启动
        """
        for _ in range(max_retries):
            try:
                # 刷新容器状态
                container.reload()
                
                # 检查容器是否在运行
                if container.status == 'running':
                    return True
                    
            except Exception as e:
                pass
                
            time.sleep(delay)
            
        return False

    def _prepare_container_config(self, client, service_config, container_name, network_name,
                                environment, ports, memory_limit, cpu_limit,project_name):
        try:
            # 首先尝试拉取镜像
            image_name = service_config['image']
            try:
                client.images.get(image_name)
            except docker.errors.ImageNotFound:
                client.images.pull(image_name)
            
            container_config = {
                'image': image_name,
                'name': container_name,
                'detach': True,
                'environment': environment,
                'ports': ports,
                'mem_limit': f"{memory_limit}m",
                'network': network_name,
                'cpu_quota': int(cpu_limit * 100000),
            }

            if 'entrypoint' in service_config:
                container_config['entrypoint'] = service_config['entrypoint']

            try:
                container = client.containers.create(**container_config)
                
                #print(service_config)
                if 'volumes' in service_config:
                    for volume in service_config['volumes']:
                        if isinstance(volume, str):
                            parts = volume.split(':')
                            if len(parts) >= 2:
                                host_path = parts[0]
                                container_path = parts[1]
                                
                                if hasattr(self, 'temp_dir'):
                                    original_path = os.path.join(self.temp_dir, os.path.basename(host_path))
                                    if os.path.exists(original_path):
                                        # 读取文件内容
                                        with open(original_path, 'r', encoding='utf-8') as f:
                                            content = f.read()
                                        
                                        # 替换所有服务引用为对应的容器名
                                        services = service_config.get('depends_on', [])
                                        if isinstance(services, dict):
                                            services = list(services.keys())
                                        
                                        for service in services:
                                            service_container_name = f"{project_name}_{service}"
                                            # 替换常见的服务引用模式
                                            patterns = [
                                                f"http://{service}:",
                                                f"https://{service}:",
                                                f"tcp://{service}:",
                                                f"\"{service}:",
                                                f"'{service}:",
                                                f" {service}:"
                                            ]
                                            for pattern in patterns:
                                                content = content.replace(
                                                    pattern, 
                                                    pattern.replace(service, service_container_name)
                                                )
                                        
                                        # 创建新的临时文件
                                        new_file_path = os.path.join(
                                            self.temp_dir, 
                                            f'modified_{os.path.basename(host_path)}'
                                        )
                                        with open(new_file_path, 'w', encoding='utf-8') as f:
                                            f.write(content)
                                        
                                        # 使用新的文件路径
                                        host_path = new_file_path
                                    
                                    # 创建 tar 流并复制到容器
                                    with open(host_path, 'r', encoding='utf-8') as f:
                                        content = f.read().strip()
                                        content = content.replace('\r\n', '\n')
                                        data = content.encode('utf-8')
                                    
                                    tar_stream = io.BytesIO()
                                    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                                        tarinfo = tarfile.TarInfo(name=os.path.basename(container_path))
                                        tarinfo.size = len(data)
                                        tarinfo.mode = 0o644
                                        tar.addfile(tarinfo, io.BytesIO(data))
                                    
                                    tar_stream.seek(0)
                                    container.put_archive(os.path.dirname(container_path), tar_stream)

                container.start()
                
               
                if 'command' in service_config:
                    container_config['command'] = service_config['command']
                    command = service_config.get('command')
                    if command:
                        try:
                            # 异步执行命令，不等待结果
                            container.exec_run(
                                command,
                                detach=True,  # 分离执行，立即返回
                                privileged=False  # 不使用特权模式
                            )
                        except Exception as e:
                            logger.error(f"执行命令时出错: {str(e)}")
                            raise DockerServiceException(f"容器命令执行失败: {str(e)}")
                return container

            except Exception as e:
                try:
                    container.remove(force=True)
                except:
                    pass
                raise DockerServiceException(f"准备容器配置失败: {str(e)}")

        except Exception as e:
            raise DockerServiceException(f"准备容器配置失败: {str(e)}")

    def _update_file_paths(self, compose_data, temp_dir):
        if not isinstance(compose_data, dict):
            raise DockerServiceException("无效的 compose 配置格式")
                
        services = compose_data.get('services', {})
        if not services:
            raise DockerServiceException("compose 配置中未找到服务定义")
        
        for service_name, service_config in services.items():
            if not isinstance(service_config, dict):
                raise DockerServiceException(f"服务 {service_name} 的配置格式无效")
                    
            if 'volumes' in service_config:
                updated_volumes = []
                volumes = service_config['volumes']
                
                if not isinstance(volumes, list):
                    raise DockerServiceException(
                        f"服务 {service_name} 的 volumes 配置必须是列表格式"
                    )
                
                for volume in volumes:
                    if isinstance(volume, str):
                        parts = volume.split(':')
                        if len(parts) >= 2:
                            host_path = parts[0]
                            container_path = parts[1]
                            mode = parts[2] if len(parts) > 2 else 'rw'
                            
                            if not os.path.isabs(host_path):
                                temp_file_path = os.path.join(temp_dir, os.path.basename(host_path))
                                if os.path.exists(temp_dir):
                                    updated_volume = f"{temp_file_path}:{container_path}:{mode}"
                                    updated_volumes.append(updated_volume)
                                    continue
                            
                            updated_volumes.append(volume)
                        else:
                            updated_volumes.append(volume)
                    else:
                        raise DockerServiceException(
                            f"服务 {service_name} 的卷挂载配置格式无效"
                        )
                        
                service_config['volumes'] = updated_volumes
        
        return compose_data

    def _create_container_info(self, container, service_name, container_name, ports):
        container_info = {
            'id': container.id,
            'name': container_name,
            'type': service_name,
            'ports': {}
        }
        
        if ports:
            container_ports = container.attrs['NetworkSettings']['Ports']
            for port in ports:
                if port in container_ports and container_ports[port]:
                    host_port = int(container_ports[port][0]['HostPort'])
                    container_info['ports'][port.replace('/tcp', '')] = host_port            
        return container_info

    def _wait_for_container(self, container, max_retries=30, retry_interval=1):
        for _ in range(max_retries):
            container.reload()
            if container.status == 'running':
                return True
            elif container.status == 'exited':
                logs = container.logs().decode('utf-8')
                raise DockerServiceException(
                    f"容器异常退出，退码: {container.attrs['State']['ExitCode']}，日志: {logs}"
                )
            time.sleep(retry_interval)
        return False

    def _cleanup_compose_deployment(self, client, containers_info, network):
        cleanup_errors = []
        
        try:
            if containers_info:
                for container_info in containers_info:
                    try:
                        container = client.containers.get(container_info['id'])
                        container.stop(timeout=10)
                        container.remove(force=True)
                    except docker.errors.NotFound:
                        continue
                    except Exception as e:
                        cleanup_errors.append(f"清理容器 {container_info['id']} 失败: {str(e)}")

            if network:
                try:
                    network.remove()
                except docker.errors.NotFound:
                    pass
                except Exception as e:
                    cleanup_errors.append(f"清理网络失败: {str(e)}")

            if cleanup_errors:
                print("清理过程中发生以下错误:")
                for error in cleanup_errors:
                    print(f"- {error}")
                
        except Exception as e:
            print(f"清理资源时发生预期的错误: {str(e)}")

    def _get_service_deploy_order(self, services):
        order = []
        visited = set()
        visiting = set()

        def visit(service_name):
            if service_name in visiting:
                raise DockerServiceException(f"检测到循环依赖: {service_name}")
            if service_name in visited:
                return
                
            visiting.add(service_name)
            service = services.get(service_name, {})
            
            depends_on = service.get('depends_on', [])
            if isinstance(depends_on, dict):
                depends_on = list(depends_on.keys())
                
            for dep in depends_on:
                if dep not in services:
                    raise DockerServiceException(f"服务 {service_name} 依赖的服务 {dep} 不存在")
                visit(dep)
                
            visiting.remove(service_name)
            visited.add(service_name)
            order.append(service_name)

        try:
            for service_name in services:
                if service_name not in visited:
                    visit(service_name)
        except Exception as e:
            raise DockerServiceException(f"解析服务依赖关系失败: {str(e)}")
        return order

    def _extract_compose_files(self, compose_file, user):
        temp_dir = os.path.join(
            tempfile.gettempdir(),
            "ctf", 
            f"ctf_compose_{user.username}_{uuid.uuid4().hex[:8]}"
        )
        
        try:
            os.makedirs(temp_dir, mode=0o755, exist_ok=True)
            self.temp_dir = temp_dir
            self.file_mapping = {}
            
            with zipfile.ZipFile(compose_file.path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                
                for file_path in file_list:
                    try:
                        if file_path.endswith('/'):
                            continue
                            
                        filename = os.path.basename(file_path)
                        if not filename:
                            continue
                            
                        target_path = os.path.join(temp_dir, filename)
                        target_dir = os.path.dirname(target_path)
                        
                        if not os.path.exists(target_dir):
                            os.makedirs(target_dir, mode=0o755)
                        
                        with zip_ref.open(file_path) as source:
                            content = source.read()
                            if not content:
                                continue
                                
                            with open(target_path, 'wb') as target:
                                target.write(content)
                        
                        if filename.endswith('.sh'):
                            os.chmod(target_path, 0o755)
                        
                        self.file_mapping[file_path] = target_path
                        self.file_mapping[filename] = target_path
                        
                    except Exception as e:
                        raise DockerServiceException(f"解压文件 {file_path} 失败: {str(e)}")
                
                return temp_dir
                
        except Exception as e:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise DockerServiceException(f"无yml配置文件")

    def _stop_and_remove_container_if_exists(self, client, container_name):
        try:
            container = client.containers.get(container_name)
            try:
                container.stop(timeout=10)
            except Exception as e:
                print(f"停止容器时出错: {str(e)}")
                
            try:
                container.remove(force=True)
            except Exception as e:
                print(f"强制删除容器时出错: {str(e)}")
                raise
                
        except docker.errors.NotFound:
            pass
        except Exception as e:
            raise DockerServiceException(f"处理已存在的容器时出错: {str(e)}")

    def _get_or_create_network(self, client, network_name=None):
        network_name = network_name or self.network_name
        try:
            network = client.networks.get(network_name)
            return network
        except docker.errors.NotFound:
            return client.networks.create(
                network_name,
                driver="bridge",
                attachable=True
            )

    def _get_container_port(self, container, port):
        ports = container.attrs['NetworkSettings']['Ports']
        if f'{port}/tcp' in ports and ports[f'{port}/tcp']:
            return int(ports[f'{port}/tcp'][0]['HostPort'])
        return None
    
    def stop_and_remove_container(self, container_id):
        with self.get_client() as client:
            try:
                # 获取容器
                container = client.containers.get(container_id)
                
                # 获取容器的网络信息
                network_ids = [net_id for net_id in container.attrs['NetworkSettings']['Networks'].keys()]
                
                # 处理每个网络
                for network_id in network_ids:
                    try:
                        network = client.networks.get(network_id)
                        
                        # 获取网络上的所有容器
                        if 'Containers' in network.attrs:
                            for container_in_network in network.attrs['Containers'].keys():
                                try:
                                    network.disconnect(container_in_network, force=True)
                                except Exception as e:
                                    print(f"断开容器 {container_in_network} 的网络连接时出错: {str(e)}")
                    except Exception as e:
                        print(f"处理网络 {network_id} 时出错: {str(e)}")
                
                # 停止并删除容器
                container.stop(timeout=10)
                container.remove(force=True)
                
                # 清理相关网络
                for network_id in network_ids:
                    try:
                        network = client.networks.get(network_id)
                        network.remove()
                    except NotFound:
                        pass
                    except Exception as e:
                        print(f"清理网络 {network_id} 时出错: {str(e)}")
                        
            except NotFound:
                pass

    @staticmethod
    def get_docker_url(docker_engine):
        if docker_engine.host_type == 'LOCAL':
            return 'unix:///var/run/docker.sock'
        else:
            return f"tcp://{docker_engine.host}:{docker_engine.port}"

class DockerServiceException(Exception):
    pass