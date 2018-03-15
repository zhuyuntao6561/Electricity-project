from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.generic import View, TemplateView
from django.core.urlresolvers import reverse
import re
from goods.models import GoodsSKU
from users.models import User, Address
from django import db
from celery_tasks.tasks import send_active_email
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from django.conf import settings
from itsdangerous import SignatureExpired
from django.contrib.auth import authenticate, login, logout
from utils.views import LoginRequiredMixin
from django_redis import get_redis_connection
import json

# Create your views here.


class UserInfoView(View):
    """查询个人信息，浏览记录"""
    def get(self, request):
        # 获取user
        user = request.user
        # 查询该用户最近创建的地址信息
        try:
            address = user.address_set.latest('create_time')
        except Address.DoesNotExist:
            address = None

        # 查询浏览记录：需要从reids中查询出浏览记录信息
        # 创建链接到redis数据库的对象
        redis_conn = get_redis_connection('default')
        # 查询出需要展示的浏览器记录数据sku_id
        sku_ls = redis_conn.lrange('history_%s' % user.id, 0, 4)
        # 记录sku_id
        sku_list = []
        # 遍历出sku_id
        for sku_id in sku_ls:
            sku = GoodsSKU.objects.get(id=sku_id)
            sku_list.append(sku)
        # 构造上下文
        context = {
            'address': address,
            'sku_list': sku_list
        }

        # 渲染
        return render(request, 'user_center_info.html', context)


class AddressView(LoginRequiredMixin, View):
    """收货地址"""

    def get(self, request):
        """查询地址信息,并且渲染页面,响应给用户"""
        # 获取登录的user
        user = request.user

        # 查询用户最近创建信息:按照地址创建的时间倒序，取出第１个(下标为０的元素)
        # address = Address.objects.filter(user = user).order_by('-create_time')[0]
        # address = user.address_set.order_by('-create_time')[0]
        # latest:默认倒序
        try:
            address = user.address_set.latest('create_time')
        except Address.DoesNotExist:
            # 将来在模板中判断address是否为None,如果为None,就把地址空出来
            address = None
        # 构造上下文
        context = {
            # user不需要单独的传给模板，因为user在request中,而request已经通过render传入了
            # 'user': user,
            'address': address
        }
        # 渲染
        return render(request, 'user_center_site.html', context)

    def post(self, request):
        """编辑地址"""
        recv_name = request.POST.get('recv_name')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        recv_mobile = request.POST.get('recv_mobile')

        # 校验参数：这里只做为空的校验，实际开发要做数据真实性校验
        if all([recv_name, addr, zip_code, recv_mobile]):
            # 保存信息到数据库
            Address.objects.create(
                user=request.user,
                receiver_name=recv_name,
                receiver_mobile=recv_mobile,
                detail_addr=addr,
                zip_code=zip_code
            )

        # 响应结果
        return redirect(reverse('users:address'))
    # url(r'^address$', views.AddressView.as_view(), name='address')

    # url(r'^address$', login_required(views.AddressView.as_view()), name='address')


""""
if request.user.is_authenticated():
    return render(request, 'user_center_site.html')
else:
    return redirect(reverse('users:login'))
"""


class LogoutView(View):
    """退出登录"""

    def get(self, request):
        """处理退出登录逻辑:需要知道谁要退出登录,也就是需要知道清理谁的状态保持数据"""

        logout(request)
        # 也可以重定向到主页
        return redirect(reverse('users:login'))
        # return redirect(reverse('goods:index'))


