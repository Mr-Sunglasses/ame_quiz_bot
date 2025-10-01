import os
from pydantic import BaseModel


class Settings(BaseModel):
    bot_token: str
    bot_username: str
    database_url: str = "sqlite+aiosqlite:///./data.db"
    webhook_url: str | None = None
    port: int = 8080
    rate_limit_create_per_hour: int = 10
    admins: list[int] = []

    @classmethod
    def load(cls) -> "Settings":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("BOT_TOKEN is required")
        username = os.getenv("BOT_USERNAME", "").strip()
        if not username:
            raise RuntimeError("BOT_USERNAME is required")
        admins_raw = os.getenv("ADMINS", "").strip()
        admins: list[int] = []
        if admins_raw:
            for part in admins_raw.replace(";", ",").split(","):
                part = part.strip()
                if part:
                    try:
                        admins.append(int(part))
                    except ValueError:
                        continue
        return cls(
            bot_token=token,
            bot_username=username,
            database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data.db"),
            webhook_url=os.getenv("WEBHOOK_URL") or None,
            port=int(os.getenv("PORT", "8080")),
            rate_limit_create_per_hour=int(os.getenv("RATE_LIMIT_CREATE_PER_HOUR", "10")),
            admins=admins,
        )
