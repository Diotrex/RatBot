import asyncio
import logging
from typing import List, Dict
import inspect
import os
import json

from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============ КОНФИГУРАЦИЯ ============
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(os.getenv("ADMIN_ID"))]
YOUR_USERNAME = os.getenv("SUPPORT_USERNAME")
YOUR_CHANNEL = os.getenv("CHANNEL_USERNAME")
DATA_FILE = "bot_data.json"


# Хранилище данных с сохранением в файл
class Database:
    def __init__(self):
        self.subscriptions: List[Dict[str, str]] = []
        self.sponsors: List[str] = []
        self.users: set = set()
        self.blacklist: set = set()
        self.support_messages: List[Dict] = []
        self.ad_messages: List[Dict] = []
        self.broadcast_count: int = 0
        self.load_data()

    def save_data(self):
        data = {
            "subscriptions": self.subscriptions,
            "sponsors": self.sponsors,
            "users": list(self.users),
            "blacklist": list(self.blacklist),
            "support_messages": self.support_messages,
            "ad_messages": self.ad_messages,
            "broadcast_count": self.broadcast_count
        }
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Данные сохранены в файл")
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")

    def load_data(self):
        if not os.path.exists(DATA_FILE):
            logger.info("Файл данных не найден, начинаем с чистого листа")
            return
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.subscriptions = data.get("subscriptions", [])
            self.sponsors = data.get("sponsors", [])
            self.users = set(data.get("users", []))
            self.blacklist = set(data.get("blacklist", []))
            self.support_messages = data.get("support_messages", [])
            self.ad_messages = data.get("ad_messages", [])
            self.broadcast_count = data.get("broadcast_count", 0)
            logger.info(f"Данные загружены: {len(self.users)} пользователей, "
                        f"{len(self.subscriptions)} ключей, "
                        f"{len(self.sponsors)} спонсоров, "
                        f"{len(self.blacklist)} в чёрном списке")
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")

    def add_to_blacklist(self, user_id: int):
        self.blacklist.add(user_id)
        self.users.discard(user_id)
        self.save_data()
        logger.info(f"Пользователь {user_id} добавлен в чёрный список")

    def remove_from_blacklist(self, user_id: int):
        self.blacklist.discard(user_id)
        self.save_data()
        logger.info(f"Пользователь {user_id} удалён из чёрного списка")

    def is_blacklisted(self, user_id: int) -> bool:
        return user_id in self.blacklist

    def add_subscription(self, date: str, key: str):
        self.subscriptions.insert(0, {"date": date, "key": key})
        if len(self.subscriptions) > 5:
            self.subscriptions.pop()
        self.save_data()

    def remove_subscription(self, index: int):
        if 0 <= index < len(self.subscriptions):
            self.subscriptions.pop(index)
            self.save_data()

    def add_sponsor(self, username: str):
        if username not in self.sponsors:
            self.sponsors.append(username)
            self.save_data()

    def remove_sponsor(self, username: str):
        if username in self.sponsors:
            self.sponsors.remove(username)
            self.save_data()

    def get_channels_to_check(self) -> List[str]:
        return [YOUR_CHANNEL] + self.sponsors

    def add_support_message(self, user_id: int, username: str, message: str):
        from datetime import datetime
        self.support_messages.append({
            "user_id": user_id,
            "username": username,
            "message": message,
            "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "replied": False
        })
        self.save_data()

    def add_ad_message(self, user_id: int, username: str, message: str):
        from datetime import datetime
        self.ad_messages.append({
            "user_id": user_id,
            "username": username,
            "message": message,
            "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "replied": False
        })
        self.save_data()

    def add_user(self, user_id: int):
        if user_id not in self.users and user_id not in self.blacklist:
            self.users.add(user_id)
            self.save_data()


db = Database()


# ============ СОСТОЯНИЯ FSM ============
class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_sub_date = State()
    waiting_for_sub_key = State()
    waiting_for_sponsor_add = State()
    waiting_for_sponsor_remove = State()
    waiting_for_sub_remove_index = State()
    waiting_for_blacklist_add = State()
    waiting_for_blacklist_remove = State()


class UserStates(StatesGroup):
    waiting_for_support_message = State()
    waiting_for_ad_message = State()


class AdminSupportStates(StatesGroup):
    waiting_for_support_reply_select = State()
    waiting_for_support_reply_text = State()
    waiting_for_ad_reply_select = State()
    waiting_for_ad_reply_text = State()


