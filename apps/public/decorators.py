from functools import wraps
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required

def public_required():
    """公共访问装饰器"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def user_required():
    """普通用户访问装饰器"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def admin_required():
    """管理员访问装饰器"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_staff:
                return HttpResponseForbidden('需要管理员权限')
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


from functools import wraps
from django.http import JsonResponse


def api_response(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 检查用户是否已登录
        if not request.user.is_authenticated:
            return JsonResponse({
                'error': True,
                'data': {
                    'code': 'UNAUTHORIZED',
                    'message': '需要登录才能访问此API'
                }
            }, status=401)  # 401 Unauthorized

        # 允许访问
        response = view_func(request, *args, **kwargs)

        # 确保返回的数据是 JsonResponse
        if isinstance(response, JsonResponse):
            return response

        # 如果返回的是其他类型，格式化为 JsonResponse
        return JsonResponse({
            'success': True,
            'data': response
        }, status=200)  # 默认状态码为 200 OK

    return _wrapped_view