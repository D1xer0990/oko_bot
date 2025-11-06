"""Функции форматирования"""
from database.models import Person


def format_record(record: Person, show_id: bool = False) -> str:
    """Форматирует запись в простом и чистом виде"""
    result = ""
    if show_id:
        result += f"🆔 ID: {record.id}\n"
    result += f"👤 ФИО: {record.fio}\n"
    result += f"📞 Телефон: {record.phone}\n"
    result += f"📅 Дата рождения: {record.birth}\n"
    
    if record.car_number:
        result += f"🚗 Номер авто: {record.car_number}\n"
    if record.address:
        result += f"🏠 Адрес: {record.address}\n"
    if record.passport:
        result += f"📄 Паспорт: {record.passport}\n"
    
    return result.rstrip()  # Убираем последний перенос строки

