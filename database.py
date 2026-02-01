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

def get_db_engine():
    # Database connection string
    db_url = "postgresql://postgres:njqdTnwqYsOSBpMzJJKfmtrwhEzehTPc@yamabiko.proxy.rlwy.net:55821/railway"
    return create_engine(db_url)

def init_db():
    engine = get_db_engine()
    Base.metadata.create_all(engine)
    print("Database initialization complete.")

def get_session():
    engine = get_db_engine()
    Session = sessionmaker(bind=engine)
    return Session()

if __name__ == "__main__":
    init_db()
