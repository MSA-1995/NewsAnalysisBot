"""
📰 News Analysis Bot
يجيب أخبار من RSS Feeds، يحللها، ويحفظها في Database
"""

# ========== PIP UPDATE CHECK ==========
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
import os
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

import discord
from discord.ext import commands, tasks
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from textblob import TextBlob
import feedparser
import asyncio
import re
import requests
from config_encrypted import get_discord_token, get_critical_webhook

# Environment Variables
TOKEN = get_discord_token()
DATABASE_URL = os.getenv("DATABASE_URL")
CRITICAL_WEBHOOK = get_critical_webhook()

def send_critical_alert(error_type, message, details=None):
    """Send critical error alert to Discord"""
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

if not TOKEN:
    print("❌ Error: Failed to decrypt DISCORD_TOKEN!")
    exit(1)

if not DATABASE_URL:
    print("❌ Error: DATABASE_URL not found!")
    exit(1)

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

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

# Free APIs (مجانية 100%)
CRYPTOPANIC_KEY = os.getenv("CRYPTOPANIC_KEY", "")  # مجاني 300 requests/يوم
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_SECRET = os.getenv("REDDIT_SECRET", "")
reddit_token = None

# Track processed news
processed_news = set()

# Reddit Token
def get_reddit_token():
    """الحصول على Reddit Access Token"""
    global reddit_token
    if not REDDIT_CLIENT_ID or not REDDIT_SECRET:
        return None
    try:
        import requests
        auth = requests.auth.HTTPBasicAuth(REDDIT_CLIENT_ID, REDDIT_SECRET)
        data = {'grant_type': 'client_credentials'}
        headers = {'User-Agent': 'NewsBot/1.0'}
        response = requests.post('https://www.reddit.com/api/v1/access_token',
                               auth=auth, data=data, headers=headers, timeout=10)
        if response.status_code == 200:
            reddit_token = response.json()['access_token']
            return reddit_token
    except:
        pass
    return None

# CryptoPanic News
def get_cryptopanic_news(symbol):
    """جلب أخبار من CryptoPanic (Twitter + Reddit + News)"""
    if not CRYPTOPANIC_KEY:
        return []
    try:
        import requests
        coin = symbol.split('/')[0]
        url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_KEY}&currencies={coin}&filter=hot"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        news = []
        for post in data.get('results', [])[:3]:
            votes = post.get('votes', {})
            positive = votes.get('positive', 0)
            negative = votes.get('negative', 0)
            sentiment = 'POSITIVE' if positive > negative * 2 else 'NEGATIVE' if negative > positive * 2 else 'NEUTRAL'
            news.append({
                'title': post.get('title', ''),
                'url': post.get('url', ''),
                'sentiment': sentiment,
                'source': 'CryptoPanic'
            })
        return news
    except:
        return []

# Reddit News
def get_reddit_news(symbol):
    """جلب أخبار من Reddit"""
    global reddit_token
    if not reddit_token:
        reddit_token = get_reddit_token()
    if not reddit_token:
        return []
    try:
        import requests
        coin = symbol.split('/')[0].lower()
        headers = {
            'Authorization': f'bearer {reddit_token}',
            'User-Agent': 'NewsBot/1.0'
        }
        url = f"https://oauth.reddit.com/r/cryptocurrency/search?q={coin}&sort=hot&limit=3&t=day"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        news = []
        for post in data.get('data', {}).get('children', []):
            p = post.get('data', {})
            score = p.get('score', 0)
            upvote_ratio = p.get('upvote_ratio', 0.5)
            sentiment = 'POSITIVE' if upvote_ratio > 0.7 and score > 100 else 'NEGATIVE' if upvote_ratio < 0.4 else 'NEUTRAL'
            news.append({
                'title': p.get('title', ''),
                'url': f"https://reddit.com{p.get('permalink', '')}",
                'sentiment': sentiment,
                'source': 'Reddit'
            })
        return news
    except:
        return []

