import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.game import Game
from app.repositories.users import get_or_create_user
from app.services.feedback_service import store_feedback
from app.services.llm_service import LLMService
from app.services.rawg_service import RAWGService
from app.services.recommendation_engine import RecommendationEngine
from app.services.steam_service import SteamService


logger = logging.getLogger(__name__)


class Onboarding(StatesGroup):
    favorite_games = State()
    last_loved_game = State()
    dislikes = State()
    steam_profile = State()


def build_dispatcher(settings: Settings) -> Dispatcher:
    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    router = Router()

    rawg = RAWGService(settings.rawg_api_key)
    llm = LLMService(
        settings.openai_api_key,
        settings.openai_model,
        settings.openai_base_url,
        settings.openai_app_url,
        settings.openai_app_name or settings.app_name,
    )
    steam = SteamService(settings.steam_api_key)
    engine = RecommendationEngine(rawg=rawg, llm=llm)

    @router.message(Command("start"))
    async def start(message: Message, state: FSMContext) -> None:
        async with SessionLocal() as session:
            await get_or_create_user(session, message.from_user.id)
        await state.set_state(Onboarding.favorite_games)
        await message.answer("Назови свой топ-3 любимых игр")

    @router.message(Onboarding.favorite_games)
    async def favorite_games(message: Message, state: FSMContext) -> None:
        await state.update_data(favorite_games=message.text or "")
        await state.set_state(Onboarding.last_loved_game)
        await message.answer("Какая последняя игра тебе сильно зашла?")

    @router.message(Onboarding.last_loved_game)
    async def last_loved_game(message: Message, state: FSMContext) -> None:
        await state.update_data(last_loved_game=message.text or "")
        await state.set_state(Onboarding.dislikes)
        await message.answer("Что тебе НЕ нравится в играх? Жанры, механики, стиль.")

    @router.message(Onboarding.dislikes)
    async def dislikes(message: Message, state: FSMContext) -> None:
        await state.update_data(dislikes=message.text or "")
        await state.set_state(Onboarding.steam_profile)
        await message.answer("Пришли Steam profile URL или SteamID. Можно написать: пропустить")

    @router.message(Onboarding.steam_profile)
    async def steam_profile(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        async with SessionLocal() as session:
            user = await get_or_create_user(session, message.from_user.id)
            liked_games = _split_games(data.get("favorite_games", "")) + _split_games(data.get("last_loved_game", ""))
            preference_text = "\n".join([data.get("favorite_games", ""), data.get("last_loved_game", ""), data.get("dislikes", "")])
            try:
                extracted = await llm.extract_tags(session, preference_text)
            except Exception:
                logger.exception("Failed to extract preference tags")
                extracted = {"preferred_tags": [], "disliked_tags": []}
                await message.answer(
                    "Я сохранил ответы, но временно не смог обработать их через LLM. "
                    "Продолжу с базовым профилем."
                )

            steam_text = (message.text or "").strip()
            if steam_text.lower() not in {"пропустить", "skip", "-"}:
                steam_id = await steam.resolve_steam_id(steam_text)
                if steam_id:
                    user.steam_id = steam_id
                    snapshot = await steam.build_profile_snapshot(steam_id)
                    liked_games.extend(snapshot["most_played_games"][:5])

            user.preference.liked_games = list(dict.fromkeys(liked_games))
            user.preference.disliked_tags = extracted.get("disliked_tags", [])
            user.preference.preferred_tags = {tag: 1.0 for tag in extracted.get("preferred_tags", [])}
            await session.commit()

        await state.clear()
        await message.answer("Готово. Я собрал профиль вкусов. Напиши /recommend, чтобы получить 3 игры.")

    @router.message(Command("recommend"))
    async def recommend(message: Message) -> None:
        try:
            async with SessionLocal() as session:
                user = await get_or_create_user(session, message.from_user.id)
                recommendations = await engine.recommend(session, user)
        except Exception:
            logger.exception("Failed to build recommendations")
            await message.answer("Не смог собрать рекомендации прямо сейчас. Попробуй еще раз чуть позже.")
            return

        for item in recommendations:
            await _send_recommendation(bot, message.chat.id, item)

    @router.callback_query(F.data.startswith("feedback:"))
    async def feedback(callback: CallbackQuery) -> None:
        _, feedback_type, game_id = callback.data.split(":")
        async with SessionLocal() as session:
            user = await get_or_create_user(session, callback.from_user.id)
            result = await session.execute(select(Game).where(Game.id == int(game_id)))
            game = result.scalar_one()
            await store_feedback(session, user, game, feedback_type)
        await callback.answer("Учел")

    dispatcher.include_router(router)
    dispatcher["bot"] = bot
    return dispatcher


async def _send_recommendation(bot: Bot, chat_id: int, item) -> None:
    text = (
        f"<b>{item.name}</b>\n\n"
        f"{item.description}\n\n"
        f"Steam rating: {item.rating or 'n/a'}\n\n"
        f"<b>Плюсы</b>\n{_bullets(item.pros)}\n\n"
        f"<b>Минусы</b>\n{_bullets(item.cons)}"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍 Interested", callback_data=f"feedback:like:{item.game_id}"),
                InlineKeyboardButton(text="👎 Not interested", callback_data=f"feedback:dislike:{item.game_id}"),
            ],
            [InlineKeyboardButton(text="🔥 Play now", url=item.steam_url or "https://store.steampowered.com/")],
        ]
    )
    if item.cover_image:
        await bot.send_photo(chat_id, item.cover_image, caption=text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")


def _split_games(value: str) -> list[str]:
    return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items[:3]) if items else "- Пока нет данных"
