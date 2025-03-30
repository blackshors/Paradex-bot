import os
import time
import random
import logging
from threading import Timer
from dotenv import load_dotenv
from account import ACCOUNTS  # 导入账户信息
from paradex import Paradex   # 假设使用 Paradex SDK

# 加载 .env 文件中的配置项
load_dotenv()

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
    filename='trade_log.log',  # 日志文件名
    level=logging.INFO,        # 日志级别
    format='%(asctime)s - %(message)s'  # 日志格式
)

# 根据网络配置选择 API 基础 URL
if NETWORK == "mainnet":
    API_BASE_URL = "https://api.paradex.trade/v1"
elif NETWORK == "testnet":
    API_BASE_URL = "https://api.testnet.paradex.trade/v1"
else:
    raise ValueError("无效的网络配置，请在 .env 中设置 NETWORK 为 'mainnet' 或 'testnet'")

# 创建 Paradex 实例的函数
def get_paradex_instance(account):
    """根据账户信息和网络配置初始化 Paradex 实例"""
    return Paradex(
        env=NETWORK,  # 传递网络环境
        l1_address=ACCOUNTS[account]["L1_ADDRESS"],
        l2_private_key=ACCOUNTS[account]["L2_PRIVATE_KEY"],
        api_base_url=API_BASE_URL  # 传递 API 基础 URL
    )

# JWT 刷新函数
def refresh_jwt(paradex_instances):
    """刷新所有账户的 JWT 令牌，每 3 分钟执行一次"""
    for account, instance in paradex_instances.items():
        instance.refresh_jwt()  # 假设 SDK 提供此方法
        logging.info(f"账户 {account} 的 JWT 已刷新")
    # 设置下一次刷新（固定 3 分钟，即 180 秒）
    Timer(180, refresh_jwt, [paradex_instances]).start()

# 主交易逻辑
def main():
    # 获取所有账户名称
    accounts = list(ACCOUNTS.keys())
    
    # 为每个账户创建 Paradex 实例
    paradex_instances = {account: get_paradex_instance(account) for account in accounts}
    
    # 启动 JWT 自动刷新（每 3 分钟）
    refresh_jwt(paradex_instances)
    
    # 获取初始余额
    initial_balances = {}
    for account in accounts:
        balances = paradex_instances[account].get_balances()  # 获取账户余额
        usdc_balance = float(balances.get("USDC", 0))  # 获取 USDC 余额
        initial_balances[account] = usdc_balance
        logging.info(f"账户 {account} 初始 USDC 余额: {usdc_balance}")
    
    # 开始交易循环
    for round_num in range(1, ROUNDS + 1):
        logging.info(f"开始第 {round_num} 轮交易")
        
        # 随机选择两个账户进行交易
        a_long, a_short = random.sample(accounts, 2)
        crypto = random.choice(TRADING_PAIRS)  # 从配置中随机选择交易对
        
        # 获取订单簿数据
        order_book = paradex_instances[a_long].get_order_book(crypto)
        best_ask = float(order_book["asks"][0]["price"])  # 最佳卖价
        best_bid = float(order_book["bids"][0]["price"])  # 最佳买价
        
        # 计算开仓数量
        q_long = AMOUNT / best_ask   # 多头开仓数量
        q_short = AMOUNT / best_bid  # 空头开仓数量
        
        # 开仓操作
        paradex_instances[a_long].place_order(crypto, "buy", "limit", best_ask, q_long)
        paradex_instances[a_short].place_order(crypto, "sell", "limit", best_bid, q_short)
        logging.info(f"账户 {a_long} 开多仓, 账户 {a_short} 开空仓, 交易对: {crypto}")
        
        # 随机等待一段时间后平仓
        wait_time = random.uniform(WAIT_OPEN_CLOSE_MIN, WAIT_OPEN_CLOSE_MAX)
        time.sleep(wait_time)
        
        # 获取最新订单簿用于平仓
        order_book = paradex_instances[a_long].get_order_book(crypto)
        close_ask = float(order_book["asks"][0]["price"])  # 平仓卖价
        close_bid = float(order_book["bids"][0]["price"])  # 平仓买价
        
        # 平仓操作
        paradex_instances[a_long].place_order(crypto, "sell", "limit", close_bid, q_long)
        paradex_instances[a_short].place_order(crypto, "buy", "limit", close_ask, q_short)
        logging.info(f"账户 {a_long} 平多仓, 账户 {a_short} 平空仓, 交易对: {crypto}")
        
        # 轮次间随机等待
        round_wait = random.uniform(WAIT_ROUND_MIN, WAIT_ROUND_MAX)
        time.sleep(round_wait)
    
    # 获取最终余额并计算损耗
    for account in accounts:
        balances = paradex_instances[account].get_balances()
        usdc_balance = float(balances.get("USDC", 0))
        initial = initial_balances[account]
        loss = initial - usdc_balance
        logging.info(f"账户 {account} 最终 USDC 余额: {usdc_balance}, 损耗: {loss}")

# go
if __name__ == "__main__":
    main()