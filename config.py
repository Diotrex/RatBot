import os

# Токен бота и админ
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(os.getenv("ADMIN_ID"))]

# Каналы
YOUR_CHANNEL = os.getenv("CHANNEL_USERNAME")

# Supabase
SUPABASE_URL = "https://nvoqmpraqhxuxlzozgdp.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_XWsv7Sp4kH9vHpuQUDrmdw_Fo4b1cqX")

# Количество элементов на странице
ITEMS_PER_PAGE = 8

# Задержка между сообщениями рассылки (секунды)
BROADCAST_DELAY = 5

# Автоудаление ключей (дни) — по умолчанию 30
VPN_AUTO_DELETE_DAYS = 30
PROXY_AUTO_DELETE_DAYS = 30
