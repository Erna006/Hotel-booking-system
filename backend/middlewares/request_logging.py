import logging
import time
from uuid import uuid4

from fastapi import Request

logger = logging.getLogger("hotel.api")


async def request_logging(request: Request, call_next):
    request.state.request_id = str(uuid4())
    start = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id

    # Bodies, tokens, passwords and query strings must not enter logs.
    logger.info(
        "request_id=%s method=%s status=%s duration_ms=%.1f",
        request.state.request_id,
        request.method,
        response.status_code,
        (time.monotonic() - start) * 1000,
    )
    return response
