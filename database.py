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

_client = None

def get_client():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client

async def init_db():
    client = get_client()
    try:
        r = await client.get(f"{BASE_URL}/users?limit=1", headers=HEADERS)
        logger.info(f"Supabase подключена (статус {r.status_code})")
    except Exception as e:
        logger.error(f"Ошибка подключения к Supabase: {e}")
        raise

async def close_db():
    global _client
    if _client:
        await _client.aclose()
        _client = None

# ============ ПОЛЬЗОВАТЕЛИ ============

async def add_user(user_id: int, username: str = None):
    client = get_client()
    r = await client.get(f"{BASE_URL}/users?user_id=eq.{user_id}", headers=HEADERS)
    existing = r.json()
    if existing:
        if username and existing[0].get('username') != username:
            await client.patch(f"{BASE_URL}/users?user_id=eq.{user_id}", headers=HEADERS, 
                json={"username": username})
        return existing[0]
    await client.post(f"{BASE_URL}/users", headers=HEADERS, json={
        "user_id": user_id, "username": username,
        "vpn_notify": False, "proxy_notify": False
    })
    r = await client.get(f"{BASE_URL}/users?user_id=eq.{user_id}", headers=HEADERS)
    return r.json()[0] if r.json() else None

async def get_user(user_id: int):
    client = get_client()
    r = await client.get(f"{BASE_URL}/users?user_id=eq.{user_id}", headers=HEADERS)
    data = r.json()
    return data[0] if data else None

async def get_all_users():
    client = get_client()
    r = await client.get(f"{BASE_URL}/users?select=user_id", headers=HEADERS)
    data = r.json()
    return [row['user_id'] for row in data] if data else []

async def get_users_count():
    client = get_client()
    r = await client.get(f"{BASE_URL}/users?select=user_id", headers={"Prefer": "count=exact", **HEADERS})
    content_range = r.headers.get("content-range", "0/0")
    return int(content_range.split("/")[-1]) if "/" in content_range else 0

async def set_vpn_notify(user_id: int, value: bool):
    client = get_client()
    await client.patch(f"{BASE_URL}/users?user_id=eq.{user_id}", headers=HEADERS, json={"vpn_notify": value})

async def set_proxy_notify(user_id: int, value: bool):
    client = get_client()
    await client.patch(f"{BASE_URL}/users?user_id=eq.{user_id}", headers=HEADERS, json={"proxy_notify": value})

async def get_users_with_vpn_notify():
    client = get_client()
    r = await client.get(f"{BASE_URL}/users?vpn_notify=eq.true&select=user_id", headers=HEADERS)
    data = r.json()
    return [row['user_id'] for row in data] if data else []

async def get_users_with_proxy_notify():
    client = get_client()
    r = await client.get(f"{BASE_URL}/users?proxy_notify=eq.true&select=user_id", headers=HEADERS)
    data = r.json()
    return [row['user_id'] for row in data] if data else []

# ============ ЧЁРНЫЙ СПИСОК ============

async def add_to_blacklist(user_id: int):
    client = get_client()
    r = await client.get(f"{BASE_URL}/blacklist?user_id=eq.{user_id}", headers=HEADERS)
    if not r.json():
        await client.post(f"{BASE_URL}/blacklist", headers=HEADERS, json={"user_id": user_id})

async def remove_from_blacklist(user_id: int):
    client = get_client()
    await client.delete(f"{BASE_URL}/blacklist?user_id=eq.{user_id}", headers=HEADERS)

async def is_blacklisted(user_id: int) -> bool:
    client = get_client()
    r = await client.get(f"{BASE_URL}/blacklist?user_id=eq.{user_id}", headers=HEADERS)
    data = r.json()
    return len(data) > 0 if data else False

async def get_blacklist():
    client = get_client()
    r = await client.get(f"{BASE_URL}/blacklist?select=user_id", headers=HEADERS)
    data = r.json()
    return [row['user_id'] for row in data] if data else []

# ============ VPN КЛЮЧИ ============

async def add_vpn_key(date: str, key: str):
    client = get_client()
    r = await client.get(f"{BASE_URL}/vpn_keys?select=id&order=id.asc&limit=1", 
        headers={"Prefer": "count=exact", **HEADERS})
    content_range = r.headers.get("content-range", "0/0")
    total = int(content_range.split("/")[-1]) if "/" in content_range else 0
    if total >= 50:
        oldest = r.json()
        if oldest:
            await client.delete(f"{BASE_URL}/vpn_keys?id=eq.{oldest[0]['id']}", headers=HEADERS)
    await client.post(f"{BASE_URL}/vpn_keys", headers=HEADERS, json={"date": date, "key": key})

async def remove_vpn_key(key_id: int):
    client = get_client()
    await client.delete(f"{BASE_URL}/vpn_keys?id=eq.{key_id}", headers=HEADERS)

async def get_vpn_keys_page(page: int = 1):
    client = get_client()
    offset = (page - 1) * ITEMS_PER_PAGE
    r = await client.get(
        f"{BASE_URL}/vpn_keys?select=*&order=id.desc&limit={ITEMS_PER_PAGE}&offset={offset}",
        headers={"Prefer": "count=exact", **HEADERS}
    )
    content_range = r.headers.get("content-range", "0/0")
    total = int(content_range.split("/")[-1]) if "/" in content_range else 0
    data = r.json()
    return (data if data else []), total

async def get_all_vpn_keys():
    client = get_client()
    r = await client.get(f"{BASE_URL}/vpn_keys?select=*&order=id.desc", headers=HEADERS)
    data = r.json()
    return data if data else []

