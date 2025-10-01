from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

_engine: AsyncEngine | None = None
_SessionFactory: sessionmaker | None = None


def init_engine(database_url: str) -> None:
    global _engine, _SessionFactory
    _engine = create_async_engine(database_url, echo=False, future=True)
    _SessionFactory = sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Engine not initialized")
    return _engine


def get_session_factory() -> sessionmaker:
    if _SessionFactory is None:
        raise RuntimeError("Session factory not initialized")
    return _SessionFactory
