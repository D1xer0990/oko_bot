"""Обработчики команд бота"""
from .start import register_start_handlers
from .auth import register_auth_handlers
from .search import register_search_handlers
from .add import register_add_handlers
from .logs import register_logs_handlers
from .common import register_common_handlers

__all__ = [
    'register_start_handlers',
    'register_auth_handlers',
    'register_search_handlers',
    'register_add_handlers',
    'register_logs_handlers',
    'register_common_handlers'
]

