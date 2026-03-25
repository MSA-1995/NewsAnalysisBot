"""
📰 News Analysis Bot - News Fetcher
Fetch news from RSS feeds and free APIs
"""

import feedparser
import aiohttp
import asyncio
from datetime import datetime
from config import RSS_FEEDS, CRYPTOPANIC_KEY, REDDIT_CLIENT_ID, REDDIT_SECRET, SYMBOLS

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

async def get_coingecko_news(symbol):
    """جلب معلومات من CoinGecko بشكل غير متزامن"""
    try:
        coin = symbol.split('/')[0].lower()
        coin_map = {
            'btc': 'bitcoin', 'eth': 'ethereum', 'bnb': 'binancecoin',
            'sol': 'solana', 'ada': 'cardano', 'matic': 'matic-network',
            'avax': 'avalanche-2', 'link': 'chainlink'
        }
        coin_id = coin_map.get(coin, coin)
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    print(f"⚠️ CoinGecko API error: {response.status}")
                    return []
                data = await response.json()
                market = data.get('market_data', {})
                price_change = market.get('price_change_percentage_24h') # No default

                # Handle None case for price_change
                if price_change is not None:
                    sentiment = 'POSITIVE' if price_change > 2 else 'NEGATIVE' if price_change < -2 else 'NEUTRAL'
                    return [{
                        'title': f"{coin.upper()} Market: {price_change:.2f}% (24h)",
                        'url': data.get('links', {}).get('homepage', [''])[0],
                        'sentiment': sentiment,
                        'source': 'CoinGecko'
                    }]
                else:
                    # Return neutral if no price data is available
                    return [{
                        'title': f"{coin.upper()} Market data not available",
                        'url': data.get('links', {}).get('homepage', [''])[0],
                        'sentiment': 'NEUTRAL',
                        'source': 'CoinGecko'
                    }]
    except Exception as e:
        print(f"⚠️ CoinGecko error: {e}")
