from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client
from django.conf import settings


class FastDFSStorage(Storage):
    """实现Django对接fdfs的文件存储:当运维在后台站点上传图片时调用的"""

    def __init__(self, client_conf=None, server_ip=None):
        """初始化方法"""

        if client_conf is None:
            # 当外界没有传入client_conf
           client_conf = settings.CLIENT_CONF
        # 当外界传入了client_conf
        self.client_conf = client_conf

        if server_ip is None:
            server_ip = settings.SERVER_IP
        self.server_ip = server_ip

    def _open(self, name, mode='rb'):
        """打开文件时调用的:此处制作存储,不需要打开文件,所以pass"""
        pass

    def _save(self, name, content):
        """存储文件时调用的:name是要上传的文件名字,content是File对象,提供read(),获取文件内容"""

        # 创建fdfs对接的对象
        client = Fdfs_client(self.client_conf)


        # 获取要上传的文件内容
        file_data = content.read()
        # 调用上传的方法,并且接受返回值
        try:
            ret = client.upload_by_buffer(file_data)
        except Exception as e:
            print(e) # 方便自己调试时使用的
            raise

        # 判断是否上传成功
        if ret.get('Status') == 'Upload successed.':
            # 如果上传成功
            # 获取file_id
            file_id = ret.get('Remote file_id')
            # 存储file_id:只需要返回file_id,我们的client,会自动的检测当前站点中正在使用的模型类,然后存储进去
            # 如果当前运维在操作GoodsSKU模型类,上传图片,那么return file_id,会自动存储到GoodsSKU模型类对应的数据库表中
            return file_id
        else:
            # 上传失败:抛出异常即可
            raise Exception('上传失败')

    def exists(self, name):
        """判断文件是否已经被存储在文件系统中,此时,需要返回False,因为我们需要告诉Django文件不在文件系统,让django继续存储文件到fdfs"""
        return False

    def url(self, name):
        """返回保存的文件的路径的,name表示保存的文件的路径"""
        # 把要获取的文件的名字传入,拼接该文件的全路径,得到下载地址,供下载时使用的
        # return 'http://192.168.103.129:8888/group1/M00/00/00/wKhngVqR0WGACYJ1AALb6Vx4KgI55.jpeg'

        return self.server_ip + name

"""
ip + path
path = group1/M00/00/00/wKhngVqR0WGACYJ1AALb6Vx4KgI55.jpeg

ip = nginx的ip:端口(192.168.103.129:8888)  (用户  nginx fdfs)

ip + path = http://192.168.103.129:8888/group1/M00/00/00/wKhngVqR0WGACYJ1AALb6Vx4KgI55.jpeg
"""

"""
1. import fdfs_client.client module
2. instantiate class Fdfs_client
3. call memeber functions

>>> from fdfs_client.client import *
>>> client = Fdfs_client('/etc/fdfs/client.conf')
>>> ret = client.upload_by_filename('test')
>>> ret
{'Group name':'group1','Status':'Upload successed.', 'Remote file_id':'group1/M00/00/00/
	wKjzh0_xaR63RExnAAAaDqbNk5E1398.py','Uploaded size':'6.0KB','Local file name':'test'
	, 'Storage IP':'192.168.243.133'}
"""

"""
1.创建client对象, 参数是 client.conf
2.调用client.upload_by_bffer(file)
3.接受返回值,内部包含了file_id
4.存储file_id
"""