import json
from collections.abc import Sequence

from sqlalchemy import delete, func, select, update
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
