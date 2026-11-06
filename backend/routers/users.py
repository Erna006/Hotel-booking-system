from uuid import UUID
import sqlalchemy as sa
from fastapi import APIRouter, HTTPException
from backend.models import Guests
from backend.routers.common import DB, User, Admin, Limit, Offset, page
from backend.schemas import Profile, ProfilePatch, AdminPatch, Page

router = APIRouter(prefix='/users', tags=['users'])


@router.get('/me', response_model=Profile)
async def me(user: User):
    return dict(user)


@router.patch('/me', response_model=Profile)
async def profile(body: ProfilePatch, user: User, db: DB):
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return dict(user)
    return dict(await db.fetch_one(Guests.update().where(Guests.c.id == user['id'])
        .values(**changes).returning(*Guests.c)))


@router.get('', response_model=Page[Profile])
async def users(db: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return await page(db, sa.select(Guests).order_by(Guests.c.created_at, Guests.c.id), limit, offset)


@router.patch('/{user_id}', response_model=Profile)
async def update_user(user_id: UUID, body: AdminPatch, db: DB, admin: Admin):
    async with db.transaction():
        # Serialize all role changes, including concurrent attempts to remove the last admin.
        await db.execute(sa.text('SELECT pg_advisory_xact_lock(724031)'))
        target = await db.fetch_one(sa.select(Guests).where(Guests.c.id == user_id).with_for_update())
        if not target:
            raise HTTPException(404, 'User not found')
        changes = body.model_dump(exclude_unset=True)
        if target['role'] == 'admin' and target['is_active'] and (
            changes.get('role', 'admin') != 'admin' or changes.get('is_active') is False
        ):
            count = await db.fetch_val(sa.select(sa.func.count()).select_from(Guests).where(
                Guests.c.role == 'admin', Guests.c.is_active.is_(True)))
            if count <= 1:
                raise HTTPException(409, 'Cannot remove the last active administrator')
        if not changes:
            return dict(target)
        return dict(await db.fetch_one(Guests.update().where(Guests.c.id == user_id)
            .values(**changes).returning(*Guests.c)))
