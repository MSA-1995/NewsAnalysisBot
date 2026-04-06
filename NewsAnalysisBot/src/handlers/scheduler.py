"""
📰 News Analysis Bot - Scheduler
Task scheduling functions
"""

from discord.ext import tasks
import asyncio
from src.core.database import async_cleanup_old_news # Import the async version

# RSS Feed Checker
@tasks.loop(minutes=30)
async def check_rss_feeds_task():
    """فحص RSS Feeds + Free APIs كل 30 دقيقة"""
    from main import check_rss_feeds
    await check_rss_feeds()

@check_rss_feeds_task.before_loop
async def before_check_rss():
    from src.handlers.discord_bot import bot
    await bot.wait_until_ready()

# Auto-cleanup old news
@tasks.loop(hours=1)
async def cleanup_old_news_task():
    """The task that calls the async cleanup function."""
    print("🔄 Starting scheduled cleanup of old news...")
    await async_cleanup_old_news() # Await the async function
    print("✅ Scheduled cleanup finished.")

@cleanup_old_news_task.before_loop
async def before_cleanup():
    """Wait until the bot is ready before starting the loop."""
    from news_bot import bot # Local import to avoid circular dependency
    await bot.wait_until_ready()