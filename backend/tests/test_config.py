import os
import pytest

def test_config_loads_required_vars(monkeypatch):
    monkeypatch.setenv("TOTP_SECRET", "JBSWY3DPEHPK3PXP")
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/db")
    monkeypatch.setenv("MEDIA_DIR", "/tmp/media")
    import importlib
    import app.config as cfg
    importlib.reload(cfg)
    from app.config import settings
    assert settings.totp_secret == "JBSWY3DPEHPK3PXP"
    assert settings.admin_token == "secret"
    assert settings.media_dir == "/tmp/media"

from pathlib import Path

def test_config_raises_on_missing_totp_secret(monkeypatch):
    monkeypatch.delenv("TOTP_SECRET", raising=False)
    env_path = Path(".env")
    temp_env_path = Path(".env.bak")
    if env_path.exists():
        env_path.rename(temp_env_path)
    try:
        import importlib
        import app.config as cfg
        with pytest.raises(Exception):
            importlib.reload(cfg)
            from app.config import settings
            _ = settings.totp_secret
    finally:
        if temp_env_path.exists():
            temp_env_path.rename(env_path)
