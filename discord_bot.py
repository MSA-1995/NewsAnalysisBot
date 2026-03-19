"""
📰 News Analysis Bot - Discord Bot
Discord bot functionality
"""

import discord
from discord.ext import commands, tasks
import os
import asyncio
from datetime import datetime
from config import TOKEN, RSS_FEEDS, SYMBOLS
from database import get_db_connection, create_table, save_news, cleanup_old_news, get_news_stats, get_coin_sentiment
from news_fetcher import check_rss_feeds
from sentiment import analyze_sentiment
from config_encrypted import get_discord_token, get_critical_webhook

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

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
        stats = get_news_stats()
        
        if not stats:
            await ctx.send("❌ Database connection failed!")
            return
        
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
        
        news = get_coin_sentiment(symbol)
        
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