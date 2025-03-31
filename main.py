import os
import time
import random
import logging
from threading import Timer
from dotenv import load_dotenv
from account import ACCOUNTS  # 导入账户信息
from paradex_py import Paradex  # 使用正确的包名
from paradex_py.api.http_client import HttpClient as BaseHttpClient  # 导入基础HttpClient
from util.utils import CustomHttpClient
from core.api_clients.paradex import ParadexClient
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


# 主交易逻辑
def main():
    accounts = ["account1", "account2"]
    paradexClient = ParadexClient()
    paradex_instances = {account: paradexClient.get_paradex_instance(account) for account in accounts}
    paradexClient.refresh_jwt(paradex_instances)
    
    initial_balances = {}
    for account in accounts:
        try:
            balances = paradex_instances[account].api_client.fetch_account_summary()
            usdc_balance = float(balances.margin_cushion)
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
