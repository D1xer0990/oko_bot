"""Обработчики добавления записей"""
from aiogram import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import Message
from utils.keyboards import get_main_keyboard, get_admin_keyboard, get_cancel_keyboard
from utils.auth import auth_manager
from utils.formatters import format_record
from utils.validators import validate_fio, validate_phone, validate_date, normalize_phone
from database.database import db
from states import AddPersonStates

# Временное хранилище данных пользователей
user_temp_data = {}


async def add_button_handler(message: Message, state: FSMContext):
    """Обработчик кнопки добавления"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if not auth_manager.is_authorized(user_id):
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    
    # Инициализируем временные данные пользователя
    user_temp_data[user_id] = {}
    
    # Запускаем процесс добавления
    await AddPersonStates.waiting_for_fio.set()
    db.log_user_action(user_id, username, "ADD_START", "Начало пошагового добавления записи")
    
    await message.answer(
        "📝 <b>Добавление новой записи</b>\n\n"
        "🔄 <b>Шаг 1/6:</b> Введите ФИО (Фамилия Имя Отчество)\n\n"
        "💡 <i>Пример:</i> Иванов Иван Иванович",
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )


async def process_fio(message: Message, state: FSMContext):
    """Обработчик ввода ФИО"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if message.text == "❌ Отмена":
        await cancel_add_process(message, state, user_id, username)
        return
    
    fio = message.text.strip()
    
    # Валидация ФИО
    is_valid, error_msg = validate_fio(fio)
    if not is_valid:
        await message.answer(f"❌ <b>Ошибка:</b> {error_msg}\n\n🔄 <i>Попробуйте еще раз:</i>", parse_mode='HTML')
        return
    
    # Сохраняем ФИО во временные данные
    user_temp_data[user_id]['fio'] = fio
    
    # Переходим к следующему шагу
    await AddPersonStates.waiting_for_phone.set()
    await message.answer(
        f"✅ <b>ФИО сохранено:</b> {fio}\n\n"
        "🔄 <b>Шаг 2/6:</b> Введите номер телефона\n\n"
        "📱 <i>Формат:</i> 11 цифр (например: 79991234567)",
        parse_mode='HTML'
    )


async def process_phone(message: Message, state: FSMContext):
    """Обработчик ввода телефона"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if message.text == "❌ Отмена":
        await cancel_add_process(message, state, user_id, username)
        return
    
    phone = message.text.strip()
    
    # Валидация телефона
    is_valid, error_msg = validate_phone(phone)
    if not is_valid:
        await message.answer(f"❌ <b>Ошибка:</b> {error_msg}\n\n🔄 <i>Попробуйте еще раз:</i>", parse_mode='HTML')
        return
    
    # Нормализуем телефон
    phone = normalize_phone(phone)
    
    # Проверяем, нет ли дубликатов
    existing_person = db.get_person_by_phone(phone)
    if existing_person:
        await message.answer(
            f"❌ <b>Ошибка:</b> Запись с телефоном {phone} уже существует!\n\n"
            "🔄 <i>Попробуйте другой номер:</i>",
            parse_mode='HTML'
        )
        return
    
    # Сохраняем телефон во временные данные
    user_temp_data[user_id]['phone'] = phone
    
    # Переходим к следующему шагу
    await AddPersonStates.waiting_for_birth.set()
    await message.answer(
        f"✅ <b>Телефон сохранен:</b> {phone}\n\n"
        "🔄 <b>Шаг 3/6:</b> Введите дату рождения\n\n"
        "📅 <i>Формат:</i> YYYY-MM-DD (например: 1992-03-15)",
        parse_mode='HTML'
    )


async def process_birth(message: Message, state: FSMContext):
    """Обработчик ввода даты рождения"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if message.text == "❌ Отмена":
        await cancel_add_process(message, state, user_id, username)
        return
    
    birth = message.text.strip()
    
    # Валидация даты
    is_valid, error_msg = validate_date(birth)
    if not is_valid:
        await message.answer(f"❌ <b>Ошибка:</b> {error_msg}\n\n🔄 <i>Попробуйте еще раз:</i>", parse_mode='HTML')
        return
    
    # Сохраняем дату рождения во временные данные
    user_temp_data[user_id]['birth'] = birth
    
    # Переходим к следующему шагу
    await AddPersonStates.waiting_for_car.set()
    await message.answer(
        f"✅ <b>Дата рождения сохранена:</b> {birth}\n\n"
        "🔄 <b>Шаг 4/6:</b> Введите номер автомобиля (или отправьте 'пропустить')\n\n"
        "🚗 <i>Пример:</i> A123AA123\n"
        "⏭️ <i>Или отправьте:</i> пропустить",
        parse_mode='HTML'
    )


