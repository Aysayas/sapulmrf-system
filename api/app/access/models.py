from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Staff screens marked "according to authorization" in the approved requirements (STF-03, 07, 08) + live camera
# and the exported-reports list (STF-09).
SCREENS = ("segregation", "predictions", "alerts", "camera", "reports")


class StaffAccess(Base):
    __tablename__ = "staff_access"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    screen: Mapped[str] = mapped_column(String(30), primary_key=True)
    granted: Mapped[bool] = mapped_column(default=False)
