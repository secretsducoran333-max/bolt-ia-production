# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from settings import settings

# Usamos a DATABASE_URL do arquivo de configurações
_db_url = settings.DATABASE_URL

# Se a URL começar com postgres://, ajustar para postgresql://
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

# Se DATABASE_URL contém placeholder "host", usar SQLite local
if "host" in _db_url or "password" in _db_url:
    _db_url = "sqlite:///./bolt_ia.db"
    print(f"⚠️ Usando SQLite local: {_db_url}")
    engine = create_engine(_db_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        _db_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()