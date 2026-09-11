import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback for development if .env is missing or empty
    DATABASE_URL = "postgresql+asyncpg://user:password@127.0.0.1:5434/farmland_db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL logging
    future=True,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before use (handles stale connections)
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session():
    """
    Dependency for FastAPI to provide a database session.
    """
    async with async_session_factory() as session:
        yield session
