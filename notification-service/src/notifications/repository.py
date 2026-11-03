import uuid
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from src.notifications.models import Notification, NotificationStatus


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_notification(
        self,
        event_id: str | uuid.UUID,
        loan_id: str | uuid.UUID,
        recipient: str,
        message: str,
        status: NotificationStatus = NotificationStatus.SENT,
    ) -> bool:
        eid = uuid.UUID(str(event_id))
        lid = uuid.UUID(str(loan_id))

        stmt = (
            insert(Notification)
            .values(
                event_id=eid,
                loan_id=lid,
                recipient=str(recipient),
                message=message,
                status=status,
            )
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0