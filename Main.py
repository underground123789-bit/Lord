import os
import re
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from playwright.async_api import async_playwright

TOKEN = os.environ.get("TELEGRAM_TOKEN")

async def capture_screenshot(url: str, output_path: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path=output_path)
        await browser.close()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text or ""
    url_match = re.search(r'https?://[^\s]+tradingview\.com[^\s]+', message_text)
    
    if url_match:
        chart_url = url_match.group(0)
        status_msg = await update.message.reply_text("⏳ جاري سحب صورة التشارت...")
        image_path = "chart.png"
        try:
            await capture_screenshot(chart_url, image_path)
            with open(image_path, "rb") as photo:
                await update.message.reply_photo(photo=photo, caption="📊 تشارت التنبيه المباشر")
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ حدث خطأ أثناء التقاط الصورة: {str(e)}")
        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

def main():
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN environment variable is not set!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
