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

import database as db
from config import ADMIN_IDS, BROADCAST_DELAY
from keyboards import (
    MENU_TEXT, get_main_menu_keyboard,
    get_check_subscription_keyboard,
    get_vpn_page_keyboard, get_vpn_key_detail_keyboard,
    get_proxy_page_keyboard,
    get_comment_skip_keyboard, get_vless_skip_keyboard,
    get_settings_keyboard,
    get_first_time_vpn_keyboard, get_first_time_proxy_keyboard,
    get_admin_keyboard,
    get_admin_vpn_menu_keyboard, get_admin_proxy_menu_keyboard,
    get_admin_sponsors_keyboard, get_admin_blacklist_keyboard,
    get_admin_support_menu_keyboard,
    get_admin_broadcast_menu_keyboard, get_admin_autodelete_menu_keyboard,
    get_support_reply_list_keyboard, get_ad_reply_list_keyboard,
    get_back_keyboard, get_confirm_notify_keyboard,
    get_admin_notify_reply_keyboard
)

logger = logging.getLogger(__name__)
router = Router()


# ============ FSM STATES ============
class AdminStates(StatesGroup):
    waiting_for_vpn_key = State()
    waiting_for_vpn_comment = State()
    waiting_for_vpn_vless = State()
    waiting_for_vpn_remove_id = State()
    waiting_for_proxy_name = State()
    waiting_for_proxy_url = State()
    waiting_for_proxy_remove_id = State()
    waiting_for_sponsor_add = State()
    waiting_for_sponsor_remove = State()
    waiting_for_blacklist_add = State()
    waiting_for_blacklist_remove = State()
    waiting_for_broadcast_all = State()
    waiting_for_broadcast_id = State()
    waiting_for_broadcast_id_text = State()
    waiting_for_vpn_autodelete_days = State()
    waiting_for_proxy_autodelete_days = State()


class UserStates(StatesGroup):
    waiting_for_support_message = State()
    waiting_for_ad_message = State()
    waiting_first_time = State()


class AdminReplyStates(StatesGroup):
    waiting_for_support_reply_select = State()
    waiting_for_support_reply_text = State()
    waiting_for_ad_reply_select = State()
    waiting_for_ad_reply_text = State()


# ============ HELPERS ============

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
            logger.error(f"Check sub error {channel}: {e}")
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
            f"• Бесплатные VPN-ключи и proxy для Telegram.\n\n"
            f"⚠️ Для использования подпишитесь на каналы:\n\n"
            f"{channels_list}\n\n"
            f"Подпишитесь и нажмите кнопку проверки:",
            reply_markup=get_check_subscription_keyboard(channels)
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if user is None:
        await db.add_user(message.from_user.id, message.from_user.username or f"id{message.from_user.id}")
        await message.answer(
            "🔔 Хотите получать уведомления о новых VPN-ключах?",
            reply_markup=get_first_time_vpn_keyboard()
        )
        await state.set_state(UserStates.waiting_first_time)
        await state.update_data(first_step="vpn")
    else:
        await message.answer(MENU_TEXT, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)


