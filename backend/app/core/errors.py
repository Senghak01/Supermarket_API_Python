import logging
from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from app.core.config import settings

logger = logging.getLogger("supermarket.api")


class AppError(Exception):
    """Domain/Application error with HTTP status code and message."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message

    @classmethod
    def bad_request(cls, message: str) -> "AppError":
        return cls(status.HTTP_400_BAD_REQUEST, message)

    @classmethod
    def unauthorized(cls, message: str = "Invalid email or password.") -> "AppError":
        return cls(status.HTTP_401_UNAUTHORIZED, message)

    @classmethod
    def forbidden(cls, message: str = "Forbidden.") -> "AppError":
        return cls(status.HTTP_403_FORBIDDEN, message)

    @classmethod
    def not_found(cls, message: str) -> "AppError":
        return cls(status.HTTP_404_NOT_FOUND, message)

    @classmethod
    def conflict(cls, message: str) -> "AppError":
        return cls(status.HTTP_409_CONFLICT, message)


def register_error_handlers(app: FastAPI) -> None:
    """Register custom exception handlers matching mobile app contract: { "status": code, "message": "..." }"""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": exc.status_code, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Formulate clear readable validation messages
        errors = exc.errors()
        if errors:
            first_err = errors[0]
            loc = " -> ".join(str(l) for l in first_err.get("loc", []) if l != "body")
            msg = first_err.get("msg", "Validation error")
            message = f"{loc}: {msg}" if loc else msg
        else:
            message = "Validation error"

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": status.HTTP_400_BAD_REQUEST, "message": message},
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"status": status.HTTP_429_TOO_MANY_REQUESTS, "message": "Too many requests. Please try again later."},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled error during {request.method} {request.url.path}: {exc}")
        message = (
            "An unexpected error occurred. Please try again later."
            if settings.is_production
            else str(exc)
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": message},
        )

