"""Функции валидации данных"""
from datetime import datetime
import re


def validate_fio(fio: str) -> tuple[bool, str]:
    """
    Валидация ФИО
    Возвращает (is_valid, error_message)
    """
    fio = fio.strip()
    
    if not fio:
        return False, "ФИО не может быть пустым"
    
    if len(fio.split()) < 2:
        return False, "ФИО должно содержать минимум фамилию и имя"
    
    if len(fio) > 200:
        return False, "ФИО слишком длинное (максимум 200 символов)"
    
    # Проверка на допустимые символы (буквы, пробелы, дефисы)
    if not re.match(r'^[а-яА-ЯёЁa-zA-Z\s\-]+$', fio):
        return False, "ФИО содержит недопустимые символы"
    
    return True, ""


def validate_phone(phone: str) -> tuple[bool, str]:
    """
    Валидация телефона
    Возвращает (is_valid, error_message)
    """
    phone = phone.strip()
    
    # Удаляем все нецифровые символы для проверки
    digits_only = re.sub(r'\D', '', phone)
    
    if not digits_only:
        return False, "Телефон должен содержать цифры"
    
    if len(digits_only) != 11:
        return False, "Телефон должен содержать 11 цифр"
    
    # Проверка на российский формат (начинается с 7 или 8)
    if not digits_only.startswith(('7', '8')):
        return False, "Телефон должен начинаться с 7 или 8"
    
    return True, ""


def validate_date(date_str: str) -> tuple[bool, str]:
    """
    Валидация даты в формате YYYY-MM-DD
    Возвращает (is_valid, error_message)
    """
    date_str = date_str.strip()
    
    try:
        # Проверка формата
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return False, "Неверный формат даты. Используйте: YYYY-MM-DD"
        
        # Парсинг даты
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Проверка разумности даты (не в будущем и не слишком старые)
        current_year = datetime.now().year
        if date_obj.year > current_year:
            return False, "Дата не может быть в будущем"
        
        if date_obj.year < 1900:
            return False, "Дата слишком старая (минимум 1900 год)"
        
        return True, ""
    except ValueError:
        return False, "Неверная дата. Проверьте правильность ввода"


def normalize_phone(phone: str) -> str:
    """Нормализует телефон к формату 11 цифр"""
    digits_only = re.sub(r'\D', '', phone)
    if len(digits_only) == 11:
        # Если начинается с 8, заменяем на 7
        if digits_only.startswith('8'):
            digits_only = '7' + digits_only[1:]
        return digits_only
    return phone

