import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI
from src.config import Settings
from src.db.session import init_engine, get_engine
from src.db.models import Base
from src.bot.routes import router as bot_router


async def _migrate(conn) -> None:
    from sqlalchemy import text, inspect

    def do_migrate(sync_conn):
        insp = inspect(sync_conn)
        cols = [c["name"] for c in insp.get_columns("questions")]
        if "pretext" not in cols:
            sync_conn.execute(text("ALTER TABLE questions ADD COLUMN pretext TEXT"))
    await conn.run_sync(do_migrate)


async def init_db(settings: Settings) -> None:
    init_engine(settings.database_url)
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate(conn)


async def run_long_polling(settings: Settings) -> None:
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(bot_router)
    print("Starting bot with long polling...")
    await dp.start_polling(bot)


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI()

    @app.on_event("startup")
    async def on_startup():
        await init_db(settings)
        # Webhook wiring can be added here

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    return app


if __name__ == "__main__":
    s = Settings.load()
    asyncio.run(init_db(s))
    asyncio.run(run_long_polling(s))
