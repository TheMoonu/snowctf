import html
import re

def sanitize_content(content):
    # 转义 HTML 特殊字符
    content = html.escape(content)
    
    # 移除可能的脚本标签
    content = re.sub(r'<script.*?>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
    
    # 移除可能的 onclick 和其他危险的属性
    content = re.sub(r'\bon\w+\s*=', '', content, flags=re.IGNORECASE)
    
    # 移除可能的 javascript: 链接
    content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
    
    # 移除可能的数据 URI
    content = re.sub(r'data:\s*\w+/\w+;base64,', '', content, flags=re.IGNORECASE)
    
    return content.strip()