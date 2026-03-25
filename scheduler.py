"""
📰 News Analysis Bot - Scheduler
Task scheduling functions
"""

from discord.ext import tasks
from news_bot import check_rss_feeds
from database import cleanup_old_news

# RSS Feed Checker
@tasks.loop(minutes=30)
async def check_rss_feeds_task():
    """فحص RSS Feeds + Free APIs كل 30 دقيقة"""
    await check_rss_feeds()

@check_rss_feeds_task.before_loop
async def before_check_rss():
    from discord_bot import bot
    await bot.wait_until_ready()

# Auto-cleanup old news
@tasks.loop(hours=1)
async def cleanup_old_news_task():
    """حذف الأخبار الأقدم من 24 ساعة كل ساعة"""
    cleanup_old_news()

@cleanup_old_news_task.before_loop
async def before_cleanup():
    from discord_bot import bot
    await bot.wait_until_ready()
