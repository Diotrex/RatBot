import asyncio
import logging
from datetime import datetime

from aiogram import Bot, F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from config import ADMIN_IDS, YOUR_CHANNEL, BROADCAST_DELAY, ITEMS_PER_PAGE
from keyboards import (
    MENU_TEXT, get_main_menu_keyboard,
    get_check_subscription_keyboard,
    get_vpn_page_keyboard, get_proxy_page_keyboard,
    get_settings_keyboard,
    get_first_time_vpn_keyboard, get_first_time_proxy_keyboard,
    get_admin_keyboard,
    get_admin_vpn_menu_keyboard, get_admin_proxy_menu_keyboard,
    get_admin_sponsors_keyboard, get_admin_blacklist_keyboard,
    get_admin_support_menu_keyboard,
    get_back_keyboard, get_confirm_notify_keyboard
)

logger = logging.getLogger(__name__)
router = Router()


# ============ СОСТОЯНИЯ FSM ============
class AdminStates(StatesGroup):
    waiting_for_vpn_date = State()
    waiting_for_vpn_key = State()
    waiting_for_vpn_remove_id = State()
    waiting_for_proxy_name = State()
    waiting_for_proxy_url = State()
    waiting_for_proxy_remove_id = State()
    waiting_for_sponsor_add = State()
    waiting_for_sponsor_remove = State()
    waiting_for_blacklist_add = State()
    waiting_for_blacklist_remove = State()
    waiting_for_broadcast = State()
    waiting_for_broadcast_id = State()
    waiting_for_broadcast_id_text = State()


class UserStates(StatesGroup):
    waiting_for_support_message = State()
    waiting_for_ad_message = State()
    waiting_first_time = State()


class AdminReplyStates(StatesGroup):
    waiting_for_support_reply_select = State()
    waiting_for_support_reply_text = State()
    waiting_for_ad_reply_select = State()
    waiting_for_ad_reply_text = State()


# ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============

async def safe_edit_text(message: Message, text: str, reply_markup=None, parse_mode=None):
    try:
        await message.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise e


async def check_user_subscriptions(bot: Bot, user_id: int) -> tuple:
    channels = await db.get_channels_to_check()
    not_subscribed = []
    for channel in channels:
        try:
            chat_member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                not_subscribed.append(channel)
        except Exception as e:
            logger.error(f"Error checking subscription for {channel}: {e}")
            not_subscribed.append(channel)
    return len(not_subscribed) == 0, not_subscribed