# ============ КЛАВИАТУРЫ ============
MENU_TEXT = (
    "<b>🐀 Rat VPN</b>\n\n"
    "🔌 Подключиться — получить актуальный VPN-ключ.\n"
    "📖 Инструкция — если подключаетесь впервые.\n"
    "📢 Реклама — сотрудничество и размещение рекламы.\n"
    "🆘 Поддержка — сообщить о проблеме или задать вопрос.\n\n"
    "⬇️ Приятного использования! 🚀"
)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔌 Подключиться", callback_data="connect"))
    builder.row(InlineKeyboardButton(text="📖 Инструкция", callback_data="instruction"))
    builder.row(
        InlineKeyboardButton(text="📢 Реклама", callback_data="ad"),
        InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")
    )
    return builder.as_markup()


def get_subscriptions_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(5):
        if i < len(db.subscriptions):
            builder.row(InlineKeyboardButton(
                text=f"📅 {db.subscriptions[i]['date']}",
                callback_data=f"sub_{i}"
            ))
        else:
            builder.row(InlineKeyboardButton(
                text="-",
                callback_data="no_sub"
            ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    return builder.as_markup()


def get_check_subscription_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    channels = db.get_channels_to_check()
    for channel in channels:
        channel_link = channel.replace('@', '')
        builder.row(InlineKeyboardButton(
            text=f"📢 {channel}",
            url=f"https://t.me/{channel_link}"
        ))
    builder.row(InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub"))
    return builder.as_markup()


def get_admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔑 Ключи", callback_data="admin_subs_menu"))
    builder.row(InlineKeyboardButton(text="📢 Спонсоры", callback_data="admin_sponsors_menu"))
    builder.row(InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="🆘 Поддержка", callback_data="admin_support_menu"))
    builder.row(InlineKeyboardButton(text="🚫 Чёрный список", callback_data="admin_blacklist_menu"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    return builder.as_markup()


def get_admin_subs_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить ключ", callback_data="admin_add_sub"))
    builder.row(InlineKeyboardButton(text="❌ Удалить ключ", callback_data="admin_remove_sub"))
    builder.row(InlineKeyboardButton(text="📋 Список ключей", callback_data="admin_list_subs"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


def get_admin_sponsors_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить спонсора", callback_data="admin_add_sponsor"))
    builder.row(InlineKeyboardButton(text="❌ Удалить спонсора", callback_data="admin_remove_sponsor"))
    builder.row(InlineKeyboardButton(text="📋 Список спонсоров", callback_data="admin_list_sponsors"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


def get_admin_support_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📨 Обращения в поддержку", callback_data="admin_support_list"))
    builder.row(InlineKeyboardButton(text="📢 Заявки на рекламу", callback_data="admin_ad_list"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


def get_admin_blacklist_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить в чёрный список", callback_data="admin_blacklist_add"))
    builder.row(InlineKeyboardButton(text="❌ Удалить из чёрного списка", callback_data="admin_blacklist_remove"))
    builder.row(InlineKeyboardButton(text="📋 Список чёрного списка", callback_data="admin_blacklist_list"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin"))
    return builder.as_markup()


def get_back_keyboard(callback_data: str = "back_to_admin") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data))
    return builder.as_markup()


# ============ ХЕНДЛЕРЫ ============
router = Router()


async def check_user_subscriptions(bot: Bot, user_id: int) -> tuple:
    channels = db.get_channels_to_check()
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


async def safe_edit_text(message: Message, text: str, reply_markup=None, parse_mode=None):
    try:
        await message.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise e


@router.message(Command("start"))
async def cmd_start(message: Message):
    if db.is_blacklisted(message.from_user.id):
        await message.answer("🚫 Вы заблокированы.")
        return
    is_subscribed, not_subscribed = await check_user_subscriptions(message.bot, message.from_user.id)
    if not is_subscribed:
        channels = db.get_channels_to_check()
        channels_list = "\n".join([f"• {ch}" for ch in channels])
        await message.answer(
            f"👋 Добро пожаловать в Rat VPN!\n\n"
            f"• Здесь вы можете бесплатно получать актуальные VPN-ключи для Happ.\n\n"
            f"⚠️ Для использования бота необходимо подписаться на каналы:\n\n"
            f"{channels_list}\n\n"
            f"Нажмите на кнопки ниже, чтобы перейти в каналы, "
            f"а затем нажмите кнопку проверки:",
            reply_markup=get_check_subscription_keyboard()
        )
    else:
        db.add_user(message.from_user.id)
        await message.answer(MENU_TEXT, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "check_sub")
async def process_check_sub(callback: CallbackQuery):
    if db.is_blacklisted(callback.from_user.id):
        await callback.message.edit_text("🚫 Вы заблокированы.")
        await callback.answer()
        return
    is_subscribed, not_subscribed = await check_user_subscriptions(callback.bot, callback.from_user.id)
    if is_subscribed:
        db.add_user(callback.from_user.id)
        await safe_edit_text(callback.message, MENU_TEXT, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)
    else:
        not_sub_list = "\n".join([f"• {ch}" for ch in not_subscribed])
        await safe_edit_text(callback.message,
            f"❌ Вы подписались не на все каналы!\n\nНе подписаны на:\n{not_sub_list}\n\nНажмите на кнопки ниже, чтобы перейти в каналы:",
            reply_markup=get_check_subscription_keyboard())
    await callback.answer()


def check_subscription_required(func):
    async def wrapper(callback: CallbackQuery, **kwargs):
        if db.is_blacklisted(callback.from_user.id):
            await callback.message.edit_text("🚫 Вы заблокированы.")
            await callback.answer()
            return
        is_subscribed, not_subscribed = await check_user_subscriptions(callback.bot, callback.from_user.id)
        if not is_subscribed:
            not_sub_list = "\n".join([f"• {ch}" for ch in not_subscribed])
            await safe_edit_text(callback.message,
                f"⚠️ Вы не подписаны на:\n{not_sub_list}\n\nПодпишитесь и нажмите кнопку проверки:",
                reply_markup=get_check_subscription_keyboard())
            await callback.answer()
            return
        db.add_user(callback.from_user.id)
        func_params = inspect.signature(func).parameters
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in func_params}
        return await func(callback, **filtered_kwargs)
    return wrapper


@router.callback_query(F.data == "instruction")
@check_subscription_required
async def process_instruction(callback: CallbackQuery):
    await safe_edit_text(
        callback.message,
        "📖 Как подключиться:\n\n"
        "1. Скачайте Happ или любой другой клиент с поддержкой VLESS\n\n"
        "2. В боте нажмите «🔌 Подключиться» и выберите актуальный ключ\n\n"
        "3. Скопируйте ключ — просто нажмите на него\n\n"
        "4. В программе нажмите «Добавить сервер» → вставьте скопированную ссылку\n\n"
        "5. Готово! Подключайтесь и пользуйтесь 🎉\n\n"
        "📅 Обновление ключей:\n"
        "• Новые ключи публикуются каждый день\n"
        "• Старые ключи постепенно удаляются\n"
        "• Всегда 5 актуальных ключей\n\n"
        "💬 Вопросы? Жмите «🆘 Поддержка»",
        reply_markup=get_back_keyboard("back_to_main")
    )
    await callback.answer()


@router.callback_query(F.data == "connect")
@check_subscription_required
async def process_connect(callback: CallbackQuery):
    await safe_edit_text(callback.message, "🔑 Выберите актуальный ключ:", reply_markup=get_subscriptions_keyboard())
    await callback.answer()


@router.callback_query(F.data == "no_sub")
async def process_no_sub(callback: CallbackQuery):
    await callback.answer("❌ Этот ключ пока недоступен", show_alert=True)


@router.callback_query(F.data.startswith("sub_"))
@check_subscription_required
async def process_sub_selection(callback: CallbackQuery):
    sub_index = int(callback.data.split("_")[1])
    if 0 <= sub_index < len(db.subscriptions):
        sub = db.subscriptions[sub_index]
        key_text = f"`{sub['key']}`"
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Назад к ключам", callback_data="connect"))
        await safe_edit_text(callback.message,
            f"🔐 Ключ от {sub['date']}:\n\n{key_text}\n\n⚠️ Нажмите на ключ, чтобы скопировать его.",
            reply_markup=builder.as_markup(), parse_mode=ParseMode.MARKDOWN)
    await callback.answer()


@router.callback_query(F.data == "support")
@check_subscription_required
async def process_support(callback: CallbackQuery, state: FSMContext):
    await safe_edit_text(callback.message,
        "🆘 Поддержка\n\nОпишите вашу проблему как можно подробнее.\nОтправьте одно сообщение, и я передам его администратору.",
        reply_markup=get_back_keyboard("back_to_main"))
    await state.set_state(UserStates.waiting_for_support_message)
    await callback.answer()


@router.message(StateFilter(UserStates.waiting_for_support_message))
async def process_support_message(message: Message, state: FSMContext):
    db.add_support_message(user_id=message.from_user.id,
        username=message.from_user.username or f"id{message.from_user.id}",
        message=message.text)
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(chat_id=admin_id,
                text=f"📨 Новое обращение в поддержку!\n\n👤 От: @{message.from_user.username or 'нет username'} (ID: {message.from_user.id})\n🕒 {db.support_messages[-1]['timestamp']}\n\n💬 Сообщение:\n{message.text}")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    await message.answer("✅ Ваше сообщение отправлено! Администратор свяжется с вами в ближайшее время.",
        reply_markup=get_back_keyboard("back_to_main"))
    await state.clear()


@router.callback_query(F.data == "ad")
@check_subscription_required
async def process_ad(callback: CallbackQuery, state: FSMContext):
    await safe_edit_text(callback.message,
        "📢 Реклама\n\nОпишите ваше предложение или вопрос по рекламе.\nОтправьте одно сообщение, и я передам его администратору.",
        reply_markup=get_back_keyboard("back_to_main"))
    await state.set_state(UserStates.waiting_for_ad_message)
    await callback.answer()


@router.message(StateFilter(UserStates.waiting_for_ad_message))
async def process_ad_message(message: Message, state: FSMContext):
    db.add_ad_message(user_id=message.from_user.id,
        username=message.from_user.username or f"id{message.from_user.id}",
        message=message.text)
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(chat_id=admin_id,
                text=f"📢 Новая заявка на рекламу!\n\n👤 От: @{message.from_user.username or 'нет username'} (ID: {message.from_user.id})\n🕒 {db.ad_messages[-1]['timestamp']}\n\n💬 Сообщение:\n{message.text}")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    await message.answer("✅ Ваша заявка отправлена! Администратор свяжется с вами в ближайшее время.",
        reply_markup=get_back_keyboard("back_to_main"))
    await state.clear()


@router.callback_query(F.data == "back_to_main")
@check_subscription_required
async def process_back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit_text(callback.message, MENU_TEXT, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)
    await callback.answer()


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


@router.callback_query(F.data == "admin_subs_menu")
async def admin_subs_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "🔑 Управление ключами:", reply_markup=get_admin_subs_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_list_subs")
async def admin_list_subs(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    if not db.subscriptions:
        text = "📋 Ключей пока нет."
    else:
        text = "📋 Список ключей:\n\n" + "\n".join([f"{i + 1}. {sub['date']}" for i, sub in enumerate(db.subscriptions)])
    await safe_edit_text(callback.message, text, reply_markup=get_back_keyboard("admin_subs_menu"))
    await callback.answer()


@router.callback_query(F.data == "admin_add_sub")
async def admin_add_sub_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "📅 Введите дату ключа (например: 17.06.2026):", reply_markup=get_back_keyboard("admin_subs_menu"))
    await state.set_state(AdminStates.waiting_for_sub_date)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_sub_date))
async def admin_add_sub_date(message: Message, state: FSMContext):
    await state.update_data(sub_date=message.text)
    await message.answer("🔑 Теперь отправьте ключ:", reply_markup=get_back_keyboard("admin_subs_menu"))
    await state.set_state(AdminStates.waiting_for_sub_key)


@router.message(StateFilter(AdminStates.waiting_for_sub_key))
async def admin_add_sub_key(message: Message, state: FSMContext):
    data = await state.get_data()
    sub_date = data['sub_date']
    sub_key = message.text
    db.add_subscription(sub_date, sub_key)
    await message.answer(f"✅ Ключ от {sub_date} успешно добавлен!\nВсего ключей: {len(db.subscriptions)}/5",
        reply_markup=get_back_keyboard("admin_subs_menu"))
    await state.clear()


@router.callback_query(F.data == "admin_remove_sub")
async def admin_remove_sub_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    if not db.subscriptions:
        await safe_edit_text(callback.message, "❌ Нет ключей для удаления.", reply_markup=get_back_keyboard("admin_subs_menu"))
        await callback.answer()
        return
    subs_list = "\n".join([f"{i}: {sub['date']}" for i, sub in enumerate(db.subscriptions)])
    await safe_edit_text(callback.message,
        f"📋 Список ключей:\n\n{subs_list}\n\nВведите номер ключа для удаления (0-{len(db.subscriptions) - 1}):",
        reply_markup=get_back_keyboard("admin_subs_menu"))
    await state.set_state(AdminStates.waiting_for_sub_remove_index)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_sub_remove_index))
async def admin_remove_sub_index(message: Message, state: FSMContext):
    try:
        index = int(message.text)
        if 0 <= index < len(db.subscriptions):
            removed = db.subscriptions.pop(index)
            await message.answer(f"✅ Ключ {removed['date']} удален!", reply_markup=get_back_keyboard("admin_subs_menu"))
        else:
            await message.answer("❌ Неверный индекс.", reply_markup=get_back_keyboard("admin_subs_menu"))
            return
    except ValueError:
        await message.answer("❌ Введите число.", reply_markup=get_back_keyboard("admin_subs_menu"))
        return
    await state.clear()


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
    if not db.sponsors:
        text = "📋 Спонсоров пока нет."
    else:
        text = "📋 Список спонсоров:\n\n" + "\n".join([f"• {s}" for s in db.sponsors])
    await safe_edit_text(callback.message, text, reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await callback.answer()


@router.callback_query(F.data == "admin_add_sponsor")
async def admin_add_sponsor_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message,
        "📢 Отправьте username канала (например: @sponsor_channel):\n\n⚠️ Бот должен быть админом канала!",
        reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await state.set_state(AdminStates.waiting_for_sponsor_add)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_sponsor_add))
async def admin_add_sponsor_finish(message: Message, state: FSMContext):
    username = message.text.strip()
    if not username.startswith('@'):
        username = '@' + username
    db.add_sponsor(username)
    await message.answer(f"✅ Спонсор {username} добавлен!", reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await state.clear()


@router.callback_query(F.data == "admin_remove_sponsor")
async def admin_remove_sponsor_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    if not db.sponsors:
        await safe_edit_text(callback.message, "❌ Нет спонсоров.", reply_markup=get_back_keyboard("admin_sponsors_menu"))
        await callback.answer()
        return
    sponsors_list = "\n".join([f"• {s}" for s in db.sponsors])
    await safe_edit_text(callback.message,
        f"📋 Список спонсоров:\n\n{sponsors_list}\n\nОтправьте username для удаления:",
        reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await state.set_state(AdminStates.waiting_for_sponsor_remove)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_sponsor_remove))
async def admin_remove_sponsor_finish(message: Message, state: FSMContext):
    username = message.text.strip()
    if not username.startswith('@'):
        username = '@' + username
    db.remove_sponsor(username)
    await message.answer(f"✅ Спонсор {username} удален!", reply_markup=get_back_keyboard("admin_sponsors_menu"))
    await state.clear()


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
    if not db.blacklist:
        text = "📋 Чёрный список пуст."
    else:
        text = "📋 Чёрный список:\n\n" + "\n".join([f"• ID: {uid}" for uid in db.blacklist])
    await safe_edit_text(callback.message, text, reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await callback.answer()


@router.callback_query(F.data == "admin_blacklist_add")
async def admin_blacklist_add_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "🚫 Введите ID пользователя для добавления в чёрный список:",
        reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await state.set_state(AdminStates.waiting_for_blacklist_add)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_blacklist_add))
async def admin_blacklist_add_finish(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
        db.add_to_blacklist(user_id)
        await message.answer(f"✅ Пользователь {user_id} добавлен в чёрный список!", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    except ValueError:
        await message.answer("❌ Введите корректный ID.", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await state.clear()


@router.callback_query(F.data == "admin_blacklist_remove")
async def admin_blacklist_remove_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    if not db.blacklist:
        await safe_edit_text(callback.message, "❌ Чёрный список пуст.", reply_markup=get_back_keyboard("admin_blacklist_menu"))
        await callback.answer()
        return
    await safe_edit_text(callback.message, "🚫 Введите ID пользователя для удаления из чёрного списка:",
        reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await state.set_state(AdminStates.waiting_for_blacklist_remove)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_blacklist_remove))
async def admin_blacklist_remove_finish(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
        if user_id in db.blacklist:
            db.remove_from_blacklist(user_id)
            await message.answer(f"✅ Пользователь {user_id} удалён из чёрного списка!", reply_markup=get_back_keyboard("admin_blacklist_menu"))
        else:
            await message.answer("❌ Пользователь не найден в чёрном списке.", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    except ValueError:
        await message.answer("❌ Введите корректный ID.", reply_markup=get_back_keyboard("admin_blacklist_menu"))
    await state.clear()


@router.callback_query(F.data == "admin_support_menu")
async def admin_support_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, "🆘 Управление обращениями:", reply_markup=get_admin_support_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_support_list")
async def admin_support_list(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    if not db.support_messages:
        text = "📨 Обращений пока нет."
        reply_markup = get_back_keyboard("admin_support_menu")
    else:
        text = "📨 Обращения в поддержку:\n\n"
        for i, msg in enumerate(db.support_messages):
            status = "✅" if msg['replied'] else "❌"
            text += f"{i}. {status} @{msg['username']} ({msg['timestamp']})\n   💬 {msg['message'][:100]}\n\n"
        text += "Нажмите кнопку ниже, чтобы выбрать обращение для ответа:"
        reply_builder = InlineKeyboardBuilder()
        reply_builder.row(InlineKeyboardButton(text="💬 Ответить на обращение", callback_data="admin_support_reply"))
        reply_builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_support_menu"))
        reply_markup = reply_builder.as_markup()
    await safe_edit_text(callback.message, text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data == "admin_support_reply")
async def admin_support_reply_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    if not db.support_messages:
        await callback.answer("Нет обращений для ответа", show_alert=True)
        return
    await safe_edit_text(callback.message, "📝 Введите номер обращения, на которое хотите ответить:",
        reply_markup=get_back_keyboard("admin_support_menu"))
    await state.set_state(AdminSupportStates.waiting_for_support_reply_select)
    await callback.answer()


@router.message(StateFilter(AdminSupportStates.waiting_for_support_reply_select))
async def admin_support_reply_select(message: Message, state: FSMContext):
    try:
        index = int(message.text)
        if 0 <= index < len(db.support_messages):
            msg = db.support_messages[index]
            await state.update_data(reply_index=index)
            await message.answer(f"📨 Обращение #{index} от @{msg['username']}:\n\n💬 {msg['message']}\n\nВведите ваш ответ:",
                reply_markup=get_back_keyboard("admin_support_menu"))
            await state.set_state(AdminSupportStates.waiting_for_support_reply_text)
        else:
            await message.answer("❌ Неверный номер обращения. Попробуйте снова:", reply_markup=get_back_keyboard("admin_support_menu"))
    except ValueError:
        await message.answer("❌ Введите число.", reply_markup=get_back_keyboard("admin_support_menu"))


@router.message(StateFilter(AdminSupportStates.waiting_for_support_reply_text))
async def admin_support_reply_send(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data['reply_index']
    reply_text = message.text
    msg = db.support_messages[index]
    try:
        await message.bot.send_message(chat_id=msg['user_id'], text=f"📩 Ответ от поддержки:\n\n{reply_text}")
        msg['replied'] = True
        db.save_data()
        await message.answer(f"✅ Ответ отправлен пользователю @{msg['username']}!", reply_markup=get_back_keyboard("admin_support_menu"))
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}", reply_markup=get_back_keyboard("admin_support_menu"))
    await state.clear()


@router.callback_query(F.data == "admin_ad_list")
async def admin_ad_list(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    if not db.ad_messages:
        text = "📢 Заявок на рекламу пока нет."
        reply_markup = get_back_keyboard("admin_support_menu")
    else:
        text = "📢 Заявки на рекламу:\n\n"
        for i, msg in enumerate(db.ad_messages):
            status = "✅" if msg['replied'] else "❌"
            text += f"{i}. {status} @{msg['username']} ({msg['timestamp']})\n   💬 {msg['message'][:100]}\n\n"
        text += "Нажмите кнопку ниже, чтобы выбрать заявку для ответа:"
        reply_builder = InlineKeyboardBuilder()
        reply_builder.row(InlineKeyboardButton(text="💬 Ответить на заявку", callback_data="admin_ad_reply"))
        reply_builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_support_menu"))
        reply_markup = reply_builder.as_markup()
    await safe_edit_text(callback.message, text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data == "admin_ad_reply")
async def admin_ad_reply_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    if not db.ad_messages:
        await callback.answer("Нет заявок для ответа", show_alert=True)
        return
    await safe_edit_text(callback.message, "📝 Введите номер заявки, на которую хотите ответить:",
        reply_markup=get_back_keyboard("admin_support_menu"))
    await state.set_state(AdminSupportStates.waiting_for_ad_reply_select)
    await callback.answer()


@router.message(StateFilter(AdminSupportStates.waiting_for_ad_reply_select))
async def admin_ad_reply_select(message: Message, state: FSMContext):
    try:
        index = int(message.text)
        if 0 <= index < len(db.ad_messages):
            msg = db.ad_messages[index]
            await state.update_data(reply_index=index)
            await message.answer(f"📢 Заявка #{index} от @{msg['username']}:\n\n💬 {msg['message']}\n\nВведите ваш ответ:",
                reply_markup=get_back_keyboard("admin_support_menu"))
            await state.set_state(AdminSupportStates.waiting_for_ad_reply_text)
        else:
            await message.answer("❌ Неверный номер заявки. Попробуйте снова:", reply_markup=get_back_keyboard("admin_support_menu"))
    except ValueError:
        await message.answer("❌ Введите число.", reply_markup=get_back_keyboard("admin_support_menu"))


@router.message(StateFilter(AdminSupportStates.waiting_for_ad_reply_text))
async def admin_ad_reply_send(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data['reply_index']
    reply_text = message.text
    msg = db.ad_messages[index]
    try:
        await message.bot.send_message(chat_id=msg['user_id'], text=f"📩 Ответ от администратора:\n\n{reply_text}")
        msg['replied'] = True
        db.save_data()
        await message.answer(f"✅ Ответ отправлен пользователю @{msg['username']}!", reply_markup=get_back_keyboard("admin_support_menu"))
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}", reply_markup=get_back_keyboard("admin_support_menu"))
    await state.clear()


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    await safe_edit_text(callback.message, f"📨 Введите сообщение для рассылки ({len(db.users)} чел.):",
        reply_markup=get_back_keyboard("back_to_admin"))
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()


@router.message(StateFilter(AdminStates.waiting_for_broadcast))
async def admin_broadcast_send(message: Message, state: FSMContext):
    success_count = 0
    fail_count = 0
    await message.answer("📤 Начинаю рассылку...")
    for user_id in db.users:
        if user_id in db.blacklist:
            continue
        try:
            await message.bot.send_message(chat_id=user_id, text=message.text)
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            fail_count += 1
    db.broadcast_count += 1
    db.save_data()
    await message.answer(f"📊 Рассылка завершена!\n\n✅ Успешно: {success_count}\n❌ Ошибок: {fail_count}",
        reply_markup=get_back_keyboard("back_to_admin"))
    await state.clear()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    support_count = len(db.support_messages)
    support_unreplied = sum(1 for m in db.support_messages if not m['replied'])
    ad_count = len(db.ad_messages)
    ad_unreplied = sum(1 for m in db.ad_messages if not m['replied'])
    await safe_edit_text(callback.message,
        f"📊 Статистика бота:\n\n"
        f"👥 Пользователей: {len(db.users)}\n🚫 Черный список: {len(db.blacklist)}\n"
        f"🔑 Активных ключей: {len(db.subscriptions)}/5\n📢 Спонсоров: {len(db.sponsors)}\n"
        f"📨 Рассылок: {db.broadcast_count}\n\n"
        f"🆘 Обращений в поддержку: {support_count} (не отвечено: {support_unreplied})\n"
        f"📢 Заявок на рекламу: {ad_count} (не отвечено: {ad_unreplied})\n\n"
        f"📋 Каналы для подписки:\n" + "\n".join([f"• {ch}" for ch in db.get_channels_to_check()]),
        reply_markup=get_back_keyboard("back_to_admin"))
    await callback.answer()


async def handle(request):
    return web.Response(text="Bot is running")


async def run_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()


async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logger.info(f"Бот запущен! Загружено пользователей: {len(db.users)}, в чёрном списке: {len(db.blacklist)}")
    channels = db.get_channels_to_check()
    for channel in channels:
        try:
            chat = await bot.get_chat(chat_id=channel)
            logger.info(f"✅ Канал {channel} доступен (ID: {chat.id})")
        except Exception as e:
            logger.error(f"❌ Канал {channel} недоступен: {e}")
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(run_web_server())
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"Ошибка соединения: {e}. Перезапуск через 5 сек...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
