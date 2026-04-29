from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.user import User
from app.repositories.games import list_candidate_games, upsert_game
from app.schemas.recommendation import GameRecommendation
from app.services.llm_service import LLMService
from app.services.rawg_service import RAWGService


class RecommendationEngine:
    def __init__(self, rawg: RAWGService, llm: LLMService) -> None:
        self.rawg = rawg
        self.llm = llm

    async def recommend(self, session: AsyncSession, user: User, limit: int = 3) -> list[GameRecommendation]:
        await self._ensure_candidates(session, user)
        candidates = await list_candidate_games(session, limit=300)
        scored = sorted(
            ((self._score_game(user, game), game) for game in candidates),
            key=lambda item: item[0],
            reverse=True,
        )

        recommendations: list[GameRecommendation] = []
        for score, game in scored[:limit]:
            summary = await self.llm.summarize_game(session, game.name, game.description, game.tags)
            recommendations.append(
                GameRecommendation(
                    game_id=game.id,
                    name=game.name,
                    description=game.description or self._fallback_description(game),
                    cover_image=game.cover_image,
                    rating=game.rating,
                    pros=summary.get("pros", [])[:3],
                    cons=summary.get("cons", [])[:3],
                    score=round(score, 3),
                    steam_url=self._steam_search_url(game.name),
                )
            )
        return recommendations

    async def _ensure_candidates(self, session: AsyncSession, user: User) -> None:
        preference = user.preference
        seed_queries = list(dict.fromkeys((preference.liked_games or [])[:6]))
        for query in seed_queries:
            for item in await self.rawg.search_games(query, page_size=5):
                await upsert_game(session, item)

        preferred_tags = sorted(
            (preference.preferred_tags or {}).items(),
            key=lambda item: item[1],
            reverse=True,
        )
        tag_names = [name for name, _ in preferred_tags[:6]]
        if tag_names:
            for item in await self.rawg.popular_by_tags(tag_names, page_size=50):
                await upsert_game(session, item)

    def _score_game(self, user: User, game: Game) -> float:
        preference = user.preference
        preferred_tags = preference.preferred_tags or {}
        inferred_tags = preference.inferred_tags or {}
        disliked_tags = set(preference.disliked_tags or [])
        game_tags = set((game.tags or []) + (game.genres or []))

        tag_match_score = sum(float(preferred_tags.get(tag, 0)) for tag in game_tags)
        inferred_score = sum(float(inferred_tags.get(tag, 0)) * 0.6 for tag in game_tags)
        popularity_weight = min((game.rating or 0) / 5, 1.0) * 2
        disliked_penalty = len(game_tags.intersection(disliked_tags)) * 3
        liked_name_bonus = 1.5 if game.name in (preference.liked_games or []) else 0

        return tag_match_score + inferred_score + popularity_weight + liked_name_bonus - disliked_penalty

    def _fallback_description(self, game: Game) -> str:
        tags = ", ".join((game.tags or game.genres or [])[:5])
        return f"Игра с акцентом на {tags}." if tags else "Подходит как кандидат для новой рекомендации."

    def _steam_search_url(self, name: str) -> str:
        return f"https://store.steampowered.com/search/?term={name.replace(' ', '+')}"

