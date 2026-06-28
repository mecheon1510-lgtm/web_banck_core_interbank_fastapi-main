from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.cfg_config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,       # reconecta si la conexión se cae
    pool_size=5,
    max_overflow=10
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# Dependencia para inyectar en cada endpoint
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()