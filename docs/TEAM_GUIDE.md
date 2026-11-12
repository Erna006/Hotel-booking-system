# Общий контракт и инструкции команде

## Что готово у Person 1

`backend/core`, `backend/models`, `backend/middlewares`: настройки, databases, четыре таблицы, роли, JWT и Argon2,
общие ошибки, журнал запросов, health endpoints, общий запрос пересечений.
`backend/migrations`: начальная миграция, включая расширение btree_gist.
Функциональные endpoints ниже реализованы в routers. Инструкции сохранены как контракт
модулей и исходное распределение задач; оно не обозначает авторство коммитов.

Архитектура: async router → бизнес-логика → databases → PostgreSQL.
Маршруты создавайте в `backend/routers/auth.py`, `users.py`, `rooms.py`, `bookings.py`, `payments.py`.
Pydantic schemas можно хранить в отдельной папке `backend/schemas`, бизнес-логику — в `backend/services`,
когда она перестанет помещаться в простой обработчик.
Подключайте router в `backend/main.py` через `app.include_router(router, prefix="/api/v1")`.
Используйте `async def`, `await session.fetch_one/fetch_all/fetch_val/execute`.
Сессию получайте через `Depends(get_session)` из `backend.core.db`.
Все таблицы используют единую `db.metadata`; ORM, Base и SQLAlchemy Session не используются.
Не создавайте второй пул или собственные определения enum.

## Схема и инварианты

- UUID у всех PK, FK с RESTRICT: историю не удаляем каскадом.
- `Guests`/`guests` — аккаунт **любой роли**, включая сотрудников; отдельной User нет.
  Поля: id, email (trim/lower, unique), password_hash, full_name, role, is_active, created_at.
- `Rooms`: id, number (unique), room_type, capacity > 0, price_per_night > 0,
  currency (по умолчанию KZT), is_active. Тип номера — строка, например standard/deluxe/suite.
- `Bookings`: id, guest_id, room_id, check_in, check_out, status, total_amount, currency, created_at.
  total_amount — фиксируется сервером при создании, изменение цены Room не меняет историю.
- `Payments`: id, booking_id, idempotency_key (UUID, globally unique), amount, currency,
  status, failure_reason, created_at. Строка на каждую новую попытку; повтор ключа возвращает прежний результат.
- Даты — ISO `YYYY-MM-DD`, интервал `[check_in, check_out)`, минимум одна ночь.
  Person 4 запрещает заезд в прошлом по дате отеля (Asia/Qyzylorda).
- Пересечение: existing.check_in < requested.check_out AND existing.check_out > requested.check_in.
  `pending` и `confirmed` блокируют номер; `cancelled` освобождает. Соседние даты допустимы.
  Используйте `backend.models.availability.overlapping_bookings` для общего условия.
- Ограничение `excl_booking_room_dates` защищает от гонок даже между одновременными транзакциями.
  SQLSTATE 23P01 превращается в HTTP 409 `room_unavailable`.
- Деньги: Decimal/Numeric(12,2), в JSON строки `"25000.00"`, никогда float.
  Стоимость = цена за ночь × (check_out - check_in).days, только на сервере.
- Время created_at — UTC с часовым поясом; пароли, хеши и JWT не логировать.
- pending → confirmed только после успешной тестовой оплаты; pending → cancelled;
  confirmed → cancelled разрешено (реальных списаний и возвратов в учебном проекте нет).
  cancelled — конечный статус. Провал платежа оставляет pending.
  Автоматического срока истечения pending пока нет: бронь блокирует номер до отмены/оплаты.

## Доступ

Роли в API и БД: `guest`, `receptionist`, `admin`.
Используйте `get_current_user`, `require_roles`, `require_booking_access` из `backend.middlewares.auth`.
JWT хранит sub=UUID; роль и is_active всегда читаются из БД, поэтому блокировка действует сразу.
Гость работает только со своими бронями и платежами. Для чужого объекта возвращаем 404.
Сотрудники видят и отменяют любые брони; только admin меняет номера и пользователей.
Тестовую оплату вызывает владелец брони; сотрудник не платит за другого гостя.
У списковых запросов обязательно фильтруйте guest_id для гостя: проверка одного объекта этого не заменяет.

## Person 2 — Auth & Users

1. Используйте существующую таблицу Guests и функции `hash_password`, `verify_password`, `create_access_token`
   из `backend.middlewares.tokens`.
