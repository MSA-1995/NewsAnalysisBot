"""
👁️ Trading Bot Monitor
يراقب نبضة البوت الرئيسي ويغير الحالة في الديسكورد
يشتغل داخل بوت الأخبار
"""

import requests
from datetime import datetime, timezone
from database import get_trading_bot_status, save_status_message_id, get_trainer_status, save_trainer_message_id
from config_encrypted import get_critical_webhook

CRITICAL_WEBHOOK = get_critical_webhook()

# ========== إعدادات ==========
HEARTBEAT_TIMEOUT = 90       # ثانية
TRAINER_TIMEOUT   = 180      # ثانية — التدريب يأخذ وقت أطول

# حالة البوت الرئيسي
_status_message_id = None
_current_status    = None
_server_icon       = None

# حالة سكريبت التدريب
_trainer_message_id = None
_trainer_status     = None

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
        # الداتابيز تحسب الفرق بتوقيتها الموحد — بدون أي فرق بين سيرفرين
        seconds_since = float(row.get('seconds_since') or 9999)

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


# ========== مراقبة سكريبت التدريب ==========

def _send_trainer_message(status):
    """إرسال رسالة حالة التدريب"""
    global _trainer_message_id

    if not CRITICAL_WEBHOOK:
        return

    embed = _build_trainer_embed(status)
    try:
        r = requests.post(
            CRITICAL_WEBHOOK + "?wait=true",
            json={"embeds": [embed]},
            timeout=5
        )
        if r.status_code == 200:
            _trainer_message_id = r.json().get('id')
            save_trainer_message_id(_trainer_message_id)
            print(f"✅ Trainer status message sent — ID: {_trainer_message_id}")
    except Exception as e:
        print(f"⚠️ Send trainer status error: {e}")


def _edit_trainer_message(status):
    """تعديل رسالة حالة التدريب"""
    global _trainer_message_id

    if not CRITICAL_WEBHOOK or not _trainer_message_id:
        return

    try:
        parts = CRITICAL_WEBHOOK.rstrip('/').split('/')
        webhook_id    = parts[-2]
        webhook_token = parts[-1]
    except:
        return

    embed    = _build_trainer_embed(status)
    edit_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}/messages/{_trainer_message_id}"

    try:
        r = requests.patch(edit_url, json={"embeds": [embed]}, timeout=5)
        if r.status_code == 404:
            print("⚠️ Trainer message deleted — sending new one")
            _trainer_message_id = None
            save_trainer_message_id(None)
            _send_trainer_message(status)
    except Exception as e:
        print(f"⚠️ Edit trainer status error: {e}")


def _build_trainer_embed(status):
    """بناء embed حالة التدريب"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    base = {
        "footer":    {"text": "MSA Training Bot • System Monitor"},
        "timestamp": datetime.utcnow().isoformat()
    }

    if _server_icon:
        base["thumbnail"] = {"url": _server_icon}

    if status == 'ONLINE':
        base.update({
            "title":       "Training Bot — RUNNING",
            "color":       0x00ff00,
            "description": "سكريبت تدريب المستشارين يعمل بشكل طبيعي",
            "fields": [
                {"name": "الحالة",      "value": "متصل",   "inline": True},
                {"name": "آخر تحديث",  "value": now,       "inline": True},
                {"name": "نظام المراقبة", "value": "يعمل بشكل طبيعي", "inline": False},
                {"name": "معدل التحديث", "value": "كل 30 ثانية", "inline": True},
            ],
        })
    else:
        base.update({
            "title":       "Training Bot — OFFLINE",
            "color":       0xff0000,
            "description": "سكريبت تدريب المستشارين متوقف أو انقطع",
            "fields": [
                {"name": "الحالة",      "value": "غير متصل", "inline": True},
                {"name": "آخر تحديث",  "value": now,         "inline": True},
                {"name": "تنبيه",       "value": "سكريبت التدريب توقف", "inline": False},
                {"name": "معدل التحديث", "value": "كل 30 ثانية", "inline": True},
            ],
        })

    return base


def update_trainer_status():
    """مراقبة سكريبت التدريب — تُستدعى كل 30 ثانية"""
    global _trainer_status, _trainer_message_id

    row = get_trainer_status()

    if not row:
        new_status = 'OFFLINE'
    else:
        seconds_since = float(row.get('seconds_since') or 9999)
        new_status    = 'ONLINE' if seconds_since <= TRAINER_TIMEOUT else 'OFFLINE'

        if _trainer_message_id is None and row.get('status_message_id'):
            _trainer_message_id = row['status_message_id']
            print(f"✅ Restored trainer message ID: {_trainer_message_id}")

    if _trainer_message_id is None:
        _trainer_status = new_status
        _send_trainer_message(new_status)
        return

    if new_status != _trainer_status:
        print(f"🔄 Trainer status changed: {_trainer_status} → {new_status}")
        _trainer_status = new_status
        _edit_trainer_message(new_status)
    else:
        _edit_trainer_message(new_status)
