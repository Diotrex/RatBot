import httpx
from config import SUPABASE_URL, SUPABASE_KEY, ITEMS_PER_PAGE
import logging

logger = logging.getLogger(__name__)

BASE_URL = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

async def init_db():
    """Создаёт таблицы через SQL API Supabase"""
    # Supabase сам создаст таблицы при первом запросе,
    # но можно создать их через SQL Editor в дашборде.
    # Пока просто проверяем подключение
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{SUPABASE_URL}/rest/v1/users?limit=1", headers=HEADERS)
            logger.info(f"Supabase подключена (статус {r.status_code})")
        except Exception as e:
            logger.error(f"Ошибка подключения к Supabase: {e}")
            raise

async def close_db():
    pass  # httpx не требует закрытия

# ============ ПОЛЬЗОВАТЕЛИ ============

async def add_user(user_id: int, username: str = None):
    async with httpx.AsyncClient() as client:
        # Проверяем существует ли
        r = await client.get(f"{BASE_URL}/users?user_id=eq.{user_id}", headers=HEADERS)
        if r.json():
            return
        await client.post(f"{BASE_URL}/users", headers=HEADERS, json={
            "user_id": user_id, "username": username,
            "vpn_notify": False, "proxy_notify": False
        })

async def get_user(user_id: int):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/users?user_id=eq.{user_id}", headers=HEADERS)
        data = r.json()
        return data[0] if data else None

async def get_all_users():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/users?select=user_id", headers=HEADERS)
        return [row['user_id'] for row in r.json()]

async def get_users_count():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/users?select=user_id", headers={"Prefer": "count=exact", **HEADERS})
        return int(r.headers.get("content-range", "0/0").split("/")[-1])

async def set_vpn_notify(user_id: int, value: bool):
    async with httpx.AsyncClient() as client:
        await client.patch(f"{BASE_URL}/users?user_id=eq.{user_id}", headers=HEADERS, json={"vpn_notify": value})

async def set_proxy_notify(user_id: int, value: bool):
    async with httpx.AsyncClient() as client:
        await client.patch(f"{BASE_URL}/users?user_id=eq.{user_id}", headers=HEADERS, json={"proxy_notify": value})

async def get_users_with_vpn_notify():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/users?vpn_notify=eq.true&select=user_id", headers=HEADERS)
        return [row['user_id'] for row in r.json()]

async def get_users_with_proxy_notify():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/users?proxy_notify=eq.true&select=user_id", headers=HEADERS)
        return [row['user_id'] for row in r.json()]

# ============ ЧЁРНЫЙ СПИСОК ============

async def add_to_blacklist(user_id: int):
    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE_URL}/blacklist", headers=HEADERS, json={"user_id": user_id})

async def remove_from_blacklist(user_id: int):
    async with httpx.AsyncClient() as client:
        await client.delete(f"{BASE_URL}/blacklist?user_id=eq.{user_id}", headers=HEADERS)

async def is_blacklisted(user_id: int) -> bool:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/blacklist?user_id=eq.{user_id}", headers=HEADERS)
        return len(r.json()) > 0

async def get_blacklist():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/blacklist?select=user_id", headers=HEADERS)
        return [row['user_id'] for row in r.json()]

# ============ VPN КЛЮЧИ ============

async def add_vpn_key(date: str, key: str):
    async with httpx.AsyncClient() as client:
        # Удаляем старые если больше 50
        r = await client.get(f"{BASE_URL}/vpn_keys?select=id&order=id.asc&limit=1", headers={
            "Prefer": "count=exact", **HEADERS})
        total = int(r.headers.get("content-range", "0/0").split("/")[-1])
        if total >= 50:
            oldest = r.json()
            if oldest:
                await client.delete(f"{BASE_URL}/vpn_keys?id=eq.{oldest[0]['id']}", headers=HEADERS)
        await client.post(f"{BASE_URL}/vpn_keys", headers=HEADERS, json={"date": date, "key": key})

async def remove_vpn_key(key_id: int):
    async with httpx.AsyncClient() as client:
        await client.delete(f"{BASE_URL}/vpn_keys?id=eq.{key_id}", headers=HEADERS)

async def get_vpn_keys_page(page: int = 1):
    offset = (page - 1) * ITEMS_PER_PAGE
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BASE_URL}/vpn_keys?select=*&order=id.desc&limit={ITEMS_PER_PAGE}&offset={offset}",
            headers={"Prefer": "count=exact", **HEADERS}
        )
        total = int(r.headers.get("content-range", "0/0").split("/")[-1])
        return r.json(), total

async def get_all_vpn_keys():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/vpn_keys?select=*&order=id.desc", headers=HEADERS)
        return r.json()

# ============ ПРОКСИ ============

