import random
import string
import asyncio
import logging
import sys
import aiohttp
import certifi
import ssl
import time
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand, \
    BotCommandScopeDefault, BotCommandScopeChat
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramConflictError
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PhoneCodeInvalidError
from telethon.tl.functions.messages import GetHistoryRequest, DeleteHistoryRequest
import time
from telethon.tl.functions.messages import GetBotCallbackAnswerRequest
from telethon.tl.types import KeyboardButtonUrl, KeyboardButtonCallback

# Проверка версии Python
if sys.version_info < (3, 8):
    raise RuntimeError("This bot requires Python 3.8 or higher")

# Настройка кодировки консоли для Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Форматтер для логов
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Обработчик для файла
file_handler = logging.FileHandler("bot.log", encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# Обработчик для консоли с поддержкой UTF-8
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)

# Добавление обработчиков
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# Токен бота и ID администраторов
BOT_TOKEN = "8177021318:AAEusRPXgP6URYs8MCpSQ3--6dw1_Cf86N0"
ADMIN_IDS = {5241019139, 7438900969}  # Множество ID администраторов (добавьте реальные ID)

# Конфигурация для telethon
API_ID = "27683579"
API_HASH = "a1d0fc7d0c9a41ff5e0ae6a6ed8e2dbb"
PHONE_NUMBER = "+79131500404"
SESSION_STRING = "1ApWapzMBu6o7KbVYr0NFMa4oWpQd4o83V6Yt0zfvx2Q95EpLbVmZYF9BBqHyOTc-pWVqHblX8hCJ6kPxRZ2-KNOpkbmIjFqPJt-W0efl2jNLTq7OhHC3cJGOqCvST68KuCRAePf9fUdPMRnoqRLLavBiSRIldnLUvQciiWBSp3HIAXbEJSuPpq3ugDRyFLvwG8svvz9bDs0EK0Ykw3z_H9UtrwPPgXVj8FoFF7_jomQxGhz0J5UiR1uW0m2rKj3YRfe8zSw50STPFNteITYysb5s2rj5I1GD1U_aNsHS0mMb8QWkCVAaRJWTpRnZkXq1Cf21xVmVAX_8EBVqB1m5FCR9AzbnqQM="
TARGET_BOT = 'bini228777_bot'

# Инициализация клиента telethon с использованием строки сессии
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Хранилища
banned_users = set()
all_users = {}
subscribed_users = {}
support_questions = []
keys = {}

# Генерация списка отправителей
senders = {}
for _ in range(250):  # Gmail
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(8, 12)))
    senders[f"{username}@gmail.com"] = "dummy_password"
for _ in range(250):  # Mail.ru
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(8, 12)))
    senders[f"{username}@mail.ru"] = "dummy_password"
receivers = ['sms@telegram.org', 'dmca@telegram.org', 'abuse@telegram.org', 'sticker@telegram.org',
             'support@telegram.org']

# Настройка SSL контекста
ssl_context = ssl.create_default_context(cafile=certifi.where())

# Вспомогательные функции для взаимодействия с @hunterscambot
async def wait_for_specific_response(client, bot_username, keyword, timeout=10):
    logger.info(f"Waiting for message containing: {keyword.replace('🔍', '[magnifying glass]')}")
    start_time = time.time()
    while time.time() - start_time < timeout:
        history = await client(GetHistoryRequest(
            peer=bot_username,
            limit=1,
            offset_date=None,
            offset_id=0,
            max_id=0,
            min_id=0,
            add_offset=0,
            hash=0
        ))
        if history.messages:
            last_msg = history.messages[0].message
            if keyword in last_msg:
                logger.info("Received expected message")
                return True
        await asyncio.sleep(1)
    logger.warning("Timeout: expected message not received")
    return False

async def get_n_latest_bot_messages(client, bot_username, count=2):
    history = await client(GetHistoryRequest(
        peer=bot_username,
        limit=count + 1,
        offset_date=None,
        offset_id=0,
        max_id=0,
        min_id=0,
        add_offset=0,
        hash=0
    ))
    return history.messages

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
            async with session.get(url, ssl=ssl_context) as response:
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
        expired_keys = [key for key, data in keys.items() if
                        data["used"] and data["expires"] and data["expires"] < current_time]
        for key in expired_keys:
            del keys[key]
            logger.info(f"Key {key} removed due to expiration")
        await asyncio.sleep(3600)

