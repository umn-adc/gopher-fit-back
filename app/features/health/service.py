import json
from datetime import UTC, datetime

from app.core.validation import timestamp_text
from app.features.health.models import (
    PROVIDERS,
    HealthConnectionORM,
    HealthConnectionResponse,
    HealthConnectRequest,
    Provider,
)
from app.features.health.repository import Counts, HealthRepository


def stored_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class HealthService:
    def __init__(self, repository: HealthRepository):
        self.repository = repository

    def _response(
        self, provider: Provider, connection: HealthConnectionORM | None, counts: Counts
    ) -> HealthConnectionResponse:
        totals = counts.get(provider, {})
        connected = connection is not None and connection.connected
        return HealthConnectionResponse(
            provider=provider,
            connected=connected,
            data_types=json.loads(connection.data_types) if connected and connection else [],
            connected_at=stored_time(connection.connected_at if connection else None),
            last_synced_at=stored_time(connection.last_synced_at if connection else None),
            synced_days=totals.get("days", 0),
            synced_workouts=totals.get("workouts", 0),
            synced_weights=totals.get("weights", 0),
        )

    def connections(self, user_id: int) -> list[HealthConnectionResponse]:
        rows = {row.provider: row for row in self.repository.connections(user_id)}
        counts = self.repository.counts(user_id)
        return [self._response(provider, rows.get(provider), counts) for provider in PROVIDERS]

    def _one(self, user_id: int, provider: Provider) -> HealthConnectionResponse:
        connection = self.repository.connection(user_id, provider)
        return self._response(provider, connection, self.repository.counts(user_id))

    def connect(
        self,
        user_id: int,
        provider: Provider,
        request: HealthConnectRequest,
        now: datetime | None = None,
    ) -> HealthConnectionResponse:
        now = now or datetime.now(UTC)
        self.repository.connect(user_id, provider, list(request.data_types), timestamp_text(now))
        return self._one(user_id, provider)

    def disconnect(self, user_id: int, provider: Provider) -> None:
        self.repository.disconnect(user_id, provider)

    def delete_data(self, user_id: int, provider: Provider) -> None:
        self.repository.delete_data(user_id, provider)
