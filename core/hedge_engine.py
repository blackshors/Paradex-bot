import os
import time
import random
import logging
from dotenv import load_dotenv
from core.api_clients.paradex import ParadexClient
from account import ACCOUNTS  # 导入账户信息


# 配置日志，记录交易信息
logging.basicConfig(
    filename='trade_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)


class HedgeEngine:
    def __init__(self):
        # 加载 .env 文件中的配置项
        load_dotenv()

        # 打印环境变量用于调试
        print("DEBUG - Environment variables:")
        for key in ["WAIT_OPEN_CLOSE_MIN", "WAIT_OPEN_CLOSE_MAX", "WAIT_ROUND_MIN", "WAIT_ROUND_MAX", "PROXY_ENABLED", "PROXY_URL"]:
            print(f"{key}: {os.getenv(key)}")

        # 从 .env 文件中读取配置项并转换为适当类型
        self.LEVERAGE = int(os.getenv("LEVERAGE"))  # 交易杠杆
        self.AMOUNT = float(os.getenv("AMOUNT"))    # 每笔交易金额（美元）
        self.ROUNDS = int(os.getenv("ROUNDS"))      # 交易轮次
        self.WAIT_OPEN_CLOSE_MIN = float(os.getenv("WAIT_OPEN_CLOSE_MIN"))  # 开仓和平仓最小等待时间（秒）
        self.WAIT_OPEN_CLOSE_MAX = float(os.getenv("WAIT_OPEN_CLOSE_MAX"))  # 开仓和平仓最大等待时间（秒）
        self.WAIT_ROUND_MIN = float(os.getenv("WAIT_ROUND_MIN"))            # 每轮交易最小等待时间（秒）
        self.WAIT_ROUND_MAX = float(os.getenv("WAIT_ROUND_MAX"))            # 每轮交易最大等待时间（秒）
        self.TRADING_PAIRS = os.getenv("TRADING_PAIRS").split(",")          # 交易对列表


    def paradex_unrealized_pnl(self, pair):
        # 拿到当前浮盈百分比情况
        paradex_order_price_buy = self.paradex_clients.order_detail(self.accounts_buy)
        paradex_order_price_sell = self.paradex_clients.order_detail(self.accounts_sell)
        if paradex_order_price_buy + paradex_order_price_sell >= pair['max_price_deviation']:
            logging.info(f"检测到未实现盈亏满足条件{pair['max_price_deviation']}%，直接限价平仓")
            self.paradex_clients.close_order(self.accounts_buy)
            self.paradex_clients.close_order(self.accounts_buy)
            return False
        return True

    def check_close(self):
        paradex_buy = self.paradex_clients.count_unorder(self.accounts_buy)
        paradex_sell = self.paradex_clients.count_unorder(self.accounts_sell)
        isFlag = False
        if paradex_buy > 0:
            logging.info("paradex buy存在未平仓，等待平仓中.....")
            self.paradex_clients.close_order(self.accounts_buy)
            isFlag = True
        if paradex_sell > 0:
            logging.info("paradex sell存在未平仓，等待平仓中.....")
            self.paradex_clients.close_order(self.accounts_sell)
            isFlag = True
        return isFlag

# 随机获取对冲账号
    def random_account(self,accounts,exclude):
        # 获取所有账户
        option_account = [key for key in ACCOUNTS if key not in exclude]
        
        while len(accounts) < 2:
            if len(option_account) <= 1:  # 如果没有足够的账户可选，跳出循环
                break
            account = random.choice(option_account)  # 从剩余账户中随机选择
            if account not in accounts:  # 确保没有重复的账户
                accounts.append(account)
        
        if len(accounts) != 2:
            print("满足交易条件的对冲账号不足！")
            return False
        return True

    def run(self,accounts,exclude):
        paradexClient = ParadexClient()
        paradex_instances = {account: paradexClient.get_paradex_instance(account) for account in accounts}
        paradexClient.refresh_jwt(paradex_instances)
        
        initial_balances = {}
        for account in accounts:
            try:
                balances = paradex_instances[account].api_client.fetch_account_summary()
                usdc_balance = float(balances.margin_cushion)
                if((self.AMOUNT * 1.1 / self.LEVERAGE)>usdc_balance):
                    exclude.append(account)
                    accounts.remove(account)
                    break
                initial_balances[account] = usdc_balance
                logging.info(f"账户 {account} 初始 USDC 余额: {usdc_balance}")
            except Exception as e:
                logging.error(f"获取账户 {account} 余额失败: {str(e)}")
                raise
        # 对冲账号不满足条件，则跳出方法
        if(len(accounts)<2):
            return
        
        for round_num in range(1, self.ROUNDS + 1):
            logging.info(f"开始第 {round_num} 轮交易")
            while True:
                a_long, a_short = random.sample(accounts, 2)
                if ACCOUNTS[a_long]["L1_ADDRESS"] != ACCOUNTS[a_short]["L1_ADDRESS"]:
                    break
            crypto = random.choice(self.TRADING_PAIRS)
            
            order_book = paradex_instances[a_long].api_client.get_order_book(crypto)
            best_ask = float(order_book["asks"][0]["price"])
            best_bid = float(order_book["bids"][0]["price"])
            
            q_long = self.AMOUNT / best_ask
            q_short = self.AMOUNT / best_bid
            
            paradex_instances[a_long].api_client.place_order(crypto, "buy", "limit", best_ask, q_long)
            paradex_instances[a_short].api_client.place_order(crypto, "sell", "limit", best_bid, q_short)
            logging.info(f"账户 {a_long} 开多仓, 账户 {a_short} 开空仓, 交易对: {crypto}")
            
            wait_time = random.uniform(self.WAIT_OPEN_CLOSE_MIN, self.WAIT_OPEN_CLOSE_MAX)
            time.sleep(wait_time)
            
            order_book = paradex_instances[a_long].api_client.get_order_book(crypto)
            close_ask = float(order_book["asks"][0]["price"])
            close_bid = float(order_book["bids"][0]["price"])
            
            paradex_instances[a_long].api_client.place_order(crypto, "sell", "limit", close_bid, q_long)
            paradex_instances[a_short].api_client.place_order(crypto, "buy", "limit", close_ask, q_short)
            logging.info(f"账户 {a_long} 平多仓, 账户 {a_short} 平空仓, 交易对: {crypto}")
            
            round_wait = random.uniform(self.WAIT_ROUND_MIN, self.WAIT_ROUND_MAX)
            time.sleep(round_wait)
        
        for account in accounts:
            balances = paradex_instances[account].api_client.get_balances()
            usdc_balance = float(balances.get("USDC", {}).get("available", 0))
            initial = initial_balances[account]
            loss = initial - usdc_balance
            logging.info(f"账户 {account} 最终 USDC 余额: {usdc_balance}, 损耗: {loss}")
            # for i in range(self.rounds):
            #     logging.info(f"开始第 {i + 1} 轮刷量")
            #     self.log_balances()
            #     # 检查是否还存在有未关闭的仓位
            #     while self.check_close():
            #         logging.info("仓位未完全关闭，等待处理")
            #         time.sleep(3)

            #     for pair in self.pairs:
            #         logging.info(
            #             f"第 {i + 1} 轮刷量，本次的交易品种是{pair['paradex_symbol']}，开始检查交易所是否存在该交易品种....")
            #         if not self.check_token(pair):
            #             break
            #         # 获得最新行情报价
            #         market_para_price = self.paradex_clients.get_market_price(pair['paradex_symbol'])
            #         # 限价买入
            #         self.paradex_clients.limit_order(pair, 'SELL', market_para_price, self.accounts_sell)
            #         self.paradex_clients.limit_order(pair, 'BUY', market_para_price, self.accounts_buy)
            #         while self.paradex_unrealized_pnl(pair):
            #             logging.warning("实时监测中......")
            #             time.sleep(2)

            #         time.sleep(random.randint(*self.trade_interval))
            #     self.log_balances()
            #     logging.info(f"结束第 {i + 1} 轮刷量")
            #     time.sleep(random.randint(*self.round_interval))
            # logging.info("刷量结束")
