from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game


async def upsert_game(session: AsyncSession, data: dict) -> Game:
    result = await session.execute(select(Game).where(Game.external_id == str(data["external_id"])))
    game = result.scalar_one_or_none()
    if game is None:
        game = Game(external_id=str(data["external_id"]), name=data["name"])
        session.add(game)

    game.name = data["name"]
    game.description = data.get("description") or ""
    game.genres = data.get("genres") or []
    game.tags = data.get("tags") or []
    game.rating = data.get("rating")
    game.released_at = data.get("released_at")
    game.cover_image = data.get("cover_image")
    game.similar_games = data.get("similar_games") or []
    game.metadata_json = data.get("metadata_json") or {}
    await session.commit()
    await session.refresh(game)
    return game


async def find_games_by_names(session: AsyncSession, names: list[str]) -> list[Game]:
    if not names:
        return []
    result = await session.execute(select(Game).where(Game.name.in_(names)))
    return list(result.scalars().all())


async def list_candidate_games(session: AsyncSession, limit: int = 300) -> list[Game]:
    result = await session.execute(select(Game).order_by(Game.rating.desc().nullslast()).limit(limit))
    return list(result.scalars().all())