async def process_car(message: Message, state: FSMContext):
    """Обработчик ввода номера автомобиля"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if message.text == "❌ Отмена":
        await cancel_add_process(message, state, user_id, username)
        return
    
    car_number = message.text.strip()
    
    # Если пользователь хочет пропустить
    if car_number.lower() in ['пропустить', 'skip', 'нет', 'н', '']:
        car_number = ""
    
    # Сохраняем номер автомобиля во временные данные
    user_temp_data[user_id]['car_number'] = car_number
    
    # Переходим к следующему шагу
    await AddPersonStates.waiting_for_address.set()
    await message.answer(
        f"✅ <b>Номер автомобиля сохранен:</b> {car_number if car_number else 'не указан'}\n\n"
        "🔄 <b>Шаг 5/6:</b> Введите адрес (или отправьте 'пропустить')\n\n"
        "🏠 <i>Пример:</i> г. Москва, ул. Ленина, д. 1, кв. 1\n"
        "⏭️ <i>Или отправьте:</i> пропустить",
        parse_mode='HTML'
    )


async def process_address(message: Message, state: FSMContext):
    """Обработчик ввода адреса"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if message.text == "❌ Отмена":
        await cancel_add_process(message, state, user_id, username)
        return
    
    address = message.text.strip()
    
    # Если пользователь хочет пропустить
    if address.lower() in ['пропустить', 'skip', 'нет', 'н', '']:
        address = ""
    
    # Сохраняем адрес во временные данные
    user_temp_data[user_id]['address'] = address
    
    # Переходим к следующему шагу
    await AddPersonStates.waiting_for_passport.set()
    await message.answer(
        f"✅ <b>Адрес сохранен:</b> {address if address else 'не указан'}\n\n"
        "🔄 <b>Шаг 6/6:</b> Введите паспортные данные (или отправьте 'пропустить')\n\n"
        "📄 <i>Пример:</i> 1234 567890\n"
        "⏭️ <i>Или отправьте:</i> пропустить",
        parse_mode='HTML'
    )


async def process_passport(message: Message, state: FSMContext):
    """Обработчик ввода паспорта"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if message.text == "❌ Отмена":
        await cancel_add_process(message, state, user_id, username)
        return
    
    passport = message.text.strip()
    
    # Если пользователь хочет пропустить
    if passport.lower() in ['пропустить', 'skip', 'нет', 'н', '']:
        passport = ""
    
    # Сохраняем паспорт во временные данные
    user_temp_data[user_id]['passport'] = passport
    
    # Завершаем процесс добавления
    await finish_add_process(message, state, user_id, username)


async def finish_add_process(message: Message, state: FSMContext, user_id: int, username: str):
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
    
    # Сохраняем в базу данных
    saved_person = db.save_person(new_record)
    if saved_person:
        db.log_user_action(user_id, username, "ADD_SUCCESS", 
                         f"Добавлена запись: {new_record['fio']}, {new_record['phone']}, {new_record['birth']}")
        
        # Формируем красивое сообщение с результатом
        result_message = "🎉 <b>Запись успешно добавлена!</b>\n\n"
        result_message += format_record(saved_person)
        
        # Возвращаем основную клавиатуру
        role = auth_manager.get_user_role(user_id)
        keyboard = get_admin_keyboard() if role == "admin" else get_main_keyboard()
        
        await message.answer(result_message, reply_markup=keyboard, parse_mode='HTML')
    else:
        db.log_user_action(user_id, username, "ADD_ERROR", "Ошибка при сохранении данных")
        await message.answer("❌ <b>Ошибка при сохранении данных.</b> Попробуйте еще раз.", parse_mode='HTML')
    
    # Очищаем временные данные и состояние
    if user_id in user_temp_data:
        del user_temp_data[user_id]
    await state.finish()


async def cancel_add_process(message: Message, state: FSMContext, user_id: int, username: str):
    """Отменяет процесс добавления записи"""
    db.log_user_action(user_id, username, "ADD_CANCELLED", "Отмена добавления записи")
    
    # Очищаем временные данные
    if user_id in user_temp_data:
        del user_temp_data[user_id]
    
    # Возвращаем основную клавиатуру
    role = auth_manager.get_user_role(user_id)
    keyboard = get_admin_keyboard() if role == "admin" else get_main_keyboard()
    
    await message.answer("❌ <b>Добавление записи отменено.</b>", reply_markup=keyboard, parse_mode='HTML')
    await state.finish()


async def add_cmd(message: Message, state: FSMContext):
    """Обработчик команды /add"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if not auth_manager.is_authorized(user_id):
        db.log_user_action(user_id, username, "ADD_COMMAND", "Попытка добавления без авторизации")
        await message.answer("Доступ запрещен! Сначала введите код доступа через /start")
        return
    
    # Инициализируем временные данные пользователя
    user_temp_data[user_id] = {}
    
    # Запускаем процесс добавления
    await AddPersonStates.waiting_for_fio.set()
    db.log_user_action(user_id, username, "ADD_START", "Начало пошагового добавления записи через команду")
    
    await message.answer(
        "📝 <b>Добавление новой записи</b>\n\n"
        "🔄 <b>Шаг 1/6:</b> Введите ФИО (Фамилия Имя Отчество)\n\n"
        "💡 <i>Пример:</i> Иванов Иван Иванович",
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )


def register_add_handlers(dp: Dispatcher):
    """Регистрация обработчиков добавления"""
    dp.register_message_handler(add_button_handler, lambda m: m.text == "➕ Добавить")
    dp.register_message_handler(add_cmd, commands=["add"])
    dp.register_message_handler(process_fio, state=AddPersonStates.waiting_for_fio)
    dp.register_message_handler(process_phone, state=AddPersonStates.waiting_for_phone)
    dp.register_message_handler(process_birth, state=AddPersonStates.waiting_for_birth)
    dp.register_message_handler(process_car, state=AddPersonStates.waiting_for_car)
    dp.register_message_handler(process_address, state=AddPersonStates.waiting_for_address)
    dp.register_message_handler(process_passport, state=AddPersonStates.waiting_for_passport)

