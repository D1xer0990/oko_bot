import os
import json
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import re

# Загружаем токен из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Настройка базы данных с пулом соединений
Base = declarative_base()
engine = create_engine(
    DATABASE_URL,
    pool_size=5,  # Размер пула соединений
    max_overflow=10,  # Максимальное количество дополнительных соединений
    pool_recycle=3600,  # Время жизни соединения в секундах (1 час)
    pool_pre_ping=True  # Проверка соединений перед использованием
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Модели данных
class Person(Base):
    __tablename__ = "persons"
    
    id = Column(Integer, primary_key=True, index=True)
    fio = Column(String, nullable=False, index=True)  # Индекс для быстрого поиска
    phone = Column(String, nullable=False, index=True, unique=True)  # Индекс и уникальность
    birth = Column(String, nullable=False)
    car_number = Column(String, nullable=True, index=True)  # Индекс для поиска
    address = Column(Text, nullable=True)
    passport = Column(String, nullable=True, index=True)  # Индекс для поиска
    
    # Составной индекс для поиска
    __table_args__ = (
        Index('idx_person_search', 'fio', 'phone'),
    )

class UserLog(Base):
    __tablename__ = "user_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)  # Индекс для сортировки
    user_id = Column(Integer, nullable=False, index=True)  # Индекс для фильтрации
    username = Column(String, nullable=True)
    action = Column(String, nullable=False, index=True)  # Индекс для фильтрации
    details = Column(Text, nullable=True)
    
    # Составной индекс для частых запросов
    __table_args__ = (
        Index('idx_log_user_action', 'user_id', 'action', 'timestamp'),
    )

# Создаем таблицы
Base.metadata.create_all(bind=engine)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Коды доступа для разных ролей
USER_ACCESS_CODE = "12345"  # Обычные пользователи
ADMIN_ACCESS_CODE = "77777"  # Администраторы

# Состояния для пошагового ввода данных
class AddPersonStates(StatesGroup):
    waiting_for_fio = State()      # Ожидание ФИО
    waiting_for_phone = State()    # Ожидание телефона
    waiting_for_birth = State()    # Ожидание даты рождения
    waiting_for_car = State()      # Ожидание номера авто (опционально)
    waiting_for_address = State()  # Ожидание адреса (опционально)
    waiting_for_passport = State() # Ожидание паспорта (опционально)

class SearchStates(StatesGroup):
    waiting_for_query = State()    # Ожидание ввода поискового запроса

class CancelStates(StatesGroup):
    waiting_for_cancel = State()    # Состояние для отмены (не используется, но нужно для разделения)

# Глобальные переменные для отслеживания авторизации
authorized_users = set()  # Обычные пользователи
authorized_admins = set()  # Администраторы
authorized_usernames = set()  # Список имен пользователей, прошедших авторизацию

# Словарь для хранения временных данных пользователей при добавлении записи
user_temp_data = {}

# Функция для красивого форматирования записи
def format_record(record):
    """Форматирует запись в простом и чистом виде"""
    result = f"👤 ФИО: {record.fio}\n"
    result += f"📞 Телефон: {record.phone}\n"
    result += f"📅 Дата рождения: {record.birth}\n"
    
    if record.car_number:
        result += f"🚗 Номер авто: {record.car_number}\n"
    if record.address:
        result += f"🏠 Адрес: {record.address}\n"
    if record.passport:
        result += f"📄 Паспорт: {record.passport}\n"
    
    return result.rstrip()  # Убираем последний перенос строки

# Функции для работы с базой данных
@contextmanager
def get_db_session():
    """Контекстный менеджер для работы с сессией БД"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка в сессии БД: {e}")
        raise
    finally:
        db.close()

def load_database():
    """Загружает все записи из базы данных"""
    try:
        with get_db_session() as db:
            persons = db.query(Person).all()
            return persons
    except Exception as e:
        logger.error(f"Ошибка загрузки базы данных: {e}")
        return []

def save_person(person_data):
    """Сохраняет новую запись в базу данных"""
    try:
        with get_db_session() as db:
            person = Person(**person_data)
            db.add(person)
            db.flush()  # Получаем ID без коммита
            db.refresh(person)
            logger.info(f"Запись успешно сохранена с ID: {person.id}")
            return person
    except Exception as e:
        logger.error(f"Ошибка сохранения записи: {e}", exc_info=True)
        return None

def normalize_phone(phone):
    """Нормализует телефон к формату 11 цифр"""
    # Удаляем все нецифровые символы
    digits = re.sub(r'\D', '', phone)
    # Если начинается с 8, заменяем на 7
    if len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]
    # Если начинается с +7 или просто 7, но меньше 11 цифр, добавляем недостающие
    if len(digits) == 10:
        digits = '7' + digits
    return digits

def normalize_query(query):
    """Нормализует поисковый запрос"""
    # Удаляем лишние пробелы, приводим к нижнему регистру
    return ' '.join(query.strip().lower().split())

def search_persons(query, limit=100):
    """Улучшенный поиск записей по запросу с нормализацией"""
    try:
        # Проверяем, является ли запрос телефоном (много цифр)
        digits_only = re.sub(r'\D', '', query)
        
        with get_db_session() as db:
            if len(digits_only) >= 7:  # Если запрос содержит много цифр, ищем как телефон/паспорт
                # Нормализуем телефон для поиска
                normalized_phone = normalize_phone(query)
                # Ищем по телефону и паспорту (оба могут содержать цифры)
                persons = db.query(Person).filter(
                    Person.phone.contains(normalized_phone) |
                    Person.passport.contains(normalized_phone) |
                    Person.phone.contains(query) |  # Также ищем по оригинальному запросу
                    Person.passport.contains(query)
                ).limit(limit).all()
            else:
                # Текстовый поиск по всем полям с регистронезависимым поиском
                normalized_query = normalize_query(query)
                persons = db.query(Person).filter(
                    Person.fio.ilike(f'%{normalized_query}%') |
                    Person.phone.contains(normalized_query) |
                    Person.car_number.ilike(f'%{normalized_query}%') |
                    Person.address.ilike(f'%{normalized_query}%') |
                    Person.passport.contains(normalized_query)
                ).limit(limit).all()
            
            return persons
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return []

# Инициализация базы данных
try:
    # Проверяем подключение к базе данных
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("Подключение к базе данных успешно")
except Exception as e:
    logger.error(f"Ошибка подключения к базе данных: {e}")
    logger.error("Бот будет работать с ограниченным функционалом")

# Функции для логирования
def log_user_action(user_id, username, action, details=""):
    """Записывает действие пользователя в лог"""
    # Не логируем события авторизации для уже авторизованных пользователей
    try:
        normalized_username = (username or "").strip()
        if action.startswith("AUTH") and (
            user_id in authorized_users or
            user_id in authorized_admins or
            (normalized_username and normalized_username in authorized_usernames)
        ):
            return
    except Exception:
        # В случае любых сбоев проверки — не блокируем основное логирование
        pass
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"USER: {user_id} ({username}) | ACTION: {action} | DETAILS: {details}"
    logger.info(log_message)
    
    # Записываем в базу данных
    try:
        with get_db_session() as db:
            log_entry = UserLog(
                user_id=user_id,
                username=username,
                action=action,
                details=details
            )
            db.add(log_entry)
    except Exception as e:
        logger.error(f"Ошибка записи в базу данных: {e}")

def get_user_logs(limit=10):
    """Получает последние логи пользователей"""
    try:
        with get_db_session() as db:
            logs = db.query(UserLog).order_by(UserLog.timestamp.desc()).limit(limit).all()
            return [{
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "user_id": log.user_id,
                "username": log.username,
                "action": log.action,
                "details": log.details
            } for log in logs]
    except Exception as e:
        logger.error(f"Ошибка чтения логов: {e}")
        return []

def get_failed_auth_logs(limit=10):
    """Получает только неудачные попытки авторизации"""
    try:
        with get_db_session() as db:
            logs = db.query(UserLog).filter(
                UserLog.action == 'AUTH_FAILED'
            ).order_by(UserLog.timestamp.desc()).limit(limit).all()
            return [{
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "user_id": log.user_id,
                "username": log.username,
                "action": log.action,
                "details": log.details
            } for log in logs]
    except Exception as e:
        logger.error(f"Ошибка чтения логов: {e}")
        return []

# Создаем клавиатуры
def get_main_keyboard():
    """Создает главную клавиатуру с основными командами"""
    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=False,
        keyboard=[
            [KeyboardButton(text="🔍 Поиск"), KeyboardButton(text="➕ Добавить")],
            [KeyboardButton(text="📚 Документация"), KeyboardButton(text="📋 Список команд")]
        ]
    )
    return keyboard

def get_admin_keyboard():
    """Создает клавиатуру для администраторов"""
    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=False,
        keyboard=[
            [KeyboardButton(text="🔍 Поиск"), KeyboardButton(text="➕ Добавить")],
            [KeyboardButton(text="📊 Логи"), KeyboardButton(text="📋 Список команд")]
        ]
    )
    return keyboard

def get_inline_keyboard():
    """Создает inline клавиатуру с быстрыми действиями"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Найти запись", callback_data="search")],
            [InlineKeyboardButton(text="➕ Добавить запись", callback_data="add")],
            [InlineKeyboardButton(text="📚 Документация", callback_data="info")]
        ]
    )
    return keyboard

