"""End-to-end API tests against a dedicated, migrated PostgreSQL database."""
import asyncio
import os
from uuid import uuid4
import databases
import httpx
import pytest
import pytest_asyncio
import sqlalchemy as sa
from backend.core.db import get_session
from backend.main import app
from backend.models import Guests, Rooms, Bookings, Payments, RefreshTokens
from backend.middlewares.tokens import create_access_token, hash_password, hash_refresh_token
from datetime import datetime, timedelta, timezone


@pytest_asyncio.fixture
async def api_env():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL not set')
    async with databases.Database(url) as db:
        ids = {role: uuid4() for role in ['admin', 'guest', 'other', 'receptionist']}
        room_id = uuid4()
        encoded = hash_password('api-test-password')
        for role, uid in ids.items():
            await db.execute(Guests.insert().values(id=uid, email=f'{uid}@example.com',
                full_name='API Test', password_hash=encoded, role='guest' if role == 'other' else role))
        await db.execute(Rooms.insert().values(id=room_id, number=str(room_id)[:20],
            room_type='test', capacity=2, price_per_night='15000.00'))
        app.dependency_overrides[get_session] = lambda: db
        headers = {role: {'Authorization': f'Bearer {create_access_token(uid)}'} for role, uid in ids.items()}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            try:
                yield client, db, ids, headers, room_id
            finally:
                app.dependency_overrides.clear()
                bids = sa.select(Bookings.c.id).where(Bookings.c.guest_id.in_(list(ids.values())))
                await db.execute(Payments.delete().where(Payments.c.booking_id.in_(bids)))
                await db.execute(Bookings.delete().where(Bookings.c.guest_id.in_(list(ids.values()))))
                await db.execute(Rooms.delete().where(Rooms.c.id == room_id))
                await db.execute(RefreshTokens.delete().where(RefreshTokens.c.guest_id.in_(list(ids.values()))))
                await db.execute(Guests.delete().where(Guests.c.id.in_(list(ids.values()))))


async def reserve(client, headers, room, start='2030-06-01', end='2030-06-03'):
    return await client.post('/api/v1/bookings', headers=headers, json={
        'room_id': str(room), 'check_in': start, 'check_out': end})


async def test_booking_payment_lifecycle_and_ownership(api_env):
    client, db, ids, headers, room = api_env
    response = await reserve(client, headers['guest'], room)
    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking['total_amount'] == '30000.00'
    bid = booking['id']
    assert (await client.get(f'/api/v1/bookings/{bid}', headers=headers['other'])).status_code == 404
    assert (await client.get('/api/v1/bookings', headers=headers['other'])).json()['total'] == 0
    assert (await reserve(client, headers['other'], room)).status_code == 409
    query = f'/api/v1/rooms/available?check_in=2030-06-01&check_out=2030-06-03&room_type=test'
    assert str(room) not in [r['id'] for r in (await client.get(query)).json()['items']]
    path = f'/api/v1/bookings/{bid}/payments'
    assert (await client.post(path, headers=headers['receptionist'], json={'outcome':'succeeded'})).status_code == 422
    assert (await client.post(path, headers={**headers['receptionist'], 'Idempotency-Key': str(uuid4())}, json={'outcome':'succeeded'})).status_code == 404
    failed_headers = {**headers['guest'], 'Idempotency-Key': str(uuid4())}
    failed = await client.post(path, headers=failed_headers, json={'outcome':'failed'})
    assert failed.status_code == 200, failed.text
    assert failed.json()['booking_status'] == 'pending'
    again = await client.post(path, headers=failed_headers, json={'outcome':'failed'})
    assert again.json() == failed.json()
    assert (await client.post(path, headers=failed_headers, json={'outcome':'succeeded'})).status_code == 409
    paid_headers = {**headers['guest'], 'Idempotency-Key': str(uuid4())}
    results = await asyncio.gather(*[client.post(path, headers=paid_headers, json={'outcome':'succeeded'}) for _ in range(2)])
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert results[0].json() == results[1].json()
    assert results[0].json()['booking_status'] == 'confirmed'
    assert (await client.post(path, headers={**headers['guest'], 'Idempotency-Key': str(uuid4())}, json={'outcome':'succeeded'})).status_code == 409
    assert (await client.get(path, headers=headers['guest'])).json()['total'] == 2
    for _ in range(2):
        assert (await client.post(f'/api/v1/bookings/{bid}/cancel', headers=headers['guest'])).json()['status'] == 'cancelled'
    response = await reserve(client, headers['other'], room)
    assert response.status_code == 201, response.text


