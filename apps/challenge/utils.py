import bleach
import html
import re




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