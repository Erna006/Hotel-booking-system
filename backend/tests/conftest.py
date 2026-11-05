import os

os.environ.setdefault("POSTGRES_URL", "postgresql+asyncpg://hotel:hotel@127.0.0.1:15432/hotel_test")
os.environ.setdefault("JWT_SECRET", "unit-test-secret-only-do-not-use-outside-tests-123456789")
