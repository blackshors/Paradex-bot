import os
import time
import random
import logging
from threading import Timer
from account import ACCOUNTS  # 导入账户信息
from paradex_py import Paradex  # 使用正确的包名
from util.utils import CustomHttpClient

class ParadexClient:
    def __init__(self):
        # 从 .env 文件中读取配置项并转换为适当类型
        self.LEVERAGE = int(os.getenv("LEVERAGE"))  # 交易杠杆
        self.AMOUNT = float(os.getenv("AMOUNT"))    # 每笔交易金额（美元）
        self.ROUNDS = int(os.getenv("ROUNDS"))      # 交易轮次
        self.WAIT_OPEN_CLOSE_MIN = float(os.getenv("WAIT_OPEN_CLOSE_MIN"))  # 开仓和平仓最小等待时间（秒）
        self.WAIT_OPEN_CLOSE_MAX = float(os.getenv("WAIT_OPEN_CLOSE_MAX"))  # 开仓和平仓最大等待时间（秒）
        self.WAIT_ROUND_MIN = float(os.getenv("WAIT_ROUND_MIN"))            # 每轮交易最小等待时间（秒）
        self.WAIT_ROUND_MAX = float(os.getenv("WAIT_ROUND_MAX"))            # 每轮交易最大等待时间（秒）
        self.TRADING_PAIRS = os.getenv("TRADING_PAIRS").split(",")          # 交易对列表
        self.NETWORK = os.getenv("NETWORK")                                 # 网络配置：prod 或 testnet
        # 根据网络配置选择 API 基础 URL
        if self.NETWORK == "prod":
            self.API_BASE_URL = "https://api.paradex.trade/v1"
        elif self.NETWORK == "testnet":
            self.API_BASE_URL = "https://api.testnet.paradex.trade/v1"
        else:
            raise ValueError("无效的网络配置，请在 .env 中设置 NETWORK 为 'prod' 或 'testnet'")

    # 创建 Paradex 实例的函数
    def get_paradex_instance(self,account):
        """根据账户信息和网络配置初始化 Paradex 实例"""
        try:
            # 初始化实例
            instance = Paradex(
                env=self.NETWORK,
                l1_address=ACCOUNTS[account]["L1_ADDRESS"],
                l1_private_key=ACCOUNTS[account]["L1_PRIVATE_KEY"],
                l2_private_key=ACCOUNTS[account]["L2_PRIVATE_KEY"]
            )
            
            # 设置自定义HTTP客户端 - 临时完全禁用SSL验证进行测试
            print("临时完全禁用SSL验证进行连接测试")
            http_client = CustomHttpClient(verify_ssl=False)
            instance.api_client.http_client = http_client
            # 测试 API 连接
            if not http_client.test_connection(self.API_BASE_URL):
                raise ValueError(f"无法连接到 {self.API_BASE_URL}，请检查网络或代理设置")

            # 完成 onboarding 流程
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    onboarding_result = instance.api_client.onboarding()
                    print(f"DEBUG - Onboarding结果: {onboarding_result}")  # 调试输出
                    if onboarding_result ==None:
                        logging.warn(f"账户 {account} onboarding 成功")
                        print(f"账户 {account} onboarding 成功")  # 控制台输出
                        
                        # 获取初始JWT令牌
                        instance.api_client.auth()
                        jwt_token = instance.account.jwt_token
                        if jwt_token:
                            instance.api_client.http_client.set_jwt_token(jwt_token)
                            logging.warn(f"账户 {account} 初始JWT设置成功")
                        else:
                            logging.warn(f"账户 {account} 初始JWT获取失败")
                        
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
                    logging.warn(f"{wait_time} 秒后重试...")
                    time.sleep(wait_time)
                
            return instance
        except Exception as e:
            error_msg = f"初始化 Paradex 实例失败: {str(e)}"
            logging.error(error_msg)
            raise ValueError(error_msg)

    # JWT 刷新函数
    def refresh_jwt(self,paradex_instances):
        """刷新所有账户的 JWT 令牌，每 3 分钟执行一次"""
        for account, instance in paradex_instances.items():
            try:
                # 获取新的JWT令牌
                instance.api_client.auth()
                jwt_token = instance.account.jwt_token
                if jwt_token:
                    # 更新HTTP客户端的JWT令牌
                    instance.api_client.http_client.set_jwt_token(jwt_token)
                    logging.warn(f"账户 {account} 的 JWT 已刷新")
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
                        logging.warn(f"账户 {account} JWT 重试刷新成功")
                except Exception as retry_e:
                    logging.error(f"账户 {account} JWT 重试刷新失败: {str(retry_e)}")
        
        # 设置下一次刷新
        Timer(180, self.refresh_jwt, [paradex_instances]).start()