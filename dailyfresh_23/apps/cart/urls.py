# -*- coding:utf-8 -*-
from django.conf.urls import url
from cart import views

urlpatterns = [
    # 添加购物车
    url(r'^add$', views.AddCartView.as_view(), name='add'),

    # 展示购物车数据
    url(r'^$', views.CartInfoView.as_view(), name='info'),

    # 更新购物车
    url(r'^update$', views.UpdateCartView.as_view(), name='update'),

    # 删除购物车
    url(r'^delete$', views.DeleteCartView.as_view(), name='detele'),
]