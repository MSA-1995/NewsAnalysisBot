"""
📰 News Analysis Bot - Database Manager
Database connection and operations
"""

import os
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from src.config.config import DATABASE_URL, CRITICAL_WEBHOOK
import requests

# No more global connection pool

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

def get_db_connection():
    """Always create a new database connection."""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
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

# Save news to database
def save_news(symbol, sentiment, score, headline, source, channel_id, retry=3):
    """حفظ الخبر في قاعدة البيانات مع إعادة محاولة"""
    for attempt in range(retry):
        conn = None
        try:
            conn = get_db_connection() # Use the simplified connection function
            if not conn:
                raise Exception("Failed to get DB connection")

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
                time.sleep(3)
            else:
                return False

async def async_save_news(symbol, sentiment, score, headline, source, channel_id, retry=3):
    """Asynchronously save news to the database."""
    loop = asyncio.get_running_loop()
    try:
        # Run the synchronous save_news function in an executor
        await loop.run_in_executor(
            None, 
            save_news, 
            symbol, sentiment, score, headline, source, channel_id, retry
        )
        return True
    except Exception as e:
        print(f"❌ Async save news error: {e}")
        return False
    
    return False

# Auto-cleanup old news
def cleanup_old_news():
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

async def async_cleanup_old_news():
    """Asynchronously run the cleanup task."""
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, cleanup_old_news)
    except Exception as e:
        print(f"❌ Async cleanup error: {e}")

# Get news stats
def get_news_stats():
    """Get news statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
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
        
        return stats
    except Exception as e:
        print(f"⚠️ Stats error: {e}")
        return None

# Get coin sentiment
def get_coin_sentiment(symbol):
    """Get sentiment for specific coin"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
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
        
        return news
    except Exception as e:
        print(f"⚠️ Coin sentiment error: {e}")
        return None