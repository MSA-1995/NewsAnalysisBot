"""
📰 News Analysis Bot - Sentiment Analysis
Sentiment analysis functions
"""

from textblob import TextBlob

# Analyze sentiment
def analyze_sentiment(text):
    """تحليل المشاعر من النص"""
    try:
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