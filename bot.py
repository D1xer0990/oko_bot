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

# Загружаем токен из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

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

# Глобальные переменные для отслеживания авторизации
authorized_users = set()  # Обычные пользователи
authorized_admins = set()  # Администраторы

# Словарь для хранения временных данных пользователей при добавлении записи
user_temp_data = {}

# Функция для красивого форматирования записи
def format_record(record):
    """Форматирует запись в простом и чистом виде"""
    result = f"👤 ФИО: {record['fio']}\n"
    result += f"📞 Телефон: {record['phone']}\n"
    result += f"📅 Дата рождения: {record['birth']}\n"
    
    if record.get("car_number"):
        result += f"🚗 Номер авто: {record['car_number']}\n"
    if record.get("address"):
        result += f"🏠 Адрес: {record['address']}\n"
    if record.get("passport"):
        result += f"📄 Паспорт: {record['passport']}\n"
    
    return result.rstrip()  # Убираем последний перенос строки

# Файл для хранения данных
DATABASE_FILE = "database.json"

# Функции для работы с файлом
def load_database():
    try:
        if os.path.exists(DATABASE_FILE):
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Создаем файл с начальными данными
            initial_data = [
                {"fio": "Иванов Иван Иванович", "phone": "79991234567", "birth": "1990-01-01"},
                {"fio": "Петров Петр Петрович", "phone": "79990001122", "birth": "1985-05-12"},
            ]
            save_database(initial_data)
            return initial_data
    except Exception as e:
        print(f"Ошибка загрузки базы данных: {e}")
        return []

def save_database(data):
    try:
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ошибка сохранения базы данных: {e}")
        return False

# Загружаем базу данных
database = load_database()

# Функции для логирования
def log_user_action(user_id, username, action, details=""):
    """Записывает действие пользователя в лог"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"USER: {user_id} ({username}) | ACTION: {action} | DETAILS: {details}"
    logger.info(log_message)
    
    # Также записываем в JSON файл для удобного просмотра
    log_entry = {
        "timestamp": timestamp,
        "user_id": user_id,
        "username": username,
        "action": action,
        "details": details
    }
    
    try:
        # Загружаем существующие логи
        if os.path.exists("user_logs.json"):
            with open("user_logs.json", "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []
        
        # Добавляем новую запись
        logs.append(log_entry)
        
        # Сохраняем обратно
        with open("user_logs.json", "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logger.error(f"Ошибка записи в JSON лог: {e}")

def get_user_logs(limit=10):
    """Получает последние логи пользователей"""
    try:
        if os.path.exists("user_logs.json"):
            with open("user_logs.json", "r", encoding="utf-8") as f:
                logs = json.load(f)
            return logs[-limit:] if len(logs) > limit else logs
        return []
    except Exception as e:
        logger.error(f"Ошибка чтения логов: {e}")
        return []

def get_failed_auth_logs(limit=10):
    """Получает только неудачные попытки авторизации"""
    try:
        if os.path.exists("user_logs.json"):
            with open("user_logs.json", "r", encoding="utf-8") as f:
                logs = json.load(f)
            # Фильтруем только неудачные авторизации
            failed_logs = [log for log in logs if log['action'] == 'AUTH_FAILED']
            return failed_logs[-limit:] if len(failed_logs) > limit else failed_logs
        return []
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
        log_user_action(user_id, username, "AUTH_SUCCESS", f"Успешная авторизация пользователя с кодом: {entered_code}")
        help_text = """✅ Код доступа принят! Добро пожаловать!

🤖 Добро пожаловать в бот для работы с базой данных!

