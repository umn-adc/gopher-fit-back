import json
import logging
import re
import time
import uuid

from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import URL, Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import AuthenticationFailed
from app.features.auth.security import TokenService
from app.features.operations.service import Metrics, OperationsService

logger = logging.getLogger("gopher.requests")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {"level": record.levelname, "event": record.getMessage()}
        for name in ("request_id", "method", "route", "status", "duration_ms", "error_type"):
            if hasattr(record, name):
                data[name] = getattr(record, name)
        return json.dumps(data, ensure_ascii=True)


def configure_logging() -> None:
    root = logging.getLogger("gopher")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
        root.setLevel(logging.INFO)


class OperationalMiddleware:
    def __init__(
        self, app: ASGIApp, operations: OperationsService, metrics: Metrics, tokens: TokenService
    ):
        self.app, self.operations, self.metrics, self.tokens = app, operations, metrics, tokens

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started, status = time.monotonic(), 500
        headers = Headers(scope=scope)
        supplied = headers.get("X-Request-ID", "")
        request_id = (
            supplied if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied) else uuid.uuid4().hex
        )
        scope.setdefault("state", {})["request_id"] = request_id
        path, method = scope["path"], scope["method"]

        async def response_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = request_id
                if path.startswith(("/auth/", "/profile/")):
                    response_headers["Cache-Control"] = "no-store"
            await send(message)

        try:
            response: Response | None = None
            if method != "OPTIONS":
                try:
                    retry = await run_in_threadpool(
                        self.operations.throttle, path, (scope.get("client") or ("unknown",))[0]
                    )
                    if retry:
                        response = JSONResponse(
                            {"error": "Too many requests"},
                            status_code=429,
                            headers={"Retry-After": str(retry)},
                        )
                except SQLAlchemyError:
                    response = JSONResponse({"error": "Database operation failed"}, status_code=500)
                if response is None and path in {
                    "/auth",
                    "/profile",
                    "/nutrition",
                    "/workouts",
                    "/social",
                    "/swagger",
                }:
                    response = RedirectResponse(str(URL(scope=scope).replace(path=path + "/")), 301)
                if response is None and path.startswith(
                    ("/profile/", "/nutrition/", "/workouts/", "/social/")
                ):
                    parts = headers.get("Authorization", "").split()
                    try:
                        if len(parts) != 2 or parts[0].lower() != "bearer":
                            raise AuthenticationFailed("Requires Bearer JWT token")
                        self.tokens.verify(parts[1])
                    except AuthenticationFailed as error:
                        response = JSONResponse({"error": str(error)}, status_code=401)
            if response is not None:
                # Early auth/throttle responses need the same CORS headers as routed responses.
                origin = headers.get("origin")
                if origin in self.operations.settings.cors_origins:
                    response.headers["Access-Control-Allow-Origin"] = origin
                    response.headers["Vary"] = "Origin"
                    response.headers["Access-Control-Expose-Headers"] = "X-Request-ID, Retry-After"
                await response(scope, receive, response_send)
            else:
                await self.app(scope, receive, response_send)
        finally:
            elapsed = time.monotonic() - started
            route = getattr(scope.get("route"), "path", "unmatched")
            self.metrics.observe(method, route, status, elapsed)
            logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "route": route,
                    "status": status,
                    "duration_ms": round(elapsed * 1000, 3),
                },
            )
