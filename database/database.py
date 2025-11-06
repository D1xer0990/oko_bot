"""Оптимизированная работа с базой данных"""
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from config import DATABASE_URL, DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_RECYCLE, logger as config_logger
from .models import Base, Person, UserLog

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных с оптимизацией"""
    
    def __init__(self):
        """Инициализация подключения к БД с оптимизацией"""
        # Создаем engine с пулом соединений
        self.engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=DB_POOL_SIZE,
            max_overflow=DB_MAX_OVERFLOW,
            pool_recycle=DB_POOL_RECYCLE,
            pool_pre_ping=True,  # Проверка соединений перед использованием
            echo=False  # Отключаем SQL логирование в продакшене
        )
        
        # Создаем sessionmaker с scoped_session для thread-safety
        self.SessionLocal = scoped_session(
            sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
        )
        
        # Создаем таблицы
        self._create_tables()
        
        # Проверяем подключение
        self._check_connection()
    
    def _create_tables(self):
        """Создание таблиц в БД"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Таблицы базы данных созданы/проверены")
        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise
    
    def _check_connection(self):
        """Проверка подключения к БД"""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Подключение к базе данных успешно")
        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            logger.error("Бот будет работать с ограниченным функционалом")
            raise
    
    @contextmanager
    def get_session(self):
        """Контекстный менеджер для работы с сессией БД"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка в сессии БД: {e}")
            raise
        finally:
            session.close()
    
    def get_person_by_id(self, person_id: int):
        """Получить персону по ID"""
        try:
            with self.get_session() as session:
                return session.query(Person).filter(Person.id == person_id).first()
        except Exception as e:
            logger.error(f"Ошибка получения персоны по ID {person_id}: {e}")
            return None
    
    def get_person_by_phone(self, phone: str):
        """Получить персону по телефону (для проверки дубликатов)"""
        try:
            with self.get_session() as session:
                return session.query(Person).filter(Person.phone == phone).first()
        except Exception as e:
            logger.error(f"Ошибка получения персоны по телефону {phone}: {e}")
            return None
    
    def search_persons(self, query: str, limit: int = 100):
        """Оптимизированный поиск персон по запросу"""
        try:
            with self.get_session() as session:
                # Нормализуем запрос для поиска
                normalized_query = query.strip().lower()
                
                # Используем OR для поиска по всем полям
                # Оптимизированный запрос с использованием индексов
                results = session.query(Person).filter(
                    Person.fio.ilike(f'%{normalized_query}%') |
                    Person.phone.contains(query) |
                    Person.car_number.ilike(f'%{normalized_query}%') |
                    Person.address.ilike(f'%{normalized_query}%') |
                    Person.passport.contains(query)
                ).limit(limit).all()
                
                return results
        except Exception as e:
            logger.error(f"Ошибка поиска персон по запросу '{query}': {e}")
            return []
    
    def save_person(self, person_data: dict):
        """Сохранить новую персону в БД"""
        try:
            with self.get_session() as session:
                person = Person(**person_data)
                session.add(person)
                session.flush()  # Получаем ID без коммита
                session.refresh(person)
                return person
        except Exception as e:
            logger.error(f"Ошибка сохранения персоны: {e}")
            return None
    
    def log_user_action(self, user_id: int, username: str, action: str, details: str = ""):
        """Записать действие пользователя в лог"""
        try:
            with self.get_session() as session:
                log_entry = UserLog(
                    user_id=user_id,
                    username=username,
                    action=action,
                    details=details
                )
                session.add(log_entry)
                # Коммит происходит автоматически в контекстном менеджере
        except Exception as e:
            logger.error(f"Ошибка записи лога: {e}")
    
    def get_user_logs(self, limit: int = 10):
        """Получить последние логи пользователей"""
        try:
            with self.get_session() as session:
                logs = session.query(UserLog).order_by(
                    UserLog.timestamp.desc()
                ).limit(limit).all()
                
                return [{
                    "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "user_id": log.user_id,
                    "username": log.username,
                    "action": log.action,
                    "details": log.details
                } for log in logs]
        except Exception as e:
            logger.error(f"Ошибка чтения логов: {e}")
            return []
    
    def get_failed_auth_logs(self, limit: int = 10):
        """Получить только неудачные попытки авторизации"""
        try:
            with self.get_session() as session:
                logs = session.query(UserLog).filter(
                    UserLog.action == 'AUTH_FAILED'
                ).order_by(
                    UserLog.timestamp.desc()
                ).limit(limit).all()
                
                return [{
                    "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "user_id": log.user_id,
                    "username": log.username,
                    "action": log.action,
                    "details": log.details
                } for log in logs]
        except Exception as e:
            logger.error(f"Ошибка чтения логов неудачных авторизаций: {e}")
            return []
    
    def get_statistics(self):
        """Получить статистику по базе данных"""
        try:
            with self.get_session() as session:
                total_persons = session.query(Person).count()
                total_logs = session.query(UserLog).count()
                failed_auths = session.query(UserLog).filter(
                    UserLog.action == 'AUTH_FAILED'
                ).count()
                
                return {
                    "total_persons": total_persons,
                    "total_logs": total_logs,
                    "failed_auths": failed_auths
                }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}


# Глобальный экземпляр БД
db = Database()


def get_db_session():
    """Получить сессию БД (для обратной совместимости)"""
    return db.get_session()

