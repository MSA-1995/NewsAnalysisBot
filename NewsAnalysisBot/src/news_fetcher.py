"""
📰 News Analysis Bot - News Fetcher
Fetch news from RSS feeds and free APIs
"""

import feedparser
import aiohttp
import asyncio
from datetime import datetime
from src.config.config import RSS_FEEDS, CRYPTOPANIC_KEY, REDDIT_CLIENT_ID, REDDIT_SECRET, SYMBOLS

# Track processed news
processed_news = set()

# Reddit Token
reddit_token = None

async def get_reddit_token():
    """الحصول على Reddit Access Token بشكل غير متزامن"""
    global reddit_token
    if not REDDIT_CLIENT_ID or not REDDIT_SECRET:
        return None
    try:
        auth = aiohttp.BasicAuth(REDDIT_CLIENT_ID, REDDIT_SECRET)
        data = {'grant_type': 'client_credentials'}
        headers = {'User-Agent': 'NewsBot/1.0'}
        async with aiohttp.ClientSession() as session:
            async with session.post('https://www.reddit.com/api/v1/access_token',
                                    auth=auth, data=data, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    reddit_token = data.get('access_token')
                    return reddit_token
    except Exception as e:
        print(f"⚠️ Reddit token error: {e}")
    return None

async def get_cryptopanic_news(symbol):
    """جلب أخبار من CryptoPanic بشكل غير متزامن"""
    if not CRYPTOPANIC_KEY:
        return []
    try:
        coin = symbol.split('/')[0]
        url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_KEY}&currencies={coin}&filter=hot"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    print(f"⚠️ CryptoPanic API error: {response.status}")
                    return []
                data = await response.json()
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
    except Exception as e:
        print(f"⚠️ CryptoPanic error: {e}")
        return []

async def get_reddit_news(symbol):
    """جلب أخبار من Reddit بشكل غير متزامن"""
    global reddit_token
    if not reddit_token:
        reddit_token = await get_reddit_token()
    if not reddit_token:
        return []
    try:
        headers = {
            'Authorization': f'bearer {reddit_token}',
            'User-Agent': 'NewsBot/1.0'
        }
        coin = symbol.split('/')[0].lower()
        url = f"https://oauth.reddit.com/r/cryptocurrency/search?q={coin}&sort=hot&limit=3&t=day"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                data = None
                if response.status != 200:
                    if response.status == 401:
                        print("Reddit token expired, refreshing...")
                        reddit_token = await get_reddit_token()
                        if reddit_token:
                            headers['Authorization'] = f'bearer {reddit_token}'
                            async with session.get(url, headers=headers, timeout=10) as retry_response:
                                if retry_response.status == 200:
                                    data = await retry_response.json()
                                else:
                                    return []
                        else:
                            return []
                    else:
                        print(f"⚠️ Reddit API error: {response.status}")
                        return []
                else:
                    data = await response.json()
                
                if not data:
                    return []

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
    except Exception as e:
        print(f"⚠️ Reddit news error: {e}")
        return []

# ========================= COINGECKO BATCH CACHE =========================
# طلب واحد لكل العملات بدل 20 طلب منفصل - يمنع 429
_coingecko_cache = {}        # {coin_id: {price_change, timestamp}}
_coingecko_last_fetch = None # وقت آخر طلب batch
_COINGECKO_CACHE_TTL = 900   # 15 دقيقة (CoinGecko مجاني = 30 طلب/دقيقة)

COIN_MAP = {
    'btc': 'bitcoin', 'eth': 'ethereum', 'bnb': 'binancecoin',
    'sol': 'solana', 'ada': 'cardano', 'xrp': 'ripple',
    'doge': 'dogecoin', 'avax': 'avalanche-2', 'link': 'chainlink',
    'dot': 'polkadot', 'bch': 'bitcoin-cash', 'near': 'near',
    'uni': 'uniswap', 'atom': 'cosmos', 'xlm': 'stellar',
    'etc': 'ethereum-classic', 'grt': 'the-graph', 'aave': 'aave',
    'fil': 'filecoin', 'sand': 'the-sandbox', 'algo': 'algorand',
    'trx': 'tron', 'ltc': 'litecoin',
    # 50 عملة - العملات الجديدة
    'sui': 'sui', 'pepe': 'pepe', 'fet': 'fetch-ai', 'wld': 'worldcoin',
    'chz': 'chiliz', 'ena': 'ethena', 'shib': 'shiba-inu', 'bonk': 'bonk',
    'render': 'render-token', 'apt': 'aptos', 'ton': 'the-open-network',
    'arb': 'arbitrum', 'op': 'optimism', 'mana': 'decentraland',
    'axs': 'axie-infinity', 'theta': 'theta-token', 'icp': 'internet-computer',
    'vet': 'vechain', 'floki': 'floki', 'wif': 'dogwifcoin',
    'crv': 'curve-dao-token', 'sushi': 'sushi', '1inch': '1inch',
    'comp': 'compound', 'yfi': 'yearn-finance', 'snx': 'havven',
    'gala': 'gala', 'sui': 'sui',
}

async def _fetch_coingecko_batch():
    """طلب واحد يجلب بيانات كل العملات دفعة واحدة"""
    global _coingecko_cache, _coingecko_last_fetch
    try:
        coin_ids = ','.join(COIN_MAP.values())
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_ids}&vs_currencies=usd&include_24hr_change=true"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as response:
                if response.status == 429:
                    print("⚠️ CoinGecko 429 - سيتم المحاولة في الدورة القادمة")
                    return
                if response.status != 200:
                    print(f"⚠️ CoinGecko batch error: {response.status}")
                    return
                data = await response.json()
                _coingecko_cache = data
                _coingecko_last_fetch = datetime.now()
                print(f"✅ CoinGecko: جلب {len(data)} عملة بطلب واحد")
    except Exception as e:
        print(f"⚠️ CoinGecko batch fetch error: {e}")

async def get_coingecko_news(symbol):
    """جلب معلومات من CoinGecko - من الـ cache (طلب واحد لكل العملات)"""
    global _coingecko_last_fetch
    try:
        # تحديث الـ cache إذا انتهت صلاحيته أو فارغ
        now = datetime.now()
        cache_expired = (
            _coingecko_last_fetch is None or
            (now - _coingecko_last_fetch).total_seconds() > _COINGECKO_CACHE_TTL
        )
        if cache_expired:
            await _fetch_coingecko_batch()

        coin = symbol.split('/')[0].lower()
        coin_id = COIN_MAP.get(coin)

        # العملة مو في القائمة - تجاهل بهدوء
        if not coin_id:
            return []

        coin_data = _coingecko_cache.get(coin_id, {})
        price_change = coin_data.get('usd_24h_change')

        if price_change is not None:
            sentiment = 'POSITIVE' if price_change > 2 else 'NEGATIVE' if price_change < -2 else 'NEUTRAL'
            return [{
                'title': f"{coin.upper()} Market: {price_change:.2f}% (24h)",
                'url': f"https://www.coingecko.com/en/coins/{coin_id}",
                'sentiment': sentiment,
                'source': 'CoinGecko'
            }]
        return []
    except Exception as e:
        print(f"⚠️ CoinGecko error: {e}")
        return []