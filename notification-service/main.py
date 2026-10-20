import json
import os
import time
import pika

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")


def callback(ch, method, properties, body):
    try:
        data = json.loads(body.decode("utf-8"))

        required_fields = [
            "event_type",
            "loan_id",
            "book_id",
            "borrower_name",
            "owner_id",
        ]

        if not isinstance(data, dict) or not all(
            field in data for field in required_fields
        ):
            raise ValueError("У повідомленні відсутні обов'язкові поля")

        event_type = data["event_type"]

        if event_type == "LoanCreated":
            action = "видано позичальнику"
        elif event_type == "LoanReturned":
            action = "повернено від позичальника"
        else:
            raise ValueError(f"Невідомий тип події: {event_type}")

        print(
            f"\n[Notification Service] Отримано подію: {event_type}",
            flush=True,
        )
        print(
            f" -> Сповіщення для власника '{data['owner_id']}': "
            f"книгу ID={data['book_id']} {action} "
            f"'{data['borrower_name']}'.",
            flush=True,
        )

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as exc:
        print(
            f"[Notification Service] Некоректне повідомлення: {exc}",
            flush=True,
        )

        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=False,
        )


def run():
    while True:
        connection = None

        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    connection_attempts=3,
                    retry_delay=1,
                    socket_timeout=3,
                    heartbeat=30,
                )
            )

            channel = connection.channel()
            channel.queue_declare(
                queue="loan_notifications",
                durable=True,
            )
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue="loan_notifications",
                on_message_callback=callback,
            )

            print(
                "[Notification Service] Підключено до RabbitMQ. "
                "Очікування подій з черги",
                flush=True,
            )

            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            print(
                "[Notification Service] RabbitMQ тимчасово недоступний. "
                "Повторна спроба через 3 сек",
                flush=True,
            )
            time.sleep(3)

        except KeyboardInterrupt:
            print(
                "[Notification Service] Зупинка сервісу...",
                flush=True,
            )
            break

        finally:
            if connection is not None and connection.is_open:
                connection.close()


if __name__ == "__main__":
    run()