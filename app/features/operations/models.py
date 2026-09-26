from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.schemas import Schema


class RateBucketORM(Base):
    __tablename__ = "rate_buckets"
    __table_args__ = (Index("rate_buckets_expires", "expires_at"),)

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    window: Mapped[int] = mapped_column(primary_key=True)
    hits: Mapped[int]
    expires_at: Mapped[int]


class HealthResponse(Schema):
    status: str
