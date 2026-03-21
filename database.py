"""
📰 News Analysis Bot - Database Manager
Database connection and operations
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from config import DATABASE_URL, CRITICAL_WEBHOOK
import requests

# Database Connection Pool
_db_conn = None
_db_params = None

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
        
        if _db_conn and not _db_conn.closed:
            try:
                cursor = _db_conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                return _db_conn
            except:
                try:
                    _db_conn.close()
                except:
                    pass
                _db_conn = None
        
        _db_conn = psycopg2.connect(**_db_params)
        return _db_conn
        
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        send_critical_alert("Database Connection", "Failed to connect to database", str(e))
        return None

def create_table():
    """إنشاء جداول الأخبار و Heartbeat"""
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
            
            # جدول الأخبار
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
            
            # ========== جدول Heartbeat للبوت الرئيسي ==========
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_heartbeat (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    last_beat TIMESTAMP DEFAULT NOW(),
                    status VARCHAR(20) DEFAULT 'ONLINE',
                    status_message_id VARCHAR(50) DEFAULT NULL
                )
            """)
            
            # إضافة العمود لو ما كان موجود (للجداول القديمة)
            cursor.execute("""
                ALTER TABLE bot_heartbeat 
                ADD COLUMN IF NOT EXISTS status_message_id VARCHAR(50) DEFAULT NULL
            """)
            
            # إدخال صف واحد ثابت إذا ما كان موجود
            cursor.execute("""
                INSERT INTO bot_heartbeat (id, last_beat, status)
                VALUES (1, NOW(), 'ONLINE')
                ON CONFLICT (id) DO NOTHING
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            print("✅ news_sentiment table ready")
            print("✅ bot_heartbeat table ready")
            return
        except Exception as e:
            print(f"❌ Table creation error (attempt {attempt+1}/3): {e}")
            if attempt == 2:
                send_critical_alert("Database Table Error", "Failed to create tables", str(e))
            try:
                if conn:
                    conn.close()
            except:
                pass
            
            if attempt < 2:
                import time
                time.sleep(2)

# ========== Heartbeat Functions ==========

def get_trading_bot_status():
    """قراءة حالة البوت من الداتابيز"""
    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=unquote(parsed.password),
            sslmode='prefer',
            connect_timeout=10
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT last_beat, status, status_message_id,
                   EXTRACT(EPOCH FROM (NOW() - last_beat)) as seconds_since
            FROM bot_heartbeat WHERE id = 1
        """)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception as e:
        print(f"⚠️ Heartbeat read error: {e}")
        return None

def save_status_message_id(message_id):
    """حفظ message ID الرسالة الثابتة في الداتابيز"""
    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=unquote(parsed.password),
            sslmode='prefer',
            connect_timeout=10
        )
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bot_heartbeat SET status_message_id = %s WHERE id = 1
        """, (str(message_id) if message_id else None,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Save message ID error: {e}")

def get_trainer_status():
    """قراءة حالة سكريبت التدريب من الداتابيز"""
    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=unquote(parsed.password),
            sslmode='prefer',
            connect_timeout=10
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT last_beat, status, status_message_id,
                   EXTRACT(EPOCH FROM (NOW() - last_beat)) as seconds_since
            FROM trainer_heartbeat WHERE id = 1
        """)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception as e:
        print(f"⚠️ Trainer status read error: {e}")
        return None

def save_trainer_message_id(message_id):
    """حفظ message ID رسالة التدريب"""
    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=unquote(parsed.password),
            sslmode='prefer',
            connect_timeout=10
        )
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE trainer_heartbeat SET status_message_id = %s WHERE id = 1
        """, (str(message_id) if message_id else None,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Save trainer message ID error: {e}")

# ========== باقي الدوال ==========

def save_news(symbol, sentiment, score, headline, source, channel_id, retry=3):
    """حفظ الخبر في قاعدة البيانات مع إعادة محاولة"""
    global _db_conn
    
    for attempt in range(retry):
        conn = None
        try:
            from urllib.parse import urlparse, unquote
            parsed = urlparse(DATABASE_URL)
            
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                database=parsed.path[1:],
                user=parsed.username,
                password=unquote(parsed.password),
                sslmode='prefer',
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
                time.sleep(3)
            else:
                return False
    
    return False

def cleanup_old_news():
    """حذف الأخبار الأقدم من 24 ساعة"""
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
