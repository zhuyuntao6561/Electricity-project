from django.conf.urls import url
from users import views


urlpatterns = [
    # 注册:函数视图 http://172.0.0.1:8000/users/register
    # url(r'^register$', views.register)

    # 注册:类视图 http://172.0.0.1:8000/users/register
    url(r'^register$', views.RegisterView.as_view(), name='register'),

    # http://127.0.0.1:8000/users/active/eyJhbGciOiJIUzI1NiIsImV4cCI6MTUxOTU0Mjk5NSwiaWF0IjoxNTE5NTM5Mzk1fQ.eyJjb25maXJtIjozMn0.peXRvh6JLWmkBuSX6-hCK0e-Cd8Z9h5CBTa1PW_lYmI
    # 激活:http://127.0.0.1:8000/users/active/!@#$%^fhkb'%g
    url(r'^active/(?P<token>.+)$', views.ActiveView.as_view(), name='active'),

    # 登录:http://127.0.0.1:8000/users/login
    url(r'^login$', views.LoginView.as_view(), name='login'),

    # 退出登录:http://127.0.0.1:8000/users/logout
    url(r'^logout$', views.LogoutView.as_view(), name='logout'),

    # 收货地址:http://127.0.0.1:8000/users/address
    url(r'^address$', views.AddressView.as_view(), name='address'),

    # url(r'^address$', login_required(views.AddressView.as_view()), name='address')

    # 个人信息
    url(r'^info$', views.UserInfoView.as_view(), name='info')
]