# ============ /start ============
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if await db.is_blacklisted(message.from_user.id):
        await message.answer("🚫 Вы заблокированы.")
        return
    
    is_subscribed, not_subscribed = await check_user_subscriptions(message.bot, message.from_user.id)
    
    if not is_subscribed:
        channels = await db.get_channels_to_check()
        channels_list = "\n".join([f"• {ch}" for ch in channels])
        await message.answer(
            f"👋 Добро пожаловать в Rat VPN!\n\n"
            f"• Бесплатные VPN-ключи и прокси для Telegram.\n\n"
            f"⚠️ Для использования подпишитесь на каналы:\n\n"
            f"{channels_list}\n\n"
            f"Подпишитесь и нажмите кнопку проверки:",
            reply_markup=get_check_subscription_keyboard(channels)
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if user is None:
        # Первый вход — спрашиваем про уведомления ОДИН раз
        await db.add_user(message.from_user.id, message.from_user.username or f"id{message.from_user.id}")
        await message.answer(
            "🔔 Хотите получать уведомления о новых VPN-ключах?",
            reply_markup=get_first_time_vpn_keyboard()
        )
        await state.set_state(UserStates.waiting_first_time)
        await state.update_data(first_step="vpn")
    else:
        # Уже зарегистрирован — сразу в меню
        await message.answer(MENU_TEXT, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)


# ============ ПЕРВЫЙ ВХОД: НАСТРОЙКА УВЕДОМЛЕНИЙ ============
@router.callback_query(StateFilter(UserStates.waiting_first_time), F.data.startswith("first_vpn_"))
async def process_first_vpn(callback: CallbackQuery, state: FSMContext):
    vpn_notify = callback.data == "first_vpn_yes"
    await db.set_vpn_notify(callback.from_user.id, vpn_notify)
    
    await safe_edit_text(callback.message,
        "🔔 Хотите получать уведомления о новых прокси?",
        reply_markup=get_first_time_proxy_keyboard()
    )
    await state.update_data(first_step="proxy")
    await callback.answer()


@router.callback_query(StateFilter(UserStates.waiting_first_time), F.data.startswith("first_proxy_"))
async def process_first_proxy(callback: CallbackQuery, state: FSMContext):
    proxy_notify = callback.data == "first_proxy_yes"
    await db.set_proxy_notify(callback.from_user.id, proxy_notify)
    
    await state.clear()
    await safe_edit_text(callback.message, MENU_TEXT, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)
    await callback.answer()


# ============ ПРОВЕРКА ПОДПИСКИ ============
@router.callback_query(F.data == "check_sub")
async def process_check_sub(callback: CallbackQuery, state: FSMContext):
    if await db.is_blacklisted(callback.from_user.id):
        await callback.message.edit_text("🚫 Вы заблокированы.")
        await callback.answer()
        return
    
    is_subscribed, not_subscribed = await check_user_subscriptions(callback.bot, callback.from_user.id)
    
    if is_subscribed:
        user = await db.get_user(callback.from_user.id)
        if user is None:
            await db.add_user(callback.from_user.id, callback.from_user.username or f"id{callback.from_user.id}")
            await safe_edit_text(callback.message,
                "🔔 Хотите получать уведомления о новых VPN-ключах?",
                reply_markup=get_first_time_vpn_keyboard()
            )
            await state.set_state(UserStates.waiting_first_time)
            await state.update_data(first_step="vpn")
        else:
            await safe_edit_text(callback.message, MENU_TEXT, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)
    else:
        not_sub_list = "\n".join([f"• {ch}" for ch in not_subscribed])
        channels = await db.get_channels_to_check()
        await safe_edit_text(callback.message,
            f"❌ Вы подписались не на все каналы!\n\nНе подписаны:\n{not_sub_list}\n\nПодпишитесь и нажмите проверку:",
            reply_markup=get_check_subscription_keyboard(channels)
        )
    await callback.answer()


# ============ ГЛАВНОЕ МЕНЮ ============
@router.callback_query(F.data == "back_to_main")
async def process_back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if await db.is_blacklisted(callback.from_user.id):
        await callback.message.edit_text("🚫 Вы заблокированы.")
        await callback.answer()
        return
    await safe_edit_text(callback.message, MENU_TEXT, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)
    await callback.answer()


# ============ VPN ============
@router.callback_query(F.data == "vpn")
async def process_vpn(callback: CallbackQuery):
    if await db.is_blacklisted(callback.from_user.id):
        await callback.message.edit_text("🚫 Вы заблокированы.")
        await callback.answer()
        return
    
    keys, total = await db.get_vpn_keys_page(page=1)
    if not keys:
        await safe_edit_text(callback.message, "🔑 Пока нет VPN-ключей.", reply_markup=get_back_keyboard("back_to_main"))
        await callback.answer()
        return
    
    await safe_edit_text(callback.message, "🔑 Выберите VPN-ключ:", reply_markup=get_vpn_page_keyboard(keys, total, page=1))
    await callback.answer()


@router.callback_query(F.data.startswith("vpn_page_"))
async def process_vpn_page(callback: CallbackQuery):
    page = int(callback.data.split("_")[-1])
    keys, total = await db.get_vpn_keys_page(page=page)
    
    if not keys:
        await callback.answer("Страница пуста", show_alert=True)
        return
    
    await safe_edit_text(callback.message, "🔑 Выберите VPN-ключ:", reply_markup=get_vpn_page_keyboard(keys, total, page=page))
    await callback.answer()


@router.callback_query(F.data.startswith("vpnkey_"))
async def process_vpn_key(callback: CallbackQuery):
    key_id = int(callback.data.split("_")[-1])
    all_keys = await db.get_all_vpn_keys()
    key = None
    for k in all_keys:
        if k['id'] == key_id:
            key = k
            break
    
    if not key:
        await callback.answer("Ключ не найден", show_alert=True)
        return
    
    key_text = f"`{key['key']}`"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад к VPN", callback_data="vpn"))
    await safe_edit_text(callback.message,
        f"🔐 Ключ от {key['date']}:\n\n{key_text}\n\n⚠️ Нажмите на ключ, чтобы скопировать.",
        reply_markup=builder.as_markup(), parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


# ============ ПРОКСИ ============
@router.callback_query(F.data == "proxy")
async def process_proxy(callback: CallbackQuery):
    if await db.is_blacklisted(callback.from_user.id):
        await callback.message.edit_text("🚫 Вы заблокированы.")
        await callback.answer()
        return
    
    proxies, total = await db.get_proxy_page(page=1)
    if not proxies:
        await safe_edit_text(callback.message, "🛡️ Пока нет прокси.", reply_markup=get_back_keyboard("back_to_main"))
        await callback.answer()
        return
    
    await safe_edit_text(callback.message, "🛡️ Выберите прокси (нажмите для подключения):", reply_markup=get_proxy_page_keyboard(proxies, total, page=1))
    await callback.answer()


@router.callback_query(F.data.startswith("proxy_page_"))
async def process_proxy_page(callback: CallbackQuery):
    page = int(callback.data.split("_")[-1])
    proxies, total = await db.get_proxy_page(page=page)
    
    if not proxies:
        await callback.answer("Страница пуста", show_alert=True)
        return
    
    await safe_edit_text(callback.message, "🛡️ Выберите прокси:", reply_markup=get_proxy_page_keyboard(proxies, total, page=page))
    await callback.answer()


# ============ ИНСТРУКЦИЯ ============
@router.callback_query(F.data == "instruction")
async def process_instruction(callback: CallbackQuery):
    if await db.is_blacklisted(callback.from_user.id):
        await callback.message.edit_text("🚫 Вы заблокированы.")
        await callback.answer()
        return
    
    await safe_edit_text(
        callback.message,
        "📖 Как подключиться:\n\n"
        "1. Скачайте Happ или другой клиент с поддержкой VLESS\n\n"
        "2. В боте нажмите «🔌 VPN-ключи» и выберите ключ\n\n"
        "3. Скопируйте ключ — просто нажмите на него\n\n"
        "4. В программе нажмите «Добавить сервер» → вставьте ссылку\n\n"
        "5. Готово! Подключайтесь и пользуйтесь 🎉\n\n"
        "🛡️ Прокси для Telegram:\n"
        "• Нажмите на прокси — он подключится автоматически\n\n"
        "💬 Вопросы? Жмите «🆘 Поддержка»",
        reply_markup=get_back_keyboard("back_to_main")
    )
    await callback.answer()


# ============ НАСТРОЙКИ ============
@router.callback_query(F.data == "settings")
async def process_settings(callback: CallbackQuery):
    if await db.is_blacklisted(callback.from_user.id):
        await callback.message.edit_text("🚫 Вы заблокированы.")
        await callback.answer()
        return
    
    user = await db.get_user(callback.from_user.id)
    if not user:
        await db.add_user(callback.from_user.id, callback.from_user.username or f"id{callback.from_user.id}")
        user = await db.get_user(callback.from_user.id)
    
    vpn_notify = user.get('vpn_notify', False) if user else False
    proxy_notify = user.get('proxy_notify', False) if user else False
    
    await safe_edit_text(callback.message, "⚙️ Настройки уведомлений:", reply_markup=get_settings_keyboard(vpn_notify, proxy_notify))
    await callback.answer()


@router.callback_query(F.data == "toggle_vpn_notify")
async def toggle_vpn_notify(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await db.add_user(callback.from_user.id, callback.from_user.username or f"id{callback.from_user.id}")
        user = await db.get_user(callback.from_user.id)
    
    new_value = not user.get('vpn_notify', False)
    await db.set_vpn_notify(callback.from_user.id, new_value)
    await asyncio.sleep(0.3)
    user = await db.get_user(callback.from_user.id)
    await safe_edit_text(callback.message, "⚙️ Настройки уведомлений:", reply_markup=get_settings_keyboard(
        user.get('vpn_notify', False), user.get('proxy_notify', False)))
    await callback.answer(f"VPN-уведомления {'включены' if new_value else 'выключены'}")


@router.callback_query(F.data == "toggle_proxy_notify")
async def toggle_proxy_notify(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await db.add_user(callback.from_user.id, callback.from_user.username or f"id{callback.from_user.id}")
        user = await db.get_user(callback.from_user.id)
    
    new_value = not user.get('proxy_notify', False)
    await db.set_proxy_notify(callback.from_user.id, new_value)
    await asyncio.sleep(0.3)
    user = await db.get_user(callback.from_user.id)
    await safe_edit_text(callback.message, "⚙️ Настройки уведомлений:", reply_markup=get_settings_keyboard(
        user.get('vpn_notify', False), user.get('proxy_notify', False)))
    await callback.answer(f"Прокси-уведомления {'включены' if new_value else 'выключены'}")


# ============ ПОДДЕРЖКА ============
@router.callback_query(F.data == "support")
async def process_support(callback: CallbackQuery, state: FSMContext):
    if await db.is_blacklisted(callback.from_user.id):
        await callback.message.edit_text("🚫 Вы заблокированы.")
        await callback.answer()
        return
    
    await safe_edit_text(callback.message,
        "🆘 Поддержка\n\nОпишите вашу проблему. Отправьте одно сообщение, и я передам его администратору.",
        reply_markup=get_back_keyboard("back_to_main")
    )
    await state.set_state(UserStates.waiting_for_support_message)
    await callback.answer()


@router.message(StateFilter(UserStates.waiting_for_support_message))
async def process_support_message(message: Message, state: FSMContext):
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    await db.add_support_message(
        user_id=message.from_user.id,
        username=message.from_user.username or f"id{message.from_user.id}",
        message=message.text,
        timestamp=timestamp
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                chat_id=admin_id,
                text=f"📨 Новое обращение в поддержку!\n\n👤 От: @{message.from_user.username or 'нет username'} (ID: {message.from_user.id})\n🕒 {timestamp}\n\n💬 Сообщение:\n{message.text}"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    await message.answer("✅ Ваше сообщение отправлено! Администратор свяжется с вами в ближайшее время.", reply_markup=get_back_keyboard("back_to_main"))
    await state.clear()


# ============ РЕКЛАМА ============
@router.callback_query(F.data == "ad")
async def process_ad(callback: CallbackQuery, state: FSMContext):
    if await db.is_blacklisted(callback.from_user.id):
        await callback.message.edit_text("🚫 Вы заблокированы.")
        await callback.answer()
        return
    
    await safe_edit_text(callback.message,
        "📢 Реклама\n\nОпишите ваше предложение. Отправьте одно сообщение, и я передам его администратору.",
        reply_markup=get_back_keyboard("back_to_main")
    )
    await state.set_state(UserStates.waiting_for_ad_message)
    await callback.answer()


@router.message(StateFilter(UserStates.waiting_for_ad_message))
async def process_ad_message(message: Message, state: FSMContext):
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    await db.add_ad_message(
        user_id=message.from_user.id,
        username=message.from_user.username or f"id{message.from_user.id}",
        message=message.text,
        timestamp=timestamp
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                chat_id=admin_id,
                text=f"📢 Новая заявка на рекламу!\n\n👤 От: @{message.from_user.username or 'нет username'} (ID: {message.from_user.id})\n🕒 {timestamp}\n\n💬 Сообщение:\n{message.text}"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    await message.answer("✅ Ваша заявка отправлена! Администратор свяжется с вами в ближайшее время.", reply_markup=get_back_keyboard("back_to_main"))
    await state.clear()


# ============ АДМИН-ПАНЕЛЬ ============
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    await message.answer("⚙️ Админ-панель", reply_markup=get_admin_keyboard())


@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "⚙️ Админ-панель", reply_markup=get_admin_keyboard())
    await callback.answer()


# ============ АДМИН: VPN ============
@router.callback_query(F.data == "admin_vpn_menu")
async def admin_vpn_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "🔑 Управление VPN-ключами:", reply_markup=get_admin_vpn_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_list_vpn")
async def admin_list_vpn(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    keys = await db.get_all_vpn_keys()
    if not keys:
        text = "📋 Ключей пока нет."
    else:
        text = "📋 Список VPN-ключей:\n\n" + "\n".join([f"ID {k['id']}: {k['date']}" for k in keys])
    
    await safe_edit_text(callback.message, text, reply_markup=get_back_keyboard("admin_vpn_menu"))
    await callback.answer()


@router.callback_query(F.data == "admin_add_vpn")
async def admin_add_vpn_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "📅 Введите дату ключа (например: 18.06.2026):", reply_markup=get_back_keyboard("admin_vpn_menu"))
    await state.set_state(AdminStates.waiting_for_vpn_date)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_vpn_date))
async def admin_add_vpn_date(message: Message, state: FSMContext):
    await state.update_data(vpn_date=message.text)
    await message.answer("🔑 Теперь отправьте ключ:", reply_markup=get_back_keyboard("admin_vpn_menu"))
    await state.set_state(AdminStates.waiting_for_vpn_key)


@router.message(StateFilter(AdminStates.waiting_for_vpn_key))
async def admin_add_vpn_key(message: Message, state: FSMContext):
    data = await state.get_data()
    vpn_date = data['vpn_date']
    vpn_key = message.text
    
    await db.add_vpn_key(vpn_date, vpn_key)
    
    await message.answer(
        f"✅ VPN-ключ от {vpn_date} добавлен!\n\n📢 Оповестить пользователей?",
        reply_markup=get_confirm_notify_keyboard("vpn")
    )
    await state.clear()


# ============ АДМИН: ПРОКСИ ============
@router.callback_query(F.data == "admin_proxy_menu")
async def admin_proxy_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "🛡️ Управление прокси:", reply_markup=get_admin_proxy_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_list_proxy")
async def admin_list_proxy(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    proxies = await db.get_all_proxies()
    if not proxies:
        text = "📋 Прокси пока нет."
    else:
        text = "📋 Список прокси:\n\n" + "\n".join([f"ID {p['id']}: {p['name']}" for p in proxies])
    
    await safe_edit_text(callback.message, text, reply_markup=get_back_keyboard("admin_proxy_menu"))
    await callback.answer()


@router.callback_query(F.data == "admin_add_proxy")
async def admin_add_proxy_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "🛡️ Введите название прокси:", reply_markup=get_back_keyboard("admin_proxy_menu"))
    await state.set_state(AdminStates.waiting_for_proxy_name)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_proxy_name))
async def admin_add_proxy_name(message: Message, state: FSMContext):
    await state.update_data(proxy_name=message.text)
    await message.answer("🔗 Теперь отправьте ссылку на прокси:", reply_markup=get_back_keyboard("admin_proxy_menu"))
    await state.set_state(AdminStates.waiting_for_proxy_url)


@router.message(StateFilter(AdminStates.waiting_for_proxy_url))
async def admin_add_proxy_url(message: Message, state: FSMContext):
    data = await state.get_data()
    proxy_name = data['proxy_name']
    proxy_url = message.text
    
    await db.add_proxy(proxy_name, proxy_url)
    
    await message.answer(
        f"✅ Прокси \"{proxy_name}\" добавлен!\n\n📢 Оповестить пользователей?",
        reply_markup=get_confirm_notify_keyboard("proxy")
    )
    await state.clear()


# ============ ПОДТВЕРЖДЕНИЕ РАССЫЛКИ ============
@router.callback_query(F.data.startswith("confirm_broadcast_"))
async def confirm_broadcast(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    broadcast_type = callback.data.split("_")[-1]
    
    if broadcast_type == "vpn":
        users = await db.get_users_with_vpn_notify()
        text = "🔔 Доступен новый VPN-ключ! Нажмите «🔌 VPN-ключи» чтобы посмотреть."
    else:
        users = await db.get_users_with_proxy_notify()
        text = "🛡️ Доступен новый прокси! Нажмите «🛡️ Прокси» чтобы подключить."
    
    if not users:
        await callback.answer("Нет пользователей с включёнными уведомлениями", show_alert=True)
        await safe_edit_text(callback.message, "⚙️ Админ-панель", reply_markup=get_admin_keyboard())
        return
    
    await callback.message.edit_text(f"📤 Рассылаю {len(users)} пользователям...")
    
    success = 0
    fail = 0
    
    for user_id in users:
        try:
            await callback.bot.send_message(chat_id=user_id, text=text)
            success += 1
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            fail += 1
        await asyncio.sleep(BROADCAST_DELAY)
    
    await db.add_broadcast_log(broadcast_type, success)
    
    await callback.message.edit_text(
        f"📊 Рассылка завершена!\n\n"
        f"Тип: {'VPN' if broadcast_type == 'vpn' else 'Прокси'}\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {fail}",
        reply_markup=get_back_keyboard("back_to_admin")
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "❌ Рассылка отменена.", reply_markup=get_back_keyboard("back_to_admin"))
    await callback.answer()


# ============ АДМИН: УДАЛЕНИЕ VPN ============
@router.callback_query(F.data == "admin_remove_vpn")
async def admin_remove_vpn_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    keys = await db.get_all_vpn_keys()
    if not keys:
        await safe_edit_text(callback.message, "❌ Нет ключей для удаления.", reply_markup=get_back_keyboard("admin_vpn_menu"))
        await callback.answer()
        return
    
    text = "📋 Выберите ID ключа:\n\n" + "\n".join([f"ID {k['id']}: {k['date']}" for k in keys])
    await safe_edit_text(callback.message, text + "\n\nВведите ID:", reply_markup=get_back_keyboard("admin_vpn_menu"))
    await state.set_state(AdminStates.waiting_for_vpn_remove_id)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_vpn_remove_id))