# Функции проверки авторизации и ролей
def is_authorized(user_id):
    """Проверяет, авторизован ли пользователь (любая роль)"""
    return user_id in authorized_users or user_id in authorized_admins

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in authorized_admins

def get_user_role(user_id):
    """Возвращает роль пользователя"""
    if user_id in authorized_admins:
        return "admin"
    elif user_id in authorized_users:
        return "user"
    else:
        return "unauthorized"

# Команда /start
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if is_authorized(user_id):
        role = get_user_role(user_id)
        if role == "admin":
            log_user_action(user_id, username, "START_COMMAND", "Вход администратора")
            help_text = """👑 Добро пожаловать, администратор!

🤖 Бот для работы с базой данных
🔧 У вас есть доступ ко всем функциям, включая логи

Выберите действие с помощью кнопок ниже:"""
            await message.answer(help_text, reply_markup=get_admin_keyboard())
        else:
            log_user_action(user_id, username, "START_COMMAND", "Вход обычного пользователя")
            help_text = """🤖 Добро пожаловать в бот для работы с базой данных!

Выберите действие с помощью кнопок ниже:"""
            await message.answer(help_text, reply_markup=get_main_keyboard())
    else:
        log_user_action(user_id, username, "START_COMMAND", "Попытка входа без авторизации")
        await message.answer("Для доступа к боту требуется код авторизации.\n\nВведите код доступа:")