async def test_concurrent_booking_and_room_access(api_env):
    client, db, ids, headers, room = api_env
    results = await asyncio.gather(reserve(client, headers['guest'], room), reserve(client, headers['other'], room))
    assert sorted(r.status_code for r in results) == [201,409]
    assert (await client.patch(f'/api/v1/rooms/{room}', headers=headers['guest'], json={'is_active':False})).status_code == 403
    assert (await client.patch(f'/api/v1/rooms/{room}', headers=headers['admin'], json={'is_active':False})).status_code == 200
    assert (await client.get(f'/api/v1/rooms/{room}')).status_code == 404
    assert (await client.get('/api/v1/rooms?include_inactive=true')).status_code == 401
    assert (await client.get('/api/v1/rooms?include_inactive=true', headers=headers['guest'])).status_code == 403
    all_rooms = (await client.get('/api/v1/rooms?include_inactive=true&limit=100', headers=headers['admin'])).json()
    assert str(room) in [r['id'] for r in all_rooms['items']]
    assert (await reserve(client, headers['guest'], room, '2030-07-01','2030-07-02')).status_code == 404


async def test_auth_and_admin_protection(api_env):
    client, db, ids, headers, room = api_env
    uid = uuid4()
    email = f'{uid}@example.com'
    try:
        body = dict(email=f' {email.upper()} ', password='api-test-password', full_name='New User')
        result = await client.post('/api/v1/auth/register', json=body)
        assert result.status_code == 201, result.text
        assert result.json()['email'] == email
        assert 'password_hash' not in result.json()
        assert result.json()['role'] == 'guest'
        assert (await client.post('/api/v1/auth/register', json=body)).status_code == 409
        assert (await client.post('/api/v1/auth/register', json={**body,'role':'admin'})).status_code == 422
        login = await client.post('/api/v1/auth/login', json={'email':email,'password':body['password']})
        assert login.status_code == 200, login.text
        h = {'Authorization': f"Bearer {login.json()['access_token']}"}
        assert (await client.patch('/api/v1/users/me', headers=h, json={'role':'admin'})).status_code == 422
        assert (await client.get('/api/v1/users', headers=h)).status_code == 403
        await db.execute(Guests.update().where(Guests.c.email == email).values(is_active=False))
        assert (await client.get('/api/v1/users/me', headers=h)).status_code == 401
        assert (await client.post('/api/v1/auth/login', json={'email':email,'password':body['password']})).status_code == 401
        result = await client.patch(f"/api/v1/users/{ids['admin']}", headers=headers['admin'], json={'role':'guest'})
        assert result.status_code == 409, result.text
        result = await client.patch(f"/api/v1/users/{ids['other']}", headers=headers['admin'], json={'role':'admin'})
        assert result.status_code == 200, result.text
        assert (await client.get('/api/v1/users', headers=headers['other'])).status_code == 200
    finally:
        await db.execute(RefreshTokens.delete().where(RefreshTokens.c.guest_id.in_(
            sa.select(Guests.c.id).where(Guests.c.email == email))))
        await db.execute(Guests.delete().where(Guests.c.email == email))


async def test_payment_cancel_race(api_env):
    client, db, ids, headers, room = api_env
    booking = (await reserve(client, headers['guest'], room)).json()
    path = f"/api/v1/bookings/{booking['id']}"
    pay, cancel = await asyncio.gather(
        client.post(path+'/payments', headers={**headers['guest'],'Idempotency-Key':str(uuid4())},json={'outcome':'succeeded'}),
        client.post(path+'/cancel', headers=headers['guest']))
    assert cancel.status_code == 200
    assert pay.status_code in (200,409)
    assert (await client.get(path,headers=headers['guest'])).json()['status'] == 'cancelled'

