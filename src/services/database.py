import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback for development if .env is missing or empty
    DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/farmland_db"

# Create async engine with connection pool tuning
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL logging
    future=True,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before use (handles stale connections)
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine, 
    expire_on_commit=False,
    class_=AsyncSession
)


async def get_db_session():
    """
    Dependency for FastAPI to provide a database session.
    """
    async with async_session_factory() as session:
        yield session
