from core.api_clients.paradex import ParadexClient
# from core.position_manager import PositionManager
import logging
import random
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class HedgeEngine:
    def __init__(self, config):
        # 随机两个账户
        buy = random.randint(*[1, len(config['accounts'])])
        sell = random.randint(*[1, len(config['accounts'])])
        while buy == sell:
            sell = random.randint(*[1, len(config['accounts'])])
        self.accounts_buy = config['accounts'][f'paradex_{buy}']
        self.accounts_sell = config['accounts'][f'paradex_{sell}']
        # 初始化API
        self.paradex_clients = ParadexClient(config['url'])
        # 风控
        # self.position_manager = PositionManager()
        self.pairs = config['pairs']  # 自定义交易对
        self.rounds = config['execution']['total_rounds']  # 刷量次数
        self.trade_interval = config['execution']['intra_round_delay']  # 刷量时间随机间隔
        self.round_interval = config['execution']['inter_round_delay']  # 轮次间隔时间随机

    def check_token(self, pair):
        # 检查交易所是否存在该代币品种
        market_para_price = self.paradex_clients.get_market_price(pair['paradex_symbol'])
        if market_para_price < 0:
            logging.error(f"para交易所找不到该代币品种：{pair['paradex_symbol']}")
            return False
        return market_para_price > 0

    def log_balances(self):
        logging.info(
            f"Buy账户余额: {self.paradex_clients.account_price(self.accounts_buy)}, Sell账户余额: {self.paradex_clients.account_price(self.accounts_sell)}")

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
            self.paradex_clients.close_order(self.accounts_buy)
            isFlag = True
        return isFlag

    def run(self):
        for i in range(self.rounds):
            logging.info(f"开始第 {i + 1} 轮刷量")
            self.log_balances()
            # 检查是否还存在有未关闭的仓位
            while self.check_close():
                logging.info("仓位未完全关闭，等待处理")
                time.sleep(3)

            for pair in self.pairs:
                logging.info(
                    f"第 {i + 1} 轮刷量，本次的交易品种是{pair['paradex_symbol']}，开始检查交易所是否存在该交易品种....")
                if not self.check_token(pair):
                    break
                # 获得最新行情报价
                market_para_price = self.paradex_clients.get_market_price(pair['paradex_symbol'])
                # 限价买入
                self.paradex_clients.limit_order(pair, 'SELL', market_para_price, self.accounts_sell)
                self.paradex_clients.limit_order(pair, 'BUY', market_para_price, self.accounts_buy)
                while self.paradex_unrealized_pnl(pair):
                    logging.warning("实时监测中......")
                    time.sleep(2)

                time.sleep(random.randint(*self.trade_interval))
            self.log_balances()
            logging.info(f"结束第 {i + 1} 轮刷量")
            time.sleep(random.randint(*self.round_interval))
        logging.info("刷量结束")
