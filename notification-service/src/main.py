import asyncio
from src.core.database import Base, engine
from src.notifications.models import Notification
from src.consumer import NotificationConsumer
from src.observability import setup_observability


async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    setup_observability()
    asyncio.run(init_models())
    consumer = NotificationConsumer()
    consumer.start()