# CoinGecko News
def get_coingecko_news(symbol):
    """جلب معلومات من CoinGecko"""
    try:
        import requests
        coin = symbol.split('/')[0].lower()
        coin_map = {
            'btc': 'bitcoin', 'eth': 'ethereum', 'bnb': 'binancecoin',
            'sol': 'solana', 'ada': 'cardano', 'matic': 'matic-network',
            'avax': 'avalanche-2', 'link': 'chainlink'
        }
        coin_id = coin_map.get(coin, coin)
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        market = data.get('market_data', {})
        price_change = market.get('price_change_percentage_24h', 0)
        sentiment = 'POSITIVE' if price_change > 2 else 'NEGATIVE' if price_change < -2 else 'NEUTRAL'
        return [{
            'title': f"{coin.upper()} Market: {price_change:.2f}% (24h)",
            'url': data.get('links', {}).get('homepage', [''])[0],
            'sentiment': sentiment,
            'source': 'CoinGecko'
        }]
    except:
        return []

# Database Connection Pool
_db_conn = None
_db_params = None

def init_db_params():
    """تهيئة معاملات الاتصال"""
    global _db_params
    if _db_params:
        return
    
    from urllib.parse import urlparse, unquote
    parsed = urlparse(DATABASE_URL)
    
    _db_params = {
        'host': parsed.hostname,
        'port': parsed.port,
        'database': parsed.path[1:],
        'user': parsed.username,
        'password': unquote(parsed.password),
        'sslmode': 'require',
        'connect_timeout': 10,
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5
    }

def get_db_connection():
    """الاتصال بقاعدة البيانات مع إعادة استخدام"""
    global _db_conn, _db_params
    
    try:
        init_db_params()
        
        # فحص الاتصال الحالي
        if _db_conn and not _db_conn.closed:
            try:
                # اختبار الاتصال
                cursor = _db_conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                return _db_conn
            except:
                # الاتصال معطل - نغلقه
                try:
                    _db_conn.close()
                except:
                    pass
                _db_conn = None
        
        # إنشاء اتصال جديد
        _db_conn = psycopg2.connect(**_db_params)
        return _db_conn
        
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        send_critical_alert("Database Connection", "Failed to connect to database", str(e))
        return None

# Create news_sentiment table
def create_table():
    """إنشاء جدول الأخبار مع retry"""
    for attempt in range(3):
        try:
            conn = get_db_connection()
            if not conn:
                if attempt < 2:
                    import time
                    time.sleep(2)
                    continue
                return
            
            cursor = conn.cursor()
            
            # إنشاء الجدول إذا ما كان موجود
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_sentiment (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20),
                    sentiment VARCHAR(20),
                    score FLOAT,
                    headline TEXT,
                    source VARCHAR(200),
                    channel_id BIGINT,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            print("✅ news_sentiment table ready")
            return
        except Exception as e:
            print(f"❌ Table creation error (attempt {attempt+1}/3): {e}")
            if attempt == 2:
                send_critical_alert("Database Table Error", "Failed to create news_sentiment table", str(e))
            try:
                if conn:
                    conn.close()
            except:
                pass
            
            if attempt < 2:
                import time
                time.sleep(2)

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

