"""Обработчики авторизации"""
from aiogram import Dispatcher
from aiogram.types import Message
from utils.keyboards import get_main_keyboard, get_admin_keyboard
from utils.auth import auth_manager
from database.database import db
from config import USER_ACCESS_CODE, ADMIN_ACCESS_CODE


async def check_access_code(message: Message):
    """Обработчик проверки кода доступа"""
    entered_code = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    success, role = auth_manager.authorize_user(user_id, username, entered_code)
    
    if success:
        if role == "user":
            db.log_user_action(user_id, username, "AUTH_SUCCESS", 
                             f"Успешная авторизация пользователя с кодом: {entered_code}")
            help_text = """✅ Код доступа принят! Добро пожаловать!

🤖 Добро пожаловать в бот для работы с базой данных!

Выберите действие с помощью кнопок ниже:"""
            await message.answer(help_text, reply_markup=get_main_keyboard())
        elif role == "admin":
            db.log_user_action(user_id, username, "AUTH_SUCCESS", 
                             f"Успешная авторизация администратора с кодом: {entered_code}")
            help_text = """👑 Код администратора принят! Добро пожаловать!

🤖 Бот для работы с базой данных
🔧 У вас есть доступ ко всем функциям, включая логи

Выберите действие с помощью кнопок ниже:"""
            await message.answer(help_text, reply_markup=get_admin_keyboard())
    else:
        db.log_user_action(user_id, username, "AUTH_FAILED", f"Неверный код: {entered_code}")
        await message.answer("Неверный код доступа. Попробуйте еще раз:")


def register_auth_handlers(dp: Dispatcher):
    """Регистрация обработчиков авторизации"""
    dp.register_message_handler(
        check_access_code,
        lambda message: not auth_manager.is_authorized(message.from_user.id) 
                       and not message.text.startswith('/')
    )

