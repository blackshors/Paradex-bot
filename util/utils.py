import os
import httpx
import ssl
from paradex_py.api.http_client import HttpClient as BaseHttpClient  # 导入基础HttpClient

class CustomHttpClient(BaseHttpClient):
    def __init__(self, verify_ssl=True, jwt_token=None):
        super().__init__()
        # 创建自定义SSL上下文，完全禁用验证
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        ssl_context.minimum_version = ssl.TLSVersion.MINIMUM_SUPPORTED
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=0')
        ssl_context.options |= ssl.OP_ALL
        # ssl_context.options |= ssl.OP_LEGACY_SERVER_CONNECT
        
        # 配置更健壮的HTTP客户端，支持代理
        proxy_url = os.getenv("PROXY_URL") if os.getenv("PROXY_ENABLED") == "true" else None
        transport = httpx.HTTPTransport(
            verify=ssl_context,
            retries=5,
            http2=True,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=60
            ),
            proxy=proxy_url,
            # socket_options=[
            #     httpx.SOCKET_KEEPALIVE_INTERVAL,
            #     httpx.SOCKET_KEEPALIVE_IDLE,
            #     httpx.SOCKET_KEEPALIVE_COUNT
            # ]
        )
        self.client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(60.0, connect=30.0, read=30.0, write=30.0),
            http2=True,
            follow_redirects=True
        )
        self.jwt_token = jwt_token
        self.update_headers()

    def update_headers(self):
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ParadexBot/1.0"
        }
        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        self.client.headers.update(headers)

    def set_jwt_token(self, jwt_token):
        self.jwt_token = jwt_token
        self.update_headers()
    
    # 测试网络连接
    def test_connection(self,url):
        """测试API端点连接性"""
        try:
            print(f"正在测试连接: {url}")
            response = httpx.get(f"{url}/health", timeout=10)
            print(f"网络连接测试成功: {url} 返回状态码 {response.status_code}")
            return True
        except httpx.HTTPError as e:
            print(f"网络连接测试失败: {str(e)}")
            return False