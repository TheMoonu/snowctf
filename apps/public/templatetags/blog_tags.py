# 创建了新的tags标签文件后必须重启服务器
import json
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from django import template
from django.core.cache import cache
from django.db.models.aggregates import Count
from django.utils.html import mark_safe
from django.db.models import Q


register = template.Library()










@register.inclusion_tag('public/tags/pagecut.html', takes_context=True)
def load_pages(context, max_length=10):
    """
    自定义分页
    @param context: 上下文对象
    @param max_length: 最多显示的页面按钮数量
    @return:
    """
    paginator = context['paginator']
    page_obj = context['page_obj']
    # 分页总数不大于最大显示数，则直接显示所有页码
    if paginator.num_pages <= max_length:
        page_range = range(1, paginator.num_pages + 1)
    # 总页码大于总显示的时候，保证当前页码在中间
    else:
        left_num = max(page_obj.number - int(max_length / 2), 1)
        right_num = min(left_num + max_length - 1, paginator.num_pages)
        # 当前页面接近末尾的时候，也要保证能显示max_length个数
        if right_num - left_num < max_length - 1:
            left_num = right_num - max_length + 1
        page_range = range(left_num, right_num + 1)

    page_range = list(page_range)
    # 对应10个以上的页面，显示省略号，需要模板支持
    if 10 <= max_length < paginator.num_pages:
        if page_range[-1] == paginator.num_pages - 1:
            page_range.append(paginator.num_pages)
        elif page_range[-1] < paginator.num_pages - 1:
            page_range[-1] = "..."
            page_range.append(paginator.num_pages)

        if page_range[0] == 2:
            page_range.insert(0, 1)
        elif page_range[0] > 2:
            page_range[0] = "..."
            page_range.insert(0, 1)

    context['page_range'] = page_range
    return context







@register.simple_tag
def get_star(num):
    """得到一排星星"""
    tag_i = '<i class="fa fa-star"></i>'
    return mark_safe(tag_i * num)


@register.simple_tag
def get_star_title(num):
    """得到星星个数的说明"""
    the_dict = {
        1: '【1颗星】：微更新，涉及轻微调整或者后期规划了内容',
        2: '【2颗星】：小更新，小幅度调整，一般不会迁移表格',
        3: '【3颗星】：中等更新，一般会增加或减少模块，有表格的迁移',
        4: '【4颗星】：大更新，涉及到应用的增减',
        5: '【5颗星】：最大程度更新，一般涉及多个应用和表格的变动',
    }
    return the_dict[num]


@register.simple_tag
def my_highlight(text, q):
    """自定义标题搜索词高亮函数，忽略大小写"""
    if len(q) > 1:
        try:
            text = re.sub(q, lambda a: '<span class="highlighted">{}</span>'.format(a.group()),
                          text, flags=re.IGNORECASE)
            text = mark_safe(text)
        except:
            pass
    return text


@register.simple_tag
def get_request_param(request, param, default=None):
    """获取请求的参数"""
    return request.POST.get(param) or request.GET.get(param, default)





@register.simple_tag
def now_hour():
    """返回当前时间的小时数"""
    return datetime.now().hour


@register.simple_tag
def deal_with_full_path(full_path, key, value):
    """
    处理当前路径，包含参数的
    @param value: 参数值
    @param key: 要修改的参数，也可以新增
    @param full_path: /search/?q=python&page=2
    @return: 得到新的路径
    """
    parsed_url = urlparse(full_path)
    query_params = parse_qs(parsed_url.query)
    # 去除参数key
    query_params[key] = value
    # 重新生成URL
    updated_query_string = urlencode(query_params, doseq=True)
    updated_url = urlunparse(parsed_url._replace(query=updated_query_string))
    return updated_url


@register.filter(is_safe=True)
def my_slice(value, arg):
    """
    复制内置的标签函数，截断字符串，并给字符串添加...
    {{ friend.description|my_slice:":23" }}
    """
    try:
        bits = []
        for x in str(arg).split(':'):
            if not x:
                bits.append(None)
            else:
                bits.append(int(x))
        result = value[slice(*bits)]
        if isinstance(value, str):
            # 超过长度则在后面补...
            if len(value) > bits[-1]:
                result += '...'
            # 不是从头开始，则在前面补...
            if bits[0]:
                result = '...' + result
        return result

    except (ValueError, TypeError):
        return value



    
    return value



