import hashlib
import json

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_cache import LLMCache


class LLMService:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        app_url: str | None = None,
        app_name: str | None = None,
    ) -> None:
        default_headers = {}
        if app_url:
            default_headers["HTTP-Referer"] = app_url
        if app_name:
            default_headers["X-Title"] = app_name

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=default_headers or None,
        )
        self.model = model

    async def extract_tags(self, session: AsyncSession, text: str) -> dict:
        cache_key = self._cache_key("extract_tags", text)
        cached = await self._get_cache(session, cache_key)
        if cached:
            return cached

        prompt = (
            "Extract game preference tags from the user's Russian or English text. "
            "Return strict JSON with keys preferred_tags and disliked_tags, both arrays of lowercase strings.\n\n"
            f"Text: {text}"
        )
        payload = await self._json_completion(prompt)
        await self._set_cache(session, cache_key, payload)
        return payload

    async def summarize_game(self, session: AsyncSession, game_name: str, description: str, tags: list[str]) -> dict:
        cache_key = self._cache_key("summarize_game", f"{game_name}:{description}:{tags}")
        cached = await self._get_cache(session, cache_key)
        if cached:
            return cached

        prompt = (
            "Summarize why this game may or may not fit a player. "
            "Return strict JSON with keys pros and cons, each 2-3 short bullet strings in Russian.\n\n"
            f"Game: {game_name}\nDescription: {description}\nTags: {', '.join(tags)}"
        )
        payload = await self._json_completion(prompt)
        await self._set_cache(session, cache_key, payload)
        return payload

    async def _json_completion(self, prompt: str) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    async def _get_cache(self, session: AsyncSession, cache_key: str) -> dict | None:
        result = await session.execute(select(LLMCache).where(LLMCache.cache_key == cache_key))
        row = result.scalar_one_or_none()
        return row.payload if row else None

    async def _set_cache(self, session: AsyncSession, cache_key: str, payload: dict) -> None:
        session.add(LLMCache(cache_key=cache_key, payload=payload))
        await session.commit()

    def _cache_key(self, operation: str, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"{operation}:{digest}"