# Extract crypto symbols from text
def extract_symbols(text):
    """استخراج رموز العملات من النص"""
    symbols = []
    
    # Common crypto keywords (Top 50 - March 2026)
    crypto_keywords = {
        # Top 10 - Giants
        'BTC': 'BTC/USDT', 'BITCOIN': 'BTC/USDT',
        'ETH': 'ETH/USDT', 'ETHEREUM': 'ETH/USDT',
        'XRP': 'XRP/USDT', 'RIPPLE': 'XRP/USDT',
        'BNB': 'BNB/USDT', 'BINANCE': 'BNB/USDT',
        'SOL': 'SOL/USDT', 'SOLANA': 'SOL/USDT',
        'DOGE': 'DOGE/USDT', 'DOGECOIN': 'DOGE/USDT',
        'ADA': 'ADA/USDT', 'CARDANO': 'ADA/USDT',
        'TRX': 'TRX/USDT', 'TRON': 'TRX/USDT',
        'AVAX': 'AVAX/USDT', 'AVALANCHE': 'AVAX/USDT',
        'TON': 'TON/USDT', 'TONCOIN': 'TON/USDT',
        # 11-20 - Major Alts
        'LINK': 'LINK/USDT', 'CHAINLINK': 'LINK/USDT',
        'DOT': 'DOT/USDT', 'POLKADOT': 'DOT/USDT',
        'BCH': 'BCH/USDT', 'BITCOIN CASH': 'BCH/USDT',
        'NEAR': 'NEAR/USDT',
        'LTC': 'LTC/USDT', 'LITECOIN': 'LTC/USDT',
        'UNI': 'UNI/USDT', 'UNISWAP': 'UNI/USDT',
        'ATOM': 'ATOM/USDT', 'COSMOS': 'ATOM/USDT',
        'XLM': 'XLM/USDT', 'STELLAR': 'XLM/USDT',
        'HBAR': 'HBAR/USDT', 'HEDERA': 'HBAR/USDT',
        'ICP': 'ICP/USDT', 'INTERNET COMPUTER': 'ICP/USDT',
        # 21-30 - Strong Layer 1 & Layer 2
        'APT': 'APT/USDT', 'APTOS': 'APT/USDT',
        'ARB': 'ARB/USDT', 'ARBITRUM': 'ARB/USDT',
        'OP': 'OP/USDT', 'OPTIMISM': 'OP/USDT',
        'SUI': 'SUI/USDT',
        'INJ': 'INJ/USDT', 'INJECTIVE': 'INJ/USDT',
        'TIA': 'TIA/USDT', 'CELESTIA': 'TIA/USDT',
        'SEI': 'SEI/USDT',
        'FTM': 'FTM/USDT', 'FANTOM': 'FTM/USDT',
        'ALGO': 'ALGO/USDT', 'ALGORAND': 'ALGO/USDT',
        'VET': 'VET/USDT', 'VECHAIN': 'VET/USDT',
        # 31-40 - DeFi & Infrastructure
        'AAVE': 'AAVE/USDT',
        'FIL': 'FIL/USDT', 'FILECOIN': 'FIL/USDT',
        'RENDER': 'RENDER/USDT',
        'GRT': 'GRT/USDT', 'GRAPH': 'GRT/USDT',
        'RUNE': 'RUNE/USDT', 'THORCHAIN': 'RUNE/USDT',
        'LDO': 'LDO/USDT', 'LIDO': 'LDO/USDT',
        'CRV': 'CRV/USDT', 'CURVE': 'CRV/USDT',
        'SNX': 'SNX/USDT', 'SYNTHETIX': 'SNX/USDT',
        'MKR': 'MKR/USDT', 'MAKER': 'MKR/USDT',
        'THETA': 'THETA/USDT',
        # 41-50 - Meme, Gaming & Others
        'SHIB': 'SHIB/USDT', 'SHIBA': 'SHIB/USDT',
        'PEPE': 'PEPE/USDT',
        'WIF': 'WIF/USDT',
        'FLOKI': 'FLOKI/USDT',
        'BONK': 'BONK/USDT',
        'IMX': 'IMX/USDT', 'IMMUTABLE': 'IMX/USDT',
        'SAND': 'SAND/USDT', 'SANDBOX': 'SAND/USDT',
        'MANA': 'MANA/USDT', 'DECENTRALAND': 'MANA/USDT',
        'AXS': 'AXS/USDT', 'AXIE': 'AXS/USDT',
        'GALA': 'GALA/USDT',
    }
    
    text_upper = text.upper()
    
    for keyword, symbol in crypto_keywords.items():
        if keyword in text_upper:
            if symbol not in symbols:
                symbols.append(symbol)
    
    return symbols

# Analyze sentiment
def analyze_sentiment(text):
    """تحليل المشاعر من النص"""
    try:
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        
        # Classify sentiment
        if polarity > 0.1:
            sentiment = 'POSITIVE'
        elif polarity < -0.1:
            sentiment = 'NEGATIVE'
        else:
            sentiment = 'NEUTRAL'
        
        return sentiment, polarity
    except:
        return 'NEUTRAL', 0.0