async def admin_remove_vpn_finish(message: Message, state: FSMContext):
    try:
        key_id = int(message.text)
        await db.remove_vpn_key(key_id)
        await message.answer(f"✅ Ключ ID {key_id} удалён!", reply_markup=get_back_keyboard("admin_vpn_menu"))
    except ValueError:
        await message.answer("❌ Введите число.", reply_markup=get_back_keyboard("admin_vpn_menu"))
    await state.clear()


# ============ АДМИН: УДАЛЕНИЕ ПРОКСИ ============
@router.callback_query(F.data == "admin_remove_proxy")
async def admin_remove_proxy_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    proxies = await db.get_all_proxies()
    if not proxies:
        await safe_edit_text(callback.message, "❌ Нет прокси для удаления.", reply_markup=get_back_keyboard("admin_proxy_menu"))
        await callback.answer()
        return
    
    text = "📋 Выберите ID прокси:\n\n" + "\n".join([f"ID {p['id']}: {p['name']}" for p in proxies])
    await safe_edit_text(callback.message, text + "\n\nВведите ID:", reply_markup=get_back_keyboard("admin_proxy_menu"))
    await state.set_state(AdminStates.waiting_for_proxy_remove_id)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_proxy_remove_id))
async def admin_remove_proxy_finish(message: Message, state: FSMContext):
    try:
        proxy_id = int(message.text)
        await db.remove_proxy(proxy_id)
        await message.answer(f"✅ Прокси ID {proxy_id} удалён!", reply_markup=get_back_keyboard("admin_proxy_menu"))
    except ValueError:
        await message.answer("❌ Введите число.", reply_markup=get_back_keyboard("admin_proxy_menu"))
    await state.clear()


