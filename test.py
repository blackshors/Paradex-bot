import time
from paradex_py import Paradex
from paradex_py.environment import TESTNET
from paradex_py.environment import PROD
from util.utils import CustomHttpClient
from app_functions_sdk_py.factory import new_app_service
# import lighter
# 替换为您的 L1 地址和私钥
L1_ADDRESS = "0x12366d7bade796dcce40de1ab3610e1c39f50444"
l1_private_key = "0x72aba6b786ce964978f9069f36f97eb845b887fee3b2299a61ede11d99936670"
L2_PRIVATE_KEY = "0x47db8a4dcb7e6587609edbb6b8cff9f7afe22b34dffae164a8e350d1285226f"

# 初始化 Paradex
paradex_test = Paradex(env=TESTNET, l1_address=L1_ADDRESS,l1_private_key=l1_private_key, l2_private_key=L2_PRIVATE_KEY)
paradex_prod = Paradex(env=PROD, l1_address=L1_ADDRESS,l1_private_key=l1_private_key, l2_private_key=L2_PRIVATE_KEY)
while True:
    try:
        account_summary_test = paradex_test.api_client.fetch_account_summary()
        account_summary_prod = paradex_prod.api_client.fetch_account_summary()
        print("Paradex 测试账户摘要:")
        print(account_summary_test)
        print("Paradex生产账户摘要:")
        print(account_summary_prod)

        http_client = CustomHttpClient(verify_ssl=False)
        account_summary_test.api_client.http_client = http_client
        account_summary_test.api_client.onboarding()

        # client = lighter.ApiClient(
        #         configuration=lighter.Configuration(
        #             host="https://testnet.zklighter.elliot.ai"
        #         )
        #     )
        # account_instance = lighter.AccountApi(client)
        # res = account_instance.account(by="l1_address", value=L1_ADDRESS)
        # print("lighter,测试账户摘要:")
        # print(res)
    except Exception as e:
        print(f"错误: {e}")
    time.sleep(60)  # 每 60 秒查询一次
