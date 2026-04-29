from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, UserPreference


async def get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id).options(selectinload(User.preference))
    )
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(telegram_id=telegram_id)
    user.preference = UserPreference()
    session.add(user)
    await session.commit()
    await session.refresh(user, ["preference"])
    return user


async def list_active_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).options(selectinload(User.preference)))
    return list(result.scalars().all())