# Настройка меню команд
async def set_bot_commands():
    default_commands = [
        BotCommand(command="/start", description="🌟 Запустить бота и выбрать действие"),
        BotCommand(command="/getid", description="🆔 Узнать свой ID"),
        BotCommand(command="/activate", description="🔑 Активировать ключ для получения подписки")
    ]
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
    try:
        await bot.set_my_commands(commands=default_commands, scope=BotCommandScopeDefault())
        logger.info("Default bot commands set successfully")
        for admin_id in ADMIN_IDS:
            try:
                await bot.get_chat(admin_id)
                await bot.set_my_commands(commands=admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
                logger.info(f"Admin bot commands set successfully for admin {admin_id}")
            except Exception as e:
                logger.warning(f"Failed to set admin commands for admin {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Error setting bot commands: {e}")

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

class ScriptStates(StatesGroup):
    waiting_for_script_input = State()
    waiting_for_phone_number = State()
    waiting_for_username = State()  # Новое состояние для ввода username

# Функция генерации ключа
def generate_key(length=16):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

# Проверка бана и подписки
async def check_ban_and_subscription(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in banned_users or (user_id not in ADMIN_IDS and user_id not in subscribed_users):
        await message.answer("❌ Доступ запрещён.")
        await state.clear()
        return False
    return True

# Пользовательский скрипт
async def run_custom_script(user_id: int, callback: CallbackQuery, state: FSMContext) -> None:
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
    ])
    try:
        await callback.message.edit_text(
            "Запуск Ожидайте..."
        )

        # Создаём и запускаем клиент Telethon с использованием строки сессии
        hunter_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await hunter_client.start()
        logger.info(f"Telethon client started for user {user_id}")

        # Очистка истории чата перед началом
        try:
            logger.info(f"Clearing chat history with bini228777_bot for user {user_id}")
            await hunter_client(DeleteHistoryRequest(
                peer='bini228777_bot',
                max_id=0,
                just_clear=True,
                revoke=True
            ))
            logger.info(f"Chat history cleared with bini228777_bot for user {user_id}")
        except Exception as e:
            logger.error(f"Error clearing chat history for user {user_id}: {e}")

        # Отправка команды /start
        await hunter_client.send_message('bini228777_bot', "start")
        logger.info(f"Sent 'start' to bini228777_bot for user {user_id}")

        # Ожидание ответа от бота
        if await wait_for_specific_response(hunter_client, 'bini228777_bot', "🔍 Передайте мне то, что знаете",
                                            timeout=15):
            await asyncio.sleep(1)

            # Запрашиваем номер телефона у пользователя БЕЗ КНОПОК
            await callback.message.edit_text(
                "📱 Введите номер телефона в формате +7XXXXXXXXXX:"
            )
            # Сохраняем hunter_client в состояние
            await state.update_data(hunter_client=hunter_client, callback_message=callback.message)
            await state.set_state(ScriptStates.waiting_for_phone_number)
            logger.info(f"Set state to waiting_for_phone_number for user {user_id}")
            return  # Ждём ввода номера телефона

        else:
            await callback.message.edit_text(
                "⚠ Сообщение от bini228777_bot не получено",
                reply_markup=main_keyboard
            )
            logger.warning(f"Expected message not received from bini228777_bot for user {user_id}")
            if hunter_client.is_connected():
                await hunter_client.disconnect()

    except FloodWaitError as e:
        logger.error(f"Flood wait error for user {user_id}: wait for {e.seconds} seconds")
        await callback.message.edit_text(
            f"❌ Слишком много попыток. Пожалуйста, подождите {e.seconds} секунд и попробуйте снова.",
            reply_markup=main_keyboard
        )
        if hunter_client.is_connected():
            await hunter_client.disconnect()
    except SessionPasswordNeededError:
        logger.error(f"Two-factor authentication required for user {user_id}")
        await callback.message.edit_text(
            "❌ Требуется двухфакторная аутентификация. Обратитесь к администратору.",
            reply_markup=main_keyboard
        )
        if hunter_client.is_connected():
            await hunter_client.disconnect()
    except PhoneCodeInvalidError:
        logger.error(f"Invalid authentication code for user {user_id}")
        await callback.message.edit_text(
            "❌ Неверный код подтверждения. Попробуйте снова.",
            reply_markup=main_keyboard
        )
        if hunter_client.is_connected():
            await hunter_client.disconnect()
    except Exception as e:
        logger.error(f"Error interacting with bini228777_bot for user {user_id}: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при взаимодействии с bini228777_bot: {e}",
            reply_markup=main_keyboard
        )
        if hunter_client.is_connected():
            await hunter_client.disconnect()
    finally:
        pass

