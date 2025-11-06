"""Модели базы данных"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Person(Base):
    """Модель персоны"""
    __tablename__ = "persons"
    
    id = Column(Integer, primary_key=True, index=True)
    fio = Column(String, nullable=False, index=True)  # Индекс для быстрого поиска
    phone = Column(String, nullable=False, index=True, unique=True)  # Индекс и уникальность
    birth = Column(String, nullable=False)
    car_number = Column(String, nullable=True, index=True)  # Индекс для поиска
    address = Column(Text, nullable=True)
    passport = Column(String, nullable=True, index=True)  # Индекс для поиска
    
    # Составной индекс для поиска по нескольким полям
    __table_args__ = (
        Index('idx_person_search', 'fio', 'phone', 'car_number'),
    )


class UserLog(Base):
    """Модель лога действий пользователя"""
    __tablename__ = "user_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)  # Индекс для сортировки
    user_id = Column(Integer, nullable=False, index=True)  # Индекс для фильтрации
    username = Column(String, nullable=True)
    action = Column(String, nullable=False, index=True)  # Индекс для фильтрации по действию
    details = Column(Text, nullable=True)
    
    # Составной индекс для частых запросов
    __table_args__ = (
        Index('idx_log_user_action', 'user_id', 'action', 'timestamp'),
    )

