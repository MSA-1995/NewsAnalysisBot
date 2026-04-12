"""
News: News Analysis Bot - Enhanced Version with Rate Limiting
"""

import discord
import asyncio
import feedparser
import aiohttp
from datetime import datetime, timedelta
from src.core.utils import check_pip_update, load_env_file, send_discord
from src.config.config_encrypted import get_discord_token, get_critical_webhook
from src.handlers.discord_bot import bot
from discord.ext import commands, tasks

# Cache for sent news to prevent duplicates (stores hashes of recent news titles)
sent_news_cache = set()
NEWS_CACHE_MAX_SIZE = 200  # Keep only last 200 news
NEWS_CACHE_EXPIRY = timedelta(hours=2)  # Clear cache every 2 hours
last_news_cache_clear = datetime.now()

def _clear_expired_news_cache():
    """Clear the sent news cache if expired."""
    global last_news_cache_clear
    if datetime.now() - last_news_cache_clear > NEWS_CACHE_EXPIRY:
        sent_news_cache.clear()
        last_news_cache_clear = datetime.now()

def _is_news_duplicate(title):
    """Check if news was recently sent to prevent duplicates."""
    _clear_expired_news_cache()
    news_hash = hash(title.lower().strip())
    if news_hash in sent_news_cache:
        return True
    if len(sent_news_cache) >= NEWS_CACHE_MAX_SIZE:
        # Remove oldest (approximate by popping one)
        sent_news_cache.pop()
    sent_news_cache.add(news_hash)
    return False

# Load environment and check pip
check_pip_update()
load_env_file()

# Get Discord token
TOKEN = get_discord_token()

# Force running without Discord for news fetching
USE_DISCORD = False
print("Running news fetching without Discord notifications.")

# Import remaining modules
from src.config.config import RSS_FEEDS, CRYPTOPANIC_KEY, REDDIT_CLIENT_ID, REDDIT_SECRET, SYMBOLS
from src.news_fetcher import get_cryptopanic_news, get_reddit_news, get_coingecko_news, processed_news
from src.core.database import get_db_connection, create_table, save_news, async_save_news # Import async_save_news
from src.models.sentiment import analyze_sentiment
from src.handlers.scheduler import cleanup_old_news_task

# ========================= RATE LIMITER =========================
class RateLimiter:
    """Simple async rate limiter"""
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls = 0
        self.lock = None
        self.queue = None

    def start(self):
        """Starts the worker task — يُستدعى بعد ما يشتغل event loop"""
        self.lock = asyncio.Lock()
        self.queue = asyncio.Queue()
        asyncio.create_task(self._worker())

    async def _worker(self):
        while True:
            func, args, kwargs, fut = await self.queue.get()
            async with self.lock:
                if self.calls >= self.max_calls:
                    await asyncio.sleep(self.period)
                    self.calls = 0
                try:
                    result = await func(*args, **kwargs)
                    fut.set_result(result)
                except Exception as e:
                    fut.set_exception(e)
                self.calls += 1
            self.queue.task_done()

    async def call(self, func, *args, **kwargs):
        fut = asyncio.get_event_loop().create_future()
        await self.queue.put((func, args, kwargs, fut))
        return await fut

# إنشاء بدون تشغيل — يشتغلون في on_ready
api_rate_limiter = RateLimiter(max_calls=1, period=1.5)
discord_rate_limiter = RateLimiter(max_calls=1, period=3.0)  # زيادة الفترة لتجنب الحظر

# ========================= HELPER FUNCTIONS =========================
async def send_discord_message(channel, embed):
    """Send a Discord embed safely with rate limiting"""
    async def _send():
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as e:
            if e.status == 429:
                print("Warning: Discord 429: waiting before retry")
                await asyncio.sleep(5)
                await channel.send(embed=embed)
    await discord_rate_limiter.call(_send)

async def send_news_to_channels(symbol, title, sentiment, score, source, url):
    """Send news to all guilds using queue, with deduplication"""
    if _is_news_duplicate(title):
        return  # Skip duplicate news
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
            await send_discord_message(news_channel, embed)
            await asyncio.sleep(0.5)  # extra safety delay

async def initialize_database():
    """Runs synchronous database setup in an executor to avoid blocking."""
    loop = asyncio.get_running_loop()
    
    def _db_setup():
        """The synchronous part of the database setup."""
        try:
            # 1. Test database connection
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                conn.close()  # Close the test connection immediately
                print("Database: Test connection successful.")

                # 2. Create table (gets its own connection)
                create_table()
                print("Database: Table check/creation complete.")
            else:
                print("Database: Connection failed during setup.")
        except Exception as e:
            print(f"Database: Initialization error - {e}")

    print("Initializing database...")
    await loop.run_in_executor(None, _db_setup)
    print("Database: Initialization process finished.")