2. Создайте отдельные Pydantic request/response schemas, response никогда не включает password_hash.
3. Регистрация принимает только email/password/full_name, нормализует email, проверяет формат,
   пароль минимум 8 символов, максимум 128. Назначает исключительно guest, не принимает role/is_active.
4. Login: единая ошибка 401 для неверного email/пароля и неактивного аккаунта.
5. Профиль: PATCH позволяет только full_name/email; изменение роли — отдельный admin endpoint.
6. Не допускайте отключения/понижения последнего активного admin. Первого admin создайте отдельной
   локальной CLI-командой с вводом пароля через getpass (не публичным endpoint, не фиксированным паролем).
7. Добавьте тесты регистрации, дубля email, истёкшего JWT, отключённого аккаунта и повышения прав.

| Метод и путь /api/v1 | Доступ / данные |
| --- | --- |
| POST /auth/register | public: email, password, full_name → 201 профиль |
| POST /auth/login | public: JSON email, password → access_token, token_type=bearer |
| GET /users/me | авторизованный → профиль |
| PATCH /users/me | авторизованный: full_name/email |
| GET /users | admin, пагинация |
| PATCH /users/{id} | admin: role/is_active |

## Person 3 — Rooms

1. Добавьте CRUD и Pydantic schemas для существующей таблицы Rooms; отключение через is_active=false.
2. Каталог гостям показывает только активные номера; admin может запросить include_inactive=true.
3. Поиск проверяет даты и вместимость, исключает пересечения общим условием availability.
4. Цена поиска — предварительная; бронь повторно проверяет активность и фиксирует стоимость.
5. PATCH номера и создание брони должны брать блокировку строки Room через SELECT FOR UPDATE,
   чтобы отключение/изменение цены не расходились с созданием брони.
6. Проверяйте соседние интервалы, pending/confirmed/cancelled, фильтры и права.

| Метод и путь /api/v1 | Доступ / данные |
| --- | --- |
| GET /rooms | public: min_price, max_price, room_type, capacity, limit, offset |
| GET /rooms/available | public: check_in, check_out, capacity + фильтры → номера с total_amount |
| GET /rooms/{id} | public → номер |
| POST /rooms | admin: number, room_type, capacity, price_per_night, currency → 201 |
| PATCH /rooms/{id} | admin: изменяемые поля, включая is_active |

Статический `/rooms/available` объявите раньше `/rooms/{id}`.

## Person 4 — Bookings & Payments

1. guest_id берите из get_current_user, room_id и даты — из запроса; стоимость/статус не доверяйте клиенту.
2. В транзакции заблокируйте Room, проверьте is_active, даты и доступность; создайте pending,
   рассчитайте сумму. Успешный предварительный поиск не гарантирует создание брони.
3. БД окончательно разрешает конкуренцию. Весь блок записи помещайте в `async with session.transaction():`.
   Исключение asyncpg должно выйти из блока: это выполнит rollback до HTTP-обработчика.
   Общий handler выдаёт 409; соединение возвращается в пул. Не вызывайте session.commit()/rollback():
   это API SQLAlchemy ORM, здесь его нет.
4. На оплату и отмену блокируйте Booking через SELECT FOR UPDATE. После блокировки повторно
   проверьте владельца и статус. Платить cancelled/confirmed повторно новым ключом нельзя (409).
5. Заголовок Idempotency-Key — обязательный UUID. Существующий ключ сначала проверяйте на
   владельца, booking_id и совпадение параметров; чужой результат не раскрывайте.
6. Тестовая оплата принимает outcome=succeeded/failed (явная учебная симуляция, без реквизитов карт).
   amount/currency берите из Booking. Новая попытка → Payment; при успехе Booking → confirmed.
   Оба изменения фиксируйте одной транзакцией. При failed сохраняйте попытку и оставляйте pending.
7. Уникальный частичный индекс разрешает только один succeeded для брони; конкурентный дубль
   idempotency_key обработайте выходом из транзакции с rollback и повторным чтением с проверкой доступа.
8. Отмена confirmed оставляет исторический succeeded Payment; возврат средств не моделируется.
9. Тестируйте два одновременных бронирования, отмену против оплаты, повтор ключа и доступ к чужим данным.

