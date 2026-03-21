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

# قائمة العملات الثابتة (Top 50 by Market Cap - March 2026)
SYMBOLS = [
    # Top 10 - Giants
    'BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'BNB/USDT', 'SOL/USDT',
    'DOGE/USDT', 'ADA/USDT', 'TRX/USDT', 'AVAX/USDT', 'TON/USDT',
    # 11-20 - Major Alts
    'LINK/USDT', 'DOT/USDT', 'BCH/USDT', 'NEAR/USDT', 'LTC/USDT',
    'UNI/USDT', 'ATOM/USDT', 'XLM/USDT', 'HBAR/USDT', 'ICP/USDT',
    # 21-30 - Strong Layer 1 & Layer 2
    'APT/USDT', 'ARB/USDT', 'OP/USDT', 'SUI/USDT', 'INJ/USDT',
    'TIA/USDT', 'SEI/USDT', 'POL/USDT', 'ALGO/USDT', 'VET/USDT',
    # 31-40 - DeFi & Infrastructure
    'AAVE/USDT', 'FIL/USDT', 'RENDER/USDT', 'GRT/USDT', 'RUNE/USDT',
    'LDO/USDT', 'CRV/USDT', 'SNX/USDT', 'COMP/USDT', 'SUSHI/USDT',
    # 41-50 - Meme, Gaming & Others
    'SHIB/USDT', 'PEPE/USDT', 'WIF/USDT', 'FLOKI/USDT', 'BONK/USDT',
    'IMX/USDT', 'SAND/USDT', 'MANA/USDT', 'AXS/USDT', 'GALA/USDT',
]

# Health Check Configuration - Bot URLs
HEALTH_CHECK_CONFIG = {
    'trading_bot_url': os.getenv('TRADING_BOT_HEALTH_URL', 'http://localhost:5001/health'),
    'trainer_bot_url': os.getenv('TRAINER_BOT_HEALTH_URL', 'http://localhost:5002/health'),
    'timeout': int(os.getenv('HEALTH_CHECK_TIMEOUT', '5')),
    'retry_attempts': int(os.getenv('HEALTH_CHECK_RETRIES', '2')),
    'retry_delay': int(os.getenv('HEALTH_CHECK_RETRY_DELAY', '1'))
}