# Обработчик ввода номера телефона
@router.message(ScriptStates.waiting_for_phone_number)
async def process_phone_number(message: Message, state: FSMContext):
    user_id = message.from_user.id
    phone_number = message.text.strip()
    logger.info(f"Received phone number {phone_number} from user {user_id} in state waiting_for_phone_number")

    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
    ])

    # Извлекаем hunter_client из состояния
    data = await state.get_data()
    hunter_client = data.get("hunter_client")
    logger.info(f"Hunter client retrieved from state for user {user_id}: {hunter_client is not None}")

    if not hunter_client:
        await message.answer(
            "❌ Ошибка: клиент Telethon не доступен. Попробуйте снова.",
            reply_markup=main_keyboard
        )
        await state.clear()
        return

    try:
        # Проверка формата номера телефона
        if not phone_number.startswith("+") or len(phone_number) < 12:
            await message.answer(
                "❌ Номер телефона должен быть в формате +7XXXXXXXXXX. Попробуйте снова:"
            )
            return

        # Проверяем, что клиент подключён
        if not hunter_client.is_connected():
            await message.answer(
                "❌ Ошибка: соединение с Telegram потеряно. Попробуйте снова.",
                reply_markup=main_keyboard
            )
            await state.clear()
            return

        # Отправляем номер телефона боту
        await hunter_client.send_message('bini228777_bot', phone_number)
        logger.info(f"Sent phone number {phone_number} to bini228777_bot for user {user_id}")

        # Ждём ответа от бота
        await message.answer("Поиск...")
        await asyncio.sleep(15)  # Ожидание ответа

        # Проверяем, получили ли мы сообщения
        messages = await get_n_latest_bot_messages(hunter_client, 'bini228777_bot', count=2)
        logger.info(f"Received {len(messages) if messages else 0} messages from bini228777_bot for user {user_id}")
        if messages and len(messages) >= 2:
            response = messages[0].message
            await message.answer(
                f"😺 Отчет:\n{response}",
                reply_markup=main_keyboard
            )
            logger.info(f"Response from bini228777_bot for user {user_id}: {response}")
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id,
                                           f"🔔 Пользователь ID {user_id} получил отчет по номеру {phone_number}")
                except Exception as e:
                    logger.error(f"Error notifying admin {admin_id}: {e}")
        else:
            # Дополнительно проверим историю сообщений для отладки
            history = await hunter_client(GetHistoryRequest(
                peer='bini228777_bot',
                limit=5,
                offset_date=None,
                offset_id=0,
                max_id=0,
                min_id=0,
                add_offset=0,
                hash=0
            ))
            if history.messages:
                logger.info(f"Last 5 messages from bini228777_bot: {[msg.message for msg in history.messages]}")
            else:
                logger.info("No messages found in history from bini228777_bot")

            await message.answer(
                "⚠ bini228777_bot не ответил или недостаточно сообщений. Проверьте, работает ли бот, и попробуйте снова.",
                reply_markup=main_keyboard
            )
            logger.warning(f"No response or not enough messages from bini228777_bot for user {user_id}")
    except Exception as e:
        logger.error(f"Error sending phone number for user {user_id}: {e}")
        await message.answer(
            f"❌ Ошибка при отправке номера телефона: {e}",
            reply_markup=main_keyboard
        )
    finally:
        if hunter_client.is_connected():
            await hunter_client.disconnect()
            logger.info(f"Telethon client disconnected for user {user_id}")
        await state.clear()

