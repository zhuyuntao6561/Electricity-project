"""dailyfresh_23 URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import include, url
from django.contrib import admin


urlpatterns = [
    # 富文本编辑器
    url(r'^tinymce/', include('tinymce.urls')),
    # 站点管理器
    url(r'^admin/', include(admin.site.urls)),
    # 搜索模块 haystack
    url(r'^search/', include('haystack.urls')),
    # 用户模块
    url(r'^users/', include('users.urls', namespace='users')),
    # 商品模块 主页
    url(r'^', include('goods.urls', namespace='goods')),
    # 购物车模块
    url(r'^cart/', include('cart.urls', namespace='cart')),

    # 订单
    url(r'^orders/', include('orders.urls', namespace='orders'))
]
