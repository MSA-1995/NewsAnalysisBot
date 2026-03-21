"""
👁️ Trading Bot Monitor
يراقب نبضة البوت الرئيسي ويغير الحالة في الديسكورد
يشتغل داخل بوت الأخبار
"""

import requests
from datetime import datetime, timezone
from database import get_trading_bot_status, save_status_message_id
from config_encrypted import get_critical_webhook

CRITICAL_WEBHOOK = get_critical_webhook()

# ========== إعدادات ==========
HEARTBEAT_TIMEOUT = 120      # ثانية — لو ما في نبضة خلال 120 ثانية = أوفلاين
CHECK_INTERVAL_SECONDS = 10  # كل 10 ثواني يفحص

# حالة الرسالة الثابتة
_status_message_id = None
_current_status = None
_server_icon = None  # صورة السيرفر

def set_server_icon(icon_url):
    """تحديد صورة السيرفر"""
    global _server_icon
    _server_icon = icon_url

# ========== إرسال/تحديث الرسالة الثابتة ==========

def _send_status_message(status):
    """إرسال رسالة الحالة الأولى"""
    global _status_message_id

    if not CRITICAL_WEBHOOK:
        return

    embed = _build_embed(status)
    try:
        r = requests.post(
            CRITICAL_WEBHOOK + "?wait=true",
            json={"embeds": [embed]},
            timeout=5
        )
        if r.status_code == 200:
            _status_message_id = r.json().get('id')
            save_status_message_id(_status_message_id)
            print(f"✅ Status message sent — ID: {_status_message_id}")
    except Exception as e:
        print(f"⚠️ Send status error: {e}")


def _edit_status_message(status):
    """تعديل نفس الرسالة — لو فشل يرسل جديدة"""
    global _status_message_id

    if not CRITICAL_WEBHOOK or not _status_message_id:
        return

    try:
        parts = CRITICAL_WEBHOOK.rstrip('/').split('/')
        webhook_id = parts[-2]
        webhook_token = parts[-1]
    except:
        return

    embed = _build_embed(status)
    edit_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}/messages/{_status_message_id}"

    try:
        r = requests.patch(edit_url, json={"embeds": [embed]}, timeout=5)
        # لو الرسالة محذوفة — يرسل جديدة
        if r.status_code == 404:
            print("⚠️ Status message deleted — sending new one")
            _status_message_id = None
            save_status_message_id(None)
            _send_status_message(status)
    except Exception as e:
        print(f"⚠️ Edit status error: {e}")


def _build_embed(status):
    """بناء الـ embed حسب الحالة"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    base = {
        "footer": {"text": "MSA Trading Bot • System Monitor"},
        "timestamp": datetime.utcnow().isoformat()
    }

    if _server_icon:
        base["thumbnail"] = {"url": _server_icon}

    if status == 'ONLINE':
        base.update({
            "title": "Trading Bot — ONLINE",
            "color": 0x00ff00,
            "description": "حالة البوت الرئيسي للتداول\nيعمل بشكل طبيعي ويراقب السوق",
            "fields": [
                {"name": "الحالة", "value": "متصل", "inline": True},
                {"name": "آخر تحديث", "value": now, "inline": True},
                {"name": "نظام المراقبة", "value": "يعمل بشكل طبيعي", "inline": False},
                {"name": "معدل التحديث", "value": "كل 10 ثواني", "inline": True},
                {"name": "البيئة", "value": "Binance Testnet", "inline": True},
            ],
        })
    else:
        base.update({
            "title": "Trading Bot — OFFLINE",
            "color": 0xff0000,
            "description": "حالة البوت الرئيسي للتداول\nالبوت متوقف أو انقطع الاتصال",
            "fields": [
                {"name": "الحالة", "value": "غير متصل", "inline": True},
                {"name": "آخر تحديث", "value": now, "inline": True},
                {"name": "تنبيه", "value": "البوت توقف أو انقطع الاتصال", "inline": False},
                {"name": "معدل التحديث", "value": "كل 10 ثواني", "inline": True},
                {"name": "البيئة", "value": "Binance Testnet", "inline": True},
            ],
        })

    return base


def update_bot_status():
    """الدالة الرئيسية — تُستدعى كل 10 ثواني من بوت الأخبار"""
    global _current_status, _status_message_id

    row = get_trading_bot_status()

    if not row:
        new_status = 'OFFLINE'
    else:
        last_beat = row['last_beat']

        # توحيد التوقيت — كلهم UTC naive
        if last_beat.tzinfo is not None:
            last_beat = last_beat.replace(tzinfo=None)

        now_utc = datetime.utcnow()
        seconds_since = abs((now_utc - last_beat).total_seconds())

        if seconds_since <= HEARTBEAT_TIMEOUT:
            new_status = 'ONLINE'
        else:
            new_status = 'OFFLINE'

        # استرجاع message ID من الداتابيز لو ما عندنا
        if _status_message_id is None and row.get('status_message_id'):
            _status_message_id = row['status_message_id']
            print(f"✅ Restored message ID: {_status_message_id}")

    # أول مرة — أرسل رسالة جديدة
    if _status_message_id is None:
        _current_status = new_status
        _send_status_message(new_status)
        return

    # لو الحالة تغيرت — عدّل الرسالة
    if new_status != _current_status:
        print(f"🔄 Status changed: {_current_status} → {new_status}")
        _current_status = new_status
        _edit_status_message(new_status)
    else:
        # نفس الحالة — عدّل الوقت فقط
        _edit_status_message(new_status)
