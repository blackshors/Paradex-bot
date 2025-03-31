from core.hedge_engine import HedgeEngine

if __name__ == "__main__":
    accounts = []
    exclude = []
    bot = HedgeEngine()
    while(bot.random_account(accounts=accounts,exclude=exclude)):
        bot.run(accounts)