# ============ ПРОКСИ ============

async def add_proxy(name: str, url: str):
    client = get_client()
    r = await client.get(f"{BASE_URL}/proxy_list?select=id&order=id.asc&limit=1",
        headers={"Prefer": "count=exact", **HEADERS})
    content_range = r.headers.get("content-range", "0/0")
    total = int(content_range.split("/")[-1]) if "/" in content_range else 0
    if total >= 50:
        oldest = r.json()
        if oldest:
            await client.delete(f"{BASE_URL}/proxy_list?id=eq.{oldest[0]['id']}", headers=HEADERS)
    await client.post(f"{BASE_URL}/proxy_list", headers=HEADERS, json={"name": name, "url": url})

async def remove_proxy(proxy_id: int):
    client = get_client()
    await client.delete(f"{BASE_URL}/proxy_list?id=eq.{proxy_id}", headers=HEADERS)

async def get_proxy_page(page: int = 1):
    client = get_client()
    offset = (page - 1) * ITEMS_PER_PAGE
    r = await client.get(
        f"{BASE_URL}/proxy_list?select=*&order=id.desc&limit={ITEMS_PER_PAGE}&offset={offset}",
        headers={"Prefer": "count=exact", **HEADERS}
    )
    content_range = r.headers.get("content-range", "0/0")
    total = int(content_range.split("/")[-1]) if "/" in content_range else 0
    data = r.json()
    return (data if data else []), total

async def get_all_proxies():
    client = get_client()
    r = await client.get(f"{BASE_URL}/proxy_list?select=*&order=id.desc", headers=HEADERS)
    data = r.json()
    return data if data else []

# ============ СПОНСОРЫ ============

async def add_sponsor(username: str):
    client = get_client()
    r = await client.get(f"{BASE_URL}/sponsors?channel_username=eq.{username}", headers=HEADERS)
    if not r.json():
        await client.post(f"{BASE_URL}/sponsors", headers=HEADERS, json={"channel_username": username})

async def remove_sponsor(username: str):
    client = get_client()
    await client.delete(f"{BASE_URL}/sponsors?channel_username=eq.{username}", headers=HEADERS)

async def get_sponsors():
    client = get_client()
    r = await client.get(f"{BASE_URL}/sponsors?select=channel_username", headers=HEADERS)
    data = r.json()
    return [row['channel_username'] for row in data] if data else []

async def get_channels_to_check():
    from config import YOUR_CHANNEL
    sponsors = await get_sponsors()
    return [YOUR_CHANNEL] + sponsors

# ============ ОБРАЩЕНИЯ ============

async def add_support_message(user_id: int, username: str, message: str, timestamp: str):
    client = get_client()
    await client.post(f"{BASE_URL}/support_messages", headers=HEADERS, json={
        "user_id": user_id, "username": username, "message": message,
        "timestamp": timestamp, "replied": False
    })

async def get_support_messages():
    client = get_client()
    r = await client.get(f"{BASE_URL}/support_messages?select=*&order=id.desc", headers=HEADERS)
    data = r.json()
    return data if data else []

async def mark_support_replied(msg_id: int):
    client = get_client()
    await client.patch(f"{BASE_URL}/support_messages?id=eq.{msg_id}", headers=HEADERS, json={"replied": True})

async def add_ad_message(user_id: int, username: str, message: str, timestamp: str):
    client = get_client()
    await client.post(f"{BASE_URL}/ad_messages", headers=HEADERS, json={
        "user_id": user_id, "username": username, "message": message,
        "timestamp": timestamp, "replied": False
    })

async def get_ad_messages():
    client = get_client()
    r = await client.get(f"{BASE_URL}/ad_messages?select=*&order=id.desc", headers=HEADERS)
    data = r.json()
    return data if data else []

async def mark_ad_replied(msg_id: int):
    client = get_client()
    await client.patch(f"{BASE_URL}/ad_messages?id=eq.{msg_id}", headers=HEADERS, json={"replied": True})

# ============ РАССЫЛКА ============

async def add_broadcast_log(broadcast_type: str, count: int):
    client = get_client()
    await client.post(f"{BASE_URL}/broadcast_log", headers=HEADERS, json={
        "type": broadcast_type, "count": count
    })

async def get_broadcast_count():
    client = get_client()
    r = await client.get(f"{BASE_URL}/broadcast_log?select=id", headers={"Prefer": "count=exact", **HEADERS})
    content_range = r.headers.get("content-range", "0/0")
    return int(content_range.split("/")[-1]) if "/" in content_range else 0

async def get_stats():
    async def count_table(table, filter=""):
        client = get_client()
        url = f"{BASE_URL}/{table}?select=id"
        if filter:
            url += f"&{filter}"
        r = await client.get(url, headers={"Prefer": "count=exact", **HEADERS})
        content_range = r.headers.get("content-range", "0/0")
        return int(content_range.split("/")[-1]) if "/" in content_range else 0
    
    return {
        "users": await get_users_count(),
        "blacklist": len(await get_blacklist()),
        "vpn_keys": await count_table("vpn_keys"),
        "proxy_count": await count_table("proxy_list"),
        "support_count": await count_table("support_messages"),
        "support_unreplied": await count_table("support_messages", "replied=eq.false"),
        "ad_count": await count_table("ad_messages"),
        "ad_unreplied": await count_table("ad_messages", "replied=eq.false"),
        "sponsors": await get_sponsors(),
        "broadcast_count": await get_broadcast_count()
    }
