from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from app.core.config import Settings
from app.db.session import SessionLocal
from app.repositories.users import list_active_users
from app.services.llm_service import LLMService
from app.services.rawg_service import RAWGService
from app.services.recommendation_engine import RecommendationEngine


def build_scheduler(settings: Settings, bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.daily_recommendation_timezone)
    scheduler.add_job(
        send_daily_recommendations,
        "cron",
        hour=settings.daily_recommendation_hour,
        kwargs={"settings": settings, "bot": bot},
        id="daily_recommendations",
        replace_existing=True,
    )
    return scheduler


async def send_daily_recommendations(settings: Settings, bot: Bot) -> None:
    from app.bot.telegram_bot import _send_recommendation

    engine = RecommendationEngine(
        rawg=RAWGService(settings.rawg_api_key),
        llm=LLMService(
            settings.openai_api_key,
            settings.openai_model,
            settings.openai_base_url,
            settings.openai_app_url,
            settings.openai_app_name or settings.app_name,
        ),
    )
    async with SessionLocal() as session:
        users = await list_active_users(session)
        for user in users:
            recommendations = await engine.recommend(session, user)
            for item in recommendations:
                await _send_recommendation(bot, user.telegram_id, item)
