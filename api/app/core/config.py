from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    session_hours: int = 8
    cookie_secure: bool = False  # True in production (HTTPS)
    lockout_attempts: int = 5
    lockout_minutes: int = 5
    timezone: str = "Asia/Manila"  # "today" and daily totals follow the barangay's clock
    ollama_url: str = ""  # empty turns the AI report summaries off
    ollama_model: str = "qwen2.5:7b"


settings = Settings()
