# backend/init_db.py
import logging
from pg_db import get_cursor

logger = logging.getLogger("uvicorn")

def init_tables():
    logger.info("Checking database tables...")
    
    # 1. Users
    create_users = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        user_code VARCHAR(20) UNIQUE NOT NULL,
        password_hash VARCHAR(128) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    # 2. Friend Requests
    create_friend_requests = """
    CREATE TABLE IF NOT EXISTS friend_requests (
        id SERIAL PRIMARY KEY,
        from_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        to_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        status VARCHAR(20) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(from_user_id, to_user_id)
    );
    """

    # 3. Friendships
    create_friendships = """
    CREATE TABLE IF NOT EXISTS friendships (
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        friend_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, friend_id)
    );
    """

    # 4. Groups (包含 created_by)
    create_groups = """
    CREATE TABLE IF NOT EXISTS groups (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(100) NOT NULL,
        description TEXT,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    # 5. Group Members
    create_group_members = """
    CREATE TABLE IF NOT EXISTS group_members (
        group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        role VARCHAR(20) DEFAULT 'member', 
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (group_id, user_id)
    );
    """

    # 6. Group Messages
    create_group_messages = """
    CREATE TABLE IF NOT EXISTS group_messages (
        id SERIAL PRIMARY KEY,
        group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        sender_display VARCHAR(50),
        role VARCHAR(20) DEFAULT 'user',
        content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    with get_cursor() as cur:
        cur.execute(create_users)
        cur.execute(create_friend_requests)
        cur.execute(create_friendships)
        cur.execute(create_groups)
        cur.execute(create_group_members)
        cur.execute(create_group_messages)
    
    logger.info("Database tables initialized successfully.")