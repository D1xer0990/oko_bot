"""Управление авторизацией пользователей"""
from config import USER_ACCESS_CODE, ADMIN_ACCESS_CODE
import logging

logger = logging.getLogger(__name__)


class AuthManager:
    """Менеджер авторизации пользователей"""
    
    def __init__(self):
        self.authorized_users = set()  # Обычные пользователи
        self.authorized_admins = set()  # Администраторы
        self.authorized_usernames = set()  # Список имен пользователей
    
    def is_authorized(self, user_id: int) -> bool:
        """Проверяет, авторизован ли пользователь (любая роль)"""
        return user_id in self.authorized_users or user_id in self.authorized_admins
    
    def is_admin(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором"""
        return user_id in self.authorized_admins
    
    def get_user_role(self, user_id: int) -> str:
        """Возвращает роль пользователя"""
        if user_id in self.authorized_admins:
            return "admin"
        elif user_id in self.authorized_users:
            return "user"
        else:
            return "unauthorized"
    
    def authorize_user(self, user_id: int, username: str = None, code: str = None) -> tuple[bool, str]:
        """
        Авторизация пользователя по коду
        Возвращает (success, role)
        """
        if code == USER_ACCESS_CODE:
            self.authorized_users.add(user_id)
            if username:
                self.authorized_usernames.add(username)
            return True, "user"
        elif code == ADMIN_ACCESS_CODE:
            self.authorized_admins.add(user_id)
            if username:
                self.authorized_usernames.add(username)
            return True, "admin"
        else:
            return False, "unauthorized"
    
    def deauthorize_user(self, user_id: int):
        """Деавторизация пользователя"""
        self.authorized_users.discard(user_id)
        self.authorized_admins.discard(user_id)
    
    def should_log_auth(self, user_id: int, username: str, action: str) -> bool:
        """Проверяет, нужно ли логировать событие авторизации"""
        # Не логируем события авторизации для уже авторизованных пользователей
        if action.startswith("AUTH") and self.is_authorized(user_id):
            return False
        return True


# Глобальный экземпляр менеджера авторизации
auth_manager = AuthManager()