# ============ АДМИН: СПОНСОРЫ ============
@router.callback_query(F.data == "admin_sponsors_menu")
async def admin_sponsors_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "📢 Управление спонсорами:", reply_markup=get_admin_sponsors_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_list_sponsors")
async def admin_list_sponsors(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    sponsors = await db.get_sponsors()
    if not sponsors:
        text = "📋 Спонсоров пока нет."
    else:
        text = "📋 Список спонсоров:\n\n" + "\n".join([f"• {s}" for s in sponsors])
    
    await safe_edit_text(callback.message, text, reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await callback.answer()


@router.callback_query(F.data == "admin_add_sponsor")
async def admin_add_sponsor_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message,
        "📢 Отправьте username канала (например: @sponsor):",
        reply_markup=get_back_keyboard("admin_sponsors_menu")
    )
    await state.set_state(AdminStates.waiting_for_sponsor_add)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_sponsor_add))
async def admin_add_sponsor_finish(message: Message, state: FSMContext):
    username = message.text.strip()
    if not username.startswith('@'):
        username = '@' + username
    await db.add_sponsor(username)
    await message.answer(f"✅ Спонсор {username} добавлен!", reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await state.clear()


@router.callback_query(F.data == "admin_remove_sponsor")
async def admin_remove_sponsor_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    sponsors = await db.get_sponsors()
    if not sponsors:
        await safe_edit_text(callback.message, "❌ Нет спонсоров.", reply_markup=get_back_keyboard("admin_sponsors_menu"))
        await callback.answer()
        return
    
    text = "📋 Список спонсоров:\n\n" + "\n".join([f"• {s}" for s in sponsors])
    await safe_edit_text(callback.message, text + "\n\nОтправьте username для удаления:", reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await state.set_state(AdminStates.waiting_for_sponsor_remove)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_sponsor_remove))
