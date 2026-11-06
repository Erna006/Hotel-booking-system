import logging

import asyncpg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger("hotel.api")


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(status_code, message)
        self.code = code



def error_response(request: Request, status: int, code: str, message: str, headers=None):
    request_id = getattr(request.state, "request_id", None)
    response_headers = dict(headers or {})
    if request_id:
        response_headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}, "request_id": request_id},
        headers=response_headers,
    )


async def http_error(request: Request, exc: HTTPException):
    return error_response(request, exc.status_code, getattr(exc, "code", f"http_{exc.status_code}"), str(exc.detail), exc.headers)


async def validation_error(request: Request, exc: RequestValidationError):
    return error_response(request, 422, "validation_error", "Invalid request fields")


async def integrity_error(request: Request, exc: asyncpg.IntegrityConstraintViolationError):
    if exc.sqlstate == "23P01":
        return error_response(request, 409, "room_unavailable", "Room is unavailable for these dates")
    return error_response(request, 409, "data_conflict", "Operation conflicts with stored data")


async def transaction_error(request: Request, exc: asyncpg.PostgresError):
    return error_response(request, 409, "transaction_conflict", "Concurrent operation; retry the request")


async def unexpected_error(request: Request, exc: Exception):
    # Exception text can contain SQL parameters and credentials.
    logger.error(
        "Unhandled error type=%s request_id=%s",
        type(exc).__name__,
        getattr(request.state, "request_id", None),
    )
    return error_response(request, 500, "internal_error", "Internal server error")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(asyncpg.IntegrityConstraintViolationError, integrity_error)
    app.add_exception_handler(asyncpg.DeadlockDetectedError, transaction_error)
    app.add_exception_handler(asyncpg.SerializationError, transaction_error)
    app.add_exception_handler(Exception, unexpected_error)
