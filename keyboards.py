from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ITEMS_PER_PAGE

# ============ MAIN MENU ============

MENU_TEXT = (
    "<b>🐀 Rat VPN</b>\n\n"
    "🔌 VPN-ключи — актуальные ключи для Happ.\n"
    "🛡️ Proxy — прокси для Telegram.\n"
    "📖 Инструкция — если подключаетесь впервые.\n"
    "📢 Реклама — сотрудничество и размещение.\n"
    "🆘 Поддержка — сообщить о проблеме.\n"
    "⚙️ Настройки — уведомления.\n\n"
    "⬇️ Приятного использования! 🚀"
)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔌 VPN-ключи", callback_data="vpn"))
    builder.row(InlineKeyboardButton(text="🛡️ Proxy", callback_data="proxy"))
    builder.row(
        InlineKeyboardButton(text="📖 Инструкция", callback_data="instruction"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Реклама", callback_data="ad"),
        InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")
    )
    return builder.as_markup()


# ============ SUBSCRIPTION CHECK ============

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


# ============ VPN PAGE ============

def get_vpn_page_keyboard(keys, total: int, page: int = 1) -> InlineKeyboardMarkup:
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    builder = InlineKeyboardBuilder()

    for k in keys:
        builder.row(InlineKeyboardButton(
            text=f"📅 {k['date']}",
            callback_data=f"vpnkey_{k['id']}"
        ))

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


# ============ VPN KEY DETAIL ============

def get_vpn_key_detail_keyboard(key) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [InlineKeyboardButton(text="🔙 Назад к VPN", callback_data="vpn")]
    if key.get('vless'):
        buttons.append(InlineKeyboardButton(text="🔗 VLESS", callback_data=f"vless_{key['id']}"))
    builder.row(*buttons)
    return builder.as_markup()


# ============ COMMENT SKIP ============

def get_comment_skip_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Добавить", callback_data="add_comment"),
        InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_comment")
    )
    return builder.as_markup()


def get_vless_skip_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_vless")
    )
    return builder.as_markup()


# ============ PROXY PAGE ============

def get_proxy_page_keyboard(proxies, total: int, page: int = 1) -> InlineKeyboardMarkup:
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    builder = InlineKeyboardBuilder()

    for p in proxies:
        builder.row(InlineKeyboardButton(
            text=f"🛡️ {p['name']}",
            url=p['url']
        ))

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


# ============ SETTINGS ============

def get_settings_keyboard(vpn_notify: bool, proxy_notify: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    vpn_status = "✅" if vpn_notify else "❌"
    proxy_status = "✅" if proxy_notify else "❌"
    builder.row(InlineKeyboardButton(
        text=f"🔔 VPN-уведомления: {vpn_status}",
        callback_data="toggle_vpn_notify"
    ))
    builder.row(InlineKeyboardButton(
        text=f"🔔 Proxy-уведомления: {proxy_status}",
        callback_data="toggle_proxy_notify"
    ))
    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main"))
    return builder.as_markup()


# ============ FIRST TIME ============

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


# ============ ADMIN PANEL ============

def get_admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔑 VPN", callback_data="admin_vpn_menu"),
        InlineKeyboardButton(text="🛡️ Proxy", callback_data="admin_proxy_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Спонсоры", callback_data="admin_sponsors_menu"),
        InlineKeyboardButton(text="🆘 Обращения", callback_data="admin_support_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast_menu"),
        InlineKeyboardButton(text="⚙️ Автоудаление", callback_data="admin_autodelete_menu")
    )
    builder.row(
        InlineKeyboardButton(text="🚫 Чёрный список", callback_data="admin_blacklist_menu"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
    )
    return builder.as_markup()


# ============ ADMIN: VPN ============

def get_admin_vpn_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить VPN-ключ", callback_data="admin_add_vpn"))
    builder.row(InlineKeyboardButton(text="❌ Удалить VPN-ключ", callback_data="admin_remove_vpn"))
    builder.row(InlineKeyboardButton(text="📋 Список VPN-ключей", callback_data="admin_list_vpn"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


# ============ ADMIN: PROXY ============

def get_admin_proxy_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить proxy", callback_data="admin_add_proxy"))
    builder.row(InlineKeyboardButton(text="❌ Удалить proxy", callback_data="admin_remove_proxy"))
    builder.row(InlineKeyboardButton(text="📋 Список proxy", callback_data="admin_list_proxy"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


# ============ ADMIN: SPONSORS ============

def get_admin_sponsors_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить спонсора", callback_data="admin_add_sponsor"))
    builder.row(InlineKeyboardButton(text="❌ Удалить спонсора", callback_data="admin_remove_sponsor"))
    builder.row(InlineKeyboardButton(text="📋 Список спонсоров", callback_data="admin_list_sponsors"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


# ============ ADMIN: BLACKLIST ============

def get_admin_blacklist_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить в чёрный список", callback_data="admin_blacklist_add"))
    builder.row(InlineKeyboardButton(text="❌ Удалить из чёрного списка", callback_data="admin_blacklist_remove"))
    builder.row(InlineKeyboardButton(text="📋 Список чёрного списка", callback_data="admin_blacklist_list"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


# ============ ADMIN: SUPPORT ============

def get_admin_support_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📨 Обращения в поддержку", callback_data="admin_support_list"))
    builder.row(InlineKeyboardButton(text="📢 Заявки на рекламу", callback_data="admin_ad_list"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


# ============ ADMIN: BROADCAST MENU ============

def get_admin_broadcast_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📨 Рассылка всем", callback_data="admin_broadcast_all"))
    builder.row(InlineKeyboardButton(text="📩 Рассылка по ID", callback_data="admin_broadcast_id"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


# ============ ADMIN: AUTO DELETE MENU ============

def get_admin_autodelete_menu_keyboard(vpn_days: int, proxy_days: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"🔑 VPN: удалять через {vpn_days} дн.", 
        callback_data="admin_set_vpn_autodelete"
    ))
    builder.row(InlineKeyboardButton(
        text=f"🛡️ Proxy: удалять через {proxy_days} дн.", 
        callback_data="admin_set_proxy_autodelete"
    ))
    builder.row(InlineKeyboardButton(text="🗑️ Удалить старые сейчас", callback_data="admin_delete_old_now"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


# ============ ADMIN: SUPPORT REPLY LIST ============

def get_support_reply_list_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💬 Ответить на обращение", callback_data="admin_support_reply"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_support_menu"))
    return builder.as_markup()


def get_ad_reply_list_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💬 Ответить на заявку", callback_data="admin_ad_reply"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_support_menu"))
    return builder.as_markup()


# ============ BACK BUTTON ============

def get_back_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data))
    return builder.as_markup()


# ============ CONFIRM BROADCAST ============

def get_confirm_notify_keyboard(broadcast_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_broadcast_{broadcast_type}"),
        InlineKeyboardButton(text="❌ Нет", callback_data="cancel_broadcast")
    )
    return builder.as_markup()


# ============ ADMIN NOTIFY REPLY (from LS) ============

def get_admin_notify_reply_keyboard(msg_id: int, msg_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💬 Ответить",
        callback_data=f"reply_{msg_type}_{msg_id}"
    ))
    return builder.as_markup()
