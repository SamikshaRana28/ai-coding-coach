from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# User table
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    email = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Attempt table - har baar user code submit kare
class Attempt(Base):
    __tablename__ = "attempts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    question = Column(Text)
    code = Column(Text)
    topic = Column(String)        # arrays, graphs, dp etc
    difficulty = Column(String)   # easy, medium, hard
    time_complexity = Column(String)
    space_complexity = Column(String)
    bugs_found = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

# Tables banao database mein
def create_tables():
    Base.metadata.create_all(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()