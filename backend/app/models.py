# backend/app/models.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hash: Mapped[str] = mapped_column(String(36), unique=True, nullable=False,
                                       default=lambda: str(uuid.uuid4()))
    content_type: Mapped[str] = mapped_column(
        SAEnum("text", "image", "video", "link", name="content_type_enum"), nullable=False
    )
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    og_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    og_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    og_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
