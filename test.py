import time
from paradex_py import Paradex
from paradex_py.environment import TESTNET
from paradex_py.environment import PROD
from util.utils import CustomHttpClient
# 替换为您的 L1 地址和私钥
L1_ADDRESS = "0x7346a6bc2e0a051bab07e40adf0f132677bc582c"
l1_private_key = "0xbe5b9e7f4da915999e6055d2bdc408317eb7469963cb2fe0c6410e54bc4e1f87"
L2_PRIVATE_KEY = "0xa00bd70ff6d10f3adb368b17d7c2aa43be4c00b4fd1f6b7b5f2326158ecc82"

# 初始化 Paradex
paradex_test = Paradex(env=TESTNET, l1_address=L1_ADDRESS,l1_private_key=l1_private_key, l2_private_key=L2_PRIVATE_KEY)
paradex_prod = Paradex(env=PROD, l1_address=L1_ADDRESS,l1_private_key=l1_private_key, l2_private_key=L2_PRIVATE_KEY)
while True:
    try:
        account_summary_test = paradex_test.api_client.fetch_account_summary()
        account_summary_prod = paradex_prod.api_client.fetch_account_summary()
        print("测试账户摘要:")
        print(account_summary_test)
        print("生产账户摘要:")
        print(account_summary_prod)

        http_client = CustomHttpClient(verify_ssl=False)
        account_summary_test.api_client.http_client = http_client
        account_summary_test.api_client.onboarding()
    except Exception as e:
        print(f"错误: {e}")
    time.sleep(60)  # 每 60 秒查询一次
