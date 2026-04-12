"""
📰 News Analysis Bot - Utilities
Helper functions and utilities
"""

import os
import subprocess
import sys
import requests
import time
from datetime import datetime, timedelta

# Cache for sent messages to prevent duplicates (stores hashes of recent messages)
sent_messages_cache = set()
CACHE_MAX_SIZE = 100  # Keep only last 100 messages
CACHE_EXPIRY = timedelta(hours=1)  # Clear cache every hour
last_cache_clear = datetime.now()

def _clear_expired_cache():
    """Clear the sent messages cache if expired."""
    global last_cache_clear
    if datetime.now() - last_cache_clear > CACHE_EXPIRY:
        sent_messages_cache.clear()
        last_cache_clear = datetime.now()

def _is_message_duplicate(message):
    """Check if message was recently sent to prevent duplicates."""
    _clear_expired_cache()
    message_hash = hash(message)
    if message_hash in sent_messages_cache:
        return True
    if len(sent_messages_cache) >= CACHE_MAX_SIZE:
        # Remove oldest (approximate by popping one)
        sent_messages_cache.pop()
    sent_messages_cache.add(message_hash)
    return False

def send_discord(webhook_url, message, retries=3):
    """Send a simple Discord message with retries, rate limit handling, and deduplication."""
    if _is_message_duplicate(message):
        return  # Skip duplicate message
    for i in range(retries):
        try:
            response = requests.post(webhook_url, json={"content": message})
            if response.status_code == 429:
                wait = response.json().get('retry_after', 2)
                time.sleep(wait)
                continue
            return
        except:
            time.sleep(2)

def check_pip_update():
    """فحص وتحديث pip"""
    try:
        print("Checking pip updates...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("pip updated successfully")
        else:
            print("pip is up to date")
    except Exception as e:
        print(f"pip check skipped: {e}")

def send_critical_alert(error_type, message, details=None):
    """Send critical error alert to Discord"""
    from config import CRITICAL_WEBHOOK
    import requests
    from datetime import datetime
    
    if not CRITICAL_WEBHOOK:
        return
    
    fields = [
        {"name": "Bot", "value": "News Bot", "inline": True},
        {"name": "Error Type", "value": error_type, "inline": True},
        {"name": "Timestamp", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "inline": True},
        {"name": "Message", "value": message, "inline": False}
    ]
    
    if details:
        fields.append({"name": "Details", "value": str(details)[:1000], "inline": False})
    
    embed = {
        "title": "🚨 CRITICAL ALERT",
        "color": 0xff0000,
        "fields": fields,
        "footer": {"text": "MSA News Bot • System Alerts"},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        requests.post(CRITICAL_WEBHOOK, json={"embeds": [embed]}, timeout=5)
    except:
        pass

def load_env_file():
    """Load environment variables from .env file"""
    for _env_file in [
        '/home/container/NewsAnalysisBot/.env',
        '/home/container/.env',
    ]:
        try:
            with open(_env_file) as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line and not _line.startswith('#') and '=' in _line:
                        _k, _v = _line.split('=', 1)
                        os.environ.setdefault(_k.strip(), _v.strip())
            break
        except:
            pass