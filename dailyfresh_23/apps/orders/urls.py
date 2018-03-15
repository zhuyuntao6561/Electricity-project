# -*- coding:utf-8 -*-
from orders import views
from django.conf.urls import url

urlpatterns = [

    # 订单确认页
    url(r'^place$', views.PlaceOrederView.as_view(), name='place'),

    # 提交订单
    url(r'^commit$', views.CommitOrderView.as_view(), name='commit'),

    # 订单信息页面
    url(r'^(?P<page>\d+)$', views.UserOrdersView.as_view(), name='info'),

    # 支付
    url(r'^pay$', views.PayView.as_view(), name='pay'),

    # 查询订单
    url(r'^checkpay$', views.CheckPayView.as_view(), name='checkpay'),

    # 评价信息
    url('^comment/(?P<order_id>\d+)$', views.CommentView.as_view(), name="comment")
]