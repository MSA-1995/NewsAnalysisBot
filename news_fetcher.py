"""
📰 News Analysis Bot - News Fetcher
Fetch news from RSS feeds and free APIs
"""

import feedparser
import requests
import asyncio
from datetime import datetime
from config import RSS_FEEDS, CRYPTOPANIC_KEY, REDDIT_CLIENT_ID, REDDIT_SECRET, SYMBOLS

# Track processed news
processed_news = set()

# Reddit Token
reddit_token = None

def get_reddit_token():
    """الحصول على Reddit Access Token"""
    global reddit_token
    if not REDDIT_CLIENT_ID or not REDDIT_SECRET:
        return None
    try:
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
        headers = {
            'Authorization': f'bearer {reddit_token}',
            'User-Agent': 'NewsBot/1.0'
        }
        coin = symbol.split('/')[0].lower()
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

# RSS Feed Checker
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
                        from database import save_news
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
                            from discord_bot import send_news_to_channels
                            await send_news_to_channels(symbol, title, sentiment, score, feed.feed.get('title', 'RSS'), entry.get('link', ''))
            
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
                from database import save_news
                saved = save_news(symbol, sentiment, score, news_item['title'], news_item['source'], 0)
                if saved:
                    print(f"📰 CryptoPanic: {symbol} | {sentiment}")
                    from discord_bot import send_news_to_channels
                    await send_news_to_channels(symbol, news_item['title'], sentiment, score, news_item['source'], news_item['url'])
            
            await asyncio.sleep(2)
            
            # Reddit
            reddit_news = get_reddit_news(symbol)
            for news_item in reddit_news:
                sentiment, score = analyze_sentiment(news_item['title'])
                from database import save_news
                saved = save_news(symbol, sentiment, score, news_item['title'], news_item['source'], 0)
                if saved:
                    print(f"📰 Reddit: {symbol} | {sentiment}")
                    from discord_bot import send_news_to_channels
                    await send_news_to_channels(symbol, news_item['title'], sentiment, score, news_item['source'], news_item['url'])
            
            await asyncio.sleep(2)
            
            # CoinGecko
            cg_news = get_coingecko_news(symbol)
            for news_item in cg_news:
                sentiment, score = analyze_sentiment(news_item['title'])
                from database import save_news
                saved = save_news(symbol, sentiment, score, news_item['title'], news_item['source'], 0)
                if saved:
                    print(f"📰 CoinGecko: {symbol} | {sentiment}")
                    from discord_bot import send_news_to_channels
                    await send_news_to_channels(symbol, news_item['title'], sentiment, score, news_item['source'], news_item['url'])
            
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"⚠️ Free API error for {symbol}: {e}")
    
    # تنظيف processed_news (الاحتفاظ بآخر 1000)
    if len(processed_news) > 1000:
        processed_news.clear()
    
    print("✅ RSS + Free APIs check completed")

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
        from textblob import TextBlob
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
