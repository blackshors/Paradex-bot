from core.hedge_engine import HedgeEngine
import logging
# 配置日志，记录交易信息
logging.basicConfig(
    filename='trade_log.log',
    level=logging.WARN,
    format='%(asctime)s - %(message)s'
)
if __name__ == "__main__":
    bot = HedgeEngine()
    bot.run()
