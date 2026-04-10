"""Shared SQLAlchemy declarative base for ORM entities."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM entities in the application."""

