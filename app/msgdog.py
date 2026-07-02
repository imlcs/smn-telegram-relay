#########################################################################
#  -*- coding:utf-8 -*-  
#  File Name: app/msgdog.py
#  Author: Charles
#  Created Time: 2026-07-02 15:19:32
#########################################################################

#!/usr/bin/python
import hashlib
import time
import os
import requests
import json  # ← 补上这行

def signature(params, secret):
    sign_validator_attributes = sorted(list(params.keys()))
    lines = []
    for attr in sign_validator_attributes:
        if attr in params and params[attr] is not None:
            lines.append(f"{attr}={params[attr]}")
    lines.append(f"accessKey={secret}")
    sign_string = "|".join(lines)
    return hashlib.md5(sign_string.encode()).hexdigest()

def get_balance():
    secret = os.environ.get("MSGDOGS_SECRET")
    merchant_code = os.environ.get("MSGDOGS_MERCHANT_CODE")
    api_url = os.environ.get("MSGDOGS_API_URL", "https://www.msgdogs.com/api/wallet/balance")

    params = {
        "merchant_code": merchant_code,
        "timestamp": str(int(time.time())),
    }

    sign = signature(params, secret)

    post_data = {
        "merchant_code": merchant_code,
        "timestamp": int(params["timestamp"]),
        "sign": sign,
    }

    headers = {"Content-Type": "application/json"}
    resp = requests.post(api_url, json=post_data, headers=headers)
    data = resp.json()

    # print(f"[API 响应] {json.dumps(data, ensure_ascii=False)}")

    # ↓↓↓ 修正解析路径 ↓↓↓
    if data.get("code") == 200 and data.get("ret"):
        ret = data["ret"]
        # ret 可能是 dict（包含 balance 字段），也可能是直接就是余额数字
        if isinstance(ret, dict):
            balance = float(ret.get("balance", 0))
        else:
            balance = float(ret)
        return balance
    else:
        raise ValueError(f"API 返回异常: {data.get('msg')}")

# ===== Telegram 告警 =====
def send_telegram_alert(message):
    token = os.environ.get("TG_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    if not token or not chat_id:
        print("[警告] 未配置 TG_TOKEN 或 TG_CHAT_ID，跳过告警")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }
    requests.post(url, json=payload, timeout=10)

# ===== 主逻辑 =====
def check_once():
    threshold = float(os.environ.get("BALANCE_THRESHOLD", "100"))
    merchant_code = os.environ.get("MSGDOGS_MERCHANT_CODE", "unknown")

    try:
        balance = get_balance()
        print(f"[信息] 当前余额: {balance}, 告警阈值: {threshold}")

        if balance < threshold:
            msg = (
                f"🚨 <b>msgdogs 余额告警</b> 🚨\n"
                f"商户代码: {merchant_code}\n"
                f"当前余额: {balance}\n"
                f"告警阈值: {threshold}\n"
                f"⚠️ 余额已低于阈值，请尽快充值！"
            )
            send_telegram_alert(msg)
            print("[信息] 告警已发送到 Telegram")
            return True
        else:
            print("[信息] 余额充足，无需告警")
            return True

    except Exception as e:
        print(f"[错误] {e}")
        return False

def main():
    loop_mode = os.environ.get("LOOP_MODE", "false").lower() == "true"
    interval = int(os.environ.get("CHECK_INTERVAL_SECONDS", "3600"))

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始检测...")
    check_once()

    if loop_mode:
        print(f"[信息] 循环模式已启用，每 {interval} 秒检测一次")
        while True:
            time.sleep(interval)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始检测...")
            check_once()

if __name__ == "__main__":
    main()
