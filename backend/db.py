# backend/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Build DB URL from env (matches docker-compose and .env.example)
_host = os.getenv("POSTGRES_HOST", "postgres")
_port = os.getenv("POSTGRES_PORT", "5432")
_db = os.getenv("POSTGRES_DB", "hikebot")
_user = os.getenv("POSTGRES_USER", "hikebot")
_pwd = os.getenv("POSTGRES_PASSWORD", "hikebot")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{_user}:{_pwd}@{_host}:{_port}/{_db}",
)

# 2. 创建引擎
engine = create_engine(DATABASE_URL)

# 3. 创建 Session 工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 创建基类
Base = declarative_base()

# 5. 依赖注入
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
