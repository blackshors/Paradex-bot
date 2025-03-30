import os
import time
import random
import logging
import httpx
import ssl
from threading import Timer
from dotenv import load_dotenv
from account import ACCOUNTS  # 导入账户信息
from paradex_py import Paradex  # 使用正确的包名
from paradex_py.api.http_client import HttpClient as BaseHttpClient  # 导入基础HttpClient
import httpx

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
        ssl_context.options |= ssl.OP_LEGACY_SERVER_CONNECT
        
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
            socket_options=[
                httpx.SOCKET_KEEPALIVE_INTERVAL,
                httpx.SOCKET_KEEPALIVE_IDLE,
                httpx.SOCKET_KEEPALIVE_COUNT
            ]
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

# 加载 .env 文件中的配置项
load_dotenv()

# 打印环境变量用于调试
print("DEBUG - Environment variables:")
for key in ["WAIT_OPEN_CLOSE_MIN", "WAIT_OPEN_CLOSE_MAX", "WAIT_ROUND_MIN", "WAIT_ROUND_MAX", "PROXY_ENABLED", "PROXY_URL"]:
    print(f"{key}: {os.getenv(key)}")

# 临时启用代理进行测试
PROXY_ENABLED = True
PROXY_URL = "http://127.0.0.1:7897"

# 从 .env 文件中读取配置项并转换为适当类型
LEVERAGE = int(os.getenv("LEVERAGE"))  # 交易杠杆
AMOUNT = float(os.getenv("AMOUNT"))    # 每笔交易金额（美元）
ROUNDS = int(os.getenv("ROUNDS"))      # 交易轮次
WAIT_OPEN_CLOSE_MIN = float(os.getenv("WAIT_OPEN_CLOSE_MIN"))  # 开仓和平仓最小等待时间（秒）
WAIT_OPEN_CLOSE_MAX = float(os.getenv("WAIT_OPEN_CLOSE_MAX"))  # 开仓和平仓最大等待时间（秒）
WAIT_ROUND_MIN = float(os.getenv("WAIT_ROUND_MIN"))            # 每轮交易最小等待时间（秒）
WAIT_ROUND_MAX = float(os.getenv("WAIT_ROUND_MAX"))            # 每轮交易最大等待时间（秒）
TRADING_PAIRS = os.getenv("TRADING_PAIRS").split(",")          # 交易对列表
NETWORK = os.getenv("NETWORK")                                 # 网络配置：mainnet 或 testnet