class LoginView(View):
    """登录"""

    def get(self, request):
        """提供登录页面"""
        return render(request, 'login.html')

    def post(self, request):
        """处理登录逻辑"""
        # 自己实现: 查询用户,判断是否存在,判断是否激活,写入状态保持的信息

        # 接受用户登录表单数据
        user_name = request.POST.get('user_name')
        pwd = request.POST.get('pwd')

        # 对用户进行验证,验证是否是该网站的用户
        user = authenticate(username=user_name, password=pwd)

        # 校验用户是否存在
        if user is None:
            return render(request, 'login.html', {'error': '用户名或密码错误'})

        # 校验是否是激活用户
        if user.is_active is False:
            return render(request, 'login.html', {'error': '请激活'})

        # 能够执行到这里,才说明没有异常,可以登入一个用户.登入用户的同时需要向服务器写入状态保持信息
        # login() : 默认将用户状态保持信息,存储到django_session中
        # 提示 : 如果我们选择使用django_redis作为缓存的后端,并且希望把session数据也存储到redis中,
        # 就需要配置 SESSION_ENGINE 和 SESSION_CACHE_ALIAS,我们的login()会自动的寻找SESSION_ENGINE
        login(request, user)

        # 实现记住用户名/多少天免登陆 : 如果用户勾选了'记住用户名',我们就把状态保持时间设置为10天,反之,设置成0秒
        remembered = request.POST.get('remembered')
        if remembered != 'on':
            request.session.set_expiry(0)  # 设置状态保持0秒
        else:
            request.session.set_expiry(60*60*24*10)  # 设置状态保持10天

        # 在界面跳转之前，将cookie中的购物车数据，添加到redis中
        cart_json = request.COOKIES.get('cart')
        if cart_json is not None:
            cart_dict_cookie = json.loads(cart_json)
        else:
            cart_dict_cookie = {}

        # 查询redis中购物车数据
        redis_conn = get_redis_connection('default')
        cart_dict_redis = redis_conn.hgetall('cart_%s' % user.id)
        # 遍历cookie中购物车数据，sku_id是str，count是int
        for sku_id, count in cart_dict_cookie.items():
            # 将str转成bytes:　特别容易出错点，如果忘记转换类型，判断永远不成立的，所以永远合并不了
            sku_id = sku_id.encode()
            # 判断cookie中的商品在redis中是否存在
            if sku_id in cart_dict_redis:
                origin_count = cart_dict_redis[sku_id]
                # 这里的合并会造成购物车数据里面的数量超出某文件商品的库存
                count += int(origin_count)
                # 此处是伪代码，大家需要知道如果登录和未登录进行合并后，会有库存的问题
                # sku = GoodsSKU.objects.get(id=sku_id)
                # if count > sku.stock:
                #     return '提示用户'

            # 将cookie中的购物车数据添加到redis字典
            cart_dict_redis[sku_id] = count
        # 字典不能为空
        if cart_dict_redis:
            redis_conn.hmset('cart_%s' % user.id, cart_dict_redis)

        # 在登录成功，界面发生跳转之前，需要判断是跳转到主页面还是next参数指向的页面
        next = request.GET.get('next')

        if next is None:
            # 直接登录，跳转到主页
            response = redirect(reverse('goods:index'))
        else:
            if next == '/orders/place':

                response = redirect(reverse('cart:info'))
            else:
                # 跳转到next指向的地址
                response = redirect(next)

        # 清除cookie
        response.delete_cookie('cart')
        return response


class ActiveView(View):
    """用户激活"""

    def get(self, request, token):
        """接受和处理激活请求"""

        # 创建序列化器:参数必须和调用dumps方法是的参数相同
        serializer = Serializer(settings.SECRET_KEY, 3600)

        # 获取token,解出{"confirm": user_id} 需要在签名为过期时,读取结果
        try:
            result = serializer.loads(token)
            # result = token
        except SignatureExpired:
            return HttpResponse('激活链接已过期')

        # 读取user_id :
        user_id = result.get('confirm')

        # 查询要激活的用户
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return HttpResponse('用户不存在')

        # 重置激活状态为True
        user.is_active = True
        # 注意:需要手动保存
        user.save()

        # 响应结果:跳转到登录页面
        return redirect(reverse('users:login'))


class RegisterView(View):
    """注册:类视图"""

    def get(self, request):
        """提供注册页面"""
        return render(request, 'register.html')

    def post(self, request):
        """处理注册表单逻辑"""

        # 接受注册请求参数
        user_name = request.POST.get('user_name')
        pwd = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 校验注册请求参数
        # 判断是否缺少参数:只要有一个为空,就返回假
        if not all([user_name, pwd, email]):
            # 公司中,以开发文档为准
            return redirect(reverse('users:register'))

        # 判断邮箱格式
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'error': '邮箱格式错误'})

        # 判断是否勾选了用户协议
        if allow != 'on':
            return render(request, 'register.html', {'error': '请勾选用户协议'})

        # 保存注册请求参数
        try:
            user = User.objects.create_user(user_name, email, pwd)
        except db.IntegrityError:
            return render(request, 'register.html', {'error': '用户已存在'})

        # 重置激活状态
        user.is_active = False
        user.save()

        # 生成token
        token = user.generate_active_token()

        # 异步发送激活邮件:不能够阻塞 return
        # send_active_email(email, user_name, token)   # 错误写法
        # delay : 触发异步任务
        send_active_email.delay(email, user_name, token)

        # 响应结果
        return redirect(reverse('users:login'))


# def register(request):
#     """
#     注册:函数视图
#     如何在一个视图中,处理多种请求逻辑,前提条件是,多种逻辑对应的请求地址相同,才能找到那个包含有多种逻辑的视图
#     根据不同的请求方法,进行请求逻辑的分发
#     """
#
#     if request.method == 'GET':
#         """提供注册页面"""
#         return render(request, 'register.html')
#
#     if request.method == 'POST':
#         """处理注册表单逻辑"""
#         return HttpResponse('这里是处理注册表单逻辑')
