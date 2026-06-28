from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    PORTAL_BACKEND_URL: str = "http://localhost:8000"
    PORT: int = 8001

    class Config:
        env_file = ".env"

settings = Settings()