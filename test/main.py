from core.hedge_engine import HedgeEngine
import yaml


def load_config():
    with open('../config/config.yaml', 'r', encoding='utf-8') as f:
        return yaml.load(f.read(), Loader=yaml.FullLoader)




if __name__ == "__main__":
    config = load_config()
    bot = HedgeEngine(config)
    bot.run()