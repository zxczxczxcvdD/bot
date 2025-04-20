import random
import string
import asyncio
import logging
import sys
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramConflictError

# Проверка версии Python
if sys.version_info < (3, 8):
    raise RuntimeError("This bot requires Python 3.8 or higher")

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = "7997267152:AAFkALXJFIVl-MKBCt8sDwu4-Ci6LrNIOD8"

# Список ID админов
ADMIN_IDS = [7438900969, 5241019139]

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Хранилища
banned_users = set()  # {user_id}
all_users = {}  # {user_id: username}
subscribed_users = {}  # {user_id: {"username": username, "expires": datetime or None}}
support_questions = []
keys = {}  # {key: {"days": int, "used": bool, "user_id": int or None, "expires": datetime or None}}

# Генерация 500 случайных email
def generate_random_emails():
    emails = {}
    for _ in range(250):  # Gmail
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(8, 12)))
        email = f"{username}@gmail.com"
        emails[email] = "dummy_password"
    for _ in range(250):  # Mail.ru
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(8, 12)))
        email = f"{username}@mail.ru"
        emails[email] = "dummy_password"
    return emails

senders = generate_random_emails()
receivers = ['sms@telegram.org', 'dmca@telegram.org', 'abuse@telegram.org', 'sticker@telegram.org', 'support@telegram.org']

# Функция имитации отправки email
async def send_email(receiver, sender_email, sender_password, subject, body):
    try:
        if random.random() < 0.05:
            raise Exception("Random failure for realism")
        logger.info(f"Simulated email sent to {receiver} from {sender_email}")
        return True
    except Exception as e:
        logger.error(f"Simulated error sending email to {receiver} from {sender_email}: {e}")
        return False

# Функция для сброса обновлений
async def reset_updates():
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1"
            async with session.get(url) as response:
                if response.status == 200:
                    logger.info("Updates queue cleared")
                else:
                    logger.error(f"Failed to clear updates: {await response.text()}")
    except Exception as e:
        logger.error(f"Error clearing updates: {e}")

# Фоновая задача для проверки истёкших подписок
async def check_subscriptions():
    while True:
        current_time = datetime.now()
        expired_users = []
        for user_id, data in subscribed_users.items():
            if data["expires"] and data["expires"] < current_time:
                expired_users.append(user_id)
        for user_id in expired_users:
            username = subscribed_users[user_id]["username"]
            del subscribed_users[user_id]
            logger.info(f"Subscription for user {user_id} (@{username}) expired")
            try:
                await bot.send_message(user_id, "⏰ Ваша подписка истекла. Обратитесь в техподдержку для продления!")
            except Exception as e:
                logger.error(f"Error notifying user {user_id} about subscription expiration: {e}")
        await asyncio.sleep(60)

# Фоновая задача для очистки истёкших ключей
async def clean_expired_keys():
    while True:
        current_time = datetime.now()
        expired_keys = [key for key, data in keys.items() if data["used"] and data["expires"] and data["expires"] < current_time]
        for key in expired_keys:
            del keys[key]
            logger.info(f"Key {key} removed due to expiration")
        await asyncio.sleep(3600)  # Проверка каждый час

