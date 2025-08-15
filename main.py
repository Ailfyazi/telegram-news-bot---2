import aiohttp
import feedparser
import telegram
import hashlib
import os
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Dict, List

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    source: str
    published: datetime
    hash_id: str
    category: str = "ورزشی"

class Config:
    """تنظیمات ربات خبری"""
    NEW_BOT_TOKEN = os.getenv("NEW_BOT_TOKEN")  # کلید ربات جدید از متغیر محیطی
    NEW_CHANNEL_ID = os.getenv("NEW_CHANNEL_ID")  # آیدی کانال جدید از متغیر محیطی
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "feef020ff55047f9b7e757acd2fdfb87")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")

    NEWS_SOURCES = {
        "BBC فارسی": {
            "url": "https://feeds.bbci.co.uk/persian/rss.xml",
            "enabled": True,
            "category_weight": 1.0
        },
        "ایران اینترنشنال": {
            "url": "https://www.iranintl.com/fa/rss",
            "enabled": True,
            "category_weight": 1.0
        },
        "VOA فارسی": {
            "url": "https://ir.voanews.com/rss",
            "enabled": True,
            "category_weight": 0.8
        },
        "رادیو فردا": {
            "url": "https://www.radiofarda.com/rss",
            "enabled": True,
            "category_weight": 0.8
        },
        "DW فارسی": {
            "url": "https://rss.dw.com/rdf/rss-fa-all",
            "enabled": True,
            "category_weight": 0.9
        },
        "یورونیوز فارسی": {
            "url": "https://parsi.euronews.com/rss",
            "enabled": True,
            "category_weight": 0.7
        },
        "خبرگزاری ایسنا": {
            "url": "https://www.isna.ir/rss",
            "enabled": True,
            "category_weight": 0.6
        }
    }

    NEWS_CATEGORIES = {
        "ورزشی": {
            "keywords": ["فوتبال", "ورزش", "تیم", "بازیکن", "مسابقه", "جام", "المپیک"],
            "emoji": "⚽",
            "priority": 0.6
        }
    }

    MESSAGE_TEMPLATE = """
{emoji} **{title}**

📝 {summary}

🔗 [مطالعه بیشتر]({url})

📡 منبع: {source}
📅 {timestamp}
🏷️ #ورزشی

➖➖➖➖➖➖➖➖➖➖
    """

    BLOCKED_KEYWORDS = ["تبلیغات", "آگهی", "فروش"]
    MIN_TITLE_LENGTH = 10
    MAX_SUMMARY_LENGTH = 300
    MAX_TITLE_LENGTH = 100
    REQUEST_TIMEOUT = 30
    MAX_RETRIES = 3
    MAX_NEWS_PER_POST = 3
    DELAY_BETWEEN_POSTS = 10

    @classmethod
    def get_enabled_sources(cls) -> Dict[str, str]:
        return {
            name: source["url"]
            for name, source in cls.NEWS_SOURCES.items()
            if source["enabled"]
        }

