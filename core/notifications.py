"""
Notification services for Telegram and DingTalk.
"""
import json
import time
import hmac
import base64
import hashlib
import urllib.parse
import requests
from .models import NotificationConfig


def dingtalk_sign(secret):
    """Generate DingTalk signature."""
    timestamp = str(round(time.time() * 1000))
    secret_enc = secret.encode('utf-8')
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign


def send_dingtalk_message(text, config):
    """Send message to DingTalk."""
    if not config.webhook:
        raise Exception("钉钉 Webhook 未配置")

    timestamp, sign = dingtalk_sign(config.secret)

    url = f"{config.webhook}&timestamp={timestamp}&sign={sign}"

    payload = {
        "msgtype": "text",
        "text": {
            "content": text
        }
    }

    response = requests.post(url, json=payload, timeout=30)
    result = response.json()

    if not result.get("errcode") == 0:
        raise Exception(f"钉钉发送失败: {result.get('errmsg')}")

    return result


def send_telegram_message(text, config):
    """Send message to Telegram."""
    if not config.bot_token or not config.chat_id:
        raise Exception("Telegram 配置不完整")

    url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"

    # Split message if too long
    chunk_size = 4000
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i+chunk_size]
        response = requests.post(url, data={
            "chat_id": config.chat_id,
            "text": chunk
        }, timeout=30)

        result = response.json()
        if not result.get("ok"):
            raise Exception(f"Telegram 发送失败: {result.get('description')}")

    return result


def send_telegram_file(file_path, config):
    """Send file to Telegram."""
    if not config.bot_token or not config.chat_id:
        raise Exception("Telegram 配置不完整")

    url = f"https://api.telegram.org/bot{config.bot_token}/sendDocument"

    with open(file_path, "rb") as f:
        response = requests.post(url, data={
            "chat_id": config.chat_id
        }, files={"document": f}, timeout=30)

    result = response.json()
    if not result.get("ok"):
        raise Exception(f"Telegram 文件发送失败: {result.get('description')}")

    return result


def send_notification(text, channel=None):
    """Send notification to configured channels."""
    if channel:
        configs = NotificationConfig.objects.filter(channel=channel, is_active=True)
    else:
        configs = NotificationConfig.objects.filter(is_active=True)

    results = []
    for config in configs:
        try:
            if config.channel == 'telegram':
                result = send_telegram_message(text, config)
            elif config.channel == 'dingtalk':
                result = send_dingtalk_message(text, config)
            else:
                continue
            results.append({"channel": config.channel, "status": "success", "result": result})
        except Exception as e:
            results.append({"channel": config.channel, "status": "error", "error": str(e)})

    return results


def send_file_notification(file_path, channel='telegram'):
    """Send file notification."""
    config = NotificationConfig.objects.filter(channel=channel, is_active=True).first()
    if not config:
        raise Exception(f"找不到活跃的 {channel} 配置")

    if channel == 'telegram':
        return send_telegram_file(file_path, config)
    else:
        raise Exception("暂不支持此渠道的文件发送")