async def find_and_click_button(client, bot_username, button_position=3, timeout=15):
    logger.info(f"Searching for button at position {button_position + 1} (index {button_position})")
    start_time = time.time()
    while time.time() - start_time < timeout:
        history = await client(GetHistoryRequest(
            peer=bot_username,
            limit=1,
            offset_date=None,
            offset_id=0,
            max_id=0,
            min_id=0,
            add_offset=0,
            hash=0
        ))
        if history.messages:
            message = history.messages[0]
            logger.info(f"Message text: {message.message}")
            if hasattr(message, 'reply_markup') and message.reply_markup:
                logger.info("Found inline buttons:")
                buttons = [button for row in message.reply_markup.rows for button in row.buttons]
                for i, button in enumerate(buttons):
                    logger.info(f"Button {i + 1} (index {i}): '{button.text}' | Type: {type(button).__name__}")
                    if isinstance(button, KeyboardButtonCallback):
                        logger.info(f"Callback data for button {i + 1}: {button.data}")
                if len(buttons) > button_position:
                    target_button = buttons[button_position]
                    logger.info(f"Selected button at position {button_position + 1}: '{target_button.text}'")
                    try:
                        if isinstance(target_button, KeyboardButtonUrl):
                            logger.info(f"This is a URL button: {target_button.url}")
                            return True
                        elif isinstance(target_button, KeyboardButtonCallback):
                            logger.info(f"Sending callback query with data: {target_button.data}")
                            try:
                                await client(GetBotCallbackAnswerRequest(
                                    peer=bot_username,
                                    msg_id=message.id,
                                    data=target_button.data
                                ))
                                logger.info("Callback query successfully sent.")
                            except Exception as e:
                                if "did not answer to the callback query in time" in str(e):
                                    logger.info("Bot did not respond in time, but query sent (timeout).")
                                else:
                                    logger.error(f"Error sending callback query: {e}")
                                    return False
                            return True
                        else:
                            await message.click(button_position)
                            logger.info("Button successfully clicked via click().")
                            return True
                    except Exception as e:
                        logger.error(f"Error clicking button: {e}")
                        return False
                else:
                    logger.info(f"Not enough buttons: found {len(buttons)}, required {button_position + 1}")
        else:
            logger.info("No messages found.")
        await asyncio.sleep(1)
    logger.warning(f"Timeout: button at position {button_position + 1} not found.")
    return False

