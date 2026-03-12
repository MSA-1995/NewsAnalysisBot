"""
📰 News Analysis Bot
يجيب أخبار من RSS Feeds، يحللها، ويحفظها في Database
"""

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
from config_encrypted import get_discord_token

# Environment Variables
TOKEN = get_discord_token()
DATABASE_URL = os.getenv("DATABASE_URL")

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
]

# Track processed news
processed_news = set()

# Database Connection
def get_db_connection():
    """الاتصال بقاعدة البيانات"""
    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(DATABASE_URL)
        
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=unquote(parsed.password)
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

# Create news_sentiment table
def create_table():
    """إنشاء جدول الأخبار"""
    try:
        conn = get_db_connection()
        if not conn:
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
        
        # تعديل عمود source إذا كان صغير
        try:
            cursor.execute("""
                ALTER TABLE news_sentiment 
                ALTER COLUMN source TYPE VARCHAR(200)
            """)
            print("✅ source column updated to VARCHAR(200)")
        except Exception as e:
            # العمود موجود بالحجم الصحيح
            pass
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ news_sentiment table ready")
    except Exception as e:
        print(f"❌ Table creation error: {e}")

# Extract crypto symbols from text
def extract_symbols(text):
    """استخراج رموز العملات من النص"""
    symbols = []
    
    # Common crypto symbols
    crypto_keywords = {
        'BTC': 'BTC/USDT', 'BITCOIN': 'BTC/USDT',
        'ETH': 'ETH/USDT', 'ETHEREUM': 'ETH/USDT',
        'BNB': 'BNB/USDT', 'BINANCE': 'BNB/USDT',
        'SOL': 'SOL/USDT', 'SOLANA': 'SOL/USDT',
        'ADA': 'ADA/USDT', 'CARDANO': 'ADA/USDT',
        'AVAX': 'AVAX/USDT', 'AVALANCHE': 'AVAX/USDT',
        'LINK': 'LINK/USDT', 'CHAINLINK': 'LINK/USDT',
        'DOT': 'DOT/USDT', 'POLKADOT': 'DOT/USDT',
        'UNI': 'UNI/USDT', 'UNISWAP': 'UNI/USDT',
        'ATOM': 'ATOM/USDT', 'COSMOS': 'ATOM/USDT',
        'LTC': 'LTC/USDT', 'LITECOIN': 'LTC/USDT',
        'XRP': 'XRP/USDT', 'RIPPLE': 'XRP/USDT',
        'DOGE': 'DOGE/USDT', 'DOGECOIN': 'DOGE/USDT',
        'SHIB': 'SHIB/USDT', 'SHIBA': 'SHIB/USDT',
        'TRX': 'TRX/USDT', 'TRON': 'TRX/USDT',
        'APT': 'APT/USDT', 'APTOS': 'APT/USDT',
        'ARB': 'ARB/USDT', 'ARBITRUM': 'ARB/USDT',
        'OP': 'OP/USDT', 'OPTIMISM': 'OP/USDT',
        'FIL': 'FIL/USDT', 'FILECOIN': 'FIL/USDT',
        'NEAR': 'NEAR/USDT'
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
def save_news(symbol, sentiment, score, headline, source, channel_id):
    """حفظ الخبر في قاعدة البيانات"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
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
        print(f"❌ Save news error: {e}")
        return False

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online!")
    print(f"📊 Connected to {len(bot.guilds)} server(s)")
    print("📰 News Analysis System: ACTIVE")
    
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
                    title="📰 News Analysis Bot",
                    description="هذا الروم لعرض أخبار العملات الرقمية تلقائياً\n\n✅ **المصادر:**\n- CoinTelegraph\n- CoinDesk\n- CryptoNews\n\n🔄 **التحديث:** كل 30 دقيقة\n🧠 **التحليل:** Sentiment Analysis",
                    color=0x00ff00
                )
                welcome_embed.set_footer(text="News Analysis Bot - MSA")
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
    
    # Process all messages (you can filter by channel later)
    # For now, analyze all messages containing crypto keywords
    
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
                
                # إرسال إشعار لروم news-analysis-bot
                news_channel = discord.utils.get(message.guild.text_channels, name="news-analysis-bot")
                if news_channel:
                    sentiment_emoji = "✅" if sentiment == 'POSITIVE' else "❌" if sentiment == 'NEGATIVE' else "⚪"
                    embed = discord.Embed(
                        title=f"{sentiment_emoji} News Detected: {symbol}",
                        description=message.content[:500],
                        color=0x00ff00 if sentiment == 'POSITIVE' else 0xff0000 if sentiment == 'NEGATIVE' else 0xaaaaaa,
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="Sentiment", value=f"{sentiment} ({score:.2f})", inline=True)
                    embed.add_field(name="Source", value=f"#{message.channel.name}", inline=True)
                    embed.set_footer(text="News Analysis Bot")
                    
                    try:
                        await news_channel.send(embed=embed)
                    except:
                        pass
    
    await bot.process_commands(message)

# RSS Feed Checker
@tasks.loop(minutes=30)
async def check_rss_feeds():
    """فحص RSS Feeds كل 30 دقيقة"""
    print("🔍 Checking RSS feeds...")
    
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
                                    sentiment_emoji = "✅" if sentiment == 'POSITIVE' else "❌" if sentiment == 'NEGATIVE' else "⚪"
                                    embed = discord.Embed(
                                        title=f"{sentiment_emoji} {symbol} News",
                                        description=title[:500],
                                        color=0x00ff00 if sentiment == 'POSITIVE' else 0xff0000 if sentiment == 'NEGATIVE' else 0xaaaaaa,
                                        timestamp=datetime.now(),
                                        url=entry.get('link', '')
                                    )
                                    embed.add_field(name="Sentiment", value=f"{sentiment} ({score:.2f})", inline=True)
                                    embed.add_field(name="Source", value=feed.feed.get('title', 'RSS'), inline=True)
                                    embed.set_footer(text="News Analysis Bot - RSS Feed")
                                    
                                    try:
                                        await news_channel.send(embed=embed)
                                        await asyncio.sleep(2)  # تجنب Rate Limit
                                    except Exception as e:
                                        print(f"⚠️ Send error: {e}")
            
            await asyncio.sleep(5)  # بين كل Feed
            
        except Exception as e:
            print(f"❌ RSS Feed error ({feed_url}): {e}")
    
    # تنظيف processed_news (الاحتفاظ بآخر 1000)
    if len(processed_news) > 1000:
        processed_news.clear()
    
    print("✅ RSS check completed")

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
            title="✅ روم الأخبار موجود",
            description=f"الروم: {existing_channel.mention}\n📰 سيتم إرسال الأخبار هنا تلقائياً",
            color=0x00ff00
        )
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
        title="📰 News Analysis Bot",
        description="هذا الروم لعرض أخبار العملات الرقمية تلقائياً\n\n✅ **المصادر:**\n- CoinTelegraph\n- CoinDesk\n- CryptoNews\n\n🔄 **التحديث:** كل 30 دقيقة\n🧠 **التحليل:** Sentiment Analysis",
        color=0x00ff00
    )
    welcome_embed.set_footer(text="News Analysis Bot - MSA")
    await news_channel.send(embed=welcome_embed)
    
    # تأكيد
    confirm_embed = discord.Embed(
        title="✅ تم إنشاء روم الأخبار",
        description=f"الروم: {news_channel.mention}\n📰 سيتم إرسال الأخبار تلقائياً كل 30 دقيقة",
        color=0x00ff00
    )
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
            title="📊 News Sentiment Analysis",
            description=f"**Last 24 Hours** | {overall}",
            color=color,
            timestamp=datetime.now()
        )
        
        # Stats with progress bars
        embed.add_field(
            name="📈 Total News Analyzed",
            value=f"```{total} articles```",
            inline=False
        )
        
        embed.add_field(
            name="✅ Positive Sentiment",
            value=f"```{stats['positive']} articles ({pos_pct:.1f}%)```",
            inline=True
        )
        
        embed.add_field(
            name="❌ Negative Sentiment",
            value=f"```{stats['negative']} articles ({neg_pct:.1f}%)```",
            inline=True
        )
        
        embed.add_field(
            name="⚪ Neutral Sentiment",
            value=f"```{stats['neutral']} articles ({neu_pct:.1f}%)```",
            inline=True
        )
        
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
            title=f"📰 Recent News: {symbol}",
            color=0x00ff00
        )
        
        for item in news:
            sentiment_emoji = "✅" if item['sentiment'] == 'POSITIVE' else "❌" if item['sentiment'] == 'NEGATIVE' else "⚪"
            embed.add_field(
                name=f"{sentiment_emoji} {item['sentiment']} ({item['score']:.2f})",
                value=f"{item['headline'][:100]}...\n{item['timestamp'].strftime('%Y-%m-%d %H:%M')}",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

print("🚀 Starting News Analysis Bot...")
bot.run(TOKEN)