# ============ FIRST TIME SETUP ============
@router.callback_query(StateFilter(UserStates.waiting_first_time), F.data.startswith("first_vpn_"))
async def process_first_vpn(callback: CallbackQuery, state: FSMContext):
    vpn_notify = callback.data == "first_vpn_yes"
    await db.set_vpn_notify(callback.from_user.id, vpn_notify)
    await safe_edit_text(callback.message,
        "🔔 Хотите получать уведомления о новых proxy?",
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


# ============ CHECK SUB ============
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


# ============ BACK TO MAIN ============
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
    key = next((k for k in all_keys if k['id'] == key_id), None)
    if not key:
        await callback.answer("Ключ не найден", show_alert=True)
        return
    
    key_text = f"`{key['key']}`"
    comment = key.get('comment', 'Отсутствует')
    
    await safe_edit_text(callback.message,
        f"🔐 Ключ от {key['date']}\n"
        f"💬 Комментарий: {comment}\n\n"
        f"{key_text}\n\n"
        f"⚠️ Нажмите на ключ, чтобы скопировать.",
        reply_markup=get_vpn_key_detail_keyboard(key), parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vless_"))
async def process_vless(callback: CallbackQuery):
    key_id = int(callback.data.split("_")[-1])
    all_keys = await db.get_all_vpn_keys()
    key = next((k for k in all_keys if k['id'] == key_id), None)
    if not key or not key.get('vless'):
        await callback.answer("VLESS не найден", show_alert=True)
        return
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    vless_text = f"`{key['vless']}`"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад к ключу", callback_data=f"vpnkey_{key_id}"))
    await safe_edit_text(callback.message,
        f"🔗 VLESS от {key['date']}:\n\n{vless_text}\n\n⚠️ Нажмите, чтобы скопировать.",
        reply_markup=builder.as_markup(), parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


# ============ PROXY ============
@router.callback_query(F.data == "proxy")
async def process_proxy(callback: CallbackQuery):
    if await db.is_blacklisted(callback.from_user.id):
        await callback.message.edit_text("🚫 Вы заблокированы.")
        await callback.answer()
        return
    
    proxies, total = await db.get_proxy_page(page=1)
    if not proxies:
        await safe_edit_text(callback.message, "🛡️ Пока нет proxy.", reply_markup=get_back_keyboard("back_to_main"))
        await callback.answer()
        return
    
    await safe_edit_text(callback.message, "🛡️ Выберите proxy (нажмите для подключения):", reply_markup=get_proxy_page_keyboard(proxies, total, page=1))
    await callback.answer()


@router.callback_query(F.data.startswith("proxy_page_"))
async def process_proxy_page(callback: CallbackQuery):
    page = int(callback.data.split("_")[-1])
    proxies, total = await db.get_proxy_page(page=page)
    if not proxies:
        await callback.answer("Страница пуста", show_alert=True)
        return
    await safe_edit_text(callback.message, "🛡️ Выберите proxy:", reply_markup=get_proxy_page_keyboard(proxies, total, page=page))
    await callback.answer()


# ============ INSTRUCTION ============
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
        "2. В боте нажмите «🔌 Подключиться» и выберите актуальный ключ\n\n"
        "3. Скопируйте ключ — просто нажмите на него\n\n"
        "4. В программе нажмите «Добавить сервер» → вставьте скопированную ссылку\n\n"
        "5. Готово! Подключайтесь и пользуйтесь 🎉\n\n"
        "📅 Обновление ключей:\n"
        "• Новые ключи публикуются каждый день\n"
        "• Старые ключи постепенно удаляются\n\n"
        "💬 Вопросы? Жмите «🆘 Поддержка»",
        reply_markup=get_back_keyboard("back_to_main")
    )
    await callback.answer()


# ============ SETTINGS ============
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
    
    await safe_edit_text(callback.message, "⚙️ Настройки уведомлений:", 
        reply_markup=get_settings_keyboard(
            user.get('vpn_notify', False) if user else False,
            user.get('proxy_notify', False) if user else False
        ))
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
    await safe_edit_text(callback.message, "⚙️ Настройки уведомлений:",
        reply_markup=get_settings_keyboard(
            user.get('vpn_notify', False),
            user.get('proxy_notify', False)
        ))
    await callback.answer(f"VPN: {'✅' if new_value else '❌'}")


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
    await safe_edit_text(callback.message, "⚙️ Настройки уведомлений:",
        reply_markup=get_settings_keyboard(
            user.get('vpn_notify', False),
            user.get('proxy_notify', False)
        ))
    await callback.answer(f"Proxy: {'✅' if new_value else '❌'}")


# ============ SUPPORT ============
@router.callback_query(F.data == "support")
async def process_support(callback: CallbackQuery, state: FSMContext):
    if await db.is_blacklisted(callback.from_user.id):
        await callback.message.edit_text("🚫 Вы заблокированы.")
        await callback.answer()
        return
    await safe_edit_text(callback.message,
        "🆘 Поддержка\n\nОпишите вашу проблему как можно подробнее.\nОтправьте одно сообщение, и я передам его администратору.",
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
        message=message.text, timestamp=timestamp
    )
    
    messages = await db.get_support_messages()
    msg_id = messages[0]['id'] if messages else 0
    
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                chat_id=admin_id,
                text=f"📨 Новое обращение!\n\n👤 @{message.from_user.username or 'нет'} (ID: {message.from_user.id})\n🕒 {timestamp}\n\n💬 {message.text}",
                reply_markup=get_admin_notify_reply_keyboard(msg_id, "support")
            )
        except Exception as e:
            logger.error(f"Notify admin {admin_id}: {e}")
    
    await message.answer("✅ Отправлено!", reply_markup=get_back_keyboard("back_to_main"))
    await state.clear()


# ============ AD ============
@router.callback_query(F.data == "ad")
async def process_ad(callback: CallbackQuery, state: FSMContext):
    if await db.is_blacklisted(callback.from_user.id):
        await callback.message.edit_text("🚫 Вы заблокированы.")
        await callback.answer()
        return
    await safe_edit_text(callback.message,
        "📢 Реклама\n\nОпишите ваше предложение или вопрос по рекламе.\nОтправьте одно сообщение, и я передам его администратору.",
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
        message=message.text, timestamp=timestamp
    )
    
    messages = await db.get_ad_messages()
    msg_id = messages[0]['id'] if messages else 0
    
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                chat_id=admin_id,
                text=f"📢 Новая заявка!\n\n👤 @{message.from_user.username or 'нет'} (ID: {message.from_user.id})\n🕒 {timestamp}\n\n💬 {message.text}",
                reply_markup=get_admin_notify_reply_keyboard(msg_id, "ad")
            )
        except Exception as e:
            logger.error(f"Notify admin {admin_id}: {e}")
    
    await message.answer("✅ Отправлено!", reply_markup=get_back_keyboard("back_to_main"))
    await state.clear()