@router.message(ScriptStates.waiting_for_username)
async def process_username_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.text.strip()
    logger.info(f"Received username {username} from user {user_id} in state waiting_for_username")

    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
    ])

    # Извлекаем hunter_client из состояния
    data = await state.get_data()
    hunter_client = data.get("hunter_client")
    logger.info(f"Hunter client retrieved from state for user {user_id}: {hunter_client is not None}")

    if not hunter_client:
        await message.answer(
            "❌ Ошибка: клиент Telethon не доступен. Попробуйте снова.",
            reply_markup=main_keyboard
        )
        await state.clear()
        return

    try:
        # Проверка формата username
        if not username.startswith("@"):
            await message.answer(
                "❌ Username должен начинаться с @ (например, @username). Попробуйте снова:"
            )
            return

        # Проверяем, что клиент подключён
        if not hunter_client.is_connected():
            await message.answer(
                "❌ Ошибка: соединение с Telegram потеряно. Попробуйте снова.",
                reply_markup=main_keyboard
            )
            await state.clear()
            return

        # Отправляем username боту
        await hunter_client.send_message(TARGET_BOT, username)
        logger.info(f"Sent username {username} to {TARGET_BOT} for user {user_id}")

        # Пытаемся найти и нажать на четвёртую кнопку
        if await find_and_click_button(hunter_client, TARGET_BOT, button_position=3, timeout=15):
            await asyncio.sleep(10)  # Ожидание после нажатия кнопки
            messages = await get_n_latest_bot_messages(hunter_client, TARGET_BOT, count=2)
            if messages and len(messages) >= 2:
                response = messages[0].message
                await message.answer(
                    f"😺 Отчет по {username}:\n{response}",
                    reply_markup=main_keyboard
                )
                logger.info(f"Response from {TARGET_BOT} for user {user_id}: {response}")
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(admin_id,
                                              f"🔔 Пользователь ID {user_id} получил отчет по username {username}")
                    except Exception as e:
                        logger.error(f"Error notifying admin {admin_id}: {e}")
            else:
                await message.answer(
                    f"⚠ {TARGET_BOT} не ответил или недостаточно сообщений. Проверьте, работает ли бот, и попробуйте снова.",
                    reply_markup=main_keyboard
                )
                logger.warning(f"No response or not enough messages from {TARGET_BOT} for user {user_id}")
        else:
            await message.answer(
                "❌ Не удалось нажать на четвёртую кнопку. Попробуйте снова.",
                reply_markup=main_keyboard
            )
            logger.warning(f"Failed to click the fourth button for user {user_id}")

    except Exception as e:
        logger.error(f"Error processing username for user {user_id}: {e}")
        await message.answer(
            f"❌ Ошибка при обработке username: {e}",
            reply_markup=main_keyboard
        )
    finally:
        if hunter_client.is_connected():
            await hunter_client.disconnect()
            logger.info(f"Telethon client disconnected for user {user_id}")
        await state.clear()

# Команда /generatekey
@router.message(Command("generatekey"))
async def generate_key_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён. Эта команда только для админа.")
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
        days = keys[key]["days"]
        expires = datetime.now() + timedelta(days=days)
        keys[key]["used"] = True
        keys[key]["user_id"] = user_id
        keys[key]["expires"] = expires
        subscribed_users[user_id] = {
            "username": username,
            "expires": expires
        }
        await message.answer(f"✅ Ключ активирован! Подписка выдана до {expires.strftime('%Y-%m-%d %H:%M')}.")
        logger.info(f"User {user_id} (@{username}) activated key {key} for {days} days")
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id,
                                       f"🔔 Пользователь @{username} (ID: {user_id}) активировал ключ `{key}` на {days} дней.")
            except Exception as e:
                logger.error(f"Error notifying admin {admin_id} about key activation: {e}")
    except IndexError:
        await message.answer("❌ Укажите ключ: /activate <key>")

# Команда /listkeys
@router.message(Command("listkeys"))
async def list_keys_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён. Эта команда только для админа.")
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

