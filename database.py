from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
import os

Base = declarative_base()

class CompanyAnalysis(Base):
    __tablename__ = 'company_analysis'
    
    symbol = Column(String, primary_key=True)
    company_name = Column(String)
    sector = Column(String)
    current_price = Column(Float)
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    roe = Column(Float)
    eps_growth = Column(Float)
    debt_to_equity = Column(Float)
    ai_impact_score = Column(Float)
    recommendation = Column(String)  # LONG, SHORT, NEUTRAL
    reasoning = Column(Text)
    analysis_json = Column(JSON)  # Store full analysis structure for flexibility
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PromptConfig(Base):
    __tablename__ = 'prompt_config'
    
    id = Column(String, primary_key=True, default='default')
    system_prompt = Column(Text)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class User(Base):
    __tablename__ = 'users'
    
    email = Column(String, primary_key=True)
    password_hash = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

_engine = None
_SessionLocal = None

def get_db_engine():
    global _engine
    if _engine is None:
        # Database connection string
        db_url = "postgresql://postgres:njqdTnwqYsOSBpMzJJKfmtrwhEzehTPc@yamabiko.proxy.rlwy.net:55821/railway"
        # Pool size and max overflow for better performance
        _engine = create_engine(
            db_url, 
            pool_size=10, 
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800
        )
    return _engine

def init_db():
    engine = get_db_engine()
    Base.metadata.create_all(engine)
    print("Database initialization complete.")
    init_users()

def init_users():
    from werkzeug.security import generate_password_hash
    session = get_session()
    
    default_users = [
        {"email": "nimingze@hotmail.com", "password": "123456"},
        {"email": "liu.qian44@gmail.com", "password": "123456"}
    ]
    
    for u in default_users:
        exists = session.query(User).filter_by(email=u["email"]).first()
        if not exists:
            new_user = User(email=u["email"], password_hash=generate_password_hash(u["password"], method='pbkdf2:sha256'))
            session.add(new_user)
            print(f"Created user: {u['email']}")
    
    session.commit()
    session.close()

def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_db_engine()
        _SessionLocal = sessionmaker(bind=engine)
    return _SessionLocal()

if __name__ == "__main__":
    init_db()
