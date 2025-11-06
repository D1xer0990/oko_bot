"""Клавиатуры для бота"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
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


def get_admin_keyboard() -> ReplyKeyboardMarkup:
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


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру с кнопкой отмены"""
    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=False,
        keyboard=[[KeyboardButton(text="❌ Отмена")]]
    )
    return keyboard


def get_inline_keyboard() -> InlineKeyboardMarkup:
    """Создает inline клавиатуру с быстрыми действиями"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Найти запись", callback_data="search")],
            [InlineKeyboardButton(text="➕ Добавить запись", callback_data="add")],
            [InlineKeyboardButton(text="📚 Документация", callback_data="info")]
        ]
    )
    return keyboard

