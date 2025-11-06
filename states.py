"""Состояния FSM для бота"""
from aiogram.dispatcher.filters.state import State, StatesGroup


class AddPersonStates(StatesGroup):
    """Состояния для добавления персоны"""
    waiting_for_fio = State()      # Ожидание ФИО
    waiting_for_phone = State()    # Ожидание телефона
    waiting_for_birth = State()    # Ожидание даты рождения
    waiting_for_car = State()      # Ожидание номера авто (опционально)
    waiting_for_address = State()  # Ожидание адреса (опционально)
    waiting_for_passport = State() # Ожидание паспорта (опционально)


class SearchStates(StatesGroup):
    """Состояния для поиска"""
    waiting_for_query = State()    # Ожидание ввода поискового запроса