# Глобальный обработчик проверки кода доступа
@dp.message_handler(lambda message: not is_authorized(message.from_user.id) and not message.text.startswith('/'))
async def check_access_code(message: types.Message):
    entered_code = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if entered_code == USER_ACCESS_CODE:
        authorized_users.add(user_id)
        if username:
            authorized_usernames.add(username)
        log_user_action(user_id, username, "AUTH_SUCCESS", f"Успешная авторизация пользователя с кодом: {entered_code}")
        help_text = """✅ Код доступа принят! Добро пожаловать!

🤖 Добро пожаловать в бот для работы с базой данных!

Выберите действие с помощью кнопок ниже:"""
        await message.answer(help_text, reply_markup=get_main_keyboard())
    elif entered_code == ADMIN_ACCESS_CODE:
        authorized_admins.add(user_id)
        if username:
            authorized_usernames.add(username)
        log_user_action(user_id, username, "AUTH_SUCCESS", f"Успешная авторизация администратора с кодом: {entered_code}")
        help_text = """👑 Код администратора принят! Добро пожаловать!

🤖 Бот для работы с базой данных
🔧 У вас есть доступ ко всем функциям, включая логи

Выберите действие с помощью кнопок ниже:"""
        await message.answer(help_text, reply_markup=get_admin_keyboard())
    else:
        log_user_action(user_id, username, "AUTH_FAILED", f"Неверный код: {entered_code}")
        await message.answer("Неверный код доступа. Попробуйте еще раз:")

# Обработчики кнопок
@dp.message_handler(lambda message: message.text == "🔍 Поиск")
async def search_button_handler(message: types.Message, state: FSMContext):
    if not is_authorized(message.from_user.id):
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    await SearchStates.waiting_for_query.set()
    await message.answer(
        "🔍 <b>Поиск в базе данных</b>\n\n"
        "<i>Введите поисковый запрос (ФИО, телефон, номер авто, адрес или паспорт):</i>",
        parse_mode='HTML'
    )

