from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os

app = FastAPI()

# Настройка CORS для Vue.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{os.getenv('FRONTEND_PORT', '5173')}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Параметры подключения к PostgreSQL из .env
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "alphadb")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "06087083")
DB_PORT = os.getenv("DB_PORT", "5432")

# Строка подключения для asyncpg
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Создаём асинхронный движок SQLAlchemy
engine = create_async_engine(DATABASE_URL, echo=True)  # echo=True для отладки

# Создаём фабрику сессий
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

@app.get("/")
async def read_root():
    return {"message": "Hello from FastAPI in Docker!"}

@app.get("/test-db")
async def test_db():
    try:
        async with async_session() as session:
            # Выполняем тестовый запрос
            result = await session.execute(text("SELECT 1 AS test"))
            row = result.fetchone()
        return {"db_status": "Connected", "result": row[0] if row else None}
    except Exception as e:
        return {"db_status": "Error", "error": str(e)}

# Очистка при завершении работы
@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()