# 配置日志，记录交易信息
logging.basicConfig(
    filename='trade_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

# 根据网络配置选择 API 基础 URL
if NETWORK == "mainnet":
    API_BASE_URL = "https://api.paradex.trade/v1"
elif NETWORK == "testnet":
    API_BASE_URL = "https://api.testnet.paradex.trade/v1"
else:
    raise ValueError("无效的网络配置，请在 .env 中设置 NETWORK 为 'mainnet' 或 'testnet'")

# 测试网络连接
def test_connection(url):
    """测试API端点连接性"""
    try:
        print(f"正在测试连接: {url}")
        response = httpx.get(f"{url}/health", timeout=10)
        print(f"网络连接测试成功: {url} 返回状态码 {response.status_code}")
        return True
    except httpx.HTTPError as e:
        print(f"网络连接测试失败: {str(e)}")
        return False

# 创建 Paradex 实例的函数
def get_paradex_instance(account):
    """根据账户信息和网络配置初始化 Paradex 实例"""
    try:
        # 初始化实例
        instance = Paradex(
            env=NETWORK,
            l1_address=ACCOUNTS[account]["L1_ADDRESS"],
            l2_private_key=ACCOUNTS[account]["L2_PRIVATE_KEY"]
        )
        
        # 设置自定义HTTP客户端 - 临时完全禁用SSL验证进行测试
        print("临时完全禁用SSL验证进行连接测试")
        instance.api_client.http_client = CustomHttpClient(verify_ssl=False)
        
        # 测试 API 连接
        if not test_connection(API_BASE_URL):
            raise ValueError(f"无法连接到 {API_BASE_URL}，请检查网络或代理设置")

        # 完成 onboarding 流程
        max_retries = 3
        for attempt in range(max_retries):
            try:
                onboarding_result = instance.api_client.onboarding()
                print(f"DEBUG - Onboarding结果: {onboarding_result}")  # 调试输出
                if onboarding_result:
                    logging.info(f"账户 {account} onboarding 成功")
                    print(f"账户 {account} onboarding 成功")  # 控制台输出
                    
                    # 获取初始JWT令牌
                    jwt_token = instance.auth()
                    if jwt_token:
                        instance.api_client.http_client.set_jwt_token(jwt_token)
                        logging.info(f"账户 {account} 初始JWT设置成功")
                    else:
                        logging.warning(f"账户 {account} 初始JWT获取失败")
                    
                    break
                else:
                    error_msg = f"账户 {account} onboarding 失败(尝试 {attempt+1} 次)"
                    logging.error(error_msg)
                    print(error_msg)  # 控制台输出
                    raise ValueError(error_msg)
            except Exception as e:
                error_msg = f"账户 {account} onboarding 失败(尝试 {attempt+1} 次): {str(e)}"
                logging.error(error_msg)
                if attempt == max_retries - 1:
                    raise ValueError(error_msg)
                wait_time = (attempt + 1) * 5  # 指数退避
                logging.warning(f"{wait_time} 秒后重试...")
                time.sleep(wait_time)
            
        return instance
    except Exception as e:
        error_msg = f"初始化 Paradex 实例失败: {str(e)}"
        logging.error(error_msg)
        raise ValueError(error_msg)

# JWT 刷新函数
def refresh_jwt(paradex_instances):
    """刷新所有账户的 JWT 令牌，每 3 分钟执行一次"""
    for account, instance in paradex_instances.items():
        try:
            # 获取新的JWT令牌
            jwt_token = instance.auth()
            if jwt_token:
                # 更新HTTP客户端的JWT令牌
                instance.api_client.http_client.set_jwt_token(jwt_token)
                logging.info(f"账户 {account} 的 JWT 已刷新")
            else:
                logging.error(f"账户 {account} JWT 刷新失败: 未获取到令牌")
        except Exception as e:
            logging.error(f"账户 {account} JWT 刷新失败: {str(e)}")
            # 重试机制
            time.sleep(5)
            try:
                jwt_token = instance.auth()
                if jwt_token:
                    instance.api_client.http_client.set_jwt_token(jwt_token)
                    logging.info(f"账户 {account} JWT 重试刷新成功")
            except Exception as retry_e:
                logging.error(f"账户 {account} JWT 重试刷新失败: {str(retry_e)}")
    
    # 设置下一次刷新
    Timer(180, refresh_jwt, [paradex_instances]).start()

# 主交易逻辑
def main():
    accounts = ["account1", "account2"]
    paradex_instances = {account: get_paradex_instance(account) for account in accounts}
    refresh_jwt(paradex_instances)
    
    initial_balances = {}
    for account in accounts:
        try:
            balances = paradex_instances[account].api_client.get_balances()
            usdc_balance = float(balances.get("USDC", {}).get("available", 0))
            initial_balances[account] = usdc_balance
            logging.info(f"账户 {account} 初始 USDC 余额: {usdc_balance}")
        except Exception as e:
            logging.error(f"获取账户 {account} 余额失败: {str(e)}")
            raise

    for round_num in range(1, ROUNDS + 1):
        logging.info(f"开始第 {round_num} 轮交易")
        while True:
            a_long, a_short = random.sample(accounts, 2)
            if ACCOUNTS[a_long]["L1_ADDRESS"] != ACCOUNTS[a_short]["L1_ADDRESS"]:
                break
        crypto = random.choice(TRADING_PAIRS)
        
        order_book = paradex_instances[a_long].api_client.get_order_book(crypto)
        best_ask = float(order_book["asks"][0]["price"])
        best_bid = float(order_book["bids"][0]["price"])
        
        q_long = AMOUNT / best_ask
        q_short = AMOUNT / best_bid
        
        paradex_instances[a_long].api_client.place_order(crypto, "buy", "limit", best_ask, q_long)
        paradex_instances[a_short].api_client.place_order(crypto, "sell", "limit", best_bid, q_short)
        logging.info(f"账户 {a_long} 开多仓, 账户 {a_short} 开空仓, 交易对: {crypto}")
        
        wait_time = random.uniform(WAIT_OPEN_CLOSE_MIN, WAIT_OPEN_CLOSE_MAX)
        time.sleep(wait_time)
        
        order_book = paradex_instances[a_long].api_client.get_order_book(crypto)
        close_ask = float(order_book["asks"][0]["price"])
        close_bid = float(order_book["bids"][0]["price"])
        
        paradex_instances[a_long].api_client.place_order(crypto, "sell", "limit", close_bid, q_long)
        paradex_instances[a_short].api_client.place_order(crypto, "buy", "limit", close_ask, q_short)
        logging.info(f"账户 {a_long} 平多仓, 账户 {a_short} 平空仓, 交易对: {crypto}")
        
        round_wait = random.uniform(WAIT_ROUND_MIN, WAIT_ROUND_MAX)
        time.sleep(round_wait)
    
    for account in accounts:
        balances = paradex_instances[account].api_client.get_balances()
        usdc_balance = float(balances.get("USDC", {}).get("available", 0))
        initial = initial_balances[account]
        loss = initial - usdc_balance
        logging.info(f"账户 {account} 最终 USDC 余额: {usdc_balance}, 损耗: {loss}")

if __name__ == "__main__":
    main()
