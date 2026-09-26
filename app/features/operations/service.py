import hashlib
import hmac
import time
from collections import defaultdict
from threading import Lock

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.features.operations.repository import OperationsRepository


class OperationsService:
    def __init__(self, repository: OperationsRepository, settings: Settings, heads: set[str]):
        self.repository, self.settings, self.heads = repository, settings, heads

    def ready(self) -> bool:
        try:
            return self.repository.ready(self.heads)
        except SQLAlchemyError:
            return False

    def throttle(self, path: str, client: str) -> int | None:
        if path.startswith("/auth/recovery"):
            group, limit = "recovery", self.settings.recovery_rate_limit
        elif path.startswith("/auth/") or path == "/profile/password":
            group, limit = "auth", self.settings.auth_rate_limit
        else:
            return None
        # Hash IPs with a secret; do not persist plaintext network identities.
        key = hmac.new(
            self.settings.jwt_secret.get_secret_value().encode(),
            (group + ":" + client).encode(),
            hashlib.sha256,
        ).hexdigest()
        now, window = int(time.time()), self.settings.rate_limit_window_seconds
        hits = self.repository.hit(key, now, window)
        return window - now % window if hits > limit else None


class Metrics:
    """Bounded labels, thread-safe; each worker exposes its own counters."""

    def __init__(self) -> None:
        self.lock = Lock()
        self.counts: dict[tuple[str, str, int], int] = defaultdict(int)
        self.seconds: dict[tuple[str, str, int], float] = defaultdict(float)
        self.deliveries: dict[bool, int] = defaultdict(int)

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        with self.lock:
            key = (
                method
                if method in {"GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"}
                else "OTHER",
                route,
                status,
            )
            self.counts[key] += 1
            self.seconds[key] += seconds

    def delivery(self, success: bool) -> None:
        with self.lock:
            self.deliveries[success] += 1

    def render(self) -> str:
        with self.lock:
            lines = [
                "# TYPE gopher_http_requests_total counter",
                "# TYPE gopher_http_seconds_total counter",
            ]
            for (method, route, status), count in sorted(self.counts.items()):
                labels = f'method="{method}",route="{route}",status="{status}"'
                lines.append(f"gopher_http_requests_total{{{labels}}} {count}")
                lines.append(
                    f"gopher_http_seconds_total{{{labels}}} "
                    f"{self.seconds[method, route, status]:.6f}"
                )
            lines.append("# TYPE gopher_recovery_deliveries_total counter")
            for success, count in sorted(self.deliveries.items()):
                lines.append(
                    f'gopher_recovery_deliveries_total{{success="{str(success).lower()}"}} {count}'
                )
            return "\n".join(lines) + "\n"