# ============ ADMIN ============
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа.")
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


# ============ ADMIN: VPN ============
@router.callback_query(F.data == "admin_vpn_menu")
async def admin_vpn_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "🔑 VPN:", reply_markup=get_admin_vpn_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_list_vpn")
async def admin_list_vpn(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    keys = await db.get_all_vpn_keys()
    text = "📋 VPN:\n\n" + "\n".join([f"ID {k['id']}: {k['date']}" for k in keys]) if keys else "📋 Пусто."
    await safe_edit_text(callback.message, text, reply_markup=get_back_keyboard("admin_vpn_menu"))
    await callback.answer()

@router.callback_query(F.data == "admin_add_vpn")
async def admin_add_vpn_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "🔑 Отправьте ключ:", reply_markup=get_back_keyboard("admin_vpn_menu"))
    await state.set_state(AdminStates.waiting_for_vpn_key)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_vpn_key))
async def admin_add_vpn_key(message: Message, state: FSMContext):
    await state.update_data(vpn_key=message.text)
    await message.answer("💬 Добавить комментарий?", reply_markup=get_comment_skip_keyboard())
    await state.set_state(AdminStates.waiting_for_vpn_comment)

@router.callback_query(StateFilter(AdminStates.waiting_for_vpn_comment), F.data == "add_comment")
async def admin_add_vpn_comment_start(callback: CallbackQuery, state: FSMContext):
    await safe_edit_text(callback.message, "✏️ Введите комментарий:", reply_markup=get_back_keyboard("admin_vpn_menu"))
    await state.set_state(AdminStates.waiting_for_vpn_comment)

@router.message(StateFilter(AdminStates.waiting_for_vpn_comment))
async def admin_add_vpn_comment_text(message: Message, state: FSMContext):
    await state.update_data(vpn_comment=message.text)
    await message.answer("🔗 Отправьте VLESS-ссылку:", reply_markup=get_vless_skip_keyboard())
    await state.set_state(AdminStates.waiting_for_vpn_vless)

@router.callback_query(StateFilter(AdminStates.waiting_for_vpn_comment), F.data == "skip_comment")
async def admin_add_vpn_skip_comment(callback: CallbackQuery, state: FSMContext):
    await state.update_data(vpn_comment="Отсутствует")
    await safe_edit_text(callback.message, "🔗 Отправьте VLESS-ссылку:", reply_markup=get_vless_skip_keyboard())
    await state.set_state(AdminStates.waiting_for_vpn_vless)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_vpn_vless))
async def admin_add_vpn_vless_text(message: Message, state: FSMContext):
    data = await state.get_data()
    date_str = datetime.now().strftime("%d.%m.%Y | %H:%M")
    await db.add_vpn_key(date_str, data['vpn_key'], data.get('vpn_comment', 'Отсутствует'), message.text)
    await message.answer(f"✅ VPN добавлен! ({date_str})\n\nОповестить?", reply_markup=get_confirm_notify_keyboard("vpn"))
    await state.clear()

