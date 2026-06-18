import asyncpg
from config import SUPABASE_URL, SUPABASE_PASSWORD, ITEMS_PER_PAGE
import logging

logger = logging.getLogger(__name__)

# Глобальный пул соединений
pool = None


async def init_db():
    """Создаёт пул соединений и таблицы"""
    global pool
    # Парсим URL Supabase для asyncpg
    # SUPABASE_URL: https://xxx.supabase.co -> host: db.xxx.supabase.co
    url = SUPABASE_URL.replace("https://", "")
    host = f"db.{url}"

    pool = await asyncpg.create_pool(
        host=host,
        port=5432,
        user="postgres",
        password=SUPABASE_PASSWORD,
        database="postgres",
        ssl="require"
    )

    async with pool.acquire() as conn:
        # Создаём таблицы, если их нет
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                vpn_notify BOOLEAN DEFAULT FALSE,
                proxy_notify BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS vpn_keys (
                id SERIAL PRIMARY KEY,
                date TEXT NOT NULL,
                key TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS proxy_list (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS sponsors (
                id SERIAL PRIMARY KEY,
                channel_username TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS blacklist (
                user_id BIGINT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS support_messages (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                replied BOOLEAN DEFAULT FALSE
            );

            CREATE TABLE IF NOT EXISTS ad_messages (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                replied BOOLEAN DEFAULT FALSE
            );

            CREATE TABLE IF NOT EXISTS broadcast_log (
                id SERIAL PRIMARY KEY,
                type TEXT NOT NULL,
                count INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT NOW()
            );
        """)
        logger.info("База данных инициализирована")


async def close_db():
    """Закрывает пул соединений"""
    global pool
    if pool:
        await pool.close()


# ============ ПОЛЬЗОВАТЕЛИ ============

async def add_user(user_id: int, username: str = None):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username) 
            VALUES ($1, $2) 
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, username)


async def get_user(user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)


async def get_all_users():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        return [row['user_id'] for row in rows]


async def get_users_count():
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")


async def set_vpn_notify(user_id: int, value: bool):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET vpn_notify = $1 WHERE user_id = $2", value, user_id)


async def set_proxy_notify(user_id: int, value: bool):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET proxy_notify = $1 WHERE user_id = $2", value, user_id)


async def get_users_with_vpn_notify():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users WHERE vpn_notify = TRUE")
        return [row['user_id'] for row in rows]


async def get_users_with_proxy_notify():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users WHERE proxy_notify = TRUE")
        return [row['user_id'] for row in rows]


# ============ ЧЁРНЫЙ СПИСОК ============

async def add_to_blacklist(user_id: int):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO blacklist (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)


async def remove_from_blacklist(user_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM blacklist WHERE user_id = $1", user_id)


async def is_blacklisted(user_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM blacklist WHERE user_id = $1", user_id)
        return row is not None


async def get_blacklist():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM blacklist")
        return [row['user_id'] for row in rows]


# ============ VPN КЛЮЧИ ============

async def add_vpn_key(date: str, key: str):
    async with pool.acquire() as conn:
        # Оставляем последние 50 ключей (10 страниц)
        count = await conn.fetchval("SELECT COUNT(*) FROM vpn_keys")
        if count >= 50:
            await conn.execute("""
                DELETE FROM vpn_keys WHERE id IN (
                    SELECT id FROM vpn_keys ORDER BY id ASC LIMIT 1
                )
            """)
        await conn.execute("INSERT INTO vpn_keys (date, key) VALUES ($1, $2)", date, key)


async def remove_vpn_key(key_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM vpn_keys WHERE id = $1", key_id)


async def get_vpn_keys_page(page: int = 1):
    """Возвращает ключи для страницы (по 5 штук)"""
    offset = (page - 1) * ITEMS_PER_PAGE
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM vpn_keys ORDER BY id DESC LIMIT $1 OFFSET $2
        """, ITEMS_PER_PAGE, offset)
        total = await conn.fetchval("SELECT COUNT(*) FROM vpn_keys")
        return rows, total


async def get_all_vpn_keys():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM vpn_keys ORDER BY id DESC")
        return rows


# ============ ПРОКСИ ============

async def add_proxy(name: str, url: str):
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM proxy_list")
        if count >= 50:
            await conn.execute("""
                DELETE FROM proxy_list WHERE id IN (
                    SELECT id FROM proxy_list ORDER BY id ASC LIMIT 1
                )
            """)
        await conn.execute("INSERT INTO proxy_list (name, url) VALUES ($1, $2)", name, url)


async def remove_proxy(proxy_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM proxy_list WHERE id = $1", proxy_id)


async def get_proxy_page(page: int = 1):
    """Возвращает прокси для страницы (по 5 штук)"""
    offset = (page - 1) * ITEMS_PER_PAGE
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM proxy_list ORDER BY id DESC LIMIT $1 OFFSET $2
        """, ITEMS_PER_PAGE, offset)
        total = await conn.fetchval("SELECT COUNT(*) FROM proxy_list")
        return rows, total


async def get_all_proxies():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM proxy_list ORDER BY id DESC")
        return rows


# ============ СПОНСОРЫ ============

async def add_sponsor(username: str):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO sponsors (channel_username) VALUES ($1) ON CONFLICT DO NOTHING", username)


async def remove_sponsor(username: str):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM sponsors WHERE channel_username = $1", username)


async def get_sponsors():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT channel_username FROM sponsors")
        return [row['channel_username'] for row in rows]


async def get_channels_to_check():
    from config import YOUR_CHANNEL
    sponsors = await get_sponsors()
    return [YOUR_CHANNEL] + sponsors


# ============ ОБРАЩЕНИЯ ============

async def add_support_message(user_id: int, username: str, message: str, timestamp: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO support_messages (user_id, username, message, timestamp) 
            VALUES ($1, $2, $3, $4)
        """, user_id, username, message, timestamp)


async def get_support_messages():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM support_messages ORDER BY id DESC")


async def mark_support_replied(msg_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE support_messages SET replied = TRUE WHERE id = $1", msg_id)


async def add_ad_message(user_id: int, username: str, message: str, timestamp: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO ad_messages (user_id, username, message, timestamp) 
            VALUES ($1, $2, $3, $4)
        """, user_id, username, message, timestamp)


async def get_ad_messages():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM ad_messages ORDER BY id DESC")


async def mark_ad_replied(msg_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE ad_messages SET replied = TRUE WHERE id = $1", msg_id)


# ============ РАССЫЛКА ============

async def add_broadcast_log(broadcast_type: str, count: int):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO broadcast_log (type, count) VALUES ($1, $2)", broadcast_type, count)


async def get_broadcast_count():
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM broadcast_log")


async def get_stats():
    users = await get_users_count()
    blacklist = len(await get_blacklist())
    vpn_keys = await pool.acquire()
    async with vpn_keys as conn:
        vpn_count = await conn.fetchval("SELECT COUNT(*) FROM vpn_keys")
        proxy_count = await conn.fetchval("SELECT COUNT(*) FROM proxy_list")
        support_count = await conn.fetchval("SELECT COUNT(*) FROM support_messages")
        support_unreplied = await conn.fetchval("SELECT COUNT(*) FROM support_messages WHERE replied = FALSE")
        ad_count = await conn.fetchval("SELECT COUNT(*) FROM ad_messages")
        ad_unreplied = await conn.fetchval("SELECT COUNT(*) FROM ad_messages WHERE replied = FALSE")
        sponsors = await get_sponsors()
        broadcast_count = await get_broadcast_count()

    return {
        "users": users,
        "blacklist": blacklist,
        "vpn_keys": vpn_count,
        "proxy_count": proxy_count,
        "support_count": support_count,
        "support_unreplied": support_unreplied,
        "ad_count": ad_count,
        "ad_unreplied": ad_unreplied,
        "sponsors": sponsors,
        "broadcast_count": broadcast_count
    }