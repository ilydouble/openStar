from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_name(self, user_name: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.user_name == user_name)
        )
        return result.scalar_one_or_none()

    async def create(self, user_name: str, password_hash: str) -> User:
        user = User(user_name=user_name, password_hash=password_hash)
        self._session.add(user)
        await self._session.flush()
        return user