@router.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"
    all_users[user_id] = username
    logger.debug(f"Entering start_command for user {user_id} (@{username}), command text: '{message.text}'")
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
            [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
            [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
            [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]  # Новая кнопка
        ])
        logger.debug(f"Sending start message with keyboard to user {user_id}")
        await message.answer(
            "🌟 SN0S3R - Жалобный Убийца 🌟\n\n"
            "Выбери свою цель, обратись в поддержку или запусти скрипт! 🚀",
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
        await message.answer("❌ Доступ запрещён. Эта команда только для админа.")
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
        await message.answer("❌ Доступ запрещён. Эта команда только для админа.")
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
        await message.answer("❌ Доступ запрещён. Эта команда только для админа.")
        return
    if not all_users:
        await message.answer("📭 Пользователей пока нет.")
        return
    user_list = "\n".join(
        f"ID: {user_id}, @{username}" +
        (f" ✅ (до {subscribed_users[user_id]['expires'].strftime('%Y-%m-%d %H:%M')})" if user_id in subscribed_users and
                                                                                         subscribed_users[user_id][
                                                                                             "expires"] else " ✅" if user_id in subscribed_users else "") +
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
        await message.answer("❌ Доступ запрещён. Эта команда только для админа.")
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
        await message.answer(
            f"✅ Пользователю @{username} (ID: {user_id}) выдана подписка до {expires.strftime('%Y-%m-%d %H:%M')}.")
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
        await message.answer("❌ Доступ запрещён. Эта команда только для админа.")
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
        await message.answer("❌ Доступ запрещён. Эта команда только для админа.")
        return
    if not support_questions:
        await message.answer("📭 Вопросов пока нет.")
        return
    for idx, q in enumerate(support_questions, 1):
        await message.answer(
            f"❓ Вопрос #{idx} от @{q['username']} (ID: {q['user_id']}):\n{q['text']}"
        )
    await message.answer("📬 Ответьте, цитируя вопрос (свайп), чтобы отправить ответ пользователю.")

# Обработчик выдачи подписки
@router.callback_query(lambda c: c.data == "issue_subscription")
async def process_issue_subscription(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.message.answer("❌ Доступ запрещён.")
        return
    await state.set_state(AdminStates.waiting_for_subscription_id)
    await callback.message.answer("👤 Введите @username пользователя для выдачи подписки:")
    await callback.message.delete()

# Ввод username для подписки
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

@router.callback_query(lambda c: c.data.startswith("choice_"))
async def process_choice(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in banned_users or \
            (callback.from_user.id not in ADMIN_IDS and callback.from_user.id not in subscribed_users):
        await callback.message.answer("❌ Доступ запрещён.")
        return
    choice = callback.data
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
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
    elif choice == "choice_script":
        await run_custom_script(callback.from_user.id, callback, state)
    elif choice == "choice_username":
        await run_username_script(callback.from_user.id, callback, state)  # Новая функция
    elif choice == "choice_back":
        await callback.message.edit_text(
            "🌟 **SN0S3R - Жалобный Убийца** 🌟\n\n"
            "Выбери свою цель, обратись в поддержку или запусти скрипт! 🚀",
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
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
    ])
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"❓ Новый вопрос от @{username} (ID: {user_id}):\n{question}"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки вопроса админу {admin_id}: {e}")
    await message.answer(
        "✅ Ваш вопрос отправлен! Ожидайте ответа. 😊",
        reply_markup=main_keyboard
    )
    await state.clear()

# Обработчик ответа от администратора
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

# Обработчик ввода сообщения для скрипта
@router.message(ScriptStates.waiting_for_script_input)
async def process_script_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"
    user_input = message.text
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
    ])

    def console_code_callback():
        return input("Please enter the code you received: ")

    def console_password_callback():
        return input("Please enter your two-factor authentication password: ")

    try:
        await client.start(
            phone=PHONE_NUMBER,
            code_callback=console_code_callback,
            password=console_password_callback
        )
        logger.info(f"Telethon client started for user {user_id}")
        await client.send_message(TARGET_BOT, user_input)
        logger.info(f"Message sent to {TARGET_BOT} by user {user_id}: {user_input}")
        async for response in client.iter_messages(TARGET_BOT, limit=1, wait_time=10):
            response_text = response.text
            break
        else:
            response_text = "Не удалось получить ответ от бота."
        await message.answer(
            f"📬 **Ответ от бота {TARGET_BOT}:**\n{response_text}",
            reply_markup=main_keyboard
        )
        logger.info(f"Response from {TARGET_BOT} sent to user {user_id}: {response_text}")
    except PhoneCodeInvalidError:
        logger.error(f"Invalid authentication code for user {user_id}")
        await message.answer(
            "❌ Введён неверный код подтверждения. Попробуйте снова.",
            reply_markup=main_keyboard
        )
    except FloodWaitError as e:
        logger.error(f"Flood wait error for user {user_id}: wait for {e.seconds} seconds")
        await message.answer(
            f"❌ Слишком много попыток. Пожалуйста, подождите {e.seconds} секунд и попробуйте снова.",
            reply_markup=main_keyboard
        )
    except SessionPasswordNeededError:
        logger.error(f"Two-factor authentication required for user {user_id}")
        await message.answer(
            "❌ Требуется двухфакторная аутентификация. Введите пароль в консоли.",
            reply_markup=main_keyboard
        )
    except Exception as e:
        logger.error(f"Error processing script input for user {user_id}: {e}")
        await message.answer(
            "❌ Ошибка при отправке сообщения или получении ответа. Попробуйте позже.",
            reply_markup=main_keyboard
        )
    finally:
        await client.disconnect()
        logger.info(f"Telethon client disconnected for user {user_id}")
        await state.clear()

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
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
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
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
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

# Обработчик username для аккаунта
@router.message(ComplaintStates.username)
async def process_username(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(username=message.text)
    await state.set_state(ComplaintStates.tg_id)
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
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
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
    ])
    await message.answer("💬 Введи ссылку на чат:", reply_markup=main_keyboard)

