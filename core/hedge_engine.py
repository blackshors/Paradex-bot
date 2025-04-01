import os
import time
import random
import logging
from dotenv import load_dotenv
from core.api_clients.paradex import ParadexClient
from account import ACCOUNTS  # 导入账户信息
from paradex_py.common.order import Order,OrderSide,OrderType
from decimal import Decimal, ROUND_DOWN
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

    def check_close(self,paradex_instances,a_long,a_short,crypto):
        un_close_by = paradex_instances[a_long].api_client.fetch_orders({"market":crypto})['results']
        un_close_sell = paradex_instances[a_short].api_client.fetch_orders({"market":crypto})['results']
        isFlag = False
        if len(un_close_by)>0:
            logging.info(f"账户：{a_long}存在未平仓,剩余大小：{un_close_by[0]['size']}等待平仓中.....")
            order_book = paradex_instances[a_long].api_client.fetch_orderbook(crypto)
            close_bid = Decimal(order_book["bids"][0][0])
            size = Decimal(un_close_by[0]['size'])
            close = paradex_instances[a_long].api_client.submit_order(Order(market=crypto,order_type=OrderType.Limit,order_side=OrderSide.Sell,size=size,limit_price=close_bid))
            logging.info(f"账户 {a_long} 平多仓, {close}")
            isFlag = True
        if len(un_close_sell)>0:
            logging.info(f"账户：{a_short}存在未平仓,剩余大小：{un_close_sell[0]['size']}等待平仓中.....")
            order_book = paradex_instances[a_short].api_client.fetch_orderbook(crypto)
            close_ask = Decimal(order_book["asks"][0][0])
            size = Decimal(un_close_sell[0]['size'])
            close = paradex_instances[a_short].api_client.submit_order(Order(market=crypto,order_type=OrderType.Limit,order_side=OrderSide.Buy,size=size,limit_price=close_ask))
            logging.info(f"账户 {a_short} 平空仓, {close}")
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
            crypto = random.choice(self.TRADING_PAIRS)
            a_long = accounts[0]
            a_short = accounts[1]
            # 检查是否还存在有未关闭的仓位
            while self.check_close(paradex_instances,a_long,a_short,crypto):
                logging.info("===================仓位未完全关闭，等待处理===================")
                time.sleep(3)
            order_book = paradex_instances[a_long].api_client.fetch_orderbook(crypto)
            best_ask = Decimal(order_book["asks"][0][0])
            best_bid = Decimal(order_book["bids"][0][0])
            q_long = (Decimal(self.AMOUNT) / best_ask).quantize(Decimal("0.001"), rounding=ROUND_DOWN)
            q_short = (Decimal(self.AMOUNT) / best_bid).quantize(Decimal("0.001"), rounding=ROUND_DOWN)
            #构建Order实体
            buy = paradex_instances[a_long].api_client.submit_order(Order(market=crypto,order_type=OrderType.Limit,order_side=OrderSide.Buy,size=q_long,limit_price=best_ask))
            sell = paradex_instances[a_short].api_client.submit_order(Order(market=crypto,order_type=OrderType.Limit,order_side=OrderSide.Sell,size=q_short,limit_price=best_bid))
            logging.info(f"账户 {a_long} 开多仓, 账户 {a_short} 开空仓, 交易对: {crypto}")
            logging.info(f"账户 {a_long} 创建订单, {buy}")
            logging.info(f"账户 {a_short} 创建订单, {sell}")
            wait_time = random.uniform(self.WAIT_OPEN_CLOSE_MIN, self.WAIT_OPEN_CLOSE_MAX)
            time.sleep(wait_time)
            
            order_book = paradex_instances[a_long].api_client.fetch_orderbook(crypto)
            close_ask = Decimal(order_book["asks"][0][0])
            close_bid = Decimal(order_book["bids"][0][0])

            #构建Order实体
            close_buy = paradex_instances[a_long].api_client.submit_order(Order(market=crypto,order_type=OrderType.Limit,order_side=OrderSide.Sell,size=q_long,limit_price=close_bid))
            close_sell = paradex_instances[a_short].api_client.submit_order(Order(market=crypto,order_type=OrderType.Limit,order_side=OrderSide.Buy,size=q_short,limit_price=close_ask))
            logging.info(f"账户 {a_long} 平多仓, 账户 {a_short} 平空仓, 交易对: {crypto}")
            logging.info(f"账户 {a_long} 平多仓, {close_buy}")
            logging.info(f"账户 {a_short} 平空仓, {close_sell}")
            # 检查是否还存在有未关闭的仓位
            while self.check_close(paradex_instances,a_long,a_short,crypto):
                logging.info("===================仓位未完全关闭，等待处理===================")
                time.sleep(3)
            round_wait = random.uniform(self.WAIT_ROUND_MIN, self.WAIT_ROUND_MAX)
            time.sleep(round_wait)
        
        for account in accounts:
            balances = paradex_instances[account].api_client.fetch_balances()
            usdc_balance = float(balances.result['0']['size'])
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
