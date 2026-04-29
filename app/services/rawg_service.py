from datetime import date

import httpx


class RAWGService:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def search_games(self, query: str, page_size: int = 10) -> list[dict]:
        params = {"key": self.api_key, "search": query, "page_size": page_size}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://api.rawg.io/api/games", params=params)
            response.raise_for_status()
            return [self._normalize_game(item) for item in response.json().get("results", [])]

    async def popular_by_tags(self, tags: list[str], page_size: int = 40) -> list[dict]:
        params = {
            "key": self.api_key,
            "tags": ",".join(tags[:5]),
            "ordering": "-rating",
            "page_size": page_size,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://api.rawg.io/api/games", params=params)
            response.raise_for_status()
            return [self._normalize_game(item) for item in response.json().get("results", [])]

    def _normalize_game(self, item: dict) -> dict:
        released_at = None
        if item.get("released"):
            try:
                released_at = date.fromisoformat(item["released"])
            except ValueError:
                released_at = None

        return {
            "external_id": str(item["id"]),
            "name": item.get("name", "Unknown game"),
            "description": "",
            "genres": [genre["name"].lower() for genre in item.get("genres", [])],
            "tags": [tag["name"].lower() for tag in item.get("tags", [])[:20]],
            "rating": item.get("rating"),
            "released_at": released_at,
            "cover_image": item.get("background_image"),
            "similar_games": [],
            "metadata_json": item,
        }

