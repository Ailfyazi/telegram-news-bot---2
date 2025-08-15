#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ربات خبری تلگرام برای GitHub Actions
ورژن ساده شده برای اجرای روی سرویس‌های CI/CD
"""

import asyncio
import os
import logging
import aiohttp
import feedparser
from datetime import datetime
import hashlib
from bs4 import BeautifulSoup
import re
from telegram import Bot
from dataclasses import dataclass
from typing import List, Optional

# تنظیم لاگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    source: str
    category: str = "عمومی"

class SimpleNewsBot:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.channel_id = os.getenv('CHANNEL_ID')
        self.max_news = int(os.getenv('MAX_NEWS_PER_POST', '3'))
        
        if not self.bot_token or not self.channel_id:
            raise ValueError("BOT_TOKEN و CHANNEL_ID باید تنظیم شوند")
        
        self.bot = Bot(token=self.bot_token)
        self.news_sources = {
            "BBC فارسی": "https://feeds.bbci.co.uk/persian/rss.xml",
            "DW فارسی": "https://rss.dw.com/rdf/rss-fa-all",
            "یورونیوز فارسی": "https://parsi.euronews.com/rss"
        }
        
        self.categories = {
            "سیاسی": {
                "keywords": ["سیاست", "انتخابات", "دولت", "پارلمان", "رئیس‌جمهور"],
                "emoji": "🏛️"
            },
            "اقتصادی": {
                "keywords": ["اقتصاد", "بورس", "ارز", "تورم", "تجارت", "بانک"],
                "emoji": "💰"
            },
            "بین‌المللی": {
                "keywords": ["آمریکا", "اروپا", "جهان", "بین‌المللی", "کشور"],
                "emoji": "🌍"
            },
            "ورزشی": {
                "keywords": ["فوتبال", "ورزش", "تیم", "بازیکن", "مسابقه"],
                "emoji": "⚽"
            }
        }
    
    def clean_html(self, text: str) -> str:
        """تمیز کردن متن از HTML"""
        if not text:
            return ""
        
        soup = BeautifulSoup(text, 'html.parser')
        text = soup.get_text()
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def categorize_news(self, text: str) -> str:
        """دسته‌بندی خبر"""
        text_lower = text.lower()
        
        for category, config in self.categories.items():
            for keyword in config['keywords']:
                if keyword.lower() in text_lower:
                    return category
        
        return "عمومی"
    
    async def fetch_news_from_source(self, source: str, url: str, session: aiohttp.ClientSession) -> List[NewsItem]:
        """دریافت اخبار از یک منبع"""
        try:
            logger.info(f"دریافت اخبار از {source}...")
            
            async with session.get(url, timeout=30) as response:
                if response.status != 200:
                    logger.warning(f"خطا در {source}: {response.status}")
                    return []
                
                content = await response.text()
                feed = feedparser.parse(content)
                
                news_items = []
                for entry in feed.entries[:5]:
                    title = self.clean_html(entry.get('title', '')).strip()
                    summary = self.clean_html(entry.get('summary', '')).strip()
                    
                    if len(title) < 10:
                        continue
                    
                    # محدود کردن طول
                    title = title[:100]
                    summary = summary[:200]
                    
                    category = self.categorize_news(title + " " + summary)
                    
                    news_item = NewsItem(
                        title=title,
                        summary=summary,
                        url=entry.get('link', ''),
                        source=source,
                        category=category
                    )
                    
                    news_items.append(news_item)
                
                logger.info(f"{len(news_items)} خبر از {source} دریافت شد")
                return news_items
                
        except Exception as e:
            logger.error(f"خطا در دریافت از {source}: {e}")
            return []
    
    async def collect_all_news(self) -> List[NewsItem]:
        """جمع‌آوری اخبار از تمام منابع"""
        all_news = []
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for source, url in self.news_sources.items():
                task = self.fetch_news_from_source(source, url, session)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)
        
        # مرتب‌سازی و انتخاب بهترین اخبار
        all_news = all_news[:self.max_news]
        
        return all_news
    
    def format_message(self, news: NewsItem) -> str:
        """فرمت کردن پیام خبری"""
        category_config = self.categories.get(news.category, {"emoji": "📰"})
        emoji = category_config["emoji"]
        
        timestamp = datetime.now().strftime('%H:%M - %Y/%m/%d')
        
        message = f"""
{emoji} **{news.title}**

📝 {news.summary}

🔗 [مطالعه بیشتر]({news.url})

📡 منبع: {news.source}
📅 {timestamp}
🏷️ #{news.category.replace(' ', '_')}

➖➖➖➖➖➖➖➖➖➖
        """.strip()
        
        return message
    
    async def send_news_to_channel(self, news_items: List[NewsItem]):
        """ارسال اخبار به کانال"""
        if not news_items:
            logger.info("خبری برای ارسال وجود ندارد")
            return
        
        for news in news_items:
            try:
                message = self.format_message(news)
                
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
                
                logger.info(f"✅ خبر ارسال شد: {news.title[:50]}...")
                await asyncio.sleep(5)  # تاخیر بین پست‌ها
                
            except Exception as e:
                logger.error(f"❌ خطا در ارسال خبر: {e}")
    
    async def run_once(self):
        """اجرای یک‌باره ربات"""
        try:
            logger.info("🚀 شروع جمع‌آوری اخبار...")
            
            # جمع‌آوری اخبار
            news_items = await self.collect_all_news()
            
            if news_items:
                # ارسال اخبار
                await self.send_news_to_channel(news_items)
                logger.info(f"✅ {len(news_items)} خبر ارسال شد")
            else:
                logger.info("ℹ️  خبر جدیدی یافت نشد")
            
        except Exception as e:
            logger.error(f"❌ خطا در اجرای ربات: {e}")
            raise

async def main():
    """تابع اصلی"""
    try:
        bot = SimpleNewsBot()
        await bot.run_once()
        
    except Exception as e:
        logger.error(f"خطای کلی: {e}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
