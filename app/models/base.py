"""Shared SQLAlchemy declarative base for ORM entities."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

