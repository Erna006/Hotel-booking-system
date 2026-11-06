"""Run locally: python -m backend.create_admin. No password in command arguments."""
import asyncio
from getpass import getpass
import sqlalchemy as sa
from backend.core.db import connect, disconnect, get_session
from backend.models import Guests
from backend.middlewares.tokens import hash_password
from backend.schemas import Register


async def create(data):
    await connect()
    try:
        db = get_session()
        async with db.transaction():
            await db.execute(sa.text('SELECT pg_advisory_xact_lock(724031)'))
            await db.execute(Guests.insert().values(email=data.email, full_name=data.full_name,
                password_hash=hash_password(data.password), role='admin'))
    finally:
        await disconnect()


if __name__ == '__main__':
    email = input('Email: ')
    name = input('Full name: ')
    password = getpass('Password (12–128 characters): ')
    if password != getpass('Confirm password: '):
        raise SystemExit('Passwords do not match')
    data = Register(email=email, full_name=name, password=password)
    asyncio.run(create(data))
    print('Administrator created')
