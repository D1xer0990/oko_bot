"""Обработчики логов"""
from aiogram import Dispatcher
from aiogram.types import Message
from utils.auth import auth_manager
from database.database import db


async def logs_button_handler(message: Message):
    """Обработчик кнопки логов"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if not auth_manager.is_authorized(user_id):
        db.log_user_action(user_id, username, "LOGS_BUTTON", "Попытка просмотра логов без авторизации")
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    
    if not auth_manager.is_admin(user_id):
        db.log_user_action(user_id, username, "LOGS_BUTTON", "Попытка просмотра логов без прав администратора")
        await message.answer("🚫 Доступ запрещен! Эта функция доступна только администраторам.")
        return
    
    db.log_user_action(user_id, username, "LOGS_BUTTON", "Просмотр логов через кнопку (админ)")
    
    logs = db.get_failed_auth_logs(10)  # Только неудачные авторизации
    
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


async def logs_cmd(message: Message):
    """Обработчик команды /logs"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if not auth_manager.is_authorized(user_id):
        db.log_user_action(user_id, username, "LOGS_COMMAND", "Попытка просмотра логов без авторизации")
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    
    if not auth_manager.is_admin(user_id):
        db.log_user_action(user_id, username, "LOGS_COMMAND", "Попытка просмотра логов без прав администратора")
        await message.answer("🚫 Доступ запрещен! Эта команда доступна только администраторам.")
        return
    
    db.log_user_action(user_id, username, "LOGS_COMMAND", "Просмотр логов неудачных авторизаций (админ)")
    
    logs = db.get_failed_auth_logs(10)  # Только неудачные авторизации
    
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


def register_logs_handlers(dp: Dispatcher):
    """Регистрация обработчиков логов"""
    dp.register_message_handler(logs_button_handler, lambda m: m.text == "📊 Логи")
    dp.register_message_handler(logs_cmd, commands=["logs"])

