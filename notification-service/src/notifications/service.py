from src.notifications.schemas import EventType, LoanNotificationEvent


class NotificationService:
    def handle_event(self, event: LoanNotificationEvent) -> None:
        if event.event_type == EventType.LOAN_CREATED:
            action = "видано позичальнику"
        elif event.event_type == EventType.LOAN_RETURNED:
            action = "повернено від позичальника"
        else:
            raise ValueError(f"Невідомий тип події: {event.event_type}")

        print(
            f"\n[Notification Service] Отримано подію: {event.event_type}",
            flush=True,
        )
        print(
            f" -> Сповіщення для власника '{event.owner_id}': "
            f"книгу ID={event.book_id} {action} '{event.borrower_name}'.",
            flush=True,
        )


notification_service = NotificationService()