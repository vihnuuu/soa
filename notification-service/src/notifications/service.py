import os
from src.notifications.schemas import EventType, LoanNotificationEvent


class NotificationProcessingError(Exception):
  pass


class NotificationService:

  def handle_event(self, event: LoanNotificationEvent) -> None:
    # перемикач
    simulate_fault = (
        os.getenv("SIMULATE_SAGA_FAULT", "false").lower() == "true"
    )

    if event.event_type == EventType.LOAN_CREATED:
      if simulate_fault:
        print(
            f"\n[Notification Service] [SAGA FAULT] Збій обробки"
            f" {event.event_type} для loan_id={event.payload.loan_id}!",
            flush=True,
        )
        raise NotificationProcessingError(
            "Simulated consumer failure for SAGA testing"
        )

      due_info = (
          f" Термін повернення: до {event.payload.due_date}."
          if getattr(event.payload, "due_date", None)
          else ""
      )
      print(
          f"\n[Notification Service] Отримано подію: {event.event_type}",
          flush=True,
      )
      print(
          f" -> Сповіщення для власника '{event.payload.owner_id}': "
          f"книгу ID={event.payload.book_id} видано позичальнику '{event.payload.borrower_name}'.{due_info}",
          flush=True,
      )
      return

    if event.event_type == EventType.LOAN_RETURNED:
      print(
          f"\n[Notification Service] Отримано подію: {event.event_type}",
          flush=True,
      )
      print(
          f" -> Сповіщення для власника '{event.payload.owner_id}': "
          f"книгу ID={event.payload.book_id} повернуто від позичальника '{event.payload.borrower_name}'.",
          flush=True,
      )
      return

    raise ValueError(f"Невідомий тип події: {event.event_type}")


notification_service = NotificationService()