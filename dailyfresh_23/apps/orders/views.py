from django.core.paginator import EmptyPage, Paginator
from django.shortcuts import render, redirect
from django.views.generic import View
from utils.views import LoginRequiredMixin, LoginRequiredJSONMixin, TransactionAtomicMixin
from django.core.urlresolvers import reverse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from users.models import Address
from django.http import JsonResponse
from orders.models import OrderGoods, OrderInfo
from django.utils import timezone
from django.db import transaction
from alipay import AliPay
from django.conf import settings
# Create your views here.


class CommentView(LoginRequiredMixin, View):
    """订单评论"""

    def get(self, request, order_id):
        """提供评论页面"""
        user = request.user
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("orders:info"))

        order.status_name = OrderInfo.ORDER_STATUS[order.status]
        order.skus = []
        order_skus = order.ordergoods_set.all()
        for order_sku in order_skus:
            sku = order_sku.sku
            sku.count = order_sku.count
            sku.amount = sku.price * sku.count
            order.skus.append(sku)

        return render(request, "order_comment.html", {"order": order})

    def post(self, request, order_id):
        """处理评论内容"""
        user = request.user
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("orders:info"))

        # 获取评论条数
        total_count = request.POST.get("total_count")
        total_count = int(total_count)

        for i in range(1, total_count + 1):
            sku_id = request.POST.get("sku_%d" % i)
            content = request.POST.get('content_%d' % i, '')
            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            order_goods.comment = content
            order_goods.save()

        order.status = OrderInfo.ORDER_STATUS_ENUM["FINISHED"]
        order.save()

        return redirect(reverse("orders:info", kwargs={"page": 1}))


class CheckPayView(LoginRequiredJSONMixin, View):
    """查询订单状态"""

    def get(self, request):
        """查询订单信息:如果支付成功,需要修改订单状态和记录支付宝维护的订单id,如果失败,返回失败信息"""
        # 获取订单id
        order_id = request.GET.get('order_id')
        # 校验订单id
        if not order_id:
            return JsonResponse({'code': 2, 'message': '没有订单号'})

        # 获取订单信息:状态是待支付，支付方式是支付宝
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=request.user,
                                          status=OrderInfo.ORDER_STATUS_ENUM["UNPAID"],
                                          pay_method=OrderInfo.PAY_METHODS_ENUM["ALIPAY"])

        except OrderInfo.DoesNotExist:
            return JsonResponse({'code': 3, 'message': '订单错误'})

        # 创建用于支付宝支付的对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            # 自己生产的私钥
            app_private_key_path=settings.APP_PRIVATE_KEY_PATH,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥，
            alipay_public_key_path=settings.ALIPAY_PUBLIC_KEY_PATH,
            # RSA或者RSA2
            sign_type='RSA2',
            debug=True  # 默认False配合沙箱模式和使用
        )

        while True:
            # 调用查询接口：
            response = alipay.api_alipay_trade_query(order_id)

            # 读取判断是否失效的数据
            code = response.get('code')
            trade_status = response.get('trade_status')

            # 判断查询之后的结果
            if code == '10000' and trade_status == 'TRADE_SUCCESS':
                # 支付成功
                order.status_id = response.get('trade_on')
                order.status = OrderInfo.ORDER_STATUS_ENUM['UNCOMMENT']
                order.save()
                return JsonResponse({'code': 0, 'message': '支付成功'})
            elif code == '40004' or (code == '10000' and trade_status == 'WAIT_BUYER_PAY'):
                # 业务处理失效，但不能宣告错误，比如系统繁忙
                continue
            else:
                # 支付失败
                return JsonResponse({'code': 4, 'message': '支付失败'})


class PayView(LoginRequiredJSONMixin, View):
    """支付"""
    # 买家账号:awtjwe4419@sandbox.com
    def post(self, request):
        """创建alipay对象,调用支付接口"""

        # 获取订单id
        order_id = request.POST.get('order_id')
        # 校验订单id
        if not order_id:
            return JsonResponse({'code': 2, 'message': '没有订单号'})

        # 获取订单信息:状态是待支付，支付方式是支付宝
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=request.user,
                                          status=OrderInfo.ORDER_STATUS_ENUM["UNPAID"],
                                          pay_method=OrderInfo.PAY_METHODS_ENUM["ALIPAY"])

        except OrderInfo.DoesNotExist:
            return JsonResponse({'code': 3, 'message': '订单错误'})

        # 创建用于支付宝支付的对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            # 自己生产的私钥
            app_private_key_path=settings.APP_PRIVATE_KEY_PATH,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥，
            alipay_public_key_path=settings.ALIPAY_PUBLIC_KEY_PATH,
            # RSA或者RSA2
            sign_type='RSA2',
            debug=True  # 默认False配合沙箱模式和使用
        )

        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(order.total_amount),  # 将浮点数转成字符串
            subject='天天生鲜',
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )
        # 生成url:让用户进入支付宝页面的支付网址
        url = settings.ALIPAY_URL + '?' + order_string

        # 响应结果
        return JsonResponse({'code': 0, 'message': '支付成功', 'url': url})