@router.callback_query(StateFilter(AdminStates.waiting_for_vpn_vless), F.data == "skip_vless")
async def admin_add_vpn_skip_vless(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    date_str = datetime.now().strftime("%d.%m.%Y | %H:%M")
    await db.add_vpn_key(date_str, data['vpn_key'], data.get('vpn_comment', 'Отсутствует'))
    await safe_edit_text(callback.message, f"✅ VPN добавлен! ({date_str})\n\nОповестить?", reply_markup=get_confirm_notify_keyboard("vpn"))
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "admin_remove_vpn")
async def admin_remove_vpn_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    keys = await db.get_all_vpn_keys()
    if not keys:
        await safe_edit_text(callback.message, "❌ Нет ключей.", reply_markup=get_back_keyboard("admin_vpn_menu"))
        await callback.answer(); return
    text = "📋 ID ключа:\n\n" + "\n".join([f"ID {k['id']}: {k['date']}" for k in keys])
    await safe_edit_text(callback.message, text + "\n\nВведите ID:", reply_markup=get_back_keyboard("admin_vpn_menu"))
    await state.set_state(AdminStates.waiting_for_vpn_remove_id)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_vpn_remove_id))
async def admin_remove_vpn_finish(message: Message, state: FSMContext):
    try:
        await db.remove_vpn_key(int(message.text))
        await message.answer("✅ Удалён!", reply_markup=get_back_keyboard("admin_vpn_menu"))
    except ValueError:
        await message.answer("❌ Число.", reply_markup=get_back_keyboard("admin_vpn_menu"))
    await state.clear()


# ============ ADMIN: PROXY ============
@router.callback_query(F.data == "admin_proxy_menu")
async def admin_proxy_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "🛡️ Proxy:", reply_markup=get_admin_proxy_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_list_proxy")
async def admin_list_proxy(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    proxies = await db.get_all_proxies()
    text = "📋 Proxy:\n\n" + "\n".join([f"ID {p['id']}: {p['name']}" for p in proxies]) if proxies else "📋 Пусто."
    await safe_edit_text(callback.message, text, reply_markup=get_back_keyboard("admin_proxy_menu"))
    await callback.answer()

@router.callback_query(F.data == "admin_add_proxy")
async def admin_add_proxy_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "🛡️ Название:", reply_markup=get_back_keyboard("admin_proxy_menu"))
    await state.set_state(AdminStates.waiting_for_proxy_name)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_proxy_name))
async def admin_add_proxy_name(message: Message, state: FSMContext):
    await state.update_data(proxy_name=message.text)
    await message.answer("🔗 Ссылка:", reply_markup=get_back_keyboard("admin_proxy_menu"))
    await state.set_state(AdminStates.waiting_for_proxy_url)

@router.message(StateFilter(AdminStates.waiting_for_proxy_url))
async def admin_add_proxy_url(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_proxy(data['proxy_name'], message.text)
    await message.answer(f"✅ Proxy добавлен!\n\nОповестить?", reply_markup=get_confirm_notify_keyboard("proxy"))
    await state.clear()

@router.callback_query(F.data == "admin_remove_proxy")
async def admin_remove_proxy_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    proxies = await db.get_all_proxies()
    if not proxies:
        await safe_edit_text(callback.message, "❌ Нет proxy.", reply_markup=get_back_keyboard("admin_proxy_menu"))
        await callback.answer(); return
    text = "📋 ID:\n\n" + "\n".join([f"ID {p['id']}: {p['name']}" for p in proxies])
    await safe_edit_text(callback.message, text + "\n\nВведите ID:", reply_markup=get_back_keyboard("admin_proxy_menu"))
    await state.set_state(AdminStates.waiting_for_proxy_remove_id)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_proxy_remove_id))
async def admin_remove_proxy_finish(message: Message, state: FSMContext):
    try:
        await db.remove_proxy(int(message.text))
        await message.answer("✅ Удалён!", reply_markup=get_back_keyboard("admin_proxy_menu"))
    except ValueError:
        await message.answer("❌ Число.", reply_markup=get_back_keyboard("admin_proxy_menu"))
    await state.clear()


