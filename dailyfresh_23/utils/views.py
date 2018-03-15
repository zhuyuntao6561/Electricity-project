from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from functools import wraps
from django.db import transaction


class LoginRequiredMixin(object):
    """重写as_view()"""

    @classmethod
    def as_view(cls, **initkwargs):
        """使用login_required装饰器,装饰View的as_view()执行之后的结果"""
        view = super().as_view(**initkwargs)

        # 没有把装饰之后的结果返回,只把最原始的结果返回
        # return view

        # 把view装饰装饰之后的结果,返回
        return login_required(view)


def login_required_json(view_func):
    """验证用户是否登录，并响应json"""
    # 装饰器会修改方法的_name_,有可能修改尅视图中定义的请求方法的名字，造成请求分发失败
    # wraps装饰器会保证装饰的函数的_name_，不会被改变，而且会保留原有的说明文档信息
    @wraps(view_func)
    def wraaper(request, *args, **kwargs):
        """判断用户是否登录，如果未登录响应JSON,如果登录进入到视图"""
        if not request.user.is_authenticated():
            return JsonResponse({'code': 1, 'message': '用户未登录'})
        else:
            # 进入视图就是调用视图，保证视图内部的带妈妈可以被执行
            return view_func(request, *args, **kwargs)

    return wraaper


class LoginRequiredJSONMixin(object):
    """订单确认页"""

    @classmethod
    def as_view(cls, **initkwargs):
        """使用login_required装饰器,装饰View的as_view()执行之后的结果"""
        view = super().as_view(**initkwargs)

        # 没有把装饰之后的结果返回,只把最原始的结果返回
        # return view

        # 把view装饰装饰之后的结果,返回
        return login_required_json(view)


class TransactionAtomicMixin(object):
    """事物装饰器"""

    @classmethod
    def as_view(cls, **initkwargs):
        """使用login_required装饰器,装饰View的as_view()执行之后的结果"""
        view = super().as_view(**initkwargs)

        # 没有把装饰之后的结果返回,只把最原始的结果返回
        # return view

        # 把view装饰装饰之后的结果,返回
        return transaction.atomic(view)