async def add_proxy(name: str, url: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/proxy_list?select=id&order=id.asc&limit=1", headers={
            "Prefer": "count=exact", **HEADERS})
        total = int(r.headers.get("content-range", "0/0").split("/")[-1])
        if total >= 50:
            oldest = r.json()
            if oldest:
                await client.delete(f"{BASE_URL}/proxy_list?id=eq.{oldest[0]['id']}", headers=HEADERS)
        await client.post(f"{BASE_URL}/proxy_list", headers=HEADERS, json={"name": name, "url": url})

async def remove_proxy(proxy_id: int):
    async with httpx.AsyncClient() as client:
        await client.delete(f"{BASE_URL}/proxy_list?id=eq.{proxy_id}", headers=HEADERS)

async def get_proxy_page(page: int = 1):
    offset = (page - 1) * ITEMS_PER_PAGE
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BASE_URL}/proxy_list?select=*&order=id.desc&limit={ITEMS_PER_PAGE}&offset={offset}",
            headers={"Prefer": "count=exact", **HEADERS}
        )
        total = int(r.headers.get("content-range", "0/0").split("/")[-1])
        return r.json(), total

async def get_all_proxies():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/proxy_list?select=*&order=id.desc", headers=HEADERS)
        return r.json()

# ============ СПОНСОРЫ ============

async def add_sponsor(username: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/sponsors?channel_username=eq.{username}", headers=HEADERS)
        if not r.json():
            await client.post(f"{BASE_URL}/sponsors", headers=HEADERS, json={"channel_username": username})

async def remove_sponsor(username: str):
    async with httpx.AsyncClient() as client:
        await client.delete(f"{BASE_URL}/sponsors?channel_username=eq.{username}", headers=HEADERS)

async def get_sponsors():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/sponsors?select=channel_username", headers=HEADERS)
        return [row['channel_username'] for row in r.json()]

async def get_channels_to_check():
    from config import YOUR_CHANNEL
    sponsors = await get_sponsors()
    return [YOUR_CHANNEL] + sponsors

# ============ ОБРАЩЕНИЯ ============

async def add_support_message(user_id: int, username: str, message: str, timestamp: str):
    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE_URL}/support_messages", headers=HEADERS, json={
            "user_id": user_id, "username": username, "message": message,
            "timestamp": timestamp, "replied": False
        })

async def get_support_messages():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/support_messages?select=*&order=id.desc", headers=HEADERS)
        return r.json()

async def mark_support_replied(msg_id: int):
    async with httpx.AsyncClient() as client:
        await client.patch(f"{BASE_URL}/support_messages?id=eq.{msg_id}", headers=HEADERS, json={"replied": True})

async def add_ad_message(user_id: int, username: str, message: str, timestamp: str):
    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE_URL}/ad_messages", headers=HEADERS, json={
            "user_id": user_id, "username": username, "message": message,
            "timestamp": timestamp, "replied": False
        })

async def get_ad_messages():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/ad_messages?select=*&order=id.desc", headers=HEADERS)
        return r.json()

async def mark_ad_replied(msg_id: int):
    async with httpx.AsyncClient() as client:
        await client.patch(f"{BASE_URL}/ad_messages?id=eq.{msg_id}", headers=HEADERS, json={"replied": True})

# ============ РАССЫЛКА ============

async def add_broadcast_log(broadcast_type: str, count: int):
    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE_URL}/broadcast_log", headers=HEADERS, json={
            "type": broadcast_type, "count": count
        })

async def get_broadcast_count():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/broadcast_log?select=id", headers={"Prefer": "count=exact", **HEADERS})
        return int(r.headers.get("content-range", "0/0").split("/")[-1])

async def get_stats():
    users = await get_users_count()
    blacklist = len(await get_blacklist())
    
    async with httpx.AsyncClient() as client:
        r1 = await client.get(f"{BASE_URL}/vpn_keys?select=id", headers={"Prefer": "count=exact", **HEADERS})
        vpn_count = int(r1.headers.get("content-range", "0/0").split("/")[-1])
        
        r2 = await client.get(f"{BASE_URL}/proxy_list?select=id", headers={"Prefer": "count=exact", **HEADERS})
        proxy_count = int(r2.headers.get("content-range", "0/0").split("/")[-1])
        
        r3 = await client.get(f"{BASE_URL}/support_messages?select=id", headers={"Prefer": "count=exact", **HEADERS})
        support_count = int(r3.headers.get("content-range", "0/0").split("/")[-1])
        
        r4 = await client.get(f"{BASE_URL}/support_messages?replied=eq.false&select=id", headers={"Prefer": "count=exact", **HEADERS})
        support_unreplied = int(r4.headers.get("content-range", "0/0").split("/")[-1])
        
        r5 = await client.get(f"{BASE_URL}/ad_messages?select=id", headers={"Prefer": "count=exact", **HEADERS})
        ad_count = int(r5.headers.get("content-range", "0/0").split("/")[-1])
        
        r6 = await client.get(f"{BASE_URL}/ad_messages?replied=eq.false&select=id", headers={"Prefer": "count=exact", **HEADERS})
        ad_unreplied = int(r6.headers.get("content-range", "0/0").split("/")[-1])
    
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
