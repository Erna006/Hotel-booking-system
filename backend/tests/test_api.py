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
from backend.models import Guests, Rooms, Bookings, Payments
from backend.middlewares.tokens import create_access_token, hash_password


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
                await db.execute(Guests.delete().where(Guests.c.id.in_(list(ids.values()))))


async def reserve(client, headers, room, start='2030-06-01', end='2030-06-03', **fields):
    return await client.post('/api/v1/bookings', headers=headers, json={
        'room_id': str(room), 'check_in': start, 'check_out': end, **fields})


async def test_availability_for_selected_room(api_env):
    client, _, _, headers, room = api_env
    query = {'check_in': '2030-06-01', 'check_out': '2030-06-03', 'room_id': str(room)}
    path = '/api/v1/rooms/available'

    result = (await client.get(path, params=query)).json()
    assert result['total'] == 1
    assert result['items'][0]['id'] == str(room)
    assert result['items'][0]['total_amount'] == '30000.00'
    prices = '/api/v1/rooms/available/prices'
    assert (await client.get(prices, params=query)).json() == [
        {'currency': 'KZT', 'total_amount': '30000.00'},
    ]
    assert (await client.get(path, params={**query, 'room_id': str(uuid4())})).json()['total'] == 0
    assert (await client.get(path, params={**query, 'capacity': 3})).json()['total'] == 0

    legacy = await reserve(client, headers['guest'], room)
    assert legacy.status_code == 201
    assert legacy.json()['guest_count'] is None
    assert (await client.get(path, params=query)).json()['total'] == 0
    assert (await client.get(prices, params=query)).json() == []


async def test_booking_payment_lifecycle_and_ownership(api_env):
    client, db, ids, headers, room = api_env
    assert (await reserve(client, headers['guest'], room, guest_count=3)).status_code == 422
    response = await reserve(client, headers['guest'], room, guest_count=2)
    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking['total_amount'] == '30000.00'
    summary = (await client.get('/api/v1/bookings', headers=headers['guest'])).json()['items'][0]
    assert summary['guest_count'] == 2
    assert summary['room_number'] == str(room)[:20]
    assert summary['room_type'] == 'test'
    assert summary['room_capacity'] == 2
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
        body = dict(email=f' {email.upper()} ', password='Test1234', full_name='New User')
        assert (await client.post('/api/v1/auth/register', json={**body, 'password': 'Test123'})).status_code == 422
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


# ---------------------------------------------------------------------------
# Новые тесты: Users / Rooms (email_taken, room_number_taken, фильтры, самозащита)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def extra(api_env):
    """Удаляет пользователей и комнаты, созданные внутри тестов."""
    _, db, *_ = api_env
    created = {'emails': [], 'rooms': []}
    yield created
    await db.execute(Guests.delete().where(Guests.c.email.in_(created['emails'])))
    await db.execute(Rooms.delete().where(Rooms.c.number.in_(created['rooms'])))


async def register_user(client, email, extra):
    extra['emails'].append(email.strip().lower())
    return await client.post('/api/v1/auth/register', json={
        'email': email, 'password': 'api-test-password', 'full_name': 'Test User'})


async def create_room(client, headers, number, extra):
    extra['rooms'].append(number)
    return await client.post('/api/v1/rooms', headers=headers, json={
        'number': number, 'room_type': 'test', 'capacity': 2, 'price_per_night': '10000.00'})


# 1
async def test_register_duplicate_email(api_env, extra):
    client, *_ = api_env
    email = f'{uuid4()}@example.com'
    assert (await register_user(client, email, extra)).status_code == 201
    response = await register_user(client, email, extra)
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'email_taken'


# 2
async def test_register_duplicate_email_other_case(api_env, extra):
    client, *_ = api_env
    email = f'{uuid4()}@example.com'
    assert (await register_user(client, email, extra)).status_code == 201
    response = await register_user(client, email.upper(), extra)
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'email_taken'


# 3
async def test_profile_email_taken(api_env):
    client, db, ids, headers, room = api_env
    response = await client.patch('/api/v1/users/me', headers=headers['guest'],
                                  json={'email': f"{ids['other']}@example.com"})
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'email_taken'