# Настройка меню команд
async def set_bot_commands():
    default_commands = [
        BotCommand(command="/start", description="🌟 Запустить бота и выбрать действие"),
        BotCommand(command="/getid", description="🆔 Узнать свой ID"),
        BotCommand(command="/activate", description="🔑 Активировать ключ для получения подписки")
    ]
    await bot.set_my_commands(commands=default_commands, scope=BotCommandScopeDefault())
    admin_commands = [
        BotCommand(command="/start", description="🌟 Запустить бота"),
        BotCommand(command="/getid", description="🆔 Узнать ID пользователя"),
        BotCommand(command="/users", description="📋 Список пользователей"),
        BotCommand(command="/ban", description="🚫 Забанить пользователя"),
        BotCommand(command="/unban", description="✅ Разбанить пользователя"),
        BotCommand(command="/answer", description="📬 Ответить на вопрос техподдержки"),
        BotCommand(command="/subscribe", description="📅 Выдать подписку на время"),
        BotCommand(command="/unsubscribe", description="🗑 Удалить подписку"),
        BotCommand(command="/generatekey", description="🔑 Сгенерировать ключ"),
        BotCommand(command="/listkeys", description="📜 Список ключей")
    ]
    for admin_id in ADMIN_IDS:
        await bot.set_my_commands(commands=admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
    logger.info("Bot commands menu set successfully")

# Определение состояний
class ComplaintStates(StatesGroup):
    waiting_for_complaint_type = State()
    username = State()
    tg_id = State()
    chat_link = State()
    violation_link = State()
    channel_link = State()
    channel_violation = State()
    bot_username = State()
    group_link = State()
    group_id = State()
    group_violation = State()

class SupportStates(StatesGroup):
    waiting_for_question = State()

class AdminStates(StatesGroup):
    waiting_for_subscription_id = State()

# Функция генерации ключа
def generate_key(length=16):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

# Команда /generatekey
@router.message(Command("generatekey"))
async def generate_key_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён. Эта команда только для админов.")
        return
    try:
        days = int(message.text.split()[1])
        if days <= 0:
            await message.answer("❌ Количество дней должно быть больше 0.")
            return
        key = generate_key()
        keys[key] = {
            "days": days,
            "used": False,
            "user_id": None,
            "expires": None
        }
        await message.answer(f"✅ Ключ сгенерирован: `{key}`\nСрок действия: {days} дней")
    except (IndexError, ValueError):
        await message.answer("❌ Формат: /generatekey <days>")

# Команда /activate
@router.message(Command("activate"))
async def activate_key_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"
    
    if user_id in banned_users:
        await message.answer("❌ Вы забанены.")
        return
    
    try:
        key = message.text.split()[1]
        if key not in keys:
            await message.answer("❌ Неверный или несуществующий ключ.")
            return
        if keys[key]["used"]:
            await message.answer("❌ Этот ключ уже использован.")
            return
        
        # Активация ключа
        days = keys[key]["days"]
        expires = datetime.now() + timedelta(days=days)
        keys[key]["used"] = True
        keys[key]["user_id"] = user_id
        keys[key]["expires"] = expires
        
        # Обновление подписки пользователя
        subscribed_users[user_id] = {
            "username": username,
            "expires": expires
        }
        
        await message.answer(f"✅ Ключ активирован! Подписка выдана до {expires.strftime('%Y-%m-%d %H:%M')}.")
        logger.info(f"User {user_id} (@{username}) activated key {key} for {days} days")
        
        # Уведомление админов
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"🔔 Пользователь @{username} (ID: {user_id}) активировал ключ `{key}` на {days} дней.")
            except Exception as e:
                logger.error(f"Error notifying admin {admin_id} about key activation: {e}")
            
    except IndexError:
        await message.answer("❌ Укажите ключ: /activate <key>")

# Команда /listkeys
@router.message(Command("listkeys"))
async def list_keys_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён. Эта команда только для админов.")
        return
    if not keys:
        await message.answer("📭 Ключи отсутствуют.")
        return
    key_list = "\n".join(
        f"🔑 `{key}`: {data['days']} дней, "
        f"{'✅ использован' if data['used'] else '⏳ не использован'}, "
        f"Пользователь: {data['user_id'] or 'нет'}, "
        f"Истекает: {data['expires'].strftime('%Y-%m-%d %H:%M') if data['expires'] else 'не активирован'}"
        for key, data in keys.items()
    )
    await message.answer(f"📋 Список ключей:\n{key_list}")

# Команда /start
@router.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"
    all_users[user_id] = username  # Добавляем пользователя
    logger.debug(f"Entering start_command for user {user_id} (@{username}), command text: '{message.text}'")
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
            [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
        ])
        logger.debug(f"Sending start message with keyboard to user {user_id}")
        await message.answer(
            "🌟 **SN0S3R - Жалобный Убийца** 🌟\n\n"
            "Выбери свою цель или обратись в поддержку! 🚀",
            reply_markup=keyboard
        )
        logger.info(f"Successfully sent /start response to user {user_id} (@{username})")
    except Exception as e:
        logger.error(f"Error in /start for user {user_id}: {e}")
        await message.answer("❌ Ошибка при обработке команды. Попробуйте позже.")

# Команда /getid
@router.message(Command("getid"))
async def get_id_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"
    if message.from_user.id in ADMIN_IDS:
        try:
            target_username = message.text.split()[1].lstrip("@")
            for uid, uname in all_users.items():
                if uname.lower() == target_username.lower():
                    await message.answer(f"🆔 ID пользователя @{uname}: {uid}")
                    return
            await message.answer(f"❌ Пользователь @{target_username} не найден.")
        except IndexError:
            await message.answer(f"🆔 Ваш ID: {user_id}\nДля поиска ID: /getid @username")
    else:
        await message.answer(f"🆔 Ваш ID: {user_id}")

