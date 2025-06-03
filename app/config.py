import datetime
from datetime import tzinfo
from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='D:\\Python\\Futures_bot\\.env',
        env_file_encoding='utf-8',
        extra='allow',
    )

    BYBIT_API_KEY: str
    BYBIT_API_SECRET: str
    TESTNET: bool = True

    DB_USERNAME: str
    DB_HOST: str
    DB_PORT: str
    DB_NAME: str
    DB_PASSWORD: str

    @property
    def base_dir(self) -> str:
        return str(Path(__file__).resolve().parents[1])

    @property
    def async_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.DB_USERNAME}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


config = Config()
