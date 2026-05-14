# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    totp_secret: str
    admin_token: str
    # Cloudflare D1 config
    cf_account_id: str | None = None
    cf_database_id: str | None = None
    cf_api_token: str | None = None
    media_dir: str = "/var/board/media"
    signal_socket: str = "/var/run/signal-cli/socket"
    signal_phone_number: str = ""
    bypass_totp: bool = False
    
    # S3 Settings
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str | None = "auto"
    aws_bucket_name: str | None = None
    aws_endpoint_url: str | None = None
    aws_public_url: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()
