"""
👁️ Trading Bot Monitor
يراقب نبضة البوت الرئيسي ويغير الحالة في الديسكورد
يشتغل داخل بوت الأخبار
"""

import requests
from datetime import datetime, timezone
from database import get_trading_bot_status
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
            print(f"✅ Status message sent — ID: {_status_message_id}")
    except Exception as e:
        print(f"⚠️ Send status error: {e}")


def _edit_status_message(status):
    """تعديل نفس الرسالة بدون إرسال رسالة جديدة"""
    global _status_message_id

    if not CRITICAL_WEBHOOK or not _status_message_id:
        return

    # استخراج webhook id و token من الرابط
    try:
        parts = CRITICAL_WEBHOOK.rstrip('/').split('/')
        webhook_id = parts[-2]
        webhook_token = parts[-1]
    except:
        return

    embed = _build_embed(status)
    edit_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}/messages/{_status_message_id}"

    try:
        requests.patch(edit_url, json={"embeds": [embed]}, timeout=5)
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
            "fields": [
                {"name": "الحالة", "value": "متصل", "inline": True},
                {"name": "آخر تحديث", "value": now, "inline": True},
            ],
        })
    else:
        base.update({
            "title": "Trading Bot — OFFLINE",
            "color": 0xff0000,
            "fields": [
                {"name": "الحالة", "value": "غير متصل", "inline": True},
                {"name": "آخر تحديث", "value": now, "inline": True},
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

    # أول مرة — أرسل الرسالة
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
        # نفس الحالة — عدّل الوقت فقط (كل 10 ثواني)
        _edit_status_message(new_status)
