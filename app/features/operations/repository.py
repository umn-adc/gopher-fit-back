from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, delete
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.features.operations.models import RateBucketORM


class OperationsRepository:
    """Independent short transactions: failed auth must still count toward limits."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def ready(self, expected: set[str]) -> bool:
        with self.engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
            return set(MigrationContext.configure(connection).get_current_heads()) == expected

    def hit(self, key: str, now: int, window_seconds: int) -> int:
        window = now // window_seconds
        with Session(self.engine) as session, session.begin():
            session.connection(execution_options={"sqlite_begin_mode": "IMMEDIATE"})
            session.execute(delete(RateBucketORM).where(RateBucketORM.expires_at <= now))
            statement = insert(RateBucketORM).values(
                key=key,
                window=window,
                hits=1,
                expires_at=(window + 1) * window_seconds,
            )
            hits = session.scalar(
                statement.on_conflict_do_update(
                    index_elements=[RateBucketORM.key, RateBucketORM.window],
                    set_={"hits": RateBucketORM.hits + 1},
                ).returning(RateBucketORM.hits)
            )
            assert hits is not None
            return hits
