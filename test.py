import time
from paradex_py import Paradex
from paradex_py.environment import Environment

# 替换为您的 L1 地址和私钥
L1_ADDRESS = ""
L2_PRIVATE_KEY = ""

# 初始化 Paradex
paradex = Paradex(env="prod", l1_address=L1_ADDRESS, l2_private_key=L2_PRIVATE_KEY)

while True:
    try:
        account_summary = paradex.api_client.fetch_account_summary()
        print("账户摘要:")
        print(account_summary)
    except Exception as e:
        print(f"错误: {e}")
    time.sleep(60)  # 每 60 秒查询一次