# ============ ADMIN: SPONSORS ============
@router.callback_query(F.data == "admin_sponsors_menu")
async def admin_sponsors_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "📢 Спонсоры:", reply_markup=get_admin_sponsors_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_list_sponsors")
async def admin_list_sponsors(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    sponsors = await db.get_sponsors()
    text = "📋 Спонсоры:\n\n" + "\n".join([f"• {s}" for s in sponsors]) if sponsors else "📋 Пусто."
    await safe_edit_text(callback.message, text, reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await callback.answer()

@router.callback_query(F.data == "admin_add_sponsor")
async def admin_add_sponsor_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "📢 Username:", reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await state.set_state(AdminStates.waiting_for_sponsor_add)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_sponsor_add))
async def admin_add_sponsor_finish(message: Message, state: FSMContext):
    username = message.text.strip()
    if not username.startswith('@'): username = '@' + username
    await db.add_sponsor(username)
    await message.answer(f"✅ {username} добавлен!", reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await state.clear()

@router.callback_query(F.data == "admin_remove_sponsor")
async def admin_remove_sponsor_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    sponsors = await db.get_sponsors()
    if not sponsors:
        await safe_edit_text(callback.message, "❌ Пусто.", reply_markup=get_back_keyboard("admin_sponsors_menu"))
        await callback.answer(); return
    text = "📋\n\n" + "\n".join([f"• {s}" for s in sponsors])
    await safe_edit_text(callback.message, text + "\n\nUsername:", reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await state.set_state(AdminStates.waiting_for_sponsor_remove)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_sponsor_remove))