class UserOrdersView(LoginRequiredMixin, View):
    """用户订单页面"""

    def get(self, request, page):
        """提供订单信息页面"""

        user = request.user
        # 查询所有订单
        orders = user.orderinfo_set.all().order_by("-create_time")

        # 遍历所有订单
        for order in orders:
            # 给订单动态绑定：订单状态
            order.status_name = OrderInfo.ORDER_STATUS[order.status]
            # 给订单动态绑定：支付方式
            order.pay_method_name = OrderInfo.PAY_METHODS[order.pay_method]
            order.skus = []
            # 查询订单中所有商品
            order_skus = order.ordergoods_set.all()
            # 遍历订单中所有商品
            for order_sku in order_skus:
                sku = order_sku.sku
                sku.count = order_sku.count
                sku.amount = sku.price * sku.count
                order.skus.append(sku)

        # 分页
        page = int(page)
        try:
            paginator = Paginator(orders, 2)
            page_orders = paginator.page(page)
        except EmptyPage:
            # 如果传入的页数不存在，就默认给第1页
            page_orders = paginator.page(1)
            page = 1

        # 页数
        page_list = paginator.page_range

        # 构造上下文
        context = {
            "orders": page_orders,
            # 'page_orders': page_orders,
            "page": page,
            "page_list": page_list,
        }
        # 渲染模板
        return render(request, "user_center_order.html", context)


class CommitOrderView(LoginRequiredJSONMixin, TransactionAtomicMixin, View):
    """提交订单"""

    def post(self, request):
        """接受用户提交订单信息,存储到OrderInfo和OrderGoods表中，跳转到全部订单页面"""

        # 获取参数：user,address_id,pay_method,sku_ids,count
        user = request.user
        address_id = request.POST.get('address_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        # 校验参数：all([address_id, pay_method, sku_ids])
        if not all([address_id, sku_ids, pay_method]):
            return JsonResponse({'code': 2, 'message': '缺少参数'})

        # 判断地址
        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return JsonResponse({'code': 3, 'message': '地址不存在'})

        # 判断支付方式
        if pay_method not in OrderInfo.PAY_METHOD:
            return JsonResponse({'code': 4, 'message': '支付方式错误'})

        # 操作redis数据库
        redis_conn = get_redis_connection('default')

        # 截取出sku_ids列表
        sku_ids = sku_ids.split(',')

        # 定义临时变量
        total_count = 0
        total_sku_amount = 0

        # 使用　timezone 模块，创建order_id
        order_id = timezone.now().strftime('%Y%m%d%H%M%S') + str(user.id)

        # 在操作数据库前创建事务保存点
        sid = transaction.savepoint()

        # 暴力回滚
        try:

            # 创建OrderInfo对象
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                address=address,
                total_amount=0,
                trans_cost=10,
                pay_method=pay_method
            )
            # 遍历sku_ids
            for sku_id in sku_ids:

                for i in range(3):

                    # 循环取出sku，判断商品是否存在
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        # 异常,回滚
                        transaction.savepoint_rollback(sid)
                        return JsonResponse({'code': 5, 'message': '商品不存在'})

                    # 获取商品数量，判断库存 (redis)
                    sku_count = redis_conn.hget('cart_%s' % user.id, sku_id)
                    sku_count = int(sku_count)

                    # 判断是否超出库存
                    if sku_count > sku.stock:
                        # 异常,回滚
                        transaction.savepoint_rollback(sid)
                        return JsonResponse({'code': 6, 'message': '库存不足'})

                    # # 减少sku库存
                    # sku.stock -= sku_count
                    # # 增加sku销量
                    # sku.sales += sku_count
                    # sku.save()

                    # 模拟延迟
                    # import time
                    # time.sleep(5)

                    # 乐观锁减库存和加销量
                    origin_stock = sku.stock
                    new_stock = origin_stock - sku_count
                    new_sales = sku.sales + sku_count

                    result = GoodsSKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock, sales=new_sales)
                    if 0 == result and i < 2:
                        continue
                    elif 0 == result and i == 2:
                        # 库存在你更新时，已经被人提前更新了，你要注意库存
                        transaction.savepoint_rollback(sid)
                        return JsonResponse({'code': 8, 'message': '下单失败，检查库存'})
                    # 保存订单商品数据OrderGoods(能执行到这里说明无异常)
                    # 先创建商品订单信息
                    OrderGoods.objects.create(
                        order=order,
                        sku=sku,
                        count=sku_count,
                        price=sku.price
                    )

                    # 计算小计
                    amount = sku_count * sku.price

                    # 计算总数和总金额
                    total_count += sku_count
                    total_sku_amount += amount

                    # 成功就跳出循环
                    break

            # 修改订单信息里面的总数和总金额(OrderInfo)
            order.total_count = total_count
            order.total_amount = total_sku_amount + 10
            order.save()
        except Exception:
            # 暴力回滚
            transaction.savepoint_rollback(sid)
            return JsonResponse({'code': 7, 'message': '下单失败，暴力回滚'})

        # 没有异常，提交事务
        transaction.savepoint_commit(sid)

        # 订单生成后删除购物车(hdel)
        # 遍历sku_ids　或 *sku_ids 都可以
        redis_conn.hdel('cart_%s' % user.id, *sku_ids)

        # 响应结果
        return JsonResponse({'code': 0, 'message': '提交订单成功'})


