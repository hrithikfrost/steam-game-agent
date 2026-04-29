import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.api.routes import router
from app.bot.telegram_bot import build_dispatcher
from app.core.config import get_settings
from app.db.session import create_schema
from app.scheduler.daily import build_scheduler


settings = get_settings()
logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_schema()
    dispatcher = build_dispatcher(settings)
    bot = dispatcher["bot"]
    scheduler = build_scheduler(settings, bot)
    scheduler.start()
    polling_task = asyncio.create_task(dispatcher.start_polling(bot))
    app.state.scheduler = scheduler
    app.state.polling_task = polling_task
    yield
    scheduler.shutdown(wait=False)
    polling_task.cancel()
    await bot.session.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router)


def main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()