Выберите действие с помощью кнопок ниже:"""
        await message.answer(help_text, reply_markup=get_main_keyboard())
    elif entered_code == ADMIN_ACCESS_CODE:
        authorized_admins.add(user_id)
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
async def search_button_handler(message: types.Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    await message.answer("🔍 <b>Поиск в базе данных</b>\n\n<i>Введите поисковый запрос (ФИО, телефон, номер авто, адрес или паспорт):</i>", parse_mode='HTML')

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
    
    # Простая валидация ФИО (должно содержать минимум 2 слова)
    if len(fio.split()) < 2:
        await message.answer("❌ <b>Ошибка:</b> ФИО должно содержать минимум фамилию и имя.\n\n🔄 <i>Попробуйте еще раз:</i>", parse_mode='HTML')
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
    
    # Валидация телефона
    if not phone.isdigit() or len(phone) != 11:
        await message.answer("❌ <b>Ошибка:</b> Неверный формат телефона. Нужно 11 цифр (например: 79991234567)\n\n🔄 <i>Попробуйте еще раз:</i>", parse_mode='HTML')
        return
    
    # Проверяем, нет ли дубликатов
    for record in database:
        if record["phone"] == phone:
            await message.answer(f"❌ <b>Ошибка:</b> Запись с телефоном {phone} уже существует!\n\n🔄 <i>Попробуйте другой номер:</i>", parse_mode='HTML')
            return
    
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
    
    # Валидация даты
    try:
        year, month, day = birth.split('-')
        if len(year) != 4 or len(month) != 2 or len(day) != 2:
            raise ValueError
        # Проверяем, что дата валидна
        datetime.strptime(birth, '%Y-%m-%d')
    except:
        await message.answer("❌ <b>Ошибка:</b> Неверный формат даты. Используйте: YYYY-MM-DD (например: 1992-03-15)\n\n🔄 <i>Попробуйте еще раз:</i>", parse_mode='HTML')
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
    # Получаем данные пользователя
    temp_data = user_temp_data.get(user_id, {})
    
    # Создаем новую запись
    new_record = {
        "fio": temp_data.get('fio', ''),
        "phone": temp_data.get('phone', ''),
        "birth": temp_data.get('birth', ''),
        "car_number": temp_data.get('car_number', ''),
        "address": temp_data.get('address', ''),
        "passport": temp_data.get('passport', '')
    }
    
    # Добавляем в базу данных
    database.append(new_record)
    
    # Сохраняем в файл
    if save_database(database):
        log_user_action(user_id, username, "ADD_SUCCESS", f"Добавлена запись: {new_record['fio']}, {new_record['phone']}, {new_record['birth']}")
        
        # Формируем красивое сообщение с результатом
        result_message = "🎉 <b>Запись успешно добавлена!</b>\n\n"
        result_message += format_record(new_record)
        
        # Возвращаем основную клавиатуру
        role = get_user_role(user_id)
        if role == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = get_main_keyboard()
        
        await message.answer(result_message, reply_markup=keyboard, parse_mode='HTML')
    else:
        log_user_action(user_id, username, "ADD_ERROR", "Ошибка при сохранении данных")
        await message.answer("❌ <b>Ошибка при сохранении данных.</b> Попробуйте еще раз.", parse_mode='HTML')
    
    # Очищаем временные данные и состояние
    if user_id in user_temp_data:
        del user_temp_data[user_id]
    await state.finish()

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
        log_user_action(user_id, username, "FIND_COMMAND", "Пустой запрос")
        await message.answer("Используй: /find <ФИО, телефон, номер авто, адрес или паспорт>. Или напишите поисковый запрос")
        return

    results = []
    for record in database:
        if (query in record["fio"] or query in record["phone"] or 
            query in record.get("car_number", "") or query in record.get("address", "") or 
            query in record.get("passport", "")):
            results.append(format_record(record))

    if results:
        log_user_action(user_id, username, "SEARCH_SUCCESS", f"Найдено {len(results)} результатов по запросу: {query}")
        result_message = f"🔍 <b>Найдено результатов: {len(results)}</b>\n\n"
        result_message += "\n\n".join(results)
        await message.answer(result_message, parse_mode='HTML')
    else:
        log_user_action(user_id, username, "SEARCH_NO_RESULTS", f"Ничего не найдено по запросу: {query}")
        await message.answer("🔍 <b>Ничего не найдено</b>\n\n<i>Попробуйте изменить поисковый запрос</i>", parse_mode='HTML')

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
    help_text = """

Справка: Тут будет информация о боте
"""
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

# Обработчик любого текста (поиск по имени или телефону) - только если не в FSM состоянии
@dp.message_handler(content_types=["text"], state=None)
async def text_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if not is_authorized(user_id):
        log_user_action(user_id, username, "TEXT_SEARCH", "Попытка поиска без авторизации")
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    
    query = message.text.strip()
    if not query:
        return

    results = []
    for record in database:
        if (query in record["fio"] or query in record["phone"] or 
            query in record.get("car_number", "") or query in record.get("address", "") or 
            query in record.get("passport", "")):
            results.append(format_record(record))

    if results:
        log_user_action(user_id, username, "TEXT_SEARCH_SUCCESS", f"Найдено {len(results)} результатов по запросу: {query}")
        result_message = f"🔍 <b>Найдено результатов: {len(results)}</b>\n\n"
        result_message += "\n\n".join(results)
        await message.answer(result_message, parse_mode='HTML')
    else:
        log_user_action(user_id, username, "TEXT_SEARCH_NO_RESULTS", f"Ничего не найдено по запросу: {query}")
        await message.answer("🔍 <b>Ничего не найдено</b>\n\n<i>Попробуйте изменить поисковый запрос</i>", parse_mode='HTML')

# Запуск
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)