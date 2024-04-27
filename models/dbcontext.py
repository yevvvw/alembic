from sqlalchemy import Column, String, Integer, Identity, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

from enum import Enum

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, Identity(start=1), primary_key=True)
    name = Column(String, index=True, nullable=False)
    surname = Column(String, index=True, nullable=False)
    hashed_password = Column(String)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete='CASCADE'), nullable=False)
    company = relationship("Company", back_populates="users")

class Company(Base):
    __tablename__ = 'companies'
    id = Column(Integer, Identity(start=1), primary_key=True)
    name = Column(String, index=True, nullable=False)
    country = Column(String, index=True, nullable=False)
    users = relationship("User", back_populates="company", cascade='save-update, merge, delete', passive_deletes=True)

class Tags(Enum):
    users = "users"
    companies = "companies"