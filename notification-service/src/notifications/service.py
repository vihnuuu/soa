from src.core.database import async_session_factory
from src.notifications.repository import NotificationRepository
from src.notifications.schemas import EventType, LoanNotificationEvent


class NotificationProcessingError(Exception):
  pass


class NotificationService:

  async def handle_event(self, event: LoanNotificationEvent) -> None:
    p = event.payload

    if event.event_type == EventType.LOAN_CREATED:
      due = f" Термін повернення: до {p.due_date}." if p.due_date else ""
      message = (
          f"Книгу ID={p.book_id} видано позичальнику "
          f"'{p.borrower_name}'.{due}"
      )
    elif event.event_type == EventType.LOAN_RETURNED:
      message = (
          f"Книгу ID={p.book_id} повернуто від позичальника "
          f"'{p.borrower_name}'."
      )
    else:
      raise ValueError(f"Невідомий тип події: {event.event_type}")

    try:
      async with async_session_factory() as session:
        await NotificationRepository(session).save_notification(
            loan_id=p.loan_id,
            recipient=p.owner_id or "unknown",
            message=message,
        )
    except Exception as exc:
      raise NotificationProcessingError(f"Помилка запису в БД: {exc}") from exc

    print(
        f"\n[Notification Service] {event.event_type}: "
        f"збережено сповіщення для позики {p.loan_id}",
        flush=True,
    )


notification_service = NotificationService()