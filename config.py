import os

# Токен бота и админ
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(os.getenv("ADMIN_ID"))]

# Каналы
YOUR_CHANNEL = os.getenv("CHANNEL_USERNAME")

# Supabase
SUPABASE_URL = "https://nvoqmpraqhxuxlzozgdp.supabase.co"
SUPABASE_KEY = "sb_publishable_XWsv7Sp4kH9vHpuQUDrmdw_Fo4b1cqX"
SUPABASE_PASSWORD = "RATVPN404RAT"

# Количество элементов на странице
ITEMS_PER_PAGE = 5

# Задержка между сообщениями рассылки (секунды)
BROADCAST_DELAY = 5