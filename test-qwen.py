import dashscope
from http import HTTPStatus

dashscope.api_key = "sk-e57c05f824074986884f02e008f0d951"

def test_api():
    resp = dashscope.Generation.call(model='qwen-turbo', prompt='你好')
    if resp.status_code == HTTPStatus.OK:
        print("✅ 验证成功！")
    else:
        print(f"❌ 依然报错: {resp.code} - {resp.message}")

test_api()