@dp.message_handler(state=SearchStates.waiting_for_query)
async def process_search_query(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    try:
        # Отмена поиска через команду /start
        if message.text == "/start":
            role = get_user_role(user_id)
            keyboard = get_admin_keyboard() if role == "admin" else get_main_keyboard()
            await message.answer("Поиск отменён.", reply_markup=keyboard)
            await state.finish()
            return

        query = message.text.strip()
        if not query:
            await message.answer("Введите непустой запрос")
            return

        logger.info(f"Поиск запроса от пользователя {user_id}: {query}")

        # Выполняем поиск с ограничением
        persons = search_persons(query, limit=50)  # Ограничиваем результаты
        
        logger.info(f"Найдено результатов: {len(persons) if persons else 0}")
        
        if persons:
            log_user_action(user_id, username, "SEARCH_SUCCESS", f"Найдено {len(persons)} результатов по запросу: {query}")
            
            # Формируем сообщения с пагинацией (Telegram ограничение 4096 символов)
            MAX_MESSAGE_LENGTH = 4000  # Оставляем запас
            result_message = f"🔍 <b>Найдено результатов: {len(persons)}</b>\n\n"
            
            current_message = result_message
            for i, person in enumerate(persons, 1):
                person_text = f"<b>Результат {i}:</b>\n{format_record(person)}\n\n"
                
                # Если сообщение станет слишком длинным, отправляем текущее и начинаем новое
                if len(current_message) + len(person_text) > MAX_MESSAGE_LENGTH:
                    await message.answer(current_message, parse_mode='HTML')
                    current_message = f"<b>Продолжение (результаты {i}-{len(persons)}):</b>\n\n{person_text}"
                else:
                    current_message += person_text
            
            # Отправляем последнее сообщение
            await message.answer(current_message, parse_mode='HTML')
        else:
            log_user_action(user_id, username, "SEARCH_NO_RESULTS", f"Ничего не найдено по запросу: {query}")
            await message.answer(
                "🔍 <b>Ничего не найдено</b>\n\n"
                "<i>Попробуйте изменить поисковый запрос или использовать часть слова</i>",
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке поискового запроса: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Произошла ошибка при поиске.</b>\n\n"
            "Пожалуйста, попробуйте еще раз.",
            parse_mode='HTML'
        )
    finally:
        # Завершаем состояние и возвращаем основную клавиатуру
        try:
            role = get_user_role(user_id)
            keyboard = get_admin_keyboard() if role == "admin" else get_main_keyboard()
            await state.finish()
            await message.answer(" ", reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка при завершении состояния поиска: {e}")

@dp.message_handler(lambda message: message.text == "➕ Добавить")
async def add_button_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if not is_authorized(user_id):
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    
    # Инициализируем временные данные пользователя
    user_temp_data[user_id] = {}
    
    # Запускаем процесс добавления
    await AddPersonStates.waiting_for_fio.set()
    log_user_action(user_id, username, "ADD_START", "Начало пошагового добавления записи")
    
    # Создаем клавиатуру с кнопкой отмены
    cancel_keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=False,
        keyboard=[[KeyboardButton(text="❌ Отмена")]]
    )
    
    await message.answer(
        "📝 <b>Добавление новой записи</b>\n\n"
        "🔄 <b>Шаг 1/6:</b> Введите ФИО (Фамилия Имя Отчество)\n\n"
        "💡 <i>Пример:</i> Иванов Иван Иванович",
        reply_markup=cancel_keyboard,
        parse_mode='HTML'
    )

# Обработчик для ввода ФИО
@dp.message_handler(state=AddPersonStates.waiting_for_fio)
async def process_fio(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Проверяем, не нажал ли пользователь "Отмена"
    if message.text == "❌ Отмена":
        await cancel_add_process(message, state, user_id, username)
        return
    
    fio = message.text.strip()
    
    # Улучшенная валидация ФИО
    fio_parts = fio.split()
    if len(fio_parts) < 2:
        await message.answer(
            "❌ <b>Ошибка:</b> ФИО должно содержать минимум фамилию и имя.\n\n"
            "🔄 <i>Попробуйте еще раз:</i>",
            parse_mode='HTML'
        )
        return
    
    # Проверка на допустимые символы (буквы, пробелы, дефисы)
    if not re.match(r'^[а-яА-ЯёЁa-zA-Z\s\-]+$', fio):
        await message.answer(
            "❌ <b>Ошибка:</b> ФИО содержит недопустимые символы.\n\n"
            "💡 <i>Используйте только буквы, пробелы и дефисы</i>\n\n"
            "🔄 <i>Попробуйте еще раз:</i>",
            parse_mode='HTML'
        )
        return
    
    # Проверка длины
    if len(fio) > 200:
        await message.answer(
            "❌ <b>Ошибка:</b> ФИО слишком длинное (максимум 200 символов).\n\n"
            "🔄 <i>Попробуйте еще раз:</i>",
            parse_mode='HTML'
        )
        return
    
    # Сохраняем ФИО во временные данные
    user_temp_data[user_id]['fio'] = fio
    
    # Переходим к следующему шагу
    await AddPersonStates.waiting_for_phone.set()
    await message.answer(
        "✅ <b>ФИО сохранено:</b> " + fio + "\n\n"
        "🔄 <b>Шаг 2/6:</b> Введите номер телефона\n\n"
        "📱 <i>Формат:</i> 11 цифр (например: 79991234567)",
        parse_mode='HTML'
    )

# Обработчик для ввода телефона
@dp.message_handler(state=AddPersonStates.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Проверяем, не нажал ли пользователь "Отмена"
    if message.text == "❌ Отмена":
        await cancel_add_process(message, state, user_id, username)
        return
    
    phone = message.text.strip()
    
    # Валидация телефона (поддержка разных форматов)
    digits_only = re.sub(r'\D', '', phone)
    if len(digits_only) < 10 or len(digits_only) > 11:
        await message.answer(
            "❌ <b>Ошибка:</b> Неверный формат телефона.\n\n"
            "📱 <i>Поддерживаемые форматы:</i>\n"
            "• 79991234567\n"
            "• 89991234567\n"
            "• +7 999 123 45 67\n"
            "• 8 (999) 123-45-67\n\n"
            "🔄 <i>Попробуйте еще раз:</i>",
            parse_mode='HTML'
        )
        return
    
    # Нормализуем телефон
    normalized_phone = normalize_phone(phone)
    if len(normalized_phone) != 11:
        await message.answer(
            "❌ <b>Ошибка:</b> Не удалось нормализовать телефон. Нужно 11 цифр.\n\n"
            "🔄 <i>Попробуйте еще раз:</i>",
            parse_mode='HTML'
        )
        return
    
    # Проверяем, нет ли дубликатов
    try:
        with get_db_session() as db:
            existing_person = db.query(Person).filter(Person.phone == normalized_phone).first()
            if existing_person:
                await message.answer(
                    f"❌ <b>Ошибка:</b> Запись с телефоном {normalized_phone} уже существует!\n\n"
                    "🔄 <i>Попробуйте другой номер:</i>",
                    parse_mode='HTML'
                )
                return
    except Exception as e:
        logger.error(f"Ошибка проверки дубликатов: {e}")
    
    # Сохраняем нормализованный телефон
    phone = normalized_phone
    
    # Сохраняем телефон во временные данные
    user_temp_data[user_id]['phone'] = phone
    
    # Переходим к следующему шагу
    await AddPersonStates.waiting_for_birth.set()
    await message.answer(
        "✅ <b>Телефон сохранен:</b> " + phone + "\n\n"
        "🔄 <b>Шаг 3/6:</b> Введите дату рождения\n\n"
        "📅 <i>Формат:</i> YYYY-MM-DD (например: 1992-03-15)",
        parse_mode='HTML'
    )

# Обработчик для ввода даты рождения
@dp.message_handler(state=AddPersonStates.waiting_for_birth)
async def process_birth(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Проверяем, не нажал ли пользователь "Отмена"
    if message.text == "❌ Отмена":
        await cancel_add_process(message, state, user_id, username)
        return
    
    birth = message.text.strip()
    
    # Улучшенная валидация даты
    try:
        # Проверка формата
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', birth):
            raise ValueError("Неверный формат")
        
        # Парсинг даты
        birth_date = datetime.strptime(birth, '%Y-%m-%d')
        
        # Проверка разумности даты
        current_year = datetime.now().year
        if birth_date.year > current_year:
            await message.answer(
                "❌ <b>Ошибка:</b> Дата не может быть в будущем.\n\n"
                "🔄 <i>Попробуйте еще раз:</i>",
                parse_mode='HTML'
            )
            return
        
        if birth_date.year < 1900:
            await message.answer(
                "❌ <b>Ошибка:</b> Дата слишком старая (минимум 1900 год).\n\n"
                "🔄 <i>Попробуйте еще раз:</i>",
                parse_mode='HTML'
            )
            return
    except ValueError as e:
        await message.answer(
            "❌ <b>Ошибка:</b> Неверный формат даты.\n\n"
            "📅 <i>Используйте формат: YYYY-MM-DD</i>\n"
            "💡 <i>Пример: 1992-03-15</i>\n\n"
            "🔄 <i>Попробуйте еще раз:</i>",
            parse_mode='HTML'
        )
        return
    
    # Сохраняем дату рождения во временные данные
    user_temp_data[user_id]['birth'] = birth
    
    # Переходим к следующему шагу
    await AddPersonStates.waiting_for_car.set()
    await message.answer(
        "✅ <b>Дата рождения сохранена:</b> " + birth + "\n\n"
        "🔄 <b>Шаг 4/6:</b> Введите номер автомобиля (или отправьте 'пропустить')\n\n"
        "🚗 <i>Пример:</i> A123AA123\n"
        "⏭️ <i>Или отправьте:</i> пропустить",
        parse_mode='HTML'
    )

# Обработчик для ввода номера автомобиля
@dp.message_handler(state=AddPersonStates.waiting_for_car)
async def process_car(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Проверяем, не нажал ли пользователь "Отмена"
    if message.text == "❌ Отмена":
        await cancel_add_process(message, state, user_id, username)
        return
    
    car_number = message.text.strip()
    
    # Если пользователь хочет пропустить
    if car_number.lower() in ['пропустить', 'пропустить', 'skip', 'нет', 'н']:
        car_number = ""
    
    # Сохраняем номер автомобиля во временные данные
    user_temp_data[user_id]['car_number'] = car_number
    
    # Переходим к следующему шагу
    await AddPersonStates.waiting_for_address.set()
    await message.answer(
        "✅ <b>Номер автомобиля сохранен:</b> " + (car_number if car_number else "не указан") + "\n\n"
        "🔄 <b>Шаг 5/6:</b> Введите адрес (или отправьте 'пропустить')\n\n"
        "🏠 <i>Пример:</i> г. Москва, ул. Ленина, д. 1, кв. 1\n"
        "⏭️ <i>Или отправьте:</i> пропустить",
        parse_mode='HTML'
    )

# Обработчик для ввода адреса
@dp.message_handler(state=AddPersonStates.waiting_for_address)
async def process_address(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Проверяем, не нажал ли пользователь "Отмена"
    if message.text == "❌ Отмена":
        await cancel_add_process(message, state, user_id, username)
        return
    
    address = message.text.strip()
    
    # Если пользователь хочет пропустить
    if address.lower() in ['пропустить', 'пропустить', 'skip', 'нет', 'н']:
        address = ""
    
    # Сохраняем адрес во временные данные
    user_temp_data[user_id]['address'] = address
    
    # Переходим к следующему шагу
    await AddPersonStates.waiting_for_passport.set()
    await message.answer(
        "✅ <b>Адрес сохранен:</b> " + (address if address else "не указан") + "\n\n"
        "🔄 <b>Шаг 6/6:</b> Введите паспортные данные (или отправьте 'пропустить')\n\n"
        "📄 <i>Пример:</i> 1234 567890\n"
        "⏭️ <i>Или отправьте:</i> пропустить",
        parse_mode='HTML'
    )

# Обработчик для ввода паспорта
@dp.message_handler(state=AddPersonStates.waiting_for_passport)
async def process_passport(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Проверяем, не нажал ли пользователь "Отмена"
    if message.text == "❌ Отмена":
        await cancel_add_process(message, state, user_id, username)
        return
    
    passport = message.text.strip()
    
    # Если пользователь хочет пропустить
    if passport.lower() in ['пропустить', 'пропустить', 'skip', 'нет', 'н']:
        passport = ""
    
    # Сохраняем паспорт во временные данные
    user_temp_data[user_id]['passport'] = passport
    
    # Завершаем процесс добавления
    await finish_add_process(message, state, user_id, username)

# Функция для завершения процесса добавления
async def finish_add_process(message: types.Message, state: FSMContext, user_id: int, username: str):
    """Завершает процесс добавления записи"""
    try:
        # Получаем данные пользователя
        temp_data = user_temp_data.get(user_id, {})
        
        # Проверяем обязательные поля
        if not temp_data.get('fio') or not temp_data.get('phone') or not temp_data.get('birth'):
            log_user_action(user_id, username, "ADD_ERROR", "Отсутствуют обязательные поля")
            await message.answer(
                "❌ <b>Ошибка:</b> Отсутствуют обязательные данные.\n\n"
                "Пожалуйста, начните добавление заново.",
                parse_mode='HTML'
            )
            # Очищаем временные данные и состояние
            if user_id in user_temp_data:
                del user_temp_data[user_id]
            await state.finish()
            return
        
        # Создаем новую запись
        new_record = {
            "fio": temp_data.get('fio', ''),
            "phone": temp_data.get('phone', ''),
            "birth": temp_data.get('birth', ''),
            "car_number": temp_data.get('car_number', '') or None,
            "address": temp_data.get('address', '') or None,
            "passport": temp_data.get('passport', '') or None
        }
        
        logger.info(f"Попытка сохранения записи для пользователя {user_id}: {new_record}")
        
        # Сохраняем в базу данных
        saved_person = save_person(new_record)
        if saved_person:
            log_user_action(user_id, username, "ADD_SUCCESS", f"Добавлена запись: {new_record['fio']}, {new_record['phone']}, {new_record['birth']}")
            
            # Формируем красивое сообщение с результатом
            result_message = "🎉 <b>Запись успешно добавлена!</b>\n\n"
            result_message += format_record(saved_person)
            
            # Возвращаем основную клавиатуру
            role = get_user_role(user_id)
            if role == "admin":
                keyboard = get_admin_keyboard()
            else:
                keyboard = get_main_keyboard()
            
            await message.answer(result_message, reply_markup=keyboard, parse_mode='HTML')
        else:
            log_user_action(user_id, username, "ADD_ERROR", "Ошибка при сохранении данных")
            await message.answer(
                "❌ <b>Ошибка при сохранении данных.</b>\n\n"
                "Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Критическая ошибка при завершении добавления записи: {e}", exc_info=True)
        log_user_action(user_id, username, "ADD_ERROR", f"Критическая ошибка: {str(e)}")
        await message.answer(
            "❌ <b>Произошла ошибка при сохранении данных.</b>\n\n"
            "Пожалуйста, попробуйте еще раз.",
            parse_mode='HTML'
        )
    finally:
        # Очищаем временные данные и состояние
        if user_id in user_temp_data:
            del user_temp_data[user_id]
        try:
            await state.finish()
        except:
            pass

# Функция для отмены процесса добавления
async def cancel_add_process(message: types.Message, state: FSMContext, user_id: int, username: str):
    """Отменяет процесс добавления записи"""
    log_user_action(user_id, username, "ADD_CANCELLED", "Отмена добавления записи")
    
    # Очищаем временные данные
    if user_id in user_temp_data:
        del user_temp_data[user_id]
    
    # Возвращаем основную клавиатуру
    role = get_user_role(user_id)
    if role == "admin":
        keyboard = get_admin_keyboard()
    else:
        keyboard = get_main_keyboard()
    
    await message.answer("❌ <b>Добавление записи отменено.</b>", reply_markup=keyboard, parse_mode='HTML')
    await state.finish()

@dp.message_handler(lambda message: message.text == "📚 Документация")
async def help_button_handler(message: types.Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    help_text = """📚 Документация по боту:
Справка: Тут будет информация о боте"""
    await message.answer(help_text)

@dp.message_handler(lambda message: message.text == "📊 Логи")
async def logs_button_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if not is_authorized(user_id):
        log_user_action(user_id, username, "LOGS_BUTTON", "Попытка просмотра логов без авторизации")
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    
    if not is_admin(user_id):
        log_user_action(user_id, username, "LOGS_BUTTON", "Попытка просмотра логов без прав администратора")
        await message.answer("🚫 Доступ запрещен! Эта функция доступна только администраторам.")
        return
    
    log_user_action(user_id, username, "LOGS_BUTTON", "Просмотр логов через кнопку (админ)")
    
    logs = get_failed_auth_logs(10)  # Только неудачные авторизации
    
    if not logs:
        await message.answer("🔒 Неудачных попыток авторизации не найдено")
        return
    
    log_text = "🚨 Неудачные попытки авторизации:\n\n"
    for log in reversed(logs):  # Показываем в обратном порядке (новые сверху)
        log_text += f"🕐 {log['timestamp']}\n"
        log_text += f"👤 {log['username']} (ID: {log['user_id']})\n"
        log_text += f"❌ {log['action']}\n"
        if log['details']:
            log_text += f"📝 {log['details']}\n"
        log_text += "─" * 30 + "\n"
    
    await message.answer(log_text)

@dp.message_handler(lambda message: message.text == "📋 Список команд")
async def commands_button_handler(message: types.Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    commands_text = """📋 Доступные команды:

🔍 Поиск - найти запись по имени, телефону, номеру авто, адресу или паспорту
➕ Добавить - добавить новую запись (пошаговый ввод)
📚 Документация - показать документацию
📋 Список команд - показать все команды

Команды:
• Для поиска: используйте команду /find <ФИО, телефон, номер авто, адрес или паспорт>. Или напишите просто поисковый запрос \n
• Для добавления: используйте команду /add или кнопку "➕ Добавить" - бот проведет вас через пошаговый ввод данных \n
• Информация о боте: /info - показать информацию о боте

🔍 Поля для поиска:
• ФИО (например: Иванов Иван Иванович)
• Телефон (например: 79991234567)
• Номер авто (например: A111AA11)
• Адрес (например: г. Москва, ул. Ленина, дом 23, кв 1)
• Паспорт (например: 1234 456789)

📝 Процесс добавления записи:
1. ФИО (обязательно)
2. Телефон (обязательно, 11 цифр)
3. Дата рождения (обязательно, формат YYYY-MM-DD)
4. Номер автомобиля (опционально, можно пропустить)
5. Адрес (опционально, можно пропустить)
6. Паспортные данные (опционально, можно пропустить)

В любой момент можно отменить добавление, нажав кнопку "❌ Отмена"."""
    await message.answer(commands_text)

# Команда /find
@dp.message_handler(commands=["find"])
async def find_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if not is_authorized(user_id):
        log_user_action(user_id, username, "FIND_COMMAND", "Попытка поиска без авторизации")
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    
    query = message.get_args().strip()
    if not query:
        # Переводим в состояние ожидания запроса, если аргумент не указан
        await SearchStates.waiting_for_query.set()
        await message.answer(
            "Используй: /find <запрос> или введите запрос ниже:",
            parse_mode='HTML'
        )
        return

    # Выполняем поиск с ограничением
    persons = search_persons(query, limit=50)  # Ограничиваем результаты
    
    if persons:
        log_user_action(user_id, username, "SEARCH_SUCCESS", f"Найдено {len(persons)} результатов по запросу: {query}")
        
        # Формируем сообщения с пагинацией (Telegram ограничение 4096 символов)
        MAX_MESSAGE_LENGTH = 4000  # Оставляем запас
        result_message = f"🔍 <b>Найдено результатов: {len(persons)}</b>\n\n"
        
        current_message = result_message
        for i, person in enumerate(persons, 1):
            person_text = f"<b>Результат {i}:</b>\n{format_record(person)}\n\n"
            
            # Если сообщение станет слишком длинным, отправляем текущее и начинаем новое
            if len(current_message) + len(person_text) > MAX_MESSAGE_LENGTH:
                await message.answer(current_message, parse_mode='HTML')
                current_message = f"<b>Продолжение (результаты {i}-{len(persons)}):</b>\n\n{person_text}"
            else:
                current_message += person_text
        
        # Отправляем последнее сообщение
        await message.answer(current_message, parse_mode='HTML')
    else:
        log_user_action(user_id, username, "SEARCH_NO_RESULTS", f"Ничего не найдено по запросу: {query}")
        await message.answer(
            "🔍 <b>Ничего не найдено</b>\n\n"
            "<i>Попробуйте изменить поисковый запрос или использовать часть слова</i>",
            parse_mode='HTML'
        )

# Команда /add (теперь запускает пошаговый процесс)
@dp.message_handler(commands=["add"])
async def add_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if not is_authorized(user_id):
        log_user_action(user_id, username, "ADD_COMMAND", "Попытка добавления без авторизации")
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    
    # Инициализируем временные данные пользователя
    user_temp_data[user_id] = {}
    
    # Запускаем процесс добавления
    await AddPersonStates.waiting_for_fio.set()
    log_user_action(user_id, username, "ADD_START", "Начало пошагового добавления записи через команду")
    
    # Создаем клавиатуру с кнопкой отмены
    cancel_keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=False,
        keyboard=[[KeyboardButton(text="❌ Отмена")]]
    )
    
    await message.answer(
        "📝 <b>Добавление новой записи</b>\n\n"
        "🔄 <b>Шаг 1/6:</b> Введите ФИО (Фамилия Имя Отчество)\n\n"
        "💡 <i>Пример:</i> Иванов Иван Иванович",
        reply_markup=cancel_keyboard,
        parse_mode='HTML'
    )

# Команда /help
@dp.message_handler(commands=["info"])
async def help_cmd(message: types.Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    help_text = """Справка: Тут будет информация о боте"""
    await message.answer(help_text)

# Команда для просмотра логов (только для админов)
@dp.message_handler(commands=["logs"])
async def logs_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if not is_authorized(user_id):
        log_user_action(user_id, username, "LOGS_COMMAND", "Попытка просмотра логов без авторизации")
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    
    if not is_admin(user_id):
        log_user_action(user_id, username, "LOGS_COMMAND", "Попытка просмотра логов без прав администратора")
        await message.answer("🚫 Доступ запрещен! Эта команда доступна только администраторам.")
        return
    
    log_user_action(user_id, username, "LOGS_COMMAND", "Просмотр логов неудачных авторизаций (админ)")
    
    logs = get_failed_auth_logs(10)  # Только неудачные авторизации
    
    if not logs:
        await message.answer("🔒 Неудачных попыток авторизации не найдено")
        return
    
    log_text = "🚨 Неудачные попытки авторизации:\n\n"
    for log in reversed(logs):  # Показываем в обратном порядке (новые сверху)
        log_text += f"🕐 {log['timestamp']}\n"
        log_text += f"👤 {log['username']} (ID: {log['user_id']})\n"
        log_text += f"❌ {log['action']}\n"
        if log['details']:
            log_text += f"📝 {log['details']}\n"
        log_text += "─" * 30 + "\n"
    
    await message.answer(log_text)

# Обработчик любого произвольного текста вне состояний — выводит подсказку, не выполняя поиск
@dp.message_handler(content_types=["text"], state=None)
async def unknown_text_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    if not is_authorized(user_id):
        log_user_action(user_id, username, "UNKNOWN_COMMAND", "Сообщение без авторизации")
        await message.answer("Я не знаю такую команду. Введите /start для авторизации.")
        return

    log_user_action(user_id, username, "UNKNOWN_COMMAND", f"Неизвестная команда: {message.text}")
    await message.answer("Я не знаю такую команду. Используйте кнопки или команды: /find, /add, /info")

# Запуск
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
