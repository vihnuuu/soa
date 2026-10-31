import asyncio
import json
import pika
from src.core.config import settings
from src.loans.exceptions import EventPublishError


class EventPublisher:
    def __init__(
        self,
        host: str = settings.rabbit_host,
        queue_name: str = settings.rabbit_queue,
    ) -> None:
        self.host = host
        self.queue_name = queue_name

    def _sync_publish(self, event_data: dict) -> None:
        connection = None
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.host,
                    connection_attempts=3,
                    retry_delay=1,
                    socket_timeout=3,
                    blocked_connection_timeout=5,
                )
            )
            channel = connection.channel()
            channel.basic_publish(
                exchange="",
                routing_key=self.queue_name,
                body=json.dumps(event_data, ensure_ascii=False),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type="application/json",
                ),
                mandatory=False,
            )
        except (pika.exceptions.AMQPError, OSError, ValueError) as exc:
            raise EventPublishError(f"{type(exc).__name__}: {exc}") from exc
        finally:
            if connection is not None and connection.is_open:
                connection.close()

    async def publish(self, event_data: dict) -> None:
        await asyncio.to_thread(self._sync_publish, event_data)


event_publisher = EventPublisher()