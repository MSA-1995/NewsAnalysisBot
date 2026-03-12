# 📰 News Analysis Bot

بوت تحليل الأخبار للعملات الرقمية

## 🎯 الوظائف:

### ✅ تحليل تلقائي:
- يراقب جميع الرسائل في السيرفر
- يكتشف أسماء العملات (BTC, ETH, إلخ)
- يحلل Sentiment (إيجابي/سلبي/محايد)
- يحفظ في Database

### ✅ إشعارات تلقائية:
- يرسل في روم `#news-analysis-bot`
- Embed ملون حسب Sentiment
- يعرض العملة والتحليل

### ✅ أوامر:
- `!news_stats` - إحصائيات آخر 24 ساعة
- `!coin_sentiment BTC` - أخبار عملة معينة

---

## 🔧 الإعداد:

### Environment Variables:
```
DISCORD_TOKEN = your_bot_token
DATABASE_URL = postgresql://...
```

### الروم المطلوب:
- اسوي روم اسمه: `news-analysis-bot`
- البوت يرسل فيه تلقائياً

---

## 📊 كيف يشتغل:

1. أي شخص يكتب رسالة فيها اسم عملة
2. البوت يحلل المشاعر
3. يحفظ في Database
4. يرسل إشعار في `#news-analysis-bot`
5. Trading Bot يقرأ من Database

---

## 🔗 الربط مع Trading Bot:

```python
# Trading Bot يقرأ من نفس Database
news = storage.get_recent_news('BTC/USDT', hours=24)
if news:
    avg_sentiment = sum(n['score'] for n in news) / len(news)
    if avg_sentiment > 0.5:
        confidence += 10  # أخبار إيجابية
```

---

## 🚀 التشغيل:

### محلياً:
```bash
pip install -r requirements.txt
python news_bot.py
```

### على Koyeb:
1. ارفع على GitHub
2. اربطه بـ Koyeb
3. أضف Environment Variables
4. Deploy!

---

© 2026 MSA - News Analysis System
