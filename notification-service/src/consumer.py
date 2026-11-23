import asyncio
import json
import logging
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
from src.observability import (
    CONSUMER_UP,
    EVENTS,
    PROCESSING_SECONDS,
    REPLIES,
    extract_context,
    get_tracer,
    inject_trace_context,
)
from opentelemetry.trace import SpanKind

logger = logging.getLogger("notification_consumer")
tracer = get_tracer()


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
        started = time.perf_counter()
        carrier, event_type = None, "unknown"
        try:
            raw = json.loads(body.decode("utf-8"))
            if isinstance(raw, dict):
                carrier = raw.get("trace_context")
                event_type = str(raw.get("event_type", "unknown"))
        except ValueError:
            pass

        with tracer.start_as_current_span(
            "notification.consume",
            context=extract_context(carrier),
            kind=SpanKind.CONSUMER,
            attributes={"messaging.system": "rabbitmq", "messaging.destination": self.queue_name},
        ):
            result = self._process(ch, method, body)
            EVENTS.labels(event_type, result).inc()
            PROCESSING_SECONDS.labels(event_type).observe(time.perf_counter() - started)

    def _process(self, ch, method, body: bytes) -> str:
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
            logger.error(
                "event_rejected_to_dlq", extra={"error": str(exc), "reason": "processing_error"}
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return "rejected"

        except Exception as exc:
            logger.error(
                "event_rejected_to_dlq", extra={"error": str(exc), "reason": "unexpected"}
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return "rejected"

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
                        "trace_context": inject_trace_context(),
                    }
                )
                REPLIES.labels("ok").inc()
            except ReplyPublishError as exc:
                REPLIES.labels("error").inc()
                logger.error(
                    "saga_reply_failed_requeue",
                    extra={"error": str(exc), "loan_id": event.payload.loan_id},
                )
                time.sleep(1)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return "requeued"

        ch.basic_ack(delivery_tag=method.delivery_tag)
        return "ok"

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

                CONSUMER_UP.set(1)
                logger.info(
                    "rabbitmq_connected",
                    extra={
                        "host": self.host,
                        "queue": self.queue_name,
                        "dlq": self.dlq_name,
                        "simulate_saga_fault": settings.simulate_saga_fault,
                    },
                )
                channel.start_consuming()

            except pika.exceptions.AMQPConnectionError:
                CONSUMER_UP.set(0)
                logger.error("rabbitmq_unavailable", extra={"retry_in_s": 3})
                time.sleep(3)

            except KeyboardInterrupt:
                logger.info("shutdown")
                break

            except Exception as exc:
                CONSUMER_UP.set(0)
                logger.error("consumer_loop_failure", extra={"error": str(exc)})
                time.sleep(3)

            finally:
                if connection is not None and connection.is_open:
                    connection.close()