from pydantic_settings import BaseSettings
from sqlalchemy import create_engine


class Settings(BaseSettings):
    database_url: str


settings = Settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
