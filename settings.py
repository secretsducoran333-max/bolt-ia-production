# settings.py - Configurações do BoredFy AI
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./boredfy_ai.db"
    SECRET_KEY: str = "boredfy-super-secret-key-2025-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 horas

    class Config:
        env_file = ".env"

settings = Settings()