class NewsBot:
    def __init__(self):
        # بررسی وجود توکن و آیدی کانال
        if not Config.NEW_BOT_TOKEN:
            raise ValueError("کلید ربات (NEW_BOT_TOKEN) در متغیرهای محیطی تنظیم نشده است!")
        if not Config.NEW_CHANNEL_ID:
            raise ValueError("آیدی کانال (NEW_CHANNEL_ID) در متغیرهای محیطی تنظیم نشده است!")
        self.bot = telegram.Bot(token=Config.NEW_BOT_TOKEN)
        self.posted_news = set()
        self.session = None

    async def start_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()

    async def fetch_rss_news(self, source: str, url: str) -> List[NewsItem]:
        try:
            async with self.session.get(url, timeout=Config.REQUEST_TIMEOUT) as response:
                content = await response.text()
                feed = feedparser.parse(content)
                news_items = []
                for entry in feed.entries[:5]:
                    title = self._clean_html(entry.get('title', ''))
                    if len(title) < Config.MIN_TITLE_LENGTH:
                        continue
                    summary = self._clean_html(entry.get('summary', ''))[:Config.MAX_SUMMARY_LENGTH]
                    if any(keyword in title.lower() or keyword in summary.lower() for keyword in Config.BLOCKED_KEYWORDS):
                        continue
                    hash_id = hashlib.md5(f"{title}{url}".encode()).hexdigest()
                    if hash_id not in self.posted_news and self._categorize_news(title + " " + summary) == "ورزشی":
                        news_item = NewsItem(
                            title=title[:Config.MAX_TITLE_LENGTH],
                            summary=summary,
                            url=entry.get('link', ''),
                            source=source,
                            published=datetime.now(),
                            hash_id=hash_id,
                            category="ورزشی"
                        )
                        news_items.append(news_item)
                return news_items
        except Exception as e:
            logger.error(f"خطا در دریافت اخبار از {source}: {e}")
            return []

    async def fetch_newsapi_news(self) -> List[NewsItem]:
        try:
            url = f'https://newsapi.org/v2/top-headlines?category=sports&apiKey={Config.NEWS_API_KEY}'
            async with self.session.get(url) as response:
                response.raise_for_status()
                articles = (await response.json()).get('articles', [])
                news_items = []
                for article in articles[:5]:
                    title = self._clean_html(article['title'])
                    if len(title) < Config.MIN_TITLE_LENGTH:
                        continue
                    summary = self._clean_html(article.get('description', ''))[:Config.MAX_SUMMARY_LENGTH]
                    if any(keyword in title.lower() or keyword in summary.lower() for keyword in Config.BLOCKED_KEYWORDS):
                        continue
                    hash_id = hashlib.md5(f"{title}{article['url']}".encode()).hexdigest()
                    if hash_id not in self.posted_news:
                        news_item = NewsItem(
                            title=title[:Config.MAX_TITLE_LENGTH],
                            summary=summary,
                            url=article['url'],
                            source="NewsAPI",
                            published=datetime.now(),
                            hash_id=hash_id,
                            category="ورزشی"
                        )
                        news_items.append(news_item)
                return news_items
        except Exception as e:
            logger.error(f"Error fetching NewsAPI news: {e}")
            return []

    def _clean_html(self, text: str) -> str:
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text().strip()

    def _categorize_news(self, text: str) -> str:
        for keyword in Config.NEWS_CATEGORIES["ورزشی"]["keywords"]:
            if keyword in text:
                return "ورزشی"
        return "عمومی"

    async def summarize_news(self, text: str) -> str:
        try:
            url = 'https://openrouter.ai/api/v1/chat/completions'
            headers = {
                'Authorization': f'Bearer {Config.OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
            }
            data = {
                'model': 'anthropic/claude-3.5-sonnet',
                'messages': [
                    {'role': 'user', 'content': f'Summarize this news in 2-3 sentences in Persian:\n{text}'}
                ],
                'max_tokens': 200
            }
            async with self.session.post(url, headers=headers, json=data) as response:
                response.raise_for_status()
                summary = (await response.json())['choices'][0]['message']['content']
                return summary
        except Exception as e:
            logger.error(f"Error summarizing news: {e}")
            return text

    def _format_news_message(self, news: NewsItem) -> str:
        return Config.MESSAGE_TEMPLATE.format(
            emoji=Config.NEWS_CATEGORIES["ورزشی"]["emoji"],
            title=news.title,
            summary=news.summary,
            url=news.url,
            source=news.source,
            timestamp=news.published.strftime('%H:%M - %Y/%m/%d'),
            category="ورزشی"
        )

    async def collect_all_news(self) -> List[NewsItem]:
        await self.start_session()
        all_news = []
        newsapi_items = await self.fetch_newsapi_news()
        all_news.extend(newsapi_items)
        for source, url in Config.get_enabled_sources().items():
            rss_items = await self.fetch_rss_news(source, url)
            all_news.extend(rss_items)
        all_news.sort(key=lambda x: x.published, reverse=True)
        return all_news[:Config.MAX_NEWS_PER_POST]

    async def post_news_to_channel(self, news_items: List[NewsItem]):
        for news in news_items:
            try:
                text = f"{news.title}\n{news.summary}"
                summarized_text = await self.summarize_news(text)
                message = self._format_news_message(NewsItem(
                    title=news.title,
                    summary=summarized_text,
                    url=news.url,
                    source=news.source,
                    published=news.published,
                    hash_id=news.hash_id,
                    category="ورزشی"
                ))
                await self.bot.send_message(
                    chat_id=Config.NEW_CHANNEL_ID,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
                self.posted_news.add(news.hash_id)
                logger.info(f"خبر ارسال شد: {news.title[:50]}...")
                await asyncio.sleep(Config.DELAY_BETWEEN_POSTS)
            except Exception as e:
                logger.error(f"خطا در ارسال خبر: {e}")

async def main(context):
    try:
        bot = NewsBot()
        news_items = await bot.collect_all_news()
        if not news_items:
            return context.res.json({'status': 'error', 'message': 'No news fetched'})
        await bot.post_news_to_channel(news_items)
        await bot.close_session()
        return context.res.json({'status': 'success', 'message': f'Sent {len(news_items)} news to channel'})
    except Exception as e:
        logger.error(f"Error in main: {e}")
        return context.res.json({'status': 'error', 'message': str(e)})