# Save news to database
def save_news(symbol, sentiment, score, headline, source, channel_id, retry=3):
    """حفظ الخبر في قاعدة البيانات مع إعادة محاولة"""
    global _db_conn
    
    for attempt in range(retry):
        conn = None
        try:
            # إنشاء اتصال جديد مباشرة (بدون إعادة استخدام)
            from urllib.parse import urlparse, unquote
            parsed = urlparse(DATABASE_URL)
            
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                database=parsed.path[1:],
                user=parsed.username,
                password=unquote(parsed.password),
                sslmode='prefer',  # prefer بدلاً من require
                connect_timeout=15,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
            
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO news_sentiment 
                (symbol, sentiment, score, headline, source, channel_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (symbol, sentiment, score, headline[:500], source[:200], channel_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Save news error (attempt {attempt+1}/{retry}): {e}")
            try:
                if conn:
                    conn.rollback()
                    conn.close()
            except:
                pass
            
            if attempt < retry - 1:
                import time
                time.sleep(3)  # زيادة الانتظار من 2 إلى 3 ثواني
            else:
                return False
    
    return False

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online!")
    print(f"📊 Connected to {len(bot.guilds)} server(s)")
    print("📰 News Analysis System: ACTIVE")
    
    # Test database connection
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            print("✅ Database: Connected (Supabase)")
        else:
            print("❌ Database: Connection failed")
    except Exception as e:
        print(f"❌ Database: Connection error - {e}")
    
    # Create table
    create_table()
    
    # Auto-create news channel if not exists
    for guild in bot.guilds:
        news_channel = discord.utils.get(guild.text_channels, name="news-analysis-bot")
        if not news_channel:
            try:
                news_channel = await guild.create_text_channel(
                    name="news-analysis-bot",
                    topic="📰 Crypto News Analysis - Automated RSS Feeds",
                    reason="Auto-setup by News Analysis Bot"
                )
                
                # Welcome message
                welcome_embed = discord.Embed(
                    title="News Analysis Bot",
                    description="هذا الروم لعرض أخبار العملات الرقمية تلقائياً\n\nالمصادر:\n- CoinTelegraph\n- CoinDesk\n- CryptoNews\n\nالتحديث: كل 30 دقيقة\nالتحليل: Sentiment Analysis",
                    color=0x00ff00
                )
                welcome_embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
                welcome_embed.set_footer(text="News Analysis Bot • MSA")
                await news_channel.send(embed=welcome_embed)
                
                print(f"✅ Auto-created news channel in {guild.name}")
            except Exception as e:
                print(f"⚠️ Could not create channel in {guild.name}: {e}")
        else:
            print(f"✅ News channel exists in {guild.name}")
    
    # Start RSS feed checker
    if not check_rss_feeds.is_running():
        check_rss_feeds.start()
        print("🔄 RSS Feed Checker: STARTED")
    
    # Start auto-cleanup
    if not cleanup_old_news.is_running():
        cleanup_old_news.start()
        print("🗑️ Auto-Cleanup: STARTED (every 1 hour)")

@bot.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Only process messages in news-analysis-bot channel
    if message.channel.name != "news-analysis-bot":
        await bot.process_commands(message)
        return
    
    # Analyze messages only in news channel
    symbols = extract_symbols(message.content)
    
    if symbols:
        sentiment, score = analyze_sentiment(message.content)
        
        for symbol in symbols:
            saved = save_news(
                symbol=symbol,
                sentiment=sentiment,
                score=score,
                headline=message.content,
                source='Discord',
                channel_id=message.channel.id
            )
            
            if saved:
                print(f"📰 News saved: {symbol} | {sentiment} ({score:.2f}) | {message.channel.name}")
                
                # Send notification in same channel
                embed = discord.Embed(
                    title=f"News Detected: {symbol}",
                    description=message.content[:500],
                    color=0x00ff00 if sentiment == 'POSITIVE' else 0xff0000 if sentiment == 'NEGATIVE' else 0xaaaaaa,
                    timestamp=datetime.now()
                )
                embed.add_field(name="Sentiment", value=f"{sentiment} ({score:.2f})", inline=True)
                embed.add_field(name="Source", value=f"#{message.channel.name}", inline=True)
                embed.set_thumbnail(url=message.guild.icon.url if message.guild.icon else None)
                embed.set_footer(text="News Analysis Bot • MSA")
                
                try:
                    await message.channel.send(embed=embed)
                except:
                    pass
    
    await bot.process_commands(message)

# RSS Feed Checker
@tasks.loop(minutes=30)
async def check_rss_feeds():
    """فحص RSS Feeds + Free APIs كل 30 دقيقة"""
    print("🔍 Checking RSS feeds + Free APIs...")
    
    # 1. RSS Feeds (الموجودة)
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:5]:  # أحدث 5 أخبار
                # تجنب التكرار
                news_id = entry.get('id', entry.get('link', ''))
                if news_id in processed_news:
                    continue
                
                processed_news.add(news_id)
                
                # استخراج العنوان والوصف
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                full_text = f"{title} {description}"
                
                # استخراج العملات
                symbols = extract_symbols(full_text)
                
                if symbols:
                    # تحليل Sentiment
                    sentiment, score = analyze_sentiment(full_text)
                    
                    for symbol in symbols:
                        # حفظ في Database
                        saved = save_news(
                            symbol=symbol,
                            sentiment=sentiment,
                            score=score,
                            headline=title,
                            source=feed.feed.get('title', 'RSS'),
                            channel_id=0
                        )
                        
                        if saved:
                            print(f"📰 RSS News: {symbol} | {sentiment} ({score:.2f})")
                            
                            # إرسال في news-analysis-bot
                            for guild in bot.guilds:
                                news_channel = discord.utils.get(guild.text_channels, name="news-analysis-bot")
                                if news_channel:
                                    embed = discord.Embed(
                                        title=f"{symbol} News",
                                        description=title[:500],
                                        color=0x00ff00 if sentiment == 'POSITIVE' else 0xff0000 if sentiment == 'NEGATIVE' else 0xaaaaaa,
                                        timestamp=datetime.now(),
                                        url=entry.get('link', '')
                                    )
                                    embed.add_field(name="Sentiment", value=f"{sentiment} ({score:.2f})", inline=True)
                                    embed.add_field(name="Source", value=feed.feed.get('title', 'RSS'), inline=True)
                                    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
                                    embed.set_footer(text="News Analysis Bot • MSA")
                                    
                                    try:
                                        await news_channel.send(embed=embed)
                                        await asyncio.sleep(2)  # تجنب Rate Limit
                                    except Exception as e:
                                        print(f"⚠️ Send error: {e}")
            
            await asyncio.sleep(5)  # بين كل Feed
            
        except Exception as e:
            print(f"❌ RSS Feed error ({feed_url}): {e}")
    
    # 2. Free APIs (CryptoPanic + Reddit + CoinGecko)
    print("🔍 Checking Free APIs...")
    
    # العملات المدعومة
    supported_coins = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT', 'MATIC/USDT', 'AVAX/USDT', 'LINK/USDT']
    
    for symbol in supported_coins:
        try:
            # CryptoPanic
            cp_news = get_cryptopanic_news(symbol)
            for news_item in cp_news:
                sentiment, score = analyze_sentiment(news_item['title'])
                saved = save_news(symbol, sentiment, score, news_item['title'], news_item['source'], 0)
                if saved:
                    print(f"📰 CryptoPanic: {symbol} | {sentiment}")
                    await send_news_to_channels(symbol, news_item['title'], sentiment, score, news_item['source'], news_item['url'])
            
            await asyncio.sleep(2)
            
            # Reddit
            reddit_news = get_reddit_news(symbol)
            for news_item in reddit_news:
                sentiment, score = analyze_sentiment(news_item['title'])
                saved = save_news(symbol, sentiment, score, news_item['title'], news_item['source'], 0)
                if saved:
                    print(f"📰 Reddit: {symbol} | {sentiment}")
                    await send_news_to_channels(symbol, news_item['title'], sentiment, score, news_item['source'], news_item['url'])
            
            await asyncio.sleep(2)
            
            # CoinGecko
            cg_news = get_coingecko_news(symbol)
            for news_item in cg_news:
                sentiment, score = analyze_sentiment(news_item['title'])
                saved = save_news(symbol, sentiment, score, news_item['title'], news_item['source'], 0)
                if saved:
                    print(f"📰 CoinGecko: {symbol} | {sentiment}")
                    await send_news_to_channels(symbol, news_item['title'], sentiment, score, news_item['source'], news_item['url'])
            
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"⚠️ Free API error for {symbol}: {e}")
    
    # تنظيف processed_news (الاحتفاظ بآخر 1000)
    if len(processed_news) > 1000:
        processed_news.clear()
    
    print("✅ RSS + Free APIs check completed")

