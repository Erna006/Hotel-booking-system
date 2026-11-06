import sqlalchemy as sa
from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
from backend.models import Guests
from backend.middlewares.tokens import hash_password, verify_password, create_access_token
from backend.routers.common import DB
from backend.schemas import Register, Login, Profile, Token

router = APIRouter(prefix='/auth', tags=['auth'])
# A real hash keeps unknown-account password checks on the same expensive path.
DUMMY_HASH = hash_password('unusable-dummy-login-password')


@router.post('/register', status_code=201, response_model=Profile)
async def register(body: Register, db: DB):
    encoded = await run_in_threadpool(hash_password, body.password)
    return dict(await db.fetch_one(Guests.insert().values(
        email=body.email, full_name=body.full_name, password_hash=encoded,
        role='guest').returning(*Guests.c)))


@router.post('/login', response_model=Token)
async def login(body: Login, db: DB):
    user = await db.fetch_one(sa.select(Guests).where(Guests.c.email == body.email))
    valid = await run_in_threadpool(verify_password, body.password, user['password_hash'] if user else DUMMY_HASH)
    if not user or not valid or not user['is_active']:
        raise HTTPException(401, 'Invalid credentials', headers={'WWW-Authenticate': 'Bearer'})
    return Token(access_token=create_access_token(user['id']))
