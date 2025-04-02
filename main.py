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
    logging.info("=======================开始查询每个账户的初始金额=======================")
    analysis_account_total = bot.analysis_account_total()
    account_total = 0
    for key, value in analysis_account_total.items():
        logging.info(f"账户{key}余额：{value}USD")
        account_total+=value
    logging.info(f"合计：{account_total}USDC")
    
    while(bot.random_account(accounts=accounts,exclude=exclude)):
        bot.run(accounts,exclude,account_total)
