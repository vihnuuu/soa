import json
import time
import pika
from pydantic import ValidationError
from src.core.config import settings
from src.notifications.schemas import LoanNotificationEvent
from src.notifications.service import NotificationProcessingError, NotificationService, notification_service


class NotificationConsumer:
    def __init__(
        self,
        service: NotificationService = notification_service,
        host: str = settings.rabbit_host,
        queue_name: str = settings.rabbit_queue,
        dlq_name: str = settings.rabbit_dlq,
    ) -> None:
        self.service = service
        self.host = host
        self.queue_name = queue_name
        self.dlq_name = dlq_name
        self.dlx_name = "dlx_exchange"

    def _callback(self, ch, method, properties, body: bytes) -> None:
        try:
            raw_data = json.loads(body.decode("utf-8"))
            event = LoanNotificationEvent.model_validate(raw_data)

            self.service.handle_event(event)
            ch.basic_ack(delivery_tag=method.delivery_tag)


        except (NotificationProcessingError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            print(
                f"[Notification Service] Помилка обробки: {exc}. Перенаправлення повідомлення у DLQ",
                flush=True,
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

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
                channel.exchange_declare(exchange=self.dlx_name, exchange_type="direct", durable=True)
                channel.queue_declare(queue=self.dlq_name, durable=True)
                channel.queue_bind(exchange=self.dlx_name, queue=self.dlq_name, routing_key=self.queue_name)

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
                    f"Очікування подій з черги '{self.queue_name}' (DLQ: '{self.dlq_name}')...",
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

            finally:
                if connection is not None and connection.is_open:
                    connection.close()

