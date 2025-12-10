# backend/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. 数据库 URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/hikebot")

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