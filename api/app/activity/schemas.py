from datetime import datetime

from pydantic import BaseModel


class ActivityOut(BaseModel):
    id: int
    at: datetime
    user_id: int | None
    who: str
    action: str
    record: str
