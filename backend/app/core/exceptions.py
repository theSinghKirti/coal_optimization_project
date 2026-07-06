"""Domain exceptions and centralized FastAPI exception handlers.

Rule: never leak raw errors, SQL traces, or internal stack traces to clients.
Every handler returns a stable, minimal JSON error envelope.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

logger = logging.getLogger("codsp")


class DomainError(Exception):
    """Base class for all business-rule violations."""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(DomainError):
    """Raised for duplicate records (e.g. duplicate stock entry, duplicate hash)."""

    status_code = status.HTTP_409_CONFLICT


class ValidationFailedError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class IncompleteDataError(DomainError):
    """Raised when optimization or another workflow cannot proceed safely."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


def _error_body(message: str, code: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.message, exc.__class__.__name__),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("Request payload failed validation.", "RequestValidationError"),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        logger.warning("Integrity error on %s: %s", request.url.path, exc.__class__.__name__)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_body(
                "The request violates a database constraint (e.g. duplicate record).",
                "IntegrityError",
            ),
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
        logger.exception("Unhandled database error on %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("A database error occurred.", "DatabaseError"),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("An unexpected internal error occurred.", "InternalServerError"),
        )
