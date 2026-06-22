#########################################################################
#  -*- coding:utf-8 -*-  
#  File Name: app/main.py
#  Author: Charles
#  Created Time: 2026-06-22 17:29:53
#########################################################################

#!/usr/bin/python
from flask import Flask, request
import json
import os
import time
import requests
import logging

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
TG_API = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

LEVEL_EMOJI = {
    "Critical": "🔴",
    "Major": "🟠",
    "Minor": "🟡",
    "Info": "🔵"
}
LEVEL_STATUS = {
    "alarm" : "🔴告警触发😭",
    "ok" : "🟢告警恢复😃"
}

ALERT_CACHE = {}
DEDUPE_SECONDS = 300


def should_send_alert(msg: dict) -> bool:
    alarm_id = (
        msg.get("resource_id"),
        msg.get("metric_name"),
        msg.get("alarm_name")
    )
    state = msg.get("state")
    now = time.time()

    if state == "OK":
        ALERT_CACHE.pop(alarm_id, None)
        return True

    last = ALERT_CACHE.get(alarm_id)
    if not last:
        ALERT_CACHE[alarm_id] = now
        return True

    if now - last >= DEDUPE_SECONDS:
        ALERT_CACHE[alarm_id] = now
        return True

    return False


def safe_json_loads(text: str):
    try:
        return json.loads(text)
    except Exception:
        return {}


def send_telegram(text: str):
    try:
        requests.post(
            TG_API,
            json={
                "chat_id": TG_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except Exception as e:
        logging.exception("[TG] send failed")


def format_alert(msg: dict) -> str:
    tv = msg.get("template_variable", {})

    level = tv.get("AlarmLevel", "UNKNOWN")
    emoji = LEVEL_EMOJI.get(level, "⚪")
    accountname=tv.get("AccountName", "UNKNOWN")
    alarmtime=tv.get("AlarmTime", "UNKNOWN")

    resource = tv.get("ResourceName", "-")
    region = tv.get("Region", "-")

    metric = tv.get("MetricName", "-")
    value = tv.get("Value", "-")
    operator = tv.get("CurrentData", "-")

    alarm_status = msg.get("alarm_status", "-")
    status = LEVEL_STATUS.get(alarm_status, "⚪")

    return (
        f"{emoji} <b>华为云告警 — {level}</b>\n"
        f"<b>账号:</b> {accountname}\n"
        f"<b>名称:</b> {msg.get('alarm_name','-')}\n"
        f"<b>资源:</b> {resource} ({region})\n"
        f"<b>告警:</b> {metric} > {value}\n"
        f"<b>时间:</b> {alarmtime}\n"
        f"<b>指标:</b> {operator}\n"
        f"<b>状态:</b> {status}"
    )

@app.route("/webhook/smn", methods=["POST"])
def webhook():
    try:
        raw_body = request.data.decode("utf-8", errors="replace")
        logging.info("[SMN RAW BODY] %s", raw_body)

        data = request.get_json(force=True, silent=True) or {}

        if data.get("type") == "SubscriptionConfirmation":
            url = data.get("subscribe_url")
            if url:
                requests.get(url, timeout=10)
            return "confirmed", 200

        if data.get("type") == "Notification":
            raw_msg = data.get("message", "{}")
            if isinstance(raw_msg, str):
                msg = safe_json_loads(raw_msg)
            else:
                msg = raw_msg or {}

            if isinstance(msg, dict) and should_send_alert(msg):
                send_telegram(format_alert(msg))

            return "ok", 200

        return "ok", 200

    except Exception:
        logging.exception("[SMN] unhandled exception")
        return "ok", 200


@app.route("/")
def index():
    return "SMN Telegram Relay OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