# Команда /ban
@router.message(Command("ban"))
async def ban_user(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён. Эта команда только для админов.")
        return
    try:
        username = message.text.split()[1].lstrip("@")
        user_id = None
        for uid, uname in all_users.items():
            if uname.lower() == username.lower():
                user_id = uid
                break
        if not user_id:
            await message.answer(f"❌ Пользователь @{username} не найден.")
            return
        banned_users.add(user_id)
        await message.answer(f"✅ Пользователь @{username} (ID: {user_id}) забанен.")
    except IndexError:
        await message.answer("❌ Укажите username: /ban @username")

# Команда /unban
@router.message(Command("unban"))
async def unban_user(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён. Эта команда только для админов.")
        return
    try:
        username = message.text.split()[1].lstrip("@")
        user_id = None
        for uid, uname in all_users.items():
            if uname.lower() == username.lower():
                user_id = uid
                break
        if not user_id:
            await message.answer(f"❌ Пользователь @{username} не найден.")
            return
        banned_users.discard(user_id)
        await message.answer(f"✅ Пользователь @{username} (ID: {user_id}) разбанен.")
    except IndexError:
        await message.answer("❌ Укажите username: /unban @username")

# Команда /users
@router.message(Command("users"))
async def list_users(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён. Эта команда только для админов.")
        return
    if not all_users:
        await message.answer("📭 Пользователей пока нет.")
        return
    user_list = "\n".join(
        f"ID: {user_id}, @{username}" + 
        (f" ✅ (до {subscribed_users[user_id]['expires'].strftime('%Y-%m-%d %H:%M')})" if user_id in subscribed_users and subscribed_users[user_id]["expires"] else " ✅" if user_id in subscribed_users else "") +
        (" 🚫" if user_id in banned_users else "")
        for user_id, username in sorted(all_users.items(), key=lambda x: x[0])
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Выдать подписку", callback_data="issue_subscription")]
    ])
    await message.answer(f"📋 Список пользователей:\n{user_list}", reply_markup=keyboard)

# Команда /subscribe
@router.message(Command("subscribe"))
async def subscribe_user(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён. Эта команда только для админов.")
        return
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Формат: /subscribe @username <days>")
            return
        username = parts[1].lstrip("@")
        days = int(parts[2])
        user_id = None
        for uid, uname in all_users.items():
            if uname.lower() == username.lower():
                user_id = uid
                break
        if not user_id:
            await message.answer(f"❌ Пользователь @{username} не найден.")
            return
        if days <= 0:
            await message.answer("❌ Количество дней должно быть больше 0.")
            return
        expires = datetime.now() + timedelta(days=days)
        subscribed_users[user_id] = {
            "username": all_users[user_id],
            "expires": expires
        }
        await message.answer(f"✅ Пользователю @{username} (ID: {user_id}) выдана подписка до {expires.strftime('%Y-%m-%d %H:%M')}.")
        try:
            await bot.send_message(user_id, f"🎉 Вы получили подписку до {expires.strftime('%Y-%m-%d %H:%M')}!")
        except Exception as e:
            logger.error(f"Error notifying user {user_id} about subscription: {e}")
            await message.answer(f"⚠ Не удалось уведомить пользователя @{username}.")
    except (IndexError, ValueError):
        await message.answer("❌ Формат: /subscribe @username <days>")

# Команда /unsubscribe
@router.message(Command("unsubscribe"))
async def unsubscribe_user(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён. Эта команда только для админов.")
        return
    try:
        username = message.text.split()[1].lstrip("@")
        user_id = None
        for uid, uname in all_users.items():
            if uname.lower() == username.lower():
                user_id = uid
                break
        if not user_id:
            await message.answer(f"❌ Пользователь @{username} не найден.")
            return
        if user_id not in subscribed_users:
            await message.answer(f"❌ У пользователя @{username} нет подписки.")
            return
        del subscribed_users[user_id]
        await message.answer(f"✅ Подписка пользователя @{username} (ID: {user_id}) удалена.")
        try:
            await bot.send_message(user_id, "🗑 Ваша подписка была удалена.")
        except Exception as e:
            logger.error(f"Error notifying user {user_id} about subscription removal: {e}")
            await message.answer(f"⚠ Не удалось уведомить пользователя @{username}.")
    except IndexError:
        await message.answer("❌ Укажите username: /unsubscribe @username")

# Команда /answer
@router.message(Command("answer"))
async def answer_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён. Эта команда только для админов.")
        return
    if not support_questions:
        await message.answer("📭 Вопросов пока нет.")
        return
    for idx, q in enumerate(support_questions, 1):
        await message.answer(
            f"❓ Вопрос #{idx} от @{q['username']} (ID: {q['user_id']}):\n{q['text']}"
        )
    await message.answer("📬 Ответьте, цитируя вопрос (свайп), чтобы отправить ответ пользователю.")

# Обработчик выдачи подписки (без времени)
@router.callback_query(lambda c: c.data == "issue_subscription")
async def process_issue_subscription(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.message.answer("❌ Доступ запрещён.")
        return
    await state.set_state(AdminStates.waiting_for_subscription_id)
    await callback.message.answer("👤 Введите @username пользователя для выдачи подписки:")
    await callback.message.delete()

# Ввод username для подписки (без времени)
@router.message(AdminStates.waiting_for_subscription_id)
async def process_subscription_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён.")
        return
    try:
        username = message.text.lstrip("@")
        user_id = None
        for uid, uname in all_users.items():
            if uname.lower() == username.lower():
                user_id = uid
                break
        if not user_id:
            await message.answer(f"❌ Пользователь @{username} не найден.")
            return
        subscribed_users[user_id] = {
            "username": all_users[user_id],
            "expires": None
        }
        await message.answer(f"✅ Пользователю @{username} (ID: {user_id}) выдана бессрочная подписка.")
        try:
            await bot.send_message(user_id, "🎉 Вы получили бессрочную подписку!")
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя {user_id}: {e}")
            await message.answer(f"⚠ Не удалось уведомить пользователя @{username}.")
    except ValueError:
        await message.answer("❌ Введите корректный @username.")
    await state.clear()

# Обработчик выбора действия
@router.callback_query(lambda c: c.data.startswith("choice_"))
async def process_choice(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in banned_users or \
       (callback.from_user.id not in ADMIN_IDS and callback.from_user.id not in subscribed_users):
        await callback.message.answer("❌ Доступ запрещён.")
        return
    choice = callback.data
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    if choice == "choice_snos":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔪 Взять аккаунт", callback_data="snos_1")],
            [InlineKeyboardButton(text="📢 Взять канал", callback_data="snos_2")],
            [InlineKeyboardButton(text="🤖 Забанить бота", callback_data="snos_3")],
            [InlineKeyboardButton(text="💥 Захуярть канал", callback_data="snos_4")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="choice_back")]
        ])
        await callback.message.edit_text("🎯 Выбери цель для сноса:", reply_markup=keyboard)
    elif choice == "choice_support":
        await state.set_state(SupportStates.waiting_for_question)
        await callback.message.edit_text(
            "📩 Задайте ваш вопрос, и мы ответим максимально быстро!",
            reply_markup=main_keyboard
        )
    elif choice == "choice_back":
        await callback.message.edit_text(
            "🌟 **SN0S3R - Жалобный Убийца** 🌟\n\n"
            "Выбери свою цель или обратись в поддержку! 🚀",
            reply_markup=main_keyboard
        )

# Обработчик вопроса техподдержки
@router.message(SupportStates.waiting_for_question)
async def process_support_question(message: Message, state: FSMContext):
    question = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"
    support_questions.append({"user_id": user_id, "username": username, "text": question})
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    try:
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"❓ Новый вопрос от @{username} (ID: {user_id}):\n{question}"
            )
        await message.answer(
            "✅ Ваш вопрос отправлен! Ожидайте ответа. 😊",
            reply_markup=main_keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка отправки вопроса админам: {e}")
        await message.answer(
            "❌ Ошибка при отправке вопроса. Попробуйте позже. 😔",
            reply_markup=main_keyboard
        )
    await state.clear()

# Обработчик ответа админа
@router.message(lambda message: message.from_user.id in ADMIN_IDS and message.reply_to_message)
async def process_admin_reply(message: Message):
    reply_text = message.text
    replied_message = message.reply_to_message.text
    for question in support_questions:
        question_text = f"❓ Новый вопрос от @{question['username']} (ID: {question['user_id']}):\n{question['text']}"
        if question_text in replied_message:
            user_id = question['user_id']
            try:
                await bot.send_message(
                    user_id,
                    f"📬 Ответ от техподдержки:\n{reply_text}"
                )
                await message.answer(f"✅ Ответ отправлен пользователю (ID: {user_id}).")
                support_questions.remove(question)
            except Exception as e:
                logger.error(f"Ошибка отправки ответа пользователю {user_id}: {e}")
                await message.answer(f"❌ Ошибка отправки ответа пользователю (ID: {user_id}).")
            return
    await message.answer("❌ Не удалось найти вопрос. Убедитесь, что вы цитируете правильное сообщение.")

# Обработчик выбора типа сноса
@router.callback_query(lambda c: c.data.startswith("snos_"))
async def process_snos_choice(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in banned_users or \
       (callback.from_user.id not in ADMIN_IDS and callback.from_user.id not in subscribed_users):
        await callback.message.answer("❌ Доступ запрещён.")
        return
    choice = callback.data.split("_")[1]
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    await state.update_data(choice=choice)
    await state.set_state(ComplaintStates.waiting_for_complaint_type)
    if choice == "1":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📩 За спам/рекламу", callback_data="comp_1")],
            [InlineKeyboardButton(text="🔍 За доксинг", callback_data="comp_2")],
            [InlineKeyboardButton(text="😈 За троллинг/оск", callback_data="comp_3")],
            [InlineKeyboardButton(text="💉 Продажа наркоты", callback_data="comp_4")],
            [InlineKeyboardButton(text="👤 Кураторство в наркошопе", callback_data="comp_5")],
            [InlineKeyboardButton(text="🚨 Продажа ЦП", callback_data="comp_6")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="choice_back")]
        ])
        await callback.message.edit_text("🎯 Выбери причину жалобы на аккаунт:", reply_markup=keyboard)
    elif choice == "2":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 С личными данными", callback_data="ch_1")],
            [InlineKeyboardButton(text="🐶 С живодерством", callback_data="ch_2")],
            [InlineKeyboardButton(text="🚨 С детским порно", callback_data="ch_3")],
            [InlineKeyboardButton(text="💰 Прайсы (докс/сват)", callback_data="ch_4")],
            [InlineKeyboardButton(text="🩸 С расчлененкой", callback_data="ch_5")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="choice_back")]
        ])
        await callback.message.edit_text("🎯 Выбери причину жалобы на канал:", reply_markup=keyboard)
    elif choice == "3":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👁 Глаз Бога", callback_data="bot_1")],
            [InlineKeyboardButton(text="🐳 Синего кита", callback_data="bot_2")],
            [InlineKeyboardButton(text="🚨 Продажа ЦП", callback_data="bot_3")],
            [InlineKeyboardButton(text="💸 Мошеннические схемы", callback_data="bot_4")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="choice_back")]
        ])
        await callback.message.edit_text("🎯 Выбери причину жалобы на бота:", reply_markup=keyboard)
    elif choice == "4":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💥 Просто снос", callback_data="group_1")],
            [InlineKeyboardButton(text="📩 Спам/реклама", callback_data="group_2")],
            [InlineKeyboardButton(text="🖼 За аву/название", callback_data="group_3")],
            [InlineKeyboardButton(text="⚔ Пропаганда насилия", callback_data="group_4")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="choice_back")]
        ])
        await callback.message.edit_text("🎯 Выбери причину жалобы на группу:", reply_markup=keyboard)