# Обработчик ссылки на чат
@router.message(ComplaintStates.chat_link)
async def process_chat_link(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(chat_link=message.text)
    await state.set_state(ComplaintStates.violation_link)
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
    ])
    await message.answer("⚠ Введи ссылку на нарушение в чате:", reply_markup=main_keyboard)

# Обработчик ссылки на нарушение
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
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
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
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
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
        "4": f"Канал {channel_link} продает доксинг/результат! Нарушение: {channel_violation}. Прошу заблокировать!",
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
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
    ])
    await progress_message.edit_text(
        f"🏁 **Отправка завершена!** 🎉\n\n"
        f"**Прогресс**: {sent_emails} из {total_emails}\n"
        f"**Лог**:\n{log_text}",
        reply_markup=main_keyboard
    )

# Обработчик username бота
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
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
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
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")]
    ])
    await message.answer("🆔 Введи ID группы:", reply_markup=main_keyboard)

# Обработчик ID группы
@router.message(ComplaintStates.group_id)
async def process_group_id(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(group_id=message.text)
    await state.set_state(ComplaintStates.group_violation)
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
    ])
    await message.answer("⚠ Введи ссылку на нарушение в группе:", reply_markup=main_keyboard)

# Обработчик ссылки на нарушение в группе
@router.message(ComplaintStates.group_violation)
async def process_group_violation(message: Message, state: FSMContext):
    if not await check_ban_and_subscription(message, state):
        return
    await state.update_data(group_violation=message.text)
    data = await state.get_data()
    group_link = data.get("group_link")
    group_id = data.get("group_id")
    group_violation = data.get("group_violation")
    group_id_comp = data.get("complaint_id")
    if not senders:
        await message.answer("❌ Ошибка: нет доступных аккаунтов для отправки жалоб! 😔")
        await state.clear()
        return
    progress_message = await message.answer("🚀 **Отправка жалоб началась!** 🎬\n\nПрогресс: 0 из 2500\nЛог:\n(пусто)")
    await state.clear()
    comp_texts = {
        "1": f"Здравствуйте! Группа {group_link} (ID: {group_id}) нарушает правила Telegram! Нарушение: {group_violation}. Прошу заблокировать!",
        "2": f"Уважаемая поддержка, группа {group_link} (ID: {group_id}) занимается спамом! Нарушение: {group_violation}. Прошу заблокировать!",
        "3": f"Группа {group_link} (ID: {group_id}) нарушает правила из-за аватарки/названия! Нарушение: {group_violation}. Прошу заблокировать!",
        "4": f"Группа {group_link} (ID: {group_id}) пропагандирует насилие! Нарушение: {group_violation}. Срочно заблокируйте!"
    }
    sent_emails = 0
    total_emails = len(senders) * len(receivers)
    log_entries = []
    for sender_email, sender_password in senders.items():
        for receiver in receivers:
            comp_text = comp_texts.get(group_id_comp, comp_texts["1"])
            comp_body = comp_text.format(
                group_link=group_link.strip(),
                group_id=group_id.strip(),
                group_violation=group_violation.strip()
            )
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
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
    ])
    await progress_message.edit_text(
        f"🏁 **Отправка завершена!** 🎉\n\n"
        f"**Прогресс**: {sent_emails} из {total_emails}\n"
        f"**Лог**:\n{log_text}",
        reply_markup=main_keyboard
    )

