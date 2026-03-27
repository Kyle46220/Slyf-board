# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    totp_secret: str
    admin_token: str
    database_url: str
    media_dir: str = "/var/board/media"

    class Config:
        env_file = ".env"

settings = Settings()