| Метод и путь /api/v1 | Доступ / данные |
| --- | --- |
| POST /bookings | авторизованный: room_id, check_in, check_out, необязательный guest_count → 201 бронь текущего пользователя |
| GET /bookings | свои для guest, все для staff; limit, offset; данные номера и guest_count (null для старых броней) |
| GET /bookings/{id} | владелец или staff |
| POST /bookings/{id}/cancel | владелец или staff; повтор отмены возвращает cancelled |
| POST /bookings/{id}/payments | владелец: outcome + Idempotency-Key → Payment и booking_status |
| GET /bookings/{id}/payments | владелец или staff → история попыток |

## Person 5 — React

1. Создайте Vite React приложение в `frontend/`, API base URL через VITE_API_BASE_URL.
2. Реализуйте страницы из задания и единый API client, Bearer заголовок, обработку 401/403/409/422.
3. Токен хранится в `sessionStorage` для восстановления сессии в той же вкладке. Права проверяет backend.
4. Передавайте даты без конвертации через UTC; деньги отображайте как сумму с валютой.
5. В поиске и оплате показывайте loading и ошибки. При 409 предложите обновить поиск.
6. На одну попытку оплаты создавайте crypto.randomUUID(); сетевой retry использует тот же ключ.
   Кнопка новой попытки после failed создаёт новый ключ.
7. Показывайте учебный характер оплаты; никаких полей настоящей карты.
8. Проверяйте сценарий регистрация → поиск → бронь → failed → повтор succeeded → история → отмена,
   гостя/сотрудника/admin и мобильный экран.

## Формат API и порядок интеграции

Единый префикс `/api/v1`; UUID — строки; даты — ISO; role/status — lowercase.
Списки: `{"items": [...], "total": 10, "limit": 20, "offset": 0}`, limit 1..100, offset >= 0.
Ошибка: `{"error":{"code":"room_unavailable","message":"..."},"request_id":"..."}`.
Для обычных HTTP ошибок код `http_401`/`http_403`/`http_404`/`http_409`; валидация — `validation_error`.
Ошибку надо распознавать по status/code; message предназначен для человека.

Сначала команда принимает этот контракт. Затем Person 2–4 подключают routers независимо,
Person 5 строит страницы по тем же schemas и сверяет итоговый `/openapi.json`.
Каждый меняет миграции только новой revision и согласует изменения общей схемы с Person 1.
До объединения: миграция чистой PostgreSQL, тесты каждого модуля, общий пользовательский сценарий,
проверка 409 на конкурентное бронирование и отказа в доступе к чужой брони.

## Пример работы с новой структурой

```python
from typing import Annotated
from uuid import UUID

import databases
import sqlalchemy
from fastapi import APIRouter, Depends, HTTPException

from backend.core.db import get_session
from backend.models import Rooms

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("/{room_id}")
async def get_room(
    room_id: UUID,
    session: Annotated[databases.Database, Depends(get_session)],
):
    query = sqlalchemy.select(Rooms).where(
        Rooms.c.id == room_id,
        Rooms.c.is_active.is_(True),
    )
    room = await session.fetch_one(query)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return dict(room)
```

Для публичного ответа используйте response_model: аккаунт из auth содержит password_hash,
возвращать его целиком клиенту нельзя. Строки читаются через `row["id"]`, колонки — через `Rooms.c.id`.

```python
async with session.transaction():
    query = sqlalchemy.select(Rooms).where(Rooms.c.id == room_id).with_for_update()
    room = await session.fetch_one(query)
    # Проверить room, is_active и даты, затем выполнить insert/update через await.
```

`fetch_val(Table.insert().values(...).returning(Table.c.id))` возвращает созданный UUID.
UUID, даты создания, role/status/currency/is_active имеют server_default там, где предусмотрено схемой.
Python-side default в моделях не используем: databases не выполняет их как ORM.
Для транзакции выполняйте запросы последовательно в одной asyncio task: соединение привязано к задаче.
Не отправляйте части одной оплаты через asyncio.gather.

При гонке прямых INSERT PostgreSQL может вернуть 23P01 (пересечение) или 40P01 (deadlock).
Двойная бронь в обоих случаях не сохраняется. Deadlock/serialization error отображается в
HTTP 409 `transaction_conflict`; повторите всю операцию после rollback. Блокировка Room в штатном
сервисе создания брони сериализует конкурирующие запросы одного номера.

Жизненный цикл пула и транзакции: [документация databases](https://www.encode.io/databases/connections_and_transactions/).
