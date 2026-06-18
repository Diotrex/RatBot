from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ITEMS_PER_PAGE

# ============ ГЛАВНОЕ МЕНЮ ============

MENU_TEXT = (
    "<b>🐀 Rat VPN</b>\n\n"
    "🔌 VPN-ключи — актуальные ключи для Happ.\n"
    "🛡️ Прокси — прокси для Telegram.\n"
    "📖 Инструкция — если подключаетесь впервые.\n"
    "📢 Реклама — сотрудничество и размещение.\n"
    "🆘 Поддержка — сообщить о проблеме.\n"
    "⚙️ Настройки — уведомления.\n\n"
    "⬇️ Приятного использования! 🚀"
)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔌 VPN-ключи", callback_data="vpn"))
    builder.row(InlineKeyboardButton(text="🛡️ Прокси", callback_data="proxy"))
    builder.row(
        InlineKeyboardButton(text="📖 Инструкция", callback_data="instruction"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Реклама", callback_data="ad"),
        InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")
    )
    return builder.as_markup()


# ============ ПРОВЕРКА ПОДПИСКИ ============

def get_check_subscription_keyboard(channels: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for channel in channels:
        channel_link = channel.replace('@', '')
        builder.row(InlineKeyboardButton(
            text=f"📢 {channel}",
            url=f"https://t.me/{channel_link}"
        ))
    builder.row(InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub"))
    return builder.as_markup()


# ============ VPN СТРАНИЦА ============

def get_vpn_page_keyboard(keys, total: int, page: int = 1) -> InlineKeyboardMarkup:
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    builder = InlineKeyboardBuilder()

    for k in keys:
        builder.row(InlineKeyboardButton(
            text=f"📅 {k['date']}",
            callback_data=f"vpnkey_{k['id']}"
        ))

    # Кнопки пагинации
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"vpn_page_{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"vpn_page_{page + 1}"))
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main"))
    return builder.as_markup()


# ============ ПРОКСИ СТРАНИЦА ============

def get_proxy_page_keyboard(proxies, total: int, page: int = 1) -> InlineKeyboardMarkup:
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    builder = InlineKeyboardBuilder()

    for p in proxies:
        builder.row(InlineKeyboardButton(
            text=f"🛡️ {p['name']}",
            url=p['url']  # кнопка-ссылка для подключения прокси
        ))

    # Кнопки пагинации
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"proxy_page_{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"proxy_page_{page + 1}"))
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main"))
    return builder.as_markup()


# ============ НАСТРОЙКИ ============

def get_settings_keyboard(vpn_notify: bool, proxy_notify: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    vpn_status = "✅" if vpn_notify else "❌"
    proxy_status = "✅" if proxy_notify else "❌"

    builder.row(InlineKeyboardButton(
        text=f"🔔 VPN-уведомления: {vpn_status}",
        callback_data="toggle_vpn_notify"
    ))
    builder.row(InlineKeyboardButton(
        text=f"🔔 Прокси-уведомления: {proxy_status}",
        callback_data="toggle_proxy_notify"
    ))
    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main"))
    return builder.as_markup()


# ============ УВЕДОМЛЕНИЯ ПРИ ПЕРВОМ ЗАХОДЕ ============

def get_first_time_vpn_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Да", callback_data="first_vpn_yes"))
    builder.row(InlineKeyboardButton(text="❌ Нет", callback_data="first_vpn_no"))
    return builder.as_markup()


def get_first_time_proxy_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Да", callback_data="first_proxy_yes"))
    builder.row(InlineKeyboardButton(text="❌ Нет", callback_data="first_proxy_no"))
    return builder.as_markup()


# ============ АДМИН-ПАНЕЛЬ ============

def get_admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔑 VPN", callback_data="admin_vpn_menu"),
        InlineKeyboardButton(text="🛡️ Прокси", callback_data="admin_proxy_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Спонсоры", callback_data="admin_sponsors_menu"),
        InlineKeyboardButton(text="🆘 Обращения", callback_data="admin_support_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📨 Рассылка всем", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="📩 По ID", callback_data="admin_broadcast_id")
    )
    builder.row(
        InlineKeyboardButton(text="🚫 ЧС", callback_data="admin_blacklist_menu"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
    )
    return builder.as_markup()


# ============ АДМИН: VPN ============

def get_admin_vpn_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить VPN-ключ", callback_data="admin_add_vpn"))
    builder.row(InlineKeyboardButton(text="❌ Удалить VPN-ключ", callback_data="admin_remove_vpn"))
    builder.row(InlineKeyboardButton(text="📋 Список VPN-ключей", callback_data="admin_list_vpn"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


# ============ АДМИН: ПРОКСИ ============

def get_admin_proxy_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить прокси", callback_data="admin_add_proxy"))
    builder.row(InlineKeyboardButton(text="❌ Удалить прокси", callback_data="admin_remove_proxy"))
    builder.row(InlineKeyboardButton(text="📋 Список прокси", callback_data="admin_list_proxy"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


# ============ АДМИН: СПОНСОРЫ ============

def get_admin_sponsors_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить спонсора", callback_data="admin_add_sponsor"))
    builder.row(InlineKeyboardButton(text="❌ Удалить спонсора", callback_data="admin_remove_sponsor"))
    builder.row(InlineKeyboardButton(text="📋 Список спонсоров", callback_data="admin_list_sponsors"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


# ============ АДМИН: ЧЁРНЫЙ СПИСОК ============

def get_admin_blacklist_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить в ЧС", callback_data="admin_blacklist_add"))
    builder.row(InlineKeyboardButton(text="❌ Удалить из ЧС", callback_data="admin_blacklist_remove"))
    builder.row(InlineKeyboardButton(text="📋 Список ЧС", callback_data="admin_blacklist_list"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


# ============ АДМИН: ОБРАЩЕНИЯ ============

def get_admin_support_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📨 Поддержка", callback_data="admin_support_list"))
    builder.row(InlineKeyboardButton(text="📢 Реклама", callback_data="admin_ad_list"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


# ============ УНИВЕРСАЛЬНЫЕ КНОПКИ ============

def get_back_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data))
    return builder.as_markup()


def get_confirm_notify_keyboard(broadcast_type: str) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения рассылки (vpn или proxy)"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_broadcast_{broadcast_type}"),
        InlineKeyboardButton(text="❌ Нет", callback_data="cancel_broadcast")
    )
    return builder.as_markup()
