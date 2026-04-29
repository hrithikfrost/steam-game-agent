from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback
from app.models.game import Game
from app.models.user import User


POSITIVE_TYPES = {"like", "play"}
NEGATIVE_TYPES = {"dislike"}


async def store_feedback(session: AsyncSession, user: User, game: Game, feedback_type: str) -> None:
    session.add(Feedback(user_id=user.id, game_id=game.id, type=feedback_type))

    preference = user.preference
    preferred_tags = dict(preference.preferred_tags or {})
    disliked_tags = set(preference.disliked_tags or [])

    if feedback_type in POSITIVE_TYPES:
        for tag in (game.tags or []) + (game.genres or []):
            preferred_tags[tag] = float(preferred_tags.get(tag, 0)) + 0.5
            disliked_tags.discard(tag)
    elif feedback_type in NEGATIVE_TYPES:
        for tag in (game.tags or [])[:5]:
            preferred_tags[tag] = max(float(preferred_tags.get(tag, 0)) - 0.5, 0)
            disliked_tags.add(tag)

    preference.preferred_tags = preferred_tags
    preference.disliked_tags = sorted(disliked_tags)
    await session.commit()