async def login_as(client, uid):
    response = await client.post('/api/v1/auth/login', json={
        'email': f'{uid}@example.com', 'password': 'api-test-password'})
    assert response.status_code == 200, response.text
    return response.json()


def refresh(client, token):
    return client.post('/api/v1/auth/refresh', json={'refresh_token': token})


async def test_refresh_rotation_and_reuse_detection(api_env):
    client, db, ids, headers, room = api_env
    first = await login_as(client, ids['guest'])
    stored = await db.fetch_all(sa.select(RefreshTokens.c.token_hash)
                                .where(RefreshTokens.c.guest_id == ids['guest']))
    assert [r['token_hash'] for r in stored] == [hash_refresh_token(first['refresh_token'])]
    assert first['refresh_token'] != stored[0]['token_hash']

    rotated = await refresh(client, first['refresh_token'])
    assert rotated.status_code == 200, rotated.text
    second = rotated.json()
    assert second['refresh_token'] != first['refresh_token']
    me = await client.get('/api/v1/users/me', headers={'Authorization': f"Bearer {second['access_token']}"})
    assert me.status_code == 200

    # Replaying the rotated token is treated as theft: the whole family is revoked.
    assert (await refresh(client, first['refresh_token'])).status_code == 401
    assert (await refresh(client, second['refresh_token'])).status_code == 401
    active = await db.fetch_val(sa.select(sa.func.count()).select_from(RefreshTokens).where(
        RefreshTokens.c.guest_id == ids['guest'], RefreshTokens.c.revoked_at.is_(None)))
    assert active == 0


async def test_refresh_rejects_unknown_and_malformed(api_env):
    client, *_ = api_env
    assert (await refresh(client, 'x' * 64)).status_code == 401
    assert (await refresh(client, 'short')).status_code == 422
    assert (await client.post('/api/v1/auth/refresh', json={})).status_code == 422


async def test_refresh_expired_token(api_env):
    client, db, ids, headers, room = api_env
    token = (await login_as(client, ids['guest']))['refresh_token']
    await db.execute(RefreshTokens.update().where(RefreshTokens.c.guest_id == ids['guest'])
                     .values(expires_at=datetime.now(timezone.utc) - timedelta(days=1)))
    assert (await refresh(client, token)).status_code == 401


async def test_refresh_disabled_account(api_env):
    client, db, ids, headers, room = api_env
    token = (await login_as(client, ids['other']))['refresh_token']
    await db.execute(Guests.update().where(Guests.c.id == ids['other']).values(is_active=False))
    assert (await refresh(client, token)).status_code == 401
    unused = await db.fetch_val(sa.select(sa.func.count()).select_from(RefreshTokens).where(
        RefreshTokens.c.guest_id == ids['other'], RefreshTokens.c.revoked_at.is_(None)))
    assert unused == 1  # no rotation happened for a disabled account


async def test_logout_revokes_refresh_token(api_env):
    client, db, ids, headers, room = api_env
    token = (await login_as(client, ids['guest']))['refresh_token']
    assert (await client.post('/api/v1/auth/logout', json={'refresh_token': token})).status_code == 204
    assert (await client.post('/api/v1/auth/logout', json={'refresh_token': token})).status_code == 204
    assert (await client.post('/api/v1/auth/logout', json={'refresh_token': 'x' * 64})).status_code == 204
    assert (await refresh(client, token)).status_code == 401


async def test_concurrent_refresh_allows_single_winner(api_env):
    client, db, ids, headers, room = api_env
    token = (await login_as(client, ids['guest']))['refresh_token']
    results = await asyncio.gather(refresh(client, token), refresh(client, token))
    assert sorted(r.status_code for r in results) == [200, 401]