"""Конфигурация бота"""
import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Коды доступа
USER_ACCESS_CODE = "12345"  # Обычные пользователи
ADMIN_ACCESS_CODE = "77777"  # Администраторы

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

# Настройки БД
DB_POOL_SIZE = 5  # Размер пула соединений
DB_MAX_OVERFLOW = 10  # Максимальное количество дополнительных соединений
DB_POOL_RECYCLE = 3600  # Время жизни соединения в секундах

