"""
📰 News Analysis Bot - Utilities
Helper functions and utilities
"""

import os
import subprocess
import sys

def check_pip_update():
    """فحص وتحديث pip"""
    try:
        print("🔄 Checking pip updates...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("✅ pip updated successfully")
        else:
            print("✅ pip is up to date")
    except Exception as e:
        print(f"⚠️ pip check skipped: {e}")

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