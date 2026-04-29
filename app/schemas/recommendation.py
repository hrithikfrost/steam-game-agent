from pydantic import BaseModel


class GameRecommendation(BaseModel):
    game_id: int
    name: str
    description: str
    cover_image: str | None
    rating: float | None
    pros: list[str]
    cons: list[str]
    score: float
    steam_url: str | None = None