# 4
async def test_profile_same_email_ok(api_env):
    client, db, ids, headers, room = api_env
    response = await client.patch('/api/v1/users/me', headers=headers['guest'],
                                  json={'email': f"{ids['guest']}@example.com"})
    assert response.status_code == 200, response.text


# 5
async def test_create_room_duplicate_number(api_env, extra):
    client, db, ids, headers, room = api_env
    response = await create_room(client, headers['admin'], str(room)[:20], extra)
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'room_number_taken'


# 6
async def test_patch_room_duplicate_number(api_env, extra):
    client, db, ids, headers, room = api_env
    number = f'T{uuid4().hex[:10]}'
    created = await create_room(client, headers['admin'], number, extra)
    assert created.status_code == 201, created.text
    response = await client.patch(f"/api/v1/rooms/{created.json()['id']}",
                                  headers=headers['admin'], json={'number': str(room)[:20]})
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'room_number_taken'


# 7
async def test_users_filter_by_role(api_env):
    client, db, ids, headers, room = api_env
    uid = ids['receptionist']
    found = await client.get(f'/api/v1/users?role=receptionist&search={uid}', headers=headers['admin'])
    assert found.json()['total'] == 1
    assert found.json()['items'][0]['role'] == 'receptionist'
    missing = await client.get(f'/api/v1/users?role=guest&search={uid}', headers=headers['admin'])
    assert missing.json()['total'] == 0


# 8
async def test_users_filter_by_active(api_env):
    client, db, ids, headers, room = api_env
    await db.execute(Guests.update().where(Guests.c.id == ids['other']).values(is_active=False))
    inactive = await client.get(f"/api/v1/users?is_active=false&search={ids['other']}", headers=headers['admin'])
    assert inactive.json()['total'] == 1
    active = await client.get(f"/api/v1/users?is_active=true&search={ids['other']}", headers=headers['admin'])
    assert active.json()['total'] == 0


# 9
async def test_users_search_case_insensitive(api_env):
    client, db, ids, headers, room = api_env
    response = await client.get(f"/api/v1/users?search={str(ids['guest']).upper()}", headers=headers['admin'])
    assert response.json()['total'] == 1
    assert response.json()['items'][0]['email'] == f"{ids['guest']}@example.com"


# 10
async def test_users_filters_with_pagination(api_env):
    client, db, ids, headers, room = api_env
    tag = f'tag-{uuid4().hex}'
    await db.execute(Guests.update().where(Guests.c.id.in_(list(ids.values()))).values(full_name=tag))
    first = (await client.get(f'/api/v1/users?search={tag}&limit=2&offset=0', headers=headers['admin'])).json()
    second = (await client.get(f'/api/v1/users?search={tag}&limit=2&offset=2', headers=headers['admin'])).json()
    empty = (await client.get(f'/api/v1/users?search={tag}&limit=2&offset=4', headers=headers['admin'])).json()
    assert first['total'] == 4 and len(first['items']) == 2
    assert first['limit'] == 2 and first['offset'] == 0
    assert len(second['items']) == 2
    assert empty['items'] == []
    assert {u['id'] for u in first['items']} | {u['id'] for u in second['items']} == {str(i) for i in ids.values()}


# 11
async def test_users_list_requires_admin(api_env):
    client, db, ids, headers, room = api_env
    assert (await client.get('/api/v1/users')).status_code == 401
    assert (await client.get('/api/v1/users', headers=headers['guest'])).status_code == 403
    assert (await client.get('/api/v1/users', headers=headers['receptionist'])).status_code == 403


# 12
async def test_admin_cannot_change_self(api_env):
    client, db, ids, headers, room = api_env
    path = f"/api/v1/users/{ids['admin']}"
    for body in ({'role': 'guest'}, {'role': 'receptionist'}, {'is_active': False}):
        response = await client.patch(path, headers=headers['admin'], json=body)
        assert response.status_code == 409, body
        assert response.json()['error']['code'] == 'self_change_forbidden'
    assert (await client.patch(path, headers=headers['admin'], json={'role': 'admin'})).status_code == 200
