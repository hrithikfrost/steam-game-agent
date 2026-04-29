import re

import httpx


STEAM_API_BASE = "https://api.steampowered.com"


class SteamService:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def resolve_steam_id(self, steam_ref: str) -> str | None:
        steam_ref = steam_ref.strip()
        if steam_ref.isdigit():
            return steam_ref

        match = re.search(r"steamcommunity\.com/(?:profiles|id)/([^/?#]+)", steam_ref)
        if not match:
            return None

        value = match.group(1)
        if value.isdigit():
            return value

        params = {"key": self.api_key, "vanityurl": value}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{STEAM_API_BASE}/ISteamUser/ResolveVanityURL/v1/", params=params)
            response.raise_for_status()
            data = response.json().get("response", {})
            return data.get("steamid")

    async def get_owned_games(self, steam_id: str) -> list[dict]:
        params = {
            "key": self.api_key,
            "steamid": steam_id,
            "include_appinfo": 1,
            "include_played_free_games": 1,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{STEAM_API_BASE}/IPlayerService/GetOwnedGames/v1/", params=params)
            response.raise_for_status()
            return response.json().get("response", {}).get("games", [])

    async def get_player_achievements(self, steam_id: str, app_id: int) -> dict:
        params = {"key": self.api_key, "steamid": steam_id, "appid": app_id}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{STEAM_API_BASE}/ISteamUserStats/GetPlayerAchievements/v1/",
                params=params,
            )
            if response.status_code >= 400:
                return {}
            return response.json().get("playerstats", {})

    async def build_profile_snapshot(self, steam_id: str) -> dict:
        games = await self.get_owned_games(steam_id)
        most_played = sorted(games, key=lambda item: item.get("playtime_forever", 0), reverse=True)[:10]
        recently_played = sorted(games, key=lambda item: item.get("rtime_last_played", 0), reverse=True)[:10]
        return {
            "most_played_games": [game.get("name") for game in most_played if game.get("name")],
            "recently_played_games": [game.get("name") for game in recently_played if game.get("name")],
            "total_games": len(games),
        }

