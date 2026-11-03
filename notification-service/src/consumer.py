import asyncio
import json
import time
import uuid
import pika
from pydantic import ValidationError
from src.core.config import settings
from src.notifications.schemas import EventType, LoanNotificationEvent
from src.notifications.service import (
    NotificationProcessingError,
    NotificationService,
    notification_service,
)
from src.reply_publisher import ReplyPublisher, ReplyPublishError, reply_publisher


class NotificationConsumer:
    def __init__(
        self,
        service: NotificationService = notification_service,
        replies: ReplyPublisher = reply_publisher,
        host: str = settings.rabbit_host,
        queue_name: str = settings.rabbit_queue,
        dlq_name: str = settings.rabbit_dlq,
        dlx_name: str = settings.rabbit_dlx,
    ) -> None:
        self.service = service
        self.replies = replies
        self.host = host
        self.queue_name = queue_name
        self.dlq_name = dlq_name
        self.dlx_name = dlx_name

    def _callback(self, ch, method, properties, body: bytes) -> None:
        try:
            raw_data = json.loads(body.decode("utf-8"))
            event = LoanNotificationEvent.model_validate(raw_data)
            asyncio.run(self.service.handle_event(event))

        except (
            NotificationProcessingError,
            json.JSONDecodeError,
            ValidationError,
            ValueError,
        ) as exc:
            print(
                f"[Notification Service] Помилка обробки: {exc}. Перенаправлення повідомлення у DLQ",
                flush=True,
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        except Exception as exc:
            print(
                f"[Notification Service] Непередбачена помилка: {exc}. Відхилення повідомлення без requeue",
                flush=True,
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        if event.event_type == EventType.LOAN_CREATED:
            try:
                self.replies.publish(
                    {
                        "event_id": str(uuid.uuid4()),
                        "event_type": "LoanConfirmed",
                        "payload": {
                            "loan_id": event.payload.loan_id,
                            "source_event_id": event.event_id,
                        },
                    }
                )
            except ReplyPublishError as exc:
                print(
                    f"[Notification Service] Не вдалося опублікувати reply: {exc}. Повтор доставки",
                    flush=True,
                )
                time.sleep(1)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return

        ch.basic_ack(delivery_tag=method.delivery_tag)

    def start(self) -> None:
        while True:
            connection = None
            try:
                connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=self.host,
                        connection_attempts=3,
                        retry_delay=1,
                        socket_timeout=3,
                        heartbeat=30,
                    )
                )
                channel = connection.channel()
                channel.exchange_declare(
                    exchange=self.dlx_name,
                    exchange_type="direct",
                    durable=True,
                )
                channel.queue_declare(queue=self.dlq_name, durable=True)
                channel.queue_bind(
                    exchange=self.dlx_name,
                    queue=self.dlq_name,
                    routing_key=self.queue_name,
                )

                channel.queue_declare(
                    queue=self.queue_name,
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": self.dlx_name,
                        "x-dead-letter-routing-key": self.queue_name,
                    },
                )

                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(
                    queue=self.queue_name,
                    on_message_callback=self._callback,
                )

                print(
                    f"[Notification Service] Підключено до RabbitMQ ({self.host}). "
                    f"Очікування подій з черги '{self.queue_name}' (DLQ: '{self.dlq_name}')..."
                    f" simulate_saga_fault={settings.simulate_saga_fault}",
                    flush=True,
                )
                channel.start_consuming()

            except pika.exceptions.AMQPConnectionError:
                print(
                    "[Notification Service] RabbitMQ тимчасово недоступний. "
                    "Повторна спроба через 3 сек...",
                    flush=True,
                )
                time.sleep(3)

            except KeyboardInterrupt:
                print("[Notification Service] Зупинка сервісу", flush=True)
                break

            except Exception as exc:
                print(
                    f"[Notification Service] Несподіваний збій у циклі з'єднання: {exc}. Перепідключення...",
                    flush=True,
                )
                time.sleep(3)

            finally:
                if connection is not None and connection.is_open:
                    connection.close()