async def run_username_script(user_id: int, callback: CallbackQuery, state: FSMContext) -> None:
    main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снос", callback_data="choice_snos")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="choice_support")],
        [InlineKeyboardButton(text="Пробив по номеру", callback_data="choice_script")],
        [InlineKeyboardButton(text="Пробив по Username", callback_data="choice_username")]
    ])
    try:
        await callback.message.edit_text(
            "Запуск скрипта... Ожидайте..."
        )

        # Создаём и запускаем клиент Telethon
        hunter_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await hunter_client.start()
        logger.info(f"Telethon client started for user {user_id} for username lookup")

        # Очистка истории чата
        try:
            logger.info(f"Clearing chat history with {TARGET_BOT} for user {user_id}")
            await hunter_client(DeleteHistoryRequest(
                peer=TARGET_BOT,
                max_id=0,
                just_clear=True,
                revoke=True
            ))
            logger.info(f"Chat history cleared with {TARGET_BOT} for user {user_id}")
        except Exception as e:
            logger.error(f"Error clearing chat history for user {user_id}: {e}")

        # Отправка команды /start
        await hunter_client.send_message(TARGET_BOT, "/start")
        logger.info(f"Sent '/start' to {TARGET_BOT} for user {user_id}")

        # Ожидание ответа от бота
        response_received = await wait_for_specific_response(hunter_client, TARGET_BOT, "🔍 Передайте мне то, что знаете", timeout=15)
        if response_received:
            await asyncio.sleep(1)

            # Запрашиваем username
            await callback.message.edit_text(
                "👤 Введите username (например, @username):"
            )
            # Сохраняем hunter_client в состояние
            await state.update_data(hunter_client=hunter_client, callback_message=callback.message)
            await state.set_state(ScriptStates.waiting_for_username)
            logger.info(f"Set state to waiting_for_username for user {user_id}")
            return  # Ждём ввода username
        else:
            await callback.message.edit_text(
                f"⚠ Сообщение от {TARGET_BOT} не получено. Проверьте, работает ли бот.",
                reply_markup=main_keyboard
            )
            logger.warning(f"Expected message not received from {TARGET_BOT} for user {user_id}")
            if hunter_client.is_connected():
                await hunter_client.disconnect()

    except FloodWaitError as e:
        logger.error(f"Flood wait error for user {user_id}: wait for {e.seconds} seconds")
        await callback.message.edit_text(
            f"❌ Слишком много попыток. Пожалуйста, подождите {e.seconds} секунд и попробуйте снова.",
            reply_markup=main_keyboard
        )
        if hunter_client.is_connected():
            await hunter_client.disconnect()
    except SessionPasswordNeededError:
        logger.error(f"Two-factor authentication required for user {user_id}")
        await callback.message.edit_text(
            "❌ Требуется двухфакторная аутентификация. Обратитесь к администратору.",
            reply_markup=main_keyboard
        )
        if hunter_client.is_connected():
            await hunter_client.disconnect()
    except PhoneCodeInvalidError:
        logger.error(f"Invalid authentication code for user {user_id}")
        await callback.message.edit_text(
            "❌ Неверный код подтверждения. Попробуйте снова.",
            reply_markup=main_keyboard
        )
        if hunter_client.is_connected():
            await hunter_client.disconnect()
    except Exception as e:
        logger.error(f"Error interacting with {TARGET_BOT} for user {user_id}: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при взаимодействии с {TARGET_BOT}: {e}",
            reply_markup=main_keyboard
        )
        if hunter_client.is_connected():
            await hunter_client.disconnect()


# Основная функция
async def main():
    try:
        logger.info("Starting bot polling")
        await reset_updates()
        await set_bot_commands()
        await dp.start_polling(bot, skip_updates=True)
        logger.info("Webhook cleared, starting polling")
        tasks = [
            asyncio.create_task(check_subscriptions()),
            asyncio.create_task(clean_expired_keys())
        ]
        await asyncio.gather(*tasks)
    except TelegramConflictError:
        logger.warning("Webhook is set, attempting to delete it")
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
            async with session.get(url, ssl=ssl_context) as response:
                if response.status == 200:
                    logger.info("Webhook deleted, restarting polling")
                    await main()
                else:
                    logger.error(f"Failed to delete webhook: {await response.text()}")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