# Обработчик выбора типа жалобы
@router.callback_query(lambda c: c.data.startswith(("comp_", "ch_", "bot_", "group_")))
async def process_complaint_type(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in banned_users or \
       (callback.from_user.id not in ADMIN_IDS and callback.from_user.id not in subscribed_users):
        await callback.message.answer("❌ Доступ запрещён.")
        return
    complaint_type = callback.data.split("_")[0]
    complaint_id = callback.data.split("_")[1]
    await state.update_data(complaint_type=complaint_type, complaint_id=complaint_id)
    data = await state.get_data()
    choice = data.get("choice")
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    if choice == "1":
        await state.set_state(ComplaintStates.username)
        await callback.message.edit_text("👤 Введи USERNAME аккаунта:", reply_markup=main_keyboard)
    elif choice == "2":
        await state.set_state(ComplaintStates.channel_link)
        await callback.message.edit_text("📢 Введи ссылку на канал:", reply_markup=main_keyboard)
    elif choice == "3":
        await state.set_state(ComplaintStates.bot_username)
        await callback.message.edit_text("🤖 Введи USERNAME бота:", reply_markup=main_keyboard)
    elif choice == "4":
        await state.set_state(ComplaintStates.group_link)
        await callback.message.edit_text("💬 Введи ссылку на чат:", reply_markup=main_keyboard)

# Обработчик USERNAME для аккаунта
@router.message(ComplaintStates.username)
async def process_username(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(username=message.text)
    await state.set_state(ComplaintStates.tg_id)
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    await message.answer("🆔 Введи TG ID аккаунта:", reply_markup=main_keyboard)

# Обработчик TG ID для аккаунта
@router.message(ComplaintStates.tg_id)
async def process_id(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(tg_id=message.text)
    await state.set_state(ComplaintStates.chat_link)
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    await message.answer("💬 Введи ссылку на чат:", reply_markup=main_keyboard)

# Обработчик ссылки на чат для аккаунта
@router.message(ComplaintStates.chat_link)
async def process_chat_link(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(chat_link=message.text)
    await state.set_state(ComplaintStates.violation_link)
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    await message.answer("⚠ Введи ссылку на нарушение в чате:", reply_markup=main_keyboard)

# Обработчик ссылки на нарушение для аккаунта
@router.message(ComplaintStates.violation_link)
async def process_violation_link(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(violation_link=message.text)
    data = await state.get_data()
    username = data.get("username")
    tg_id = data.get("tg_id")
    chat_link = data.get("chat_link")
    violation_link = data.get("violation_link")
    comp_id = data.get("complaint_id")
    if not senders:
        await message.answer("❌ Ошибка: нет доступных аккаунтов для отправки жалоб! 😔")
        await state.clear()
        return
    progress_message = await message.answer("🚀 **Отправка жалоб началась!** 🎬\n\nПрогресс: 0 из 2500\nЛог:\n(пусто)")
    await state.clear()
    comp_texts = {
        "1": f"Здравствуйте! Пользователь {username} (ID: {tg_id}) занимается спамом! Чат: {chat_link}, нарушение: {violation_link}. Заблокируйте его!",
        "2": f"Уважаемая поддержка, пользователь {username} (ID: {tg_id}) распространяет личные данные! Чат: {chat_link}, нарушение: {violation_link}. Прошу заблокировать!",
        "3": f"Пользователь {username} (ID: {tg_id}) троллит и оскорбляет! Чат: {chat_link}, нарушение: {violation_link}. Заблокируйте!",
        "4": f"Пользователь {username} (ID: {tg_id}) продает наркотики! Чат: {chat_link}, нарушение: {violation_link}. Срочно заблокируйте!",
        "5": f"Пользователь {username} (ID: {tg_id}) куратор наркошопа! Чат: {chat_link}, нарушение: {violation_link}. Прошу заблокировать!",
        "6": f"Пользователь {username} (ID: {tg_id}) распространяет ЦП! Чат: {chat_link}, нарушение: {violation_link}. Немедленно заблокируйте!"
    }
    sent_emails = 0
    total_emails = len(senders) * len(receivers)
    log_entries = []
    for sender_email, sender_password in senders.items():
        for receiver in receivers:
            comp_text = comp_texts.get(comp_id, comp_texts["1"])
            comp_body = comp_text.format(
                username=username.strip(),
                tg_id=tg_id.strip(),
                chat_link=chat_link.strip(),
                violation_link=violation_link.strip()
            )
            success = await send_email(receiver, sender_email, sender_password, '⚠ Жалоба на аккаунт', comp_body)
            if success:
                sent_emails += 1
                log_entries.append(f"[✅] {sender_email} → {receiver}")
            else:
                log_entries.append(f"[❌] {sender_email} → {receiver}")
            if len(log_entries) > 10:
                log_entries.pop(0)
            log_text = "\n".join(log_entries) if log_entries else "(пусто)"
            await progress_message.edit_text(
                f"🚀 **Отправка жалоб началась!** 🎬\n\n"
                f"**Прогресс**: {sent_emails} из {total_emails}\n"
                f"**Лог**:\n{log_text}"
            )
            await asyncio.sleep(1.5)
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    await progress_message.edit_text(
        f"🏁 **Отправка завершена!** 🎉\n\n"
        f"**Прогресс**: {sent_emails} из {total_emails}\n"
        f"**Лог**:\n{log_text}",
        reply_markup=main_keyboard
    )

# Обработчик ссылки на канал
@router.message(ComplaintStates.channel_link)
async def process_channel_link(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(channel_link=message.text)
    await state.set_state(ComplaintStates.channel_violation)
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    await message.answer("⚠ Введи ссылку на нарушение в канале:", reply_markup=main_keyboard)

# Обработчик ссылки на нарушение в канале
@router.message(ComplaintStates.channel_violation)
async def process_channel_violation(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(channel_violation=message.text)
    data = await state.get_data()
    channel_link = data.get("channel_link")
    channel_violation = data.get("channel_violation")
    ch_id = data.get("complaint_id")
    if not senders:
        await message.answer("❌ Ошибка: нет доступных аккаунтов для отправки жалоб! 😔")
        await state.clear()
        return
    progress_message = await message.answer("🚀 **Отправка жалоб началась!** 🎬\n\nПрогресс: 0 из 2500\nЛог:\n(пусто)")
    await state.clear()
    comp_texts = {
        "1": f"Здравствуйте! Канал {channel_link} распространяет личные данные! Нарушение: {channel_violation}. Заблокируйте его!",
        "2": f"Уважаемая поддержка, канал {channel_link} публикует живодерство! Нарушение: {channel_violation}. Прошу заблокировать!",
        "3": f"Канал {channel_link} распространяет детское порно! Нарушение: {channel_violation}. Срочно заблокируйте!",
        "4": f"Канал {channel_link} продает доксинг/сват! Нарушение: {channel_violation}. Прошу заблокировать!",
        "5": f"Канал {channel_link} публикует расчлененку! Нарушение: {channel_violation}. Немедленно заблокируйте!"
    }
    sent_emails = 0
    total_emails = len(senders) * len(receivers)
    log_entries = []
    for sender_email, sender_password in senders.items():
        for receiver in receivers:
            comp_text = comp_texts.get(ch_id, comp_texts["1"])
            comp_body = comp_text.format(channel_link=channel_link.strip(), channel_violation=channel_violation.strip())
            success = await send_email(receiver, sender_email, sender_password, '⚠ Жалоба на канал', comp_body)
            if success:
                sent_emails += 1
                log_entries.append(f"[✅] {sender_email} → {receiver}")
            else:
                log_entries.append(f"[❌] {sender_email} → {receiver}")
            if len(log_entries) > 10:
                log_entries.pop(0)
            log_text = "\n".join(log_entries) if log_entries else "(пусто)"
            await progress_message.edit_text(
                f"🚀 **Отправка жалоб началась!** 🎬\n\n"
                f"**Прогресс**: {sent_emails} из {total_emails}\n"
                f"**Лог**:\n{log_text}"
            )
            await asyncio.sleep(1.5)
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    await progress_message.edit_text(
        f"🏁 **Отправка завершена!** 🎉\n\n"
        f"**Прогресс**: {sent_emails} из {total_emails}\n"
        f"**Лог**:\n{log_text}",
        reply_markup=main_keyboard
    )

# Обработчик USERNAME бота
@router.message(ComplaintStates.bot_username)
async def process_bot_username(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    bot_user = message.text
    data = await state.get_data()
    bot_id = data.get("complaint_id")
    if not senders:
        await message.answer("❌ Ошибка: нет доступных аккаунтов для отправки жалоб! 😔")
        await state.clear()
        return
    progress_message = await message.answer("🚀 **Отправка жалоб началась!** 🎬\n\nПрогресс: 0 из 2500\nЛог:\n(пусто)")
    await state.clear()
    comp_texts = {
        "1": f"Здравствуйте! Бот {bot_user} ищет личные данные пользователей! Прошу заблокировать!",
        "2": f"Уважаемая поддержка, бот {bot_user} подталкивает к суициду! Прошу заблокировать!",
        "3": f"Бот {bot_user} распространяет ЦП! Прошу немедленно заблокировать!",
        "4": f"Бот {bot_user} занимается мошенничеством! Прошу заблокировать!"
    }
    sent_emails = 0
    total_emails = len(senders) * len(receivers)
    log_entries = []
    for sender_email, sender_password in senders.items():
        for receiver in receivers:
            comp_text = comp_texts.get(bot_id, comp_texts["1"])
            comp_body = comp_text.format(bot_user=bot_user.strip())
            success = await send_email(receiver, sender_email, sender_password, '⚠ Жалоба на бота', comp_body)
            if success:
                sent_emails += 1
                log_entries.append(f"[✅] {sender_email} → {receiver}")
            else:
                log_entries.append(f"[❌] {sender_email} → {receiver}")
            if len(log_entries) > 10:
                log_entries.pop(0)
            log_text = "\n".join(log_entries) if log_entries else "(пусто)"
            await progress_message.edit_text(
                f"🚀 **Отправка жалоб началась!** 🎬\n\n"
                f"**Прогресс**: {sent_emails} из {total_emails}\n"
                f"**Лог**:\n{log_text}"
            )
            await asyncio.sleep(1.5)
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    await progress_message.edit_text(
        f"🏁 **Отправка завершена!** 🎉\n\n"
        f"**Прогресс**: {sent_emails} из {total_emails}\n"
        f"**Лог**:\n{log_text}",
        reply_markup=main_keyboard
    )

# Обработчик ссылки на группу
@router.message(ComplaintStates.group_link)
async def process_group_link(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(group_link=message.text)
    await state.set_state(ComplaintStates.group_id)
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    await message.answer("🆔 Введи TG ID чата:", reply_markup=main_keyboard)

# Обработчик TG ID группы
@router.message(ComplaintStates.group_id)
async def process_group_id(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(group_id=message.text)
    data = await state.get_data()
    group_choice = data.get("complaint_id")
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    if group_choice == "4":
        await state.set_state(ComplaintStates.group_violation)
        await message.answer("⚠ Введи ссылку на нарушение в чате:", reply_markup=main_keyboard)
    else:
        await send_group_complaint(message, state)
        await state.clear()

# Обработчик ссылки на нарушение в группе
@router.message(ComplaintStates.group_violation)
async def process_group_violation(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(group_violation=message.text)
    await send_group_complaint(message, state)
    await state.clear()

# Отправка жалобы на группу
async def send_group_complaint(message: Message, state: FSMContext):
    data = await state.get_data()
    user_chat = data.get("group_link")
    id_chat = data.get("group_id")
    ssilka = data.get("group_violation")
    group_choice = data.get("complaint_id")
    if not senders:
        await message.answer("❌ Ошибка: нет доступных аккаунтов для отправки жалоб! 😔")
        await state.clear()
        return
    progress_message = await message.answer("🚀 **Отправка жалоб началась!** 🎬\n\nПрогресс: 0 из 2500\nЛог:\n(пусто)")
    comp_texts = {
        "1": f"Здравствуйте! Группа {user_chat} (ID: {id_chat}) подозрительная! Прошу заблокировать!",
        "2": f"Уважаемая поддержка, группа {user_chat} (ID: {id_chat}) спамит! Прошу заблокировать!",
        "3": f"Группа {user_chat} (ID: {id_chat}) имеет провокационную аватарку! Прошу заблокировать!",
        "4": f"Группа {user_chat} (ID: {id_chat}) пропагандирует насилие! Нарушение: {ssilka}. Заблокируйте!"
    }
    sent_emails = 0
    total_emails = len(senders) * len(receivers)
    log_entries = []
    for sender_email, sender_password in senders.items():
        for receiver in receivers:
            comp_text = comp_texts.get(group_choice, comp_texts["1"])
            comp_body = comp_text.format(user_chat=user_chat.strip(), id_chat=id_chat.strip(), ssilka=ssilka.strip() if ssilka else "")
            success = await send_email(receiver, sender_email, sender_password, '⚠ Жалоба на группу', comp_body)
            if success:
                sent_emails += 1
                log_entries.append(f"[✅] {sender_email} → {receiver}")
            else:
                log_entries.append(f"[❌] {sender_email} → {receiver}")
            if len(log_entries) > 10:
                log_entries.pop(0)
            log_text = "\n".join(log_entries) if log_entries else "(пусто)"
            await progress_message.edit_text(
                f"🚀 **Отправка жалоб началась!** 🎬\n\n"
                f"**Прогресс**: {sent_emails} из {total_emails}\n"
                f"**Лог**:\n{log_text}"
            )
            await asyncio.sleep(1.5)
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")]
    ])
    await progress_message.edit_text(
        f"🏁 **Отправка завершена!** 🎉\n\n"
        f"**Прогресс**: {sent_emails} из {total_emails}\n"
        f"**Лог**:\n{log_text}",
        reply_markup=main_keyboard
    )

# Проверка бана и подписки
@router.message()
async def check_ban_and_subscription(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"
    all_users[user_id] = username
    logger.info(f"Checking ban/subscription for user {user_id} (@{username}), command: {message.text}")
    if user_id in banned_users:
        logger.info(f"User {user_id} is banned")
        await message.answer("❌ Вы забанены.")
        return False
    current_state = await state.get_state()
    if user_id in ADMIN_IDS or current_state == SupportStates.waiting_for_question.state or \
       (message.text and message.text.lower() in ["/start", "/activate"]):
        logger.info(f"Allowing user {user_id} (admin, support, /start, or /activate)")
        return True
    if user_id not in subscribed_users:
        logger.info(f"User {user_id} has no subscription")
        await message.answer("❌ У вас нет подписки. Используйте /activate <key> или обратитесь в техподдержку.")
        return False
    return True

# Запуск бота
async def main():
    logger.info("Starting bot polling")
    max_retries = 5
    retry_delay = 15
    attempt = 0
    await reset_updates()
    await set_bot_commands()
    asyncio.create_task(check_subscriptions())
    asyncio.create_task(clean_expired_keys())
    while attempt < max_retries:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook cleared, starting polling")
            await dp.start_polling(bot, handle_signals=True)
            break
        except TelegramConflictError as e:
            attempt += 1
            logger.error(f"Conflict error (attempt {attempt}/{max_retries}): {e}. Retrying in {retry_delay:.2f} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay *= 1.5
            await reset_updates()
        except Exception as e:
            logger.error(f"Unexpected error in polling: {e}")
            break
    else:
        logger.error(f"Failed to start bot after {max_retries} attempts. Please create a new token or check for other bot instances.")

if __name__ == "__main__":
    asyncio.run(main())
