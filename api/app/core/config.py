from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    session_hours: int = 8
    cookie_secure: bool = False  # True in production (HTTPS)
    lockout_attempts: int = 5
    lockout_minutes: int = 5


settings = Settings()
