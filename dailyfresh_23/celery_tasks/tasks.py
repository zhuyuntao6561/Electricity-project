# -*- coding:utf-8 -*-
from celery import Celery
from django.core.mail import send_mail
from django.conf import settings
from goods.models import GoodsCategory, Goods, GoodsSKU, GoodsImage, IndexGoodsBanner, IndexCategoryGoodsBanner, IndexPromotionBanner
from django.template import loader
import os


#创建Celery客户端(就是Celery对象)
# 参数１：是异步任务的位置 参数２:指定任务存放的队列(Redis)
app = Celery('celery_tasks.tasks', broker='redis://192.168.80.136:6379/3')


@app.task
def send_active_email(to_email, user_name, token):
    """celery客户端对象生产的异步任务"""
    subject = "天天生鲜用户激活"  # 标题
    body = ""  # 文本邮件体
    sender = settings.EMAIL_FROM  # 发件人
    receiver = [to_email]  # 接收人
    html_body = '<h1>尊敬的用户 %s, 感谢您注册天天生鲜！</h1>' \
                '<br/><p>请点击此链接激活您的帐号<a href="http://127.0.0.1:8000/users/active/%s">' \
                'http://127.0.0.1:8000/users/active/%s</a></p>' % (user_name, token, token)
    send_mail(subject, body, sender, receiver, html_message=html_body)


@app.task
def generate_static_index_html():
    """异步生成主页的静态页面"""

    # 查询商品分类信息
    categorys = GoodsCategory.objects.all()
    # 查询图片轮播信息: 默认从小到大排序
    goods_banners = IndexGoodsBanner.objects.all().order_by("index")

    # 查询商品活动信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by("index")

    # 查询商品分类列表信息
    # for category in categorys:
    #     image_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=1)
    #     category.image_banners = image_banners
    #     title_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=0)
    #     category.title_banners = title_banners
    for category in categorys:
        title_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=0).order_by('index')
        category.title_banners = title_banners

        image_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=1).order_by('index')
        category.image_banners = image_banners

    # 查询购物车信息:静态主页不要写购物车数据默认为０
    cart_num = 0

    # 构造上下文
    context = {
        'categorys': categorys,
        'goods_banners': goods_banners,
        'promotion_banners': promotion_banners,
        'cart_num': cart_num
    }

    # 得到模板
    template = loader.get_template('static_index.html')
    # 使用上下文渲染模板，得到模板数据:(不需要响应给用户，而且不需要user信息)放在静态服务器存储
    html_data = template.render(context)
    # 放在静态服务器(celery服务器)
    # 分析：这个异步任务是被celery服务器阅读的，所以生成的html_data(静态文件数据)需要存储在celery服务器的某个路径下，管理静态文件
    file_path = os.path.join(settings.STATICFILES_DIRS[0], 'index.html')
    with open(file_path, 'w') as f:
        f.write(html_data)