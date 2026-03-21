"""
🏥 Health Check Monitor for NewsAnalysisBot
يتحقق من حالة البوتات الأخرى باستخدام health check endpoints بدلاً من قاعدة البيانات
"""

import asyncio
import aiohttp
import time
from datetime import datetime
from config_encrypted import get_critical_webhook
from config import HEALTH_CHECK_CONFIG
import requests

CRITICAL_WEBHOOK = get_critical_webhook()

# إعدادات الـ Health Check من الكونفيج
HEALTH_CHECK_TIMEOUT = HEALTH_CHECK_CONFIG['timeout']
RETRY_ATTEMPTS = HEALTH_CHECK_CONFIG['retry_attempts']
RETRY_DELAY = HEALTH_CHECK_CONFIG['retry_delay']

# URLs للبوتات من الكونفيج
TRADING_BOT_URL = HEALTH_CHECK_CONFIG['trading_bot_url']
TRAINER_BOT_URL = HEALTH_CHECK_CONFIG['trainer_bot_url']

class HealthMonitor:
    def __init__(self):
        self.trading_status = "unknown"
        self.trainer_status = "unknown"
        self.last_check = None
        
    async def check_health_endpoint(self, session, url, bot_name):
        """التحقق من endpoint مع retry mechanism"""
        for attempt in range(RETRY_ATTEMPTS):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=HEALTH_CHECK_TIMEOUT)) as response:
                    if response.status == 200:
                        data = await response.json()
                        # التحقق من timestamp (أقل من دقيقة)
                        if time.time() - data.get('timestamp', 0) < 60:
                            return "online"
                        else:
                            print(f"⚠️ {bot_name}: Timestamp too old")
                            return "offline"
                    else:
                        print(f"⚠️ {bot_name}: HTTP {response.status}")
                        return "offline"
                        
            except asyncio.TimeoutError:
                print(f"⏰ {bot_name}: Timeout (attempt {attempt + 1})")
                if attempt < RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                return "offline"
                
            except Exception as e:
                print(f"❌ {bot_name}: Error - {e} (attempt {attempt + 1})")
                if attempt < RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                return "offline"
        
        return "offline"
    
    async def check_all_bots(self):
        """التحقق من جميع البوتات"""
        async with aiohttp.ClientSession() as session:
            # التحقق من TradingBot-AI
            self.trading_status = await self.check_health_endpoint(
                session, TRADING_BOT_URL, "TradingBot-AI"
            )
            
            # التحقق من DeepLearningTrainer
            self.trainer_status = await self.check_health_endpoint(
                session, TRAINER_BOT_URL, "DeepLearningTrainer"
            )
            
            self.last_check = datetime.now()
            
            print(f"🏥 Health Check Results:")
            print(f"   TradingBot-AI: {self.trading_status}")
            print(f"   DeepLearningTrainer: {self.trainer_status}")
            
            return {
                'trading': self.trading_status,
                'trainer': self.trainer_status,
                'last_check': self.last_check
            }
    
    def get_trading_status(self):
        """الحصول على حالة TradingBot-AI"""
        return self.trading_status
    
    def get_trainer_status(self):
        """الحصول على حالة DeepLearningTrainer"""
        return self.trainer_status
    
    def is_trading_online(self):
        """هل TradingBot-AI متصل؟"""
        return self.trading_status == "online"
    
    def is_trainer_online(self):
        """هل DeepLearningTrainer متصل؟"""
        return self.trainer_status == "online"

# كائن عالمي للمونيتور
health_monitor = HealthMonitor()

# دوال مساعدة للاستخدام السهل
def check_bots_health():
    """التحقق من البوتات (sync version)"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(health_monitor.check_all_bots())
    finally:
        loop.close()

async def check_bots_health_async():
    """التحقق من البوتات (async version)"""
    return await health_monitor.check_all_bots()

def get_trading_bot_health_status():
    """الحصول على حالة TradingBot-AI للديسكورد"""
    return "ONLINE" if health_monitor.is_trading_online() else "OFFLINE"

def get_trainer_health_status():
    """الحصول على حالة DeepLearningTrainer للديسكورد"""
    return "ONLINE" if health_monitor.is_trainer_online() else "OFFLINE"
