import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException

from app.core.config import Settings
from app.core.database import create_database_engine
from app.core.errors import (
    AuthenticationFailed,
    Conflict,
    InvalidInput,
    NotFound,
    StorageFailure,
    Unavailable,
)
from app.core.middleware import OperationalMiddleware, configure_logging
from app.features.auth.delivery import RecoveryMailer
from app.features.auth.router import router as auth_router
from app.features.auth.security import TokenService
from app.features.nutrition.router import router as nutrition_router
from app.features.operations.repository import OperationsRepository
from app.features.operations.router import router as operations_router
from app.features.operations.service import Metrics, OperationsService
from app.features.profile.router import router as profile_router
from app.features.social.router import router as social_router
from app.features.workouts.router import router as workout_router

logger = logging.getLogger("gopher.errors")


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]
    database = engine if engine is not None else create_database_engine(settings.database_url)

    configure_logging()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    expected = set(ScriptDirectory.from_config(config).get_heads())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            with database.connect() as connection:
                actual = set(MigrationContext.configure(connection).get_current_heads())
                if actual != expected:
                    raise RuntimeError("Run 'uv run alembic upgrade head' before starting the API")
        except SQLAlchemyError as error:
            raise RuntimeError(
                "Run 'uv run alembic upgrade head' before starting the API"
            ) from error
        try:
            yield
        finally:
            if engine is None:
                database.dispose()

    app = FastAPI(
        title="GopherFit API",
        version="2.0",
        responses={
            400: {
                "description": "Invalid input",
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}
                },
            },
            401: {"description": "Authentication required"},
            429: {
                "description": "Rate limit exceeded",
                "headers": {
                    "Retry-After": {
                        "description": "Seconds until the next window",
                        "schema": {"type": "integer"},
                    }
                },
            },
        },
        lifespan=lifespan,
        docs_url="/swagger/index.html",
        redoc_url=None,
        openapi_url="/swagger/doc.json",
        redirect_slashes=False,
    )
    app.state.session_factory = sessionmaker(database, expire_on_commit=False)
    app.state.tokens = TokenService(
        settings.jwt_secret.get_secret_value(), settings.jwt_ttl_seconds
    )

    app.state.settings = settings
    app.state.mailer = RecoveryMailer(settings)
    app.state.metrics = Metrics()
    app.state.operations = OperationsService(OperationsRepository(database), settings, expected)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        allow_credentials=False,
    )
    app.add_middleware(
        OperationalMiddleware,
        operations=app.state.operations,
        metrics=app.state.metrics,
        tokens=app.state.tokens,
    )

    async def domain_error(request: Request, error: Exception) -> JSONResponse:
        codes = {
            InvalidInput: 400,
            AuthenticationFailed: 401,
            NotFound: 404,
            Conflict: 409,
            StorageFailure: 500,
            Unavailable: 503,
        }
        if isinstance(error, StorageFailure):
            logger.error(
                "storage_failure",
                extra={
                    "error_type": type(error).__name__,
                    "request_id": getattr(request.state, "request_id", ""),
                },
            )
        return JSONResponse({"error": str(error)}, status_code=codes[type(error)])

    for error_type in (
        InvalidInput,
        AuthenticationFailed,
        NotFound,
        Conflict,
        StorageFailure,
        Unavailable,
    ):
        app.add_exception_handler(error_type, domain_error)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        details = error.errors()
        message = "Invalid JSON"
        for detail in details:
            if detail["loc"][0] == "path":
                message = "Invalid " + str(detail["loc"][-1])
                break
        return JSONResponse({"error": message}, status_code=400)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        logger.error(
            "database_failure",
            extra={
                "error_type": type(error).__name__,
                "request_id": getattr(request.state, "request_id", ""),
            },
        )
        return JSONResponse({"error": "Database operation failed"}, status_code=500)

    async def stored_data_error(request: Request, error: Exception) -> JSONResponse:
        logger.error(
            "stored_data_failure",
            extra={
                "error_type": type(error).__name__,
                "request_id": getattr(request.state, "request_id", ""),
            },
        )
        return JSONResponse({"error": "Failed to read stored data"}, status_code=500)

    app.add_exception_handler(ValidationError, stored_data_error)
    app.add_exception_handler(ResponseValidationError, stored_data_error)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, error: HTTPException) -> JSONResponse:
        return JSONResponse(
            {"error": str(error.detail)}, status_code=error.status_code, headers=error.headers
        )

    for router in (
        auth_router,
        profile_router,
        nutrition_router,
        workout_router,
        social_router,
        operations_router,
    ):
        app.include_router(router)
        # Go GET patterns also accept HEAD. Keep these out of the OpenAPI inventory.
        for route in router.routes:
            if isinstance(route, APIRoute) and "GET" in (route.methods or set()):
                app.add_api_route(
                    route.path,
                    route.endpoint,
                    methods=["HEAD"],
                    response_model=route.response_model,
                    include_in_schema=False,
                )
    original_openapi = app.openapi

    def openapi() -> dict[str, object]:
        schema = original_openapi()
        schema.setdefault("components", {}).setdefault("schemas", {})["ErrorResponse"] = {
            "type": "object",
            "required": ["error"],
            "properties": {"error": {"type": "string"}},
        }
        for operations in schema["paths"].values():
            for operation in operations.values():
                responses = operation.get("responses", {})
                responses.pop("422", None)
                for code, response in responses.items():
                    if code.startswith(("4", "5")):
                        response["content"] = {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        }
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app
