import uuid
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config import settings
from src.notifications.models import Notification, NotificationStatus


class NotificationRepository:

  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def save_notification(
      self, loan_id: str, recipient: str, message: str
  ) -> Notification:
    if settings.simulate_saga_fault:
      raise IntegrityError(
          statement="INSERT INTO notification ...",
          params={},
          orig=Exception("Збій запису в БД: змодельоване порушення обмеження"),
      )

    notification = Notification(
        id=uuid.uuid4(),
        loan_id=uuid.UUID(loan_id),
        recipient=recipient,
        message=message,
        status=NotificationStatus.SENT,
    )
    self.session.add(notification)
    await self.session.commit()
    return notification