async def admin_remove_sponsor_finish(message: Message, state: FSMContext):
    username = message.text.strip()
    if not username.startswith('@'):
        username = '@' + username
    await db.remove_sponsor(username)
    await message.answer(f"✅ Спонсор {username} удалён!", reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await state.clear()


# ============ АДМИН: ЧЁРНЫЙ СПИСОК ============
@router.callback_query(F.data == "admin_blacklist_menu")
async def admin_blacklist_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "🚫 Управление чёрным списком:", reply_markup=get_admin_blacklist_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_blacklist_list")
async def admin_blacklist_list(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    blacklist = await db.get_blacklist()
    if not blacklist:
        text = "📋 Чёрный список пуст."
    else:
        text = "📋 Чёрный список:\n\n" + "\n".join([f"• ID: {uid}" for uid in blacklist])
    
    await safe_edit_text(callback.message, text, reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await callback.answer()


@router.callback_query(F.data == "admin_blacklist_add")
async def admin_blacklist_add_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "🚫 Введите ID пользователя для добавления в ЧС:", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await state.set_state(AdminStates.waiting_for_blacklist_add)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_blacklist_add))
async def admin_blacklist_add_finish(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
        await db.add_to_blacklist(user_id)
        await message.answer(f"✅ Пользователь {user_id} добавлен в ЧС!", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    except ValueError:
        await message.answer("❌ Введите корректный ID.", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await state.clear()


@router.callback_query(F.data == "admin_blacklist_remove")
async def admin_blacklist_remove_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    blacklist = await db.get_blacklist()
    if not blacklist:
        await safe_edit_text(callback.message, "❌ ЧС пуст.", reply_markup=get_back_keyboard("admin_blacklist_menu"))
        await callback.answer()
        return
    
    await safe_edit_text(callback.message, "🚫 Введите ID пользователя для удаления из ЧС:", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await state.set_state(AdminStates.waiting_for_blacklist_remove)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_blacklist_remove))
async def admin_blacklist_remove_finish(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
        await db.remove_from_blacklist(user_id)
        await message.answer(f"✅ Пользователь {user_id} удалён из ЧС!", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    except ValueError:
        await message.answer("❌ Введите корректный ID.", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await state.clear()


# ============ АДМИН: ОБРАЩЕНИЯ ============
@router.callback_query(F.data == "admin_support_menu")
async def admin_support_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "🆘 Управление обращениями:", reply_markup=get_admin_support_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_support_list")
async def admin_support_list(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    messages = await db.get_support_messages()
    if not messages:
        text = "📨 Обращений пока нет."
        reply_markup = get_back_keyboard("admin_support_menu")
    else:
        text = "📨 Обращения в поддержку:\n\n"
        reply_builder = InlineKeyboardBuilder()
        for i, msg in enumerate(messages):
            status = "✅" if msg['replied'] else "❌"
            text += f"{i}. {status} @{msg['username']} ({msg['timestamp']})\n   💬 {msg['message'][:100]}\n\n"
            if not msg['replied']:
                reply_builder.row(InlineKeyboardButton(
                    text=f"💬 Ответить на #{i}",
                    callback_data=f"reply_support_{msg['id']}"
                ))
        reply_builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_support_menu"))
        reply_markup = reply_builder.as_markup()
    
    await safe_edit_text(callback.message, text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data.startswith("reply_support_"))
async def reply_support_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    msg_id = int(callback.data.split("_")[-1])
    messages = await db.get_support_messages()
    msg = None
    for m in messages:
        if m['id'] == msg_id:
            msg = m
            break
    
    if not msg:
        await callback.answer("Обращение не найдено", show_alert=True)
        return
    
    await state.update_data(reply_msg_id=msg['id'], reply_user_id=msg['user_id'], reply_username=msg['username'])
    await safe_edit_text(callback.message,
        f"📨 Обращение от @{msg['username']}:\n\n💬 {msg['message']}\n\nВведите ваш ответ:",
        reply_markup=get_back_keyboard("admin_support_menu")
    )
    await state.set_state(AdminReplyStates.waiting_for_support_reply_text)
    await callback.answer()


@router.message(StateFilter(AdminReplyStates.waiting_for_support_reply_text))
async def support_reply_send(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        await message.bot.send_message(chat_id=data['reply_user_id'], text=f"📩 Ответ от поддержки:\n\n{message.text}")
        await db.mark_support_replied(data['reply_msg_id'])
        await message.answer(f"✅ Ответ отправлен пользователю @{data['reply_username']}!", reply_markup=get_back_keyboard("admin_support_menu"))
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}", reply_markup=get_back_keyboard("admin_support_menu"))
    await state.clear()


@router.callback_query(F.data == "admin_ad_list")
async def admin_ad_list(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    messages = await db.get_ad_messages()
    if not messages:
        text = "📢 Заявок пока нет."
        reply_markup = get_back_keyboard("admin_support_menu")
    else:
        text = "📢 Заявки на рекламу:\n\n"
        reply_builder = InlineKeyboardBuilder()
        for i, msg in enumerate(messages):
            status = "✅" if msg['replied'] else "❌"
            text += f"{i}. {status} @{msg['username']} ({msg['timestamp']})\n   💬 {msg['message'][:100]}\n\n"
            if not msg['replied']:
                reply_builder.row(InlineKeyboardButton(
                    text=f"💬 Ответить на #{i}",
                    callback_data=f"reply_ad_{msg['id']}"
                ))
        reply_builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_support_menu"))
        reply_markup = reply_builder.as_markup()
    
    await safe_edit_text(callback.message, text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data.startswith("reply_ad_"))
async def reply_ad_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    msg_id = int(callback.data.split("_")[-1])
    messages = await db.get_ad_messages()
    msg = None
    for m in messages:
        if m['id'] == msg_id:
            msg = m
            break
    
    if not msg:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    
    await state.update_data(reply_msg_id=msg['id'], reply_user_id=msg['user_id'], reply_username=msg['username'])
    await safe_edit_text(callback.message,
        f"📢 Заявка от @{msg['username']}:\n\n💬 {msg['message']}\n\nВведите ваш ответ:",
        reply_markup=get_back_keyboard("admin_support_menu")
    )
    await state.set_state(AdminReplyStates.waiting_for_ad_reply_text)
    await callback.answer()


@router.message(StateFilter(AdminReplyStates.waiting_for_ad_reply_text))
async def ad_reply_send(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        await message.bot.send_message(chat_id=data['reply_user_id'], text=f"📩 Ответ от администратора:\n\n{message.text}")
        await db.mark_ad_replied(data['reply_msg_id'])
        await message.answer(f"✅ Ответ отправлен пользователю @{data['reply_username']}!", reply_markup=get_back_keyboard("admin_support_menu"))
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}", reply_markup=get_back_keyboard("admin_support_menu"))
    await state.clear()


# ============ АДМИН: РАССЫЛКА ВСЕМ ============
@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    count = await db.get_users_count()
    await safe_edit_text(callback.message, f"📨 Введите сообщение для рассылки ({count} чел.):", reply_markup=get_back_keyboard("back_to_admin"))
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_broadcast))
async def admin_broadcast_send(message: Message, state: FSMContext):
    users = await db.get_all_users()
    blacklist = await db.get_blacklist()
    
    success = 0
    fail = 0
    
    await message.answer("📤 Начинаю рассылку...")
    
    for user_id in users:
        if user_id in blacklist:
            continue
        try:
            await message.bot.send_message(chat_id=user_id, text=message.text)
            success += 1
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            fail += 1
        await asyncio.sleep(BROADCAST_DELAY)
    
    await db.add_broadcast_log("manual", success)
    await message.answer(
        f"📊 Рассылка завершена!\n\n✅ Успешно: {success}\n❌ Ошибок: {fail}",
        reply_markup=get_back_keyboard("back_to_admin")
    )
    await state.clear()


# ============ АДМИН: РАССЫЛКА ПО ID ============
@router.callback_query(F.data == "admin_broadcast_id")
async def admin_broadcast_id_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "📩 Введите ID пользователя:", reply_markup=get_back_keyboard("back_to_admin"))
    await state.set_state(AdminStates.waiting_for_broadcast_id)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_broadcast_id))
async def admin_broadcast_id_user(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
        await state.update_data(broadcast_user_id=user_id)
        await message.answer(f"📝 Введите текст для пользователя {user_id}:", reply_markup=get_back_keyboard("back_to_admin"))
        await state.set_state(AdminStates.waiting_for_broadcast_id_text)
    except ValueError:
        await message.answer("❌ Введите корректный ID.", reply_markup=get_back_keyboard("back_to_admin"))


@router.message(StateFilter(AdminStates.waiting_for_broadcast_id_text))
async def admin_broadcast_id_send(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data['broadcast_user_id']
    try:
        await message.bot.send_message(chat_id=user_id, text=message.text)
        await message.answer(f"✅ Сообщение отправлено пользователю {user_id}!", reply_markup=get_back_keyboard("back_to_admin"))
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=get_back_keyboard("back_to_admin"))
    await state.clear()


# ============ АДМИН: СТАТИСТИКА ============
@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    stats = await db.get_stats()
    channels = await db.get_channels_to_check()
    
    await safe_edit_text(callback.message,
        f"📊 Статистика бота:\n\n"
        f"👥 Пользователей: {stats['users']}\n"
        f"🚫 ЧС: {stats['blacklist']}\n"
        f"🔑 VPN-ключей: {stats['vpn_keys']}\n"
        f"🛡️ Прокси: {stats['proxy_count']}\n"
        f"📢 Спонсоров: {len(stats['sponsors'])}\n"
        f"📨 Рассылок: {stats['broadcast_count']}\n\n"
        f"🆘 Поддержка: {stats['support_count']} (не отвечено: {stats['support_unreplied']})\n"
        f"📢 Реклама: {stats['ad_count']} (не отвечено: {stats['ad_unreplied']})\n\n"
        f"📋 Каналы:\n" + "\n".join([f"• {ch}" for ch in channels]),
        reply_markup=get_back_keyboard("back_to_admin")
    )
    await callback.answer()


# ============ ЗАГЛУШКА ============
@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