# Auto-cleanup old news
@tasks.loop(hours=1)
async def cleanup_old_news():
    """حذف الأخبار الأقدم من 24 ساعة كل ساعة"""
    try:
        conn = get_db_connection()
        if not conn:
            return
        
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM news_sentiment 
            WHERE timestamp < NOW() - INTERVAL '24 hours'
        """)
        
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        if deleted_count > 0:
            print(f"🗑️ Cleaned up {deleted_count} old news (>24h)")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

@cleanup_old_news.before_loop
async def before_cleanup():
    await bot.wait_until_ready()

# Helper function to send news
async def send_news_to_channels(symbol, title, sentiment, score, source, url):
    """إرسال الخبر لجميع السيرفرات"""
    for guild in bot.guilds:
        news_channel = discord.utils.get(guild.text_channels, name="news-analysis-bot")
        if news_channel:
            embed = discord.Embed(
                title=f"{symbol} News",
                description=title[:500],
                color=0x00ff00 if sentiment == 'POSITIVE' else 0xff0000 if sentiment == 'NEGATIVE' else 0xaaaaaa,
                timestamp=datetime.now(),
                url=url if url else None
            )
            embed.add_field(name="Sentiment", value=f"{sentiment} ({score:.2f})", inline=True)
            embed.add_field(name="Source", value=source, inline=True)
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            embed.set_footer(text="News Analysis Bot • MSA")
            try:
                await news_channel.send(embed=embed)
                await asyncio.sleep(1)
            except:
                pass

@check_rss_feeds.before_loop
async def before_check_rss():
    await bot.wait_until_ready()

@bot.command()
async def setup_news(ctx):
    """إنشاء روم الأخبار تلقائياً"""
    await ctx.message.delete()
    
    # فحص إذا الروم موجود
    existing_channel = discord.utils.get(ctx.guild.text_channels, name="news-analysis-bot")
    
    if existing_channel:
        embed = discord.Embed(
            title="روم الأخبار موجود",
            description=f"الروم: {existing_channel.mention}\nسيتم إرسال الأخبار هنا تلقائياً",
            color=0x00ff00
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text="News Analysis Bot • MSA")
        await ctx.send(embed=embed, delete_after=10)
        return
    
    # إنشاء الروم
    news_channel = await ctx.guild.create_text_channel(
        name="news-analysis-bot",
        topic="📰 Crypto News Analysis - Automated RSS Feeds",
        reason="News Analysis Bot Setup"
    )
    
    # رسالة ترحيب
    welcome_embed = discord.Embed(
        title="News Analysis Bot",
        description="هذا الروم لعرض أخبار العملات الرقمية تلقائياً\n\nالمصادر:\n- CoinTelegraph\n- CoinDesk\n- CryptoNews\n\nالتحديث: كل 30 دقيقة\nالتحليل: Sentiment Analysis",
        color=0x00ff00
    )
    welcome_embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
    welcome_embed.set_footer(text="News Analysis Bot • MSA")
    await news_channel.send(embed=welcome_embed)
    
    # تأكيد
    confirm_embed = discord.Embed(
        title="تم إنشاء روم الأخبار",
        description=f"الروم: {news_channel.mention}\nسيتم إرسال الأخبار تلقائياً كل 30 دقيقة",
        color=0x00ff00
    )
    confirm_embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
    confirm_embed.set_footer(text="News Analysis Bot • MSA")
    await ctx.send(embed=confirm_embed, delete_after=10)
    print(f"✅ News channel created: #{news_channel.name}")

@bot.command()
async def news_stats(ctx):
    """إحصائيات الأخبار"""
    try:
        conn = get_db_connection()
        if not conn:
            await ctx.send("❌ Database connection failed!")
            return
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN sentiment = 'POSITIVE' THEN 1 END) as positive,
                COUNT(CASE WHEN sentiment = 'NEGATIVE' THEN 1 END) as negative,
                COUNT(CASE WHEN sentiment = 'NEUTRAL' THEN 1 END) as neutral
            FROM news_sentiment
            WHERE timestamp > NOW() - INTERVAL '24 hours'
        """)
        
        stats = cursor.fetchone()
        cursor.close()
        conn.close()
        
        # Calculate percentages
        total = stats['total']
        pos_pct = (stats['positive'] / total * 100) if total > 0 else 0
        neg_pct = (stats['negative'] / total * 100) if total > 0 else 0
        neu_pct = (stats['neutral'] / total * 100) if total > 0 else 0
        
        # Determine overall sentiment
        if pos_pct > 60:
            overall = "🟢 Bullish Market"
            color = 0x00ff00
        elif neg_pct > 60:
            overall = "🔴 Bearish Market"
            color = 0xff0000
        else:
            overall = "🟡 Neutral Market"
            color = 0xffaa00
        
        embed = discord.Embed(
            title="News Sentiment Analysis",
            description=f"Last 24 Hours | {overall}",
            color=color,
            timestamp=datetime.now()
        )
        
        # Stats with progress bars
        embed.add_field(
            name="Total News Analyzed",
            value=f"```{total} articles```",
            inline=False
        )
        
        embed.add_field(
            name="Positive Sentiment",
            value=f"```{stats['positive']} articles ({pos_pct:.1f}%)```",
            inline=True
        )
        
        embed.add_field(
            name="Negative Sentiment",
            value=f"```{stats['negative']} articles ({neg_pct:.1f}%)```",
            inline=True
        )
        
        embed.add_field(
            name="Neutral Sentiment",
            value=f"```{stats['neutral']} articles ({neu_pct:.1f}%)```",
            inline=True
        )
        
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text="News Analysis Bot • MSA", icon_url=bot.user.avatar.url if bot.user.avatar else None)
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
async def coin_sentiment(ctx, symbol: str):
    """عرض sentiment لعملة معينة"""
    try:
        if not symbol.endswith('/USDT'):
            symbol = f"{symbol.upper()}/USDT"
        
        conn = get_db_connection()
        if not conn:
            await ctx.send("❌ Database connection failed!")
            return
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT sentiment, score, headline, timestamp
            FROM news_sentiment
            WHERE symbol = %s
            AND timestamp > NOW() - INTERVAL '24 hours'
            ORDER BY timestamp DESC
            LIMIT 5
        """, (symbol,))
        
        news = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not news:
            await ctx.send(f"📰 No recent news for {symbol}")
            return
        
        embed = discord.Embed(
            title=f"Recent News: {symbol}",
            color=0x00ff00
        )
        
        for item in news:
            embed.add_field(
                name=f"{item['sentiment']} ({item['score']:.2f})",
                value=f"{item['headline'][:100]}...\n{item['timestamp'].strftime('%Y-%m-%d %H:%M')}",
                inline=False
            )
        
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text="News Analysis Bot • MSA")
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.event
async def on_command_error(ctx, error):
    # تجاهل أخطاء الأوامر غير الموجودة
    if isinstance(error, commands.CommandNotFound):
        return
    
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need Administrator permissions to use this command!", delete_after=5)

print("🚀 Starting News Analysis Bot...")
try:
    bot.run(TOKEN)
except Exception as e:
    print(f"❌ Bot crashed: {e}")
    send_critical_alert("Bot Crash", "News Bot stopped unexpectedly", str(e))