# ========================= BOT EVENTS =========================
@bot.event
async def on_ready():
    print(f"{bot.user} is online!")
    print(f"Connected to {len(bot.guilds)} server(s)")
    print("News Analysis System: ACTIVE")

    # Start rate limiters
    api_rate_limiter.start()
    discord_rate_limiter.start()
    print("Rate Limiters: STARTED")
    
    # Initialize database asynchronously to prevent blocking
    await initialize_database()
    
    # Auto-create news channel if not exists
    for guild in bot.guilds:
        news_channel = discord.utils.get(guild.text_channels, name="news-analysis-bot")
        if not news_channel:
            try:
                news_channel = await guild.create_text_channel(
                    name="news-analysis-bot",
                    topic="News: Crypto News Analysis - Automated RSS Feeds",
                    reason="Auto-setup by News Analysis Bot"
                )
                welcome_embed = discord.Embed(
                    title="News Analysis Bot",
                    description="هذا الروم لعرض أخبار العملات الرقمية تلقائياً\n\nالمصادر:\n- CoinTelegraph\n- CoinDesk\n- CryptoNews\n\nالتحديث: كل 30 دقيقة\nالتحليل: Sentiment Analysis",
                    color=0x00ff00
                )
                welcome_embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
                welcome_embed.set_footer(text="News Analysis Bot • MSA")
                await send_discord_message(news_channel, welcome_embed)
                print(f"OK: Auto-created news channel in {guild.name}")
            except Exception as e:
                print(f"Warning: Could not create channel in {guild.name}: {e}")
        else:
            print(f"OK: News channel exists in {guild.name}")

    # Start RSS feed checker
    if not check_rss_feeds.is_running():
        check_rss_feeds.start()
        print(" RSS Feed Checker: STARTED")
    
    # Start auto-cleanup
    if not cleanup_old_news_task.is_running():
        cleanup_old_news_task.start()
        print("Cleanup: Auto-Cleanup: STARTED (every 1 hour)")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.name != "news-analysis-bot":
        await bot.process_commands(message)
        return
    
    from src.handlers.discord_bot import extract_symbols
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
                print(f"News: News saved: {symbol} | {sentiment} ({score:.2f}) | {message.channel.name}")
                await send_news_to_channels(symbol, message.content, sentiment, score, 'Discord', None)
    
    await bot.process_commands(message)

# ========================= RSS & API CHECKER =========================
@tasks.loop(minutes=30)
async def check_rss_feeds():
    print("Checking Checking RSS feeds + Free APIs...")
    loop = asyncio.get_running_loop()
    
    # 1. RSS Feeds
    for feed_url in RSS_FEEDS:
        try:
            # Run blocking feedparser in executor
            feed = await loop.run_in_executor(None, feedparser.parse, feed_url)
            source_title = feed.feed.get('title', 'RSS')

            for entry in feed.entries[:5]:
                news_id = entry.get('id', entry.get('link', ''))
                if news_id in processed_news:
                    continue
                processed_news.add(news_id)
                
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                full_text = f"{title} {description}"
                
                from src.handlers.discord_bot import extract_symbols
                symbols = extract_symbols(full_text)
                
                if symbols:
                    sentiment, score = analyze_sentiment(full_text)
                    for symbol in symbols:
                        # Use async_save_news
                        saved = await async_save_news(symbol, sentiment, score, title, source_title, 0)
                        if saved:
                            print(f"News: RSS News: {symbol} | {sentiment} ({score:.2f})")
                            await send_news_to_channels(symbol, title, sentiment, score, source_title, entry.get('link', ''))
            
            await asyncio.sleep(5)
        except Exception as e:
            print(f"ERROR: RSS Feed error ({feed_url}): {e}")

    # 2. Free APIs
    print("Checking Checking Free APIs...")
    # Use the unified symbol list from config.py
    for symbol in SYMBOLS:
        try:
            # Correctly await the async functions via the rate limiter
            cp_news = await api_rate_limiter.call(get_cryptopanic_news, symbol)
            for news_item in cp_news:
                sentiment, score = analyze_sentiment(news_item['title'])
                saved = await async_save_news(symbol, sentiment, score, news_item['title'], news_item['source'], 0)
                if saved:
                    print(f"News: CryptoPanic: {symbol} | {sentiment}")
                    await send_news_to_channels(symbol, news_item['title'], sentiment, score, news_item['source'], news_item['url'])
            
            await asyncio.sleep(1.5)
            
            reddit_news = await api_rate_limiter.call(get_reddit_news, symbol)
            for news_item in reddit_news:
                sentiment, score = analyze_sentiment(news_item['title'])
                saved = await async_save_news(symbol, sentiment, score, news_item['title'], news_item['source'], 0)
                if saved:
                    print(f"News: Reddit: {symbol} | {sentiment}")
                    await send_news_to_channels(symbol, news_item['title'], sentiment, score, news_item['source'], news_item['url'])
            
            await asyncio.sleep(1.5)
            
            cg_news = await api_rate_limiter.call(get_coingecko_news, symbol)
            for news_item in cg_news:
                sentiment, score = analyze_sentiment(news_item['title'])
                saved = await async_save_news(symbol, sentiment, score, news_item['title'], news_item['source'], 0)
                if saved:
                    print(f"News: CoinGecko: {symbol} | {sentiment}")
                    await send_news_to_channels(symbol, news_item['title'], sentiment, score, news_item['source'], news_item['url'])
            
            await asyncio.sleep(1.5)
        except Exception as e:
            print(f"Warning: Free API error for {symbol}: {e}")
    
    if len(processed_news) > 1000:
        processed_news.clear()
    
    print("OK: RSS + Free APIs check completed")

