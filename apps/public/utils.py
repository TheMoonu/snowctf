import bleach
import html
import re

import time
import logging
from functools import wraps
from datetime import datetime
from django.apps import apps as django_apps
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
import random
import string
import uuid
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64
from django.core.cache import cache

def html_to_md_link(content):
    """将 HTML 链接转回 markdown 格式"""
    def replace_html_link(match):
        url = match.group(1)
        return f'<{url}>'
    
    return re.sub(r'<a href="([^"]+)">[^<]+</a>', replace_html_link, content)

def unescape_content(content):
    """还原已转义的内容"""
    content = html.unescape(content)
    # 将 HTML 链接转回 markdown 格式
    content = html_to_md_link(content)
    return content

def sanitize_html(html_content):
    # 0. 先还原已转义的内容
    content = unescape_content(html_content)
    
    # 1. 保存 markdown 链接
    links = {}
    def save_link(match):
        placeholder = f"LINK_{len(links)}"
        links[placeholder] = match.group(0)
        return placeholder
    
    content = re.sub(r'<(https?://[^>]+)>', save_link, content)
    
    # 2. 转义 HTML
    content = html.escape(content, quote=False)
    
    # 3. 还原并处理 markdown 链接
    def process_link(match):
        url = match.group(1)
        return f'<a href="{url}">{url}</a>'
    
    for placeholder, link in links.items():
        html_link = re.sub(r'<(https?://[^>]+)>', process_link, link)
        content = content.replace(placeholder, html_link)
    
    # 4. 清理 HTML
    allowed_tags = [
        'p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
        'em', 'strong', 'del', 'a', 'img',
        'table', 'thead', 'tbody', 'tr', 'th', 'td'
    ]
    allowed_attributes = {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title'],
        'code': ['class'],
        '*': ['class']
    }
    
    cleaned_html = bleach.clean(content, 
                              tags=allowed_tags, 
                              attributes=allowed_attributes, 
                              protocols=['http', 'https', 'mailto'],
                              strip=True)
    return cleaned_html

def escape_xss(content):
    return html.escape(content, quote=False)

import yaml
from typing import Tuple, Union

def validate_docker_compose(yaml_content: str) -> Tuple[bool, Union[str, None]]:
    """
    验证是否是有效的 docker-compose.yml 格式
    
    Args:
        yaml_content (str): 要验证的 YAML 字符串内容
        
    Returns:
        Tuple[bool, Union[str, None]]: 返回一个元组，包含:
            - bool: 是否是有效的 docker-compose 格式
            - Union[str, None]: 如果无效，返回错误信息；如果有效，返回 None
    """
    try:
        compose_data = yaml.safe_load(yaml_content)
        
        # 检查是否是字典类型
        if not isinstance(compose_data, dict):
            return False, "docker-compose 配置必须是一个字典格式"
            
        # 检查版本号
        if 'version' not in compose_data:
            return False, "缺少 version 字段"
            
        # 检查服务定义
        if 'services' not in compose_data:
            return False, "缺少 services 字段"
            
        services = compose_data['services']
        if not isinstance(services, dict):
            return False, "services 必须是一个字典格式"
            
        # 验证每个服务的必要字段
        for service_name, service_config in services.items():
            if not isinstance(service_config, dict):
                return False, f"服务 '{service_name}' 的配置必须是字典格式"
                
            # 检查是否至少包含 image 或 build 中的一个
            if 'image' not in service_config and 'build' not in service_config:
                return False, f"服务 '{service_name}' 必须指定 image 或 build"

        return True, None
        
    except yaml.YAMLError as e:
        return False, f"YAML 格式错误: {str(e)}"
    except Exception as e:
        return False, str(e)








logger = logging.getLogger('django')

def site_protocol():
    """
    返回当前使用的协议 http|https，可以给很多需要用到网站完整地址的地方调用
    :return: 当前协议
    """
    protocol = getattr(settings, 'PROTOCOL_HTTPS', 'http')
    return protocol
def site_domain():
    """
    获取当前站点的域名，这个域名实际上是去读数据库的sites表
    settings 配置中需要配置 SITE_ID ，INSTALLED_APPS 中需要添加 django.contrib.sites
    :return: 当前站点域名
    """
    if not django_apps.is_installed('django.contrib.sites'):
        raise ImproperlyConfigured(
            "get site_domain requires django.contrib.sites, which isn't installed.")

    Site = django_apps.get_model('sites.Site')
    current_site = Site.objects.get_current()
    domain = current_site.domain
    return domain

def site_full_url():
    """
    返回当前站点完整地址，协议+域名
    :return:
    """
    protocol = site_protocol()
    domain = site_domain()
    print('{}://{}'.format(protocol, domain))
    return '{}://{}'.format(protocol, domain)

from django.core.cache import cache
import json
from django.core.serializers.json import DjangoJSONEncoder

def clear_ranking_cache(competition_id=None):
    """清除排行榜缓存的辅助函数"""
    cache_keys = [
        f'user_ranking:{"all" if competition_id is None else competition_id}:10',
        f'team_ranking:{"all" if competition_id is None else competition_id}:10'
    ]
    for key in cache_keys:
        cache.delete(key)

    
def generate_captcha(length=4):
    """生成指定长度的随机验证码"""
    characters = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'  
    return ''.join(random.choice(characters) for _ in range(length))

def generate_captcha_image(captcha_text):
    """生成验证码图片"""
    width, height = 120, 40  
    image = Image.new('RGB', (width, height), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype('arial.ttf', 24)  
    except IOError:
        try:
            font = ImageFont.truetype('DejaVuSans.ttf', 24)
        except IOError:
            font = ImageFont.load_default()
    for i in range(2):  
        start_point = (random.randint(0, width // 3), random.randint(0, height))
        end_point = (random.randint(width // 3 * 2, width), random.randint(0, height))
        draw.line([start_point, end_point], fill=(random.randint(100, 200), random.randint(100, 200), random.randint(100, 200)), width=1)
    
    for i in range(15): 
        draw.point((random.randint(0, width), random.randint(0, height)), fill=(random.randint(100, 200), random.randint(100, 200), random.randint(100, 200)))
    
 
    for i, char in enumerate(captcha_text):
       
        color = (random.randint(0, 50), random.randint(0, 50), random.randint(0, 50))
      
        position = (15 + i * 25, 8 + random.randint(-2, 2))  
        draw.text(position, char, font=font, fill=color)
    
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

def create_captcha_for_registration():
    """创建验证码并存储到Redis"""
    captcha_text = generate_captcha()
    captcha_image = generate_captcha_image(captcha_text)
    captcha_key = str(uuid.uuid4())
    
    # 将验证码存储到Redis，设置5分钟过期
    cache.set(f'registration_captcha_{captcha_key}', captcha_text, 300)
    
    return {
        'captcha_key': captcha_key,
        'captcha_image': captcha_image
    }