async def admin_remove_sponsor_finish(message: Message, state: FSMContext):
    username = message.text.strip()
    if not username.startswith('@'): username = '@' + username
    await db.remove_sponsor(username)
    await message.answer(f"✅ {username} удалён!", reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await state.clear()


# ============ ADMIN: BLACKLIST ============
@router.callback_query(F.data == "admin_blacklist_menu")
async def admin_blacklist_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "🚫 Чёрный список:", reply_markup=get_admin_blacklist_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_blacklist_list")
async def admin_blacklist_list(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    bl = await db.get_blacklist()
    text = "📋 Чёрный список:\n\n" + "\n".join([f"• ID: {uid}" for uid in bl]) if bl else "📋 Пусто."
    await safe_edit_text(callback.message, text, reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await callback.answer()

@router.callback_query(F.data == "admin_blacklist_add")
async def admin_blacklist_add_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "🚫 ID:", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await state.set_state(AdminStates.waiting_for_blacklist_add)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_blacklist_add))
async def admin_blacklist_add_finish(message: Message, state: FSMContext):
    try:
        await db.add_to_blacklist(int(message.text))
        await message.answer("✅ Добавлен!", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    except ValueError:
        await message.answer("❌ ID.", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await state.clear()

@router.callback_query(F.data == "admin_blacklist_remove")
async def admin_blacklist_remove_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    bl = await db.get_blacklist()
    if not bl:
        await safe_edit_text(callback.message, "❌ Пусто.", reply_markup=get_back_keyboard("admin_blacklist_menu"))
        await callback.answer(); return
    await safe_edit_text(callback.message, "🚫 ID:", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await state.set_state(AdminStates.waiting_for_blacklist_remove)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_blacklist_remove))
async def admin_blacklist_remove_finish(message: Message, state: FSMContext):
    try:
        await db.remove_from_blacklist(int(message.text))
        await message.answer("✅ Удалён!", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    except ValueError:
        await message.answer("❌ ID.", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await state.clear()


# ============ ADMIN: SUPPORT LIST ============
@router.callback_query(F.data == "admin_support_menu")
async def admin_support_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "🆘 Обращения:", reply_markup=get_admin_support_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_support_list")
async def admin_support_list(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    messages = await db.get_support_messages()
    if not messages:
        await safe_edit_text(callback.message, "📨 Пусто.", reply_markup=get_back_keyboard("admin_support_menu"))
        await callback.answer(); return
    text = "📨 Поддержка:\n\n"
    for i, msg in enumerate(messages):
        status = "✅" if msg['replied'] else "❌"
        text += f"{i}. {status} @{msg['username']} ({msg['timestamp']})\n   💬 {msg['message'][:100]}\n\n"
    await safe_edit_text(callback.message, text, reply_markup=get_support_reply_list_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_support_reply")
async def admin_support_reply_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "📝 Номер:", reply_markup=get_back_keyboard("admin_support_menu"))
    await state.set_state(AdminReplyStates.waiting_for_support_reply_select)
    await callback.answer()

@router.message(StateFilter(AdminReplyStates.waiting_for_support_reply_select))
async def admin_support_reply_select(message: Message, state: FSMContext):
    try:
        idx = int(message.text)
        messages = await db.get_support_messages()
        if 0 <= idx < len(messages):
            msg = messages[idx]
            await state.update_data(reply_index=msg['id'], reply_user_id=msg['user_id'], reply_username=msg['username'])
            await message.answer(f"📨 @{msg['username']}:\n\n{msg['message']}\n\nОтвет:", reply_markup=get_back_keyboard("admin_support_menu"))
            await state.set_state(AdminReplyStates.waiting_for_support_reply_text)
        else:
            await message.answer("❌ Номер.", reply_markup=get_back_keyboard("admin_support_menu"))
    except ValueError:
        await message.answer("❌ Число.", reply_markup=get_back_keyboard("admin_support_menu"))

@router.message(StateFilter(AdminReplyStates.waiting_for_support_reply_text))
async def admin_support_reply_send(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        await message.bot.send_message(data['reply_user_id'], f"📩 Ответ от поддержки:\n\n{message.text}")
        await db.mark_support_replied(data['reply_index'])
        await message.answer("✅ Отправлен!", reply_markup=get_back_keyboard("admin_support_menu"))
    except Exception as e:
        await message.answer(f"❌ {e}", reply_markup=get_back_keyboard("admin_support_menu"))
    await state.clear()


# ============ ADMIN: AD LIST ============
@router.callback_query(F.data == "admin_ad_list")
async def admin_ad_list(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    messages = await db.get_ad_messages()
    if not messages:
        await safe_edit_text(callback.message, "📢 Пусто.", reply_markup=get_back_keyboard("admin_support_menu"))
        await callback.answer(); return
    text = "📢 Реклама:\n\n"
    for i, msg in enumerate(messages):
        status = "✅" if msg['replied'] else "❌"
        text += f"{i}. {status} @{msg['username']} ({msg['timestamp']})\n   💬 {msg['message'][:100]}\n\n"
    await safe_edit_text(callback.message, text, reply_markup=get_ad_reply_list_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_ad_reply")
async def admin_ad_reply_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "📝 Номер:", reply_markup=get_back_keyboard("admin_support_menu"))
    await state.set_state(AdminReplyStates.waiting_for_ad_reply_select)
    await callback.answer()

@router.message(StateFilter(AdminReplyStates.waiting_for_ad_reply_select))
async def admin_ad_reply_select(message: Message, state: FSMContext):
    try:
        idx = int(message.text)
        messages = await db.get_ad_messages()
        if 0 <= idx < len(messages):
            msg = messages[idx]
            await state.update_data(reply_index=msg['id'], reply_user_id=msg['user_id'], reply_username=msg['username'])
            await message.answer(f"📢 @{msg['username']}:\n\n{msg['message']}\n\nОтвет:", reply_markup=get_back_keyboard("admin_support_menu"))
            await state.set_state(AdminReplyStates.waiting_for_ad_reply_text)
        else:
            await message.answer("❌ Номер.", reply_markup=get_back_keyboard("admin_support_menu"))
    except ValueError:
        await message.answer("❌ Число.", reply_markup=get_back_keyboard("admin_support_menu"))

@router.message(StateFilter(AdminReplyStates.waiting_for_ad_reply_text))
async def admin_ad_reply_send(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        await message.bot.send_message(data['reply_user_id'], f"📩 Ответ от администратора:\n\n{message.text}")
        await db.mark_ad_replied(data['reply_index'])
        await message.answer("✅ Отправлен!", reply_markup=get_back_keyboard("admin_support_menu"))
    except Exception as e:
        await message.answer(f"❌ {e}", reply_markup=get_back_keyboard("admin_support_menu"))
    await state.clear()


# ============ REPLY FROM LS ============
@router.callback_query(F.data.startswith("reply_support_"))
async def reply_support_from_ls(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    msg_id = int(callback.data.split("_")[-1])
    messages = await db.get_support_messages()
    msg = next((m for m in messages if m['id'] == msg_id), None)
    if not msg:
        await callback.answer("Не найдено", show_alert=True); return
    await state.update_data(reply_index=msg['id'], reply_user_id=msg['user_id'], reply_username=msg['username'])
    await callback.message.answer(f"📨 @{msg['username']}:\n\n{msg['message']}\n\nОтвет:", reply_markup=get_back_keyboard("admin_support_menu"))
    await state.set_state(AdminReplyStates.waiting_for_support_reply_text)
    await callback.answer()

@router.callback_query(F.data.startswith("reply_ad_"))
async def reply_ad_from_ls(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    msg_id = int(callback.data.split("_")[-1])
    messages = await db.get_ad_messages()
    msg = next((m for m in messages if m['id'] == msg_id), None)
    if not msg:
        await callback.answer("Не найдено", show_alert=True); return
    await state.update_data(reply_index=msg['id'], reply_user_id=msg['user_id'], reply_username=msg['username'])
    await callback.message.answer(f"📢 @{msg['username']}:\n\n{msg['message']}\n\nОтвет:", reply_markup=get_back_keyboard("admin_support_menu"))
    await state.set_state(AdminReplyStates.waiting_for_ad_reply_text)
    await callback.answer()


# ============ ADMIN: BROADCAST ============
@router.callback_query(F.data == "admin_broadcast_menu")
async def admin_broadcast_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "📨 Рассылка:", reply_markup=get_admin_broadcast_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_broadcast_all")
async def admin_broadcast_all_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    count = await db.get_users_count()
    await safe_edit_text(callback.message, f"📨 Текст ({count} чел.):", reply_markup=get_back_keyboard("admin_broadcast_menu"))
    await state.set_state(AdminStates.waiting_for_broadcast_all)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_broadcast_all))
async def admin_broadcast_all_send(message: Message, state: FSMContext):
    users = await db.get_all_users()
    bl = await db.get_blacklist()
    success = fail = 0
    await message.answer("📤 Рассылка...")
    for uid in users:
        if uid in bl: continue
        try:
            await message.bot.send_message(uid, message.text)
            success += 1
        except Exception as e:
            logger.error(f"Broadcast {uid}: {e}")
            fail += 1
        await asyncio.sleep(BROADCAST_DELAY)
    await db.add_broadcast_log("manual", success)
    await message.answer(f"📊 Готово!\n✅ {success}\n❌ {fail}", reply_markup=get_back_keyboard("back_to_admin"))
    await state.clear()

@router.callback_query(F.data == "admin_broadcast_id")
async def admin_broadcast_id_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "📩 ID:", reply_markup=get_back_keyboard("admin_broadcast_menu"))
    await state.set_state(AdminStates.waiting_for_broadcast_id)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_broadcast_id))
async def admin_broadcast_id_user(message: Message, state: FSMContext):
    try:
        await state.update_data(broadcast_user_id=int(message.text))
        await message.answer("📝 Текст:", reply_markup=get_back_keyboard("admin_broadcast_menu"))
        await state.set_state(AdminStates.waiting_for_broadcast_id_text)
    except ValueError:
        await message.answer("❌ ID.", reply_markup=get_back_keyboard("admin_broadcast_menu"))

@router.message(StateFilter(AdminStates.waiting_for_broadcast_id_text))
async def admin_broadcast_id_send(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        await message.bot.send_message(data['broadcast_user_id'], message.text)
        await message.answer("✅ Отправлено!", reply_markup=get_back_keyboard("back_to_admin"))
    except Exception as e:
        await message.answer(f"❌ {e}", reply_markup=get_back_keyboard("back_to_admin"))
    await state.clear()


# ============ ADMIN: AUTO DELETE ============
@router.callback_query(F.data == "admin_autodelete_menu")
async def admin_autodelete_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    vpn_days = await db.get_setting("vpn_autodelete_days") or "30"
    proxy_days = await db.get_setting("proxy_autodelete_days") or "30"
    await safe_edit_text(callback.message, "⚙️ Автоудаление:", 
        reply_markup=get_admin_autodelete_menu_keyboard(int(vpn_days), int(proxy_days)))
    await callback.answer()

@router.callback_query(F.data == "admin_set_vpn_autodelete")
async def admin_set_vpn_autodelete(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "🔑 Через сколько дней удалять VPN:", reply_markup=get_back_keyboard("admin_autodelete_menu"))
    await state.set_state(AdminStates.waiting_for_vpn_autodelete_days)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_vpn_autodelete_days))
async def admin_set_vpn_autodelete_finish(message: Message, state: FSMContext):
    try:
        days = int(message.text)
        await db.set_setting("vpn_autodelete_days", str(days))
        await message.answer(f"✅ VPN: {days} дн.", reply_markup=get_back_keyboard("admin_autodelete_menu"))
    except ValueError:
        await message.answer("❌ Число.", reply_markup=get_back_keyboard("admin_autodelete_menu"))
    await state.clear()

@router.callback_query(F.data == "admin_set_proxy_autodelete")
async def admin_set_proxy_autodelete(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "🛡️ Через сколько дней удалять proxy:", reply_markup=get_back_keyboard("admin_autodelete_menu"))
    await state.set_state(AdminStates.waiting_for_proxy_autodelete_days)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_for_proxy_autodelete_days))
async def admin_set_proxy_autodelete_finish(message: Message, state: FSMContext):
    try:
        days = int(message.text)
        await db.set_setting("proxy_autodelete_days", str(days))
        await message.answer(f"✅ Proxy: {days} дн.", reply_markup=get_back_keyboard("admin_autodelete_menu"))
    except ValueError:
        await message.answer("❌ Число.", reply_markup=get_back_keyboard("admin_autodelete_menu"))
    await state.clear()

@router.callback_query(F.data == "admin_delete_old_now")
async def admin_delete_old_now(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    vpn_days = int(await db.get_setting("vpn_autodelete_days") or "30")
    proxy_days = int(await db.get_setting("proxy_autodelete_days") or "30")
    await db.delete_old_vpn_keys(vpn_days)
    await db.delete_old_proxies(proxy_days)
    await callback.answer("✅ Старые ключи/proxy удалены!", show_alert=True)
    await safe_edit_text(callback.message, "⚙️ Автоудаление:", 
        reply_markup=get_admin_autodelete_menu_keyboard(vpn_days, proxy_days))


# ============ ADMIN: BROADCAST CONFIRM ============
@router.callback_query(F.data.startswith("confirm_broadcast_"))
async def confirm_broadcast(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    btype = callback.data.split("_")[-1]
    if btype == "vpn":
        users = await db.get_users_with_vpn_notify()
        text = "🔔 Новый VPN-ключ! Жми «🔌 VPN-ключи»."
    else:
        users = await db.get_users_with_proxy_notify()
        text = "🛡️ Новый proxy! Жми «🛡️ Proxy»."
    if not users:
        await callback.answer("Нет подписчиков", show_alert=True)
        await safe_edit_text(callback.message, "⚙️ Админ-панель", reply_markup=get_admin_keyboard())
        return
    await callback.message.edit_text(f"📤 {len(users)} чел...")
    success = fail = 0
    for uid in users:
        try:
            await callback.bot.send_message(uid, text)
            success += 1
        except Exception as e:
            logger.error(f"Notify {uid}: {e}")
            fail += 1
        await asyncio.sleep(BROADCAST_DELAY)
    await db.add_broadcast_log(btype, success)
    await callback.message.edit_text(f"📊 Готово!\n✅ {success}\n❌ {fail}", reply_markup=get_back_keyboard("back_to_admin"))
    await callback.answer()

@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    await safe_edit_text(callback.message, "⚙️ Админ-панель", reply_markup=get_admin_keyboard())
    await callback.answer()


# ============ ADMIN: STATS ============
@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS: await callback.answer("⛔"); return
    stats = await db.get_stats()
    channels = await db.get_channels_to_check()
    await safe_edit_text(callback.message,
        f"📊 Статистика:\n\n"
        f"👥 Пользователей: {stats['users']} (24ч: {stats['active_24h']})\n"
        f"🚫 Чёрный список: {stats['blacklist']}\n"
        f"🔑 VPN: {stats['vpn_keys']}\n"
        f"🛡️ Proxy: {stats['proxy_count']}\n"
        f"📢 Спонсоров: {len(stats['sponsors'])}\n"
        f"📨 Рассылок: {stats['broadcast_count']}\n\n"
        f"🆘 Поддержка: {stats['support_count']} (новых: {stats['support_unreplied']})\n"
        f"📢 Реклама: {stats['ad_count']} (новых: {stats['ad_unreplied']})\n\n"
        f"📋 Каналы:\n" + "\n".join([f"• {ch}" for ch in channels]),
        reply_markup=get_back_keyboard("back_to_admin")
    )
    await callback.answer()


# ============ NOOP ============
@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
