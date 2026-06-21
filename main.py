import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from handlers import router
import database as db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def handle(request):
    return web.Response(text="DiotrexVPN Bot is running")


async def run_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    logger.info("Web server on port 10000")


async def main():
    await db.init_db()
    logger.info("DB connected")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    channels = await db.get_channels_to_check()
    for channel in channels:
        try:
            chat = await bot.get_chat(chat_id=channel)
            logger.info(f"Channel {channel} OK (ID: {chat.id})")
        except Exception as e:
            logger.error(f"Channel {channel} error: {e}")

    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(run_web_server())

    logger.info("DiotrexVPN Bot started!")
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"Connection error: {e}. Restart in 5s...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
