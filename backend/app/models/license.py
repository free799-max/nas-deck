"""本机授权状态模型。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LicenseState(Base):
    """本机唯一的授权状态，installation_id 在解绑后保留。"""

    __tablename__ = "license_states"
    __table_args__ = (CheckConstraint("id = 1", name="ck_license_state_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    installation_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    certificate: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    activation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
