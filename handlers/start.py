"""Обработчики команды /start"""
from aiogram import Dispatcher
from aiogram.types import Message
from utils.keyboards import get_main_keyboard, get_admin_keyboard
from utils.auth import auth_manager
from database.database import db


async def start_cmd(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if auth_manager.is_authorized(user_id):
        role = auth_manager.get_user_role(user_id)
        if role == "admin":
            db.log_user_action(user_id, username, "START_COMMAND", "Вход администратора")
            help_text = """👑 Добро пожаловать, администратор!

🤖 Бот для работы с базой данных
🔧 У вас есть доступ ко всем функциям, включая логи

Выберите действие с помощью кнопок ниже:"""
            await message.answer(help_text, reply_markup=get_admin_keyboard())
        else:
            db.log_user_action(user_id, username, "START_COMMAND", "Вход обычного пользователя")
            help_text = """🤖 Добро пожаловать в бот для работы с базой данных!

Выберите действие с помощью кнопок ниже:"""
            await message.answer(help_text, reply_markup=get_main_keyboard())
    else:
        db.log_user_action(user_id, username, "START_COMMAND", "Попытка входа без авторизации")
        await message.answer("Для доступа к боту требуется код авторизации.\n\nВведите код доступа:")


def register_start_handlers(dp: Dispatcher):
    """Регистрация обработчиков команды /start"""
    dp.register_message_handler(start_cmd, commands=["start"])

