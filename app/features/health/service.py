import json
from datetime import UTC, date, datetime, timedelta

from app.core.errors import Conflict, InvalidInput
from app.core.validation import timestamp_text
from app.features.health.models import (
    MAX_WINDOW_DAYS,
    PROVIDERS,
    DataType,
    HealthConnectionORM,
    HealthConnectionResponse,
    HealthConnectRequest,
    HealthSyncRequest,
    Provider,
)
from app.features.health.repository import Counts, HealthRepository

# Daily columns each data type owns; a sync only writes the columns of its types.
DAILY_COLUMNS: dict[DataType, tuple[str, ...]] = {
    "steps": ("steps",),
    "active_energy": ("active_energy_kcal",),
    "resting_heart_rate": ("resting_heart_rate_bpm",),
    "heart_rate": ("heart_rate_min_bpm", "heart_rate_avg_bpm", "heart_rate_max_bpm"),
}
# Device clocks drift; a window may end slightly after the server's "now".
CLOCK_SLACK = timedelta(days=1)


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

    def sync(
        self,
        user_id: int,
        provider: Provider,
        request: HealthSyncRequest,
        now: datetime | None = None,
    ) -> HealthConnectionResponse:
        now = now or datetime.now(UTC)
        connection = self.repository.connection(user_id, provider)
        if connection is None or not connection.connected:
            raise Conflict("Health source is not connected")
        since, until = request.since, request.until
        if until <= since:
            raise InvalidInput("Sync window must end after it starts")
        if until - since > timedelta(days=MAX_WINDOW_DAYS):
            raise InvalidInput(f"Sync window is longer than {MAX_WINDOW_DAYS} days")
        if until > now + CLOCK_SLACK:
            raise InvalidInput("Sync window ends in the future")
        types = set(request.data_types)
        if not types <= set(json.loads(connection.data_types)):
            raise InvalidInput("Data type is not connected")

        # Daily dates are the device's local days, so allow a day either side of UTC.
        first, last = since.date() - timedelta(days=1), until.date() + timedelta(days=1)
        dates = [row.date for row in request.daily]
        if len(set(dates)) != len(dates):
            raise InvalidInput("Duplicate daily date")
        if any(not first <= date.fromisoformat(day) <= last for day in dates):
            raise InvalidInput("Daily date is outside the sync window")
        for name, samples in (
            ("workout", [(w.external_id, w.start_at) for w in request.workouts]),
            ("weight", [(w.external_id, w.measured_at) for w in request.weights]),
        ):
            if len({external_id for external_id, _ in samples}) != len(samples):
                raise InvalidInput(f"Duplicate {name} external_id")
            if any(not since <= at < until for _, at in samples):
                raise InvalidInput(f"A {name} is outside the sync window")

        start, end = timestamp_text(since), timestamp_text(until)
        columns = [column for kind in request.data_types for column in DAILY_COLUMNS.get(kind, ())]
        self.repository.upsert_daily(
            user_id, provider, columns, [row.model_dump() for row in request.daily]
        )
        if "workouts" in types:
            with_heart_rate = "heart_rate" in types
            self.repository.replace_workouts(
                user_id,
                provider,
                start,
                end,
                [
                    workout.model_dump(
                        exclude=None
                        if with_heart_rate
                        else {"avg_heart_rate_bpm", "max_heart_rate_bpm"}
                    )
                    | {
                        "start_at": timestamp_text(workout.start_at),
                        "end_at": timestamp_text(workout.end_at),
                    }
                    for workout in request.workouts
                ],
            )
        if "weight" in types:
            self.repository.replace_weights(
                user_id,
                provider,
                start,
                end,
                [
                    weight.model_dump() | {"measured_at": timestamp_text(weight.measured_at)}
                    for weight in request.weights
                ],
            )
        self.repository.mark_synced(connection, timestamp_text(min(until, now)))
        return self._one(user_id, provider)
