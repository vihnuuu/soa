from datetime import datetime, timezone
import enum
import uuid
from sqlalchemy import DateTime, Enum as SAEnum, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base


class LoanStatus(str, enum.Enum):
  PENDING = "PENDING"
  ACTIVE = "ACTIVE"
  CANCELLED = "CANCELLED"
  RETURNED = "RETURNED"


class OutboxStatus(str, enum.Enum):
  NEW = "NEW"
  PROCESSED = "PROCESSED"
  FAILED = "FAILED"


class Loan(Base):
  __tablename__ = "loan"

  id: Mapped[uuid.UUID] = mapped_column(
      UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  book_id: Mapped[uuid.UUID] = mapped_column(
      UUID(as_uuid=True), nullable=False, index=True
  )
  owner_id: Mapped[uuid.UUID | None] = mapped_column(
      UUID(as_uuid=True), nullable=True, index=True
  )
  borrower_name: Mapped[str] = mapped_column(String(128), nullable=False)
  status: Mapped[LoanStatus] = mapped_column(
      SAEnum(LoanStatus, name="loan_status_enum"),
      default=LoanStatus.PENDING,
      nullable=False,
  )
  created_at: Mapped[datetime] = mapped_column(
      DateTime(timezone=True),
      default=lambda: datetime.now(timezone.utc),
      nullable=False,
  )
  due_date: Mapped[datetime | None] = mapped_column(
      DateTime(timezone=True), nullable=True
  )


class OutboxMessage(Base):
  __tablename__ = "outbox_message"

  id: Mapped[uuid.UUID] = mapped_column(
      UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  event_type: Mapped[str] = mapped_column(String(64), nullable=False)
  payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
  status: Mapped[OutboxStatus] = mapped_column(
      SAEnum(OutboxStatus, name="outbox_status_enum"),
      default=OutboxStatus.NEW,
      nullable=False,
      index=True,
  )
  retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  created_at: Mapped[datetime] = mapped_column(
      DateTime(timezone=True),
      default=lambda: datetime.now(timezone.utc),
      nullable=False,
  )
  processed_at: Mapped[datetime | None] = mapped_column(
      DateTime(timezone=True), nullable=True
  )