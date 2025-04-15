from core.hedge_engine import HedgeEngine
import logging
# 配置日志，记录交易信息
logging.basicConfig(
    filename='trade_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
if __name__ == "__main__":
    accounts = []
    exclude = []
    bot = HedgeEngine()
    bot.random_account(accounts=accounts,exclude=exclude)
    bot.run(accounts,exclude)
    # while(bot.random_account(accounts=accounts,exclude=exclude)):
    #     bot.run(accounts,exclude)
