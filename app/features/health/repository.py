import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.features.health.models import (
    HealthConnectionORM,
    HealthDailyActivityORM,
    HealthWeightSampleORM,
    HealthWorkoutORM,
)

Counts = dict[str, dict[str, int]]


class HealthRepository:
    def __init__(self, session: Session):
        self.session = session

    def connections(self, user_id: int) -> Sequence[HealthConnectionORM]:
        return self.session.scalars(
            select(HealthConnectionORM).where(HealthConnectionORM.user_id == user_id)
        ).all()

    def connection(self, user_id: int, provider: str) -> HealthConnectionORM | None:
        return self.session.get(HealthConnectionORM, (user_id, provider))

    def connect(
        self, user_id: int, provider: str, data_types: list[str], now: str
    ) -> HealthConnectionORM:
        connection = self.connection(user_id, provider)
        if connection is None:
            connection = HealthConnectionORM(user_id=user_id, provider=provider)
            self.session.add(connection)
        if not connection.connected:
            connection.connected, connection.connected_at = True, now
            connection.last_synced_at = None
        connection.data_types = json.dumps(data_types)
        self.session.flush()
        return connection

    def disconnect(self, user_id: int, provider: str) -> None:
        self.session.execute(
            update(HealthConnectionORM)
            .where(HealthConnectionORM.user_id == user_id, HealthConnectionORM.provider == provider)
            .values(connected=False, data_types="[]", connected_at=None, last_synced_at=None)
        )

    def counts(self, user_id: int) -> Counts:
        counts: Counts = {}
        for name, table in (
            ("days", HealthDailyActivityORM),
            ("workouts", HealthWorkoutORM),
            ("weights", HealthWeightSampleORM),
        ):
            rows = self.session.execute(
                select(table.provider, func.count())
                .where(table.user_id == user_id)
                .group_by(table.provider)
            )
            for provider, count in rows:
                counts.setdefault(provider, {})[name] = count
        return counts

    def delete_data(self, user_id: int, provider: str) -> None:
        for table in (HealthDailyActivityORM, HealthWorkoutORM, HealthWeightSampleORM):
            self.session.execute(
                delete(table).where(table.user_id == user_id, table.provider == provider)
            )
        self.session.execute(
            update(HealthConnectionORM)
            .where(HealthConnectionORM.user_id == user_id, HealthConnectionORM.provider == provider)
            .values(last_synced_at=None)
        )

    def upsert_daily(
        self, user_id: int, provider: str, columns: list[str], rows: list[dict[str, Any]]
    ) -> None:
        """Insert or update days, writing only `columns`; other columns keep their values."""
        if not columns or not rows:
            return
        statement = insert(HealthDailyActivityORM)
        statement = statement.on_conflict_do_update(
            index_elements=["user_id", "provider", "date"],
            set_={column: statement.excluded[column] for column in columns},
        )
        self.session.execute(
            statement,
            [
                {"user_id": user_id, "provider": provider, "date": row["date"]}
                | {column: row[column] for column in columns}
                for row in rows
            ],
        )

    def replace_workouts(
        self, user_id: int, provider: str, since: str, until: str, rows: list[dict[str, Any]]
    ) -> None:
        """Replace the window's sessions and any re-sent session that moved into it."""
        self.session.execute(
            delete(HealthWorkoutORM).where(
                HealthWorkoutORM.user_id == user_id,
                HealthWorkoutORM.provider == provider,
                or_(
                    (HealthWorkoutORM.start_at >= since) & (HealthWorkoutORM.start_at < until),
                    HealthWorkoutORM.external_id.in_([row["external_id"] for row in rows]),
                ),
            )
        )
        self.session.add_all(
            HealthWorkoutORM(user_id=user_id, provider=provider, **row) for row in rows
        )
        self.session.flush()

    def replace_weights(
        self, user_id: int, provider: str, since: str, until: str, rows: list[dict[str, Any]]
    ) -> None:
        self.session.execute(
            delete(HealthWeightSampleORM).where(
                HealthWeightSampleORM.user_id == user_id,
                HealthWeightSampleORM.provider == provider,
                or_(
                    (HealthWeightSampleORM.measured_at >= since)
                    & (HealthWeightSampleORM.measured_at < until),
                    HealthWeightSampleORM.external_id.in_([row["external_id"] for row in rows]),
                ),
            )
        )
        self.session.add_all(
            HealthWeightSampleORM(user_id=user_id, provider=provider, **row) for row in rows
        )
        self.session.flush()

    def mark_synced(self, connection: HealthConnectionORM, at: str) -> None:
        connection.last_synced_at = at
        self.session.flush()
