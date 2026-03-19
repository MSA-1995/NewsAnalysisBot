"""
📰 News Analysis Bot
Main entry point - imports all modules and starts the bot
"""

# Import all modules
from utils import check_pip_update, load_env_file
from config_encrypted import get_discord_token
from discord_bot import bot

# Load environment and check pip
check_pip_update()
load_env_file()

# Get Discord token
TOKEN = get_discord_token()

if not TOKEN:
    print("❌ Error: Failed to decrypt DISCORD_TOKEN!")
    exit(1)

# Import remaining modules
from config import RSS_FEEDS, CRYPTOPANIC_KEY, REDDIT_CLIENT_ID, REDDIT_SECRET, SYMBOLS
from news_fetcher import get_cryptopanic_news, get_reddit_news, get_coingecko_news, processed_news
from database import get_db_connection, create_table, save_news
from sentiment import analyze_sentiment
from scheduler import check_rss_feeds, cleanup_old_news

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
    from discord_bot import extract_symbols
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
                from discord_bot import extract_symbols
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
    from utils import send_critical_alert
    send_critical_alert("Bot Crash", "News Bot stopped unexpectedly", str(e))