class PlaceOrederView(LoginRequiredMixin, View):
    """去结算和立即购买的请求"""

    def post(self, request):

        # 判断用户是否登陆：LoginRequiredMixin

        # 获取参数：sku_ids, count
        sku_ids = request.POST.getlist('sku_ids')
        count = request.POST.get('count')

        # 校验sku_ids参数：not
        if not sku_ids:
            return redirect(reverse('cart:info'))

        # 商品的数量从redis中获取
        redis_conn = get_redis_connection('default')
        user_id = request.user.id
        cart_dict = redis_conn.hgetall('cart_%s' % user_id)
        # 定义临时变量
        skus = []
        total_count = 0
        total_sku_amount = 0
        trans_cost = 10

        # 校验count参数：用于区分用户从哪儿进入订单确认页面
        if count is None:
            # 如果是从购物车页面过来

            # 查询商品数据:sku_ids-->sku_id-->sku
            for sku_id in sku_ids:
                # 查看商品信息
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    return redirect(reverse('cart:info'))
                # sku_count是bytes
                sku_count = cart_dict[sku_id.encode()]
                # 为了方便后续代码计算各比较，需要先把sku_count转int
                sku_count = int(sku_count)

                # 小计
                amount = sku.price * sku_count

                # python是面向对象的动态语言
                sku.amount = amount
                sku.count = sku_count
                # 记录sku
                skus.append(sku)
                # 累计数量和金额
                total_count += sku_count
                total_sku_amount += amount

        else:

            # 如果是从详情页面过来，商品的数量从request中获取
            # 遍历商品sku_ids:如果是从详情过来，sku_ids只有一个sku_id
            for sku_id in sku_ids:
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    # 重定向购物车
                    return redirect(reverse('goods:index'))

                # 商品的数量从request中获取,并try校验
                try:
                    sku_count = int(count)
                except Exception:
                    return redirect(reverse('goods:detail', args=(sku_id,)))

                # 判断库存：立即购买没有判断库存
                if sku_count > sku.stock:
                    return redirect(reverse('goods:detail', args=(sku_id,)))

                # 计算商品小计
                amount = sku.price * sku_count

                # 封装对象
                sku.count = sku_count
                sku.amount = amount
                skus.append(sku)

                # 计算金额总和
                total_count += sku_count
                total_sku_amount += amount

                # 立即购买时，需要将用户立即购买的商品信息写入redis，方便提交订单时读取count
                redis_conn.hset('cart_%s' % user_id, sku_id, count)

        # 实付款
        total_amount = total_sku_amount + trans_cost

        # 查询用户地址信息
        try:
            address = request.user.address_set.latest('create_time')
        except Address.DoesNotExist:
            address = None
        # 构造上下文
        context = {
            'skus': skus,
            'total_count': total_count,
            'total_sku_amount': total_sku_amount,
            'trans_cost': trans_cost,
            'total_amount': total_amount,
            'address': address,
            'sku_ids': ','.join(sku_ids)
        }
        # 响应结果:html页面
        return render(request, 'place_order.html', context)


