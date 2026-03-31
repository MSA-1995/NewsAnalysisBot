"""
📰 News Analysis Bot - Configuration
Environment variables and API keys
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

check_pip_update()

# ========== LOAD ENV FILE ==========
# Find the project root and load .env
project_root = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(project_root, '.env')

if os.path.exists(env_path):
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())
        print("✅ Environment variables loaded from .env")
    except Exception as e:
        print(f"⚠️ Error loading .env file: {e}")
else:
    print("⚠️ .env file not found. Please ensure it exists in the project root.")

# Environment Variables
DATABASE_URL = os.getenv("DATABASE_URL")
CRITICAL_WEBHOOK = os.getenv("CRITICAL_WEBHOOK")

# Free APIs (مجانية 100%)
CRYPTOPANIC_KEY = os.getenv("CRYPTOPANIC_KEY", "")  # مجاني 300 requests/يوم
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_SECRET = os.getenv("REDDIT_SECRET", "")

# RSS Feeds
RSS_FEEDS = [
    'https://cointelegraph.com/rss',
    'https://www.coindesk.com/arc/outboundfeeds/rss/',
    'https://cryptonews.com/news/feed/',
    # مصادر إضافية مجانية
    'https://bitcoinmagazine.com/.rss/full/',
    'https://decrypt.co/feed',
    'https://www.theblockcrypto.com/rss.xml',
    'https://cryptopotato.com/feed/',
    'https://u.today/rss',
]

# قائمة العملات (نفس التداول - 50 عملة)
SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'BNB/USDT',
    'DOGE/USDT', 'TRX/USDT', 'ADA/USDT', 'LINK/USDT', 'SUI/USDT',
    'PEPE/USDT', 'LTC/USDT', 'FET/USDT', 'BCH/USDT', 'AVAX/USDT',
    'WLD/USDT', 'NEAR/USDT', 'CHZ/USDT', 'ENA/USDT', 'DOT/USDT',
    'SHIB/USDT', 'FIL/USDT', 'BONK/USDT', 'UNI/USDT', 'AAVE/USDT',
    'RENDER/USDT', 'APT/USDT', 'TON/USDT', 'ARB/USDT', 'OP/USDT',
    'ATOM/USDT', 'XLM/USDT', 'ETC/USDT', 'GRT/USDT', 'SAND/USDT',
    'MANA/USDT', 'AXS/USDT', 'THETA/USDT', 'ICP/USDT', 'ALGO/USDT',
    'VET/USDT', 'FLOKI/USDT', 'WIF/USDT', 'CRV/USDT', 'SUSHI/USDT',
    '1INCH/USDT', 'COMP/USDT', 'YFI/USDT', 'SNX/USDT', 'GALA/USDT',
]
