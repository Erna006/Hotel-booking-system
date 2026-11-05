# Hotel Booking System

FastAPI + PostgreSQL + SQLAlchemy Core + databases (asyncpg).
Готова основа Person 1. Задачи Person 2–5 описаны в [инструкции](docs/TEAM_GUIDE.md).

## Структура

```text
backend/
  __init__.py
  main.py               # приложение, startup/shutdown
  core/
    config.py           # conf, переменные окружения
    db.py               # metadata, connect/get_session/disconnect
    errors.py           # общие обработчики ошибок
  middlewares/
    tokens.py           # JWT, хеширование паролей
    auth.py             # текущий пользователь, роли, владелец брони
    request_logging.py  # журнал запросов
  migrations/           # Alembic
  models/               # sqlalchemy.Table и общие запросы
  routers/              # endpoints
  tests/
```

Все команды ниже выполняются **из корня проекта**. Требуются Python 3.11+
и запущенный Docker Desktop с Linux containers.

## Установка и запуск

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Вставьте полученную строку в JWT_SECRET файла .env. Шаблонный секрет отвергается.
При обновлении существующего проекта сохраните секрет и замените DATABASE_URL на POSTGRES_URL,
а схему URL — на `postgresql+asyncpg://`.

```powershell
docker compose up -d db
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Swagger: http://localhost:8000/docs. Health: `/health/live`, `/health/ready`.
PostgreSQL опубликован на `127.0.0.1:15432`. Пароль compose предназначен для локальной разработки.
Подключение открывается в lifespan приложения и закрывается при остановке.
Без подключения get_session() выдаёт RuntimeError. Внутри приложения все запросы асинхронные.
Alembic использует синхронный psycopg с теми же реквизитами.

Миграция 0001 создаёт схему и btree_gist (нужны права CREATE EXTENSION).
Миграция 0002 добавляет генерацию UUID на стороне PostgreSQL, не меняя существующие строки.
Уже применённые миграции не переписываются. create_all при запуске не используется.

## Тесты

Без отдельной тестовой БД выполняются unit-тесты, интеграционные пропускаются:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Для интеграционных тестов создайте отдельную БД (createdb — однократно):

```powershell
docker compose exec -T db createdb -U hotel hotel_test
$env:POSTGRES_URL = 'postgresql+asyncpg://hotel:hotel@127.0.0.1:15432/hotel_test'
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
$env:TEST_DATABASE_URL = $env:POSTGRES_URL
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:POSTGRES_URL
Remove-Item Env:TEST_DATABASE_URL
```

Тесты удаляют только собственные строки. Не используйте рабочую БД для тестов.
Проверены конкурентные бронирования, соседние даты, cancelled, уникальность платежей,
откат транзакции, JWT и RBAC. TestClient выдаёт предупреждение Starlette о переходе с httpx на httpx2.

## Изменение схемы

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini revision --autogenerate -m "description"
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
```

Проверяйте сгенерированные миграции вручную, особенно enum и exclusion constraints.
Новый файл модели импортируйте в backend/models/__init__.py, чтобы таблица попала в общие metadata.
