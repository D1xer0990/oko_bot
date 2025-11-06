"""Главный файл бота"""
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from config import BOT_TOKEN, logger
from database.database import db
from handlers import (
    register_start_handlers,
    register_auth_handlers,
    register_search_handlers,
    register_add_handlers,
    register_logs_handlers,
    register_common_handlers
)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Регистрация всех обработчиков
def register_all_handlers():
    """Регистрация всех обработчиков"""
    register_start_handlers(dp)
    register_auth_handlers(dp)
    register_search_handlers(dp)
    register_add_handlers(dp)
    register_logs_handlers(dp)
    register_common_handlers(dp)
    logger.info("Все обработчики зарегистрированы")


# Регистрация обработчиков
register_all_handlers()

# Запуск бота
if __name__ == "__main__":
    logger.info("Бот запущен")
    executor.start_polling(dp, skip_updates=True)