# ========================= AUTO CLEANUP =========================
@tasks.loop(hours=1)
async def cleanup_old_news():
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
            print(f"Cleanup: Cleaned up {deleted_count} old news (>24h)")
    except Exception as e:
        print(f"Warning: Cleanup error: {e}")

@cleanup_old_news.before_loop
@check_rss_feeds.before_loop
async def before_loops():
    await bot.wait_until_ready()

# ========================= ERROR HANDLING =========================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("ERROR: You need Administrator permissions to use this command!", delete_after=5)

# ========================= START BOT =========================
if __name__ == "__main__":
    print("Starting News Analysis Bot...")
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"ERROR: Discord connection failed: {e}")
        print("Running news fetching without Discord notifications...")
        # Run without Discord
        # Run without Discord
        import asyncio
        async def run_without_discord():
            await initialize_database()
            api_rate_limiter.start()
            print("News fetching started without Discord...")
            while True:
                try:
                    # Run the RSS and API checks manually
                    loop = asyncio.get_running_loop()
                    # RSS Feeds
                    for feed_url in RSS_FEEDS:
                        try:
                            feed = await loop.run_in_executor(None, feedparser.parse, feed_url)
                            source_title = feed.feed.get('title', 'RSS')
                            for entry in feed.entries[:5]:
                                news_id = entry.get('id', entry.get('link', ''))
                                if news_id in processed_news:
                                    continue
                                processed_news.add(news_id)
                                title = entry.get('title', '')
                                description = entry.get('summary', entry.get('description', ''))
                                full_text = f"{title} {description}"
                                from src.handlers.discord_bot import extract_symbols
                                symbols = extract_symbols(full_text)
                                if symbols:
                                    sentiment, score = analyze_sentiment(full_text)
                                    for symbol in symbols:
                                        saved = await async_save_news(symbol, sentiment, score, title, source_title, 0)
                                        if saved:
                                            print(f"News: RSS News: {symbol} | {sentiment} ({score:.2f})")
                        except Exception as e:
                            print(f"ERROR: RSS Feed error ({feed_url}): {e}")
                        await asyncio.sleep(5)

                    # Free APIs
                    print("Checking Free APIs...")
                    for symbol in SYMBOLS:
                        try:
                            cp_news = await api_rate_limiter.call(get_cryptopanic_news, symbol)
                            for news_item in cp_news:
                                sentiment, score = analyze_sentiment(news_item['title'])
                                saved = await async_save_news(symbol, sentiment, score, news_item['title'], news_item['source'], 0)
                                if saved:
                                    print(f"News: CryptoPanic: {symbol} | {sentiment}")
                            await asyncio.sleep(1.5)

                            reddit_news = await api_rate_limiter.call(get_reddit_news, symbol)
                            for news_item in reddit_news:
                                sentiment, score = analyze_sentiment(news_item['title'])
                                saved = await async_save_news(symbol, sentiment, score, news_item['title'], news_item['source'], 0)
                                if saved:
                                    print(f"News: Reddit: {symbol} | {sentiment}")
                            await asyncio.sleep(1.5)

                            cg_news = await api_rate_limiter.call(get_coingecko_news, symbol)
                            for news_item in cg_news:
                                sentiment, score = analyze_sentiment(news_item['title'])
                                saved = await async_save_news(symbol, sentiment, score, news_item['title'], news_item['source'], 0)
                                if saved:
                                    print(f"News: CoinGecko: {symbol} | {sentiment}")
                            await asyncio.sleep(1.5)
                        except Exception as e:
                            print(f"Warning: Free API error for {symbol}: {e}")

                    if len(processed_news) > 1000:
                        processed_news.clear()
                    print("OK: RSS + Free APIs check completed")
                    await asyncio.sleep(30 * 60)  # Wait 30 minutes
                except Exception as e:
                    print(f"Error in news loop: {e}")
                    await asyncio.sleep(60)

        asyncio.run(run_without_discord())