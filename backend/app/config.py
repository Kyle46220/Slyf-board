# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    totp_secret: str
    admin_token: str
    database_url: str
    media_dir: str = "/var/board/media"
    signal_socket: str = "/var/run/signal-cli/socket"
    signal_phone_number: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
