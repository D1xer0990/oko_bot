"""Обработчики поиска"""
from aiogram import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import Message
from utils.keyboards import get_main_keyboard, get_admin_keyboard
from utils.auth import auth_manager
from utils.formatters import format_record
from database.database import db
from states import SearchStates


async def search_button_handler(message: Message, state: FSMContext):
    """Обработчик кнопки поиска"""
    if not auth_manager.is_authorized(message.from_user.id):
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    await SearchStates.waiting_for_query.set()
    await message.answer(
        "🔍 <b>Поиск в базе данных</b>\n\n"
        "<i>Введите поисковый запрос (ФИО, телефон, номер авто, адрес или паспорт):</i>",
        parse_mode='HTML'
    )


async def process_search_query(message: Message, state: FSMContext):
    """Обработчик поискового запроса"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    # Отмена поиска через команду /start
    if message.text == "/start":
        role = auth_manager.get_user_role(user_id)
        keyboard = get_admin_keyboard() if role == "admin" else get_main_keyboard()
        await message.answer("Поиск отменён.", reply_markup=keyboard)
        await state.finish()
        return

    query = message.text.strip()
    if not query:
        await message.answer("Введите непустой запрос")
        return

    # Выполняем поиск
    persons = db.search_persons(query)
    results = [format_record(person) for person in persons]

    if results:
        db.log_user_action(user_id, username, "SEARCH_SUCCESS", 
                         f"Найдено {len(results)} результатов по запросу: {query}")
        result_message = f"🔍 <b>Найдено результатов: {len(results)}</b>\n\n"
        result_message += "\n\n".join(results)
        await message.answer(result_message, parse_mode='HTML')
    else:
        db.log_user_action(user_id, username, "SEARCH_NO_RESULTS", 
                         f"Ничего не найдено по запросу: {query}")
        await message.answer("🔍 <b>Ничего не найдено</b>\n\n<i>Попробуйте изменить поисковый запрос</i>", 
                           parse_mode='HTML')

    # Завершаем состояние и возвращаем основную клавиатуру
    role = auth_manager.get_user_role(user_id)
    keyboard = get_admin_keyboard() if role == "admin" else get_main_keyboard()
    await state.finish()
    await message.answer(" ", reply_markup=keyboard)


async def find_cmd(message: Message):
    """Обработчик команды /find"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if not auth_manager.is_authorized(user_id):
        db.log_user_action(user_id, username, "FIND_COMMAND", "Попытка поиска без авторизации")
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

    # Выполняем поиск
    persons = db.search_persons(query)
    results = [format_record(person) for person in persons]

    if results:
        db.log_user_action(user_id, username, "SEARCH_SUCCESS", 
                         f"Найдено {len(results)} результатов по запросу: {query}")
        result_message = f"🔍 <b>Найдено результатов: {len(results)}</b>\n\n"
        result_message += "\n\n".join(results)
        await message.answer(result_message, parse_mode='HTML')
    else:
        db.log_user_action(user_id, username, "SEARCH_NO_RESULTS", 
                         f"Ничего не найдено по запросу: {query}")
        await message.answer("🔍 <b>Ничего не найдено</b>\n\n<i>Попробуйте изменить поисковый запрос</i>", 
                           parse_mode='HTML')


def register_search_handlers(dp: Dispatcher):
    """Регистрация обработчиков поиска"""
    dp.register_message_handler(search_button_handler, lambda m: m.text == "🔍 Поиск")
    dp.register_message_handler(process_search_query, state=SearchStates.waiting_for_query)
    dp.register_message_handler(find_cmd, commands=["find"])

