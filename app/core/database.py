from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_database_engine(url: str) -> Engine:
    if not url.startswith("sqlite:"):
        raise ValueError("This migration supports the existing SQLite database only")
    engine = create_engine(
        url, hide_parameters=True, connect_args={"check_same_thread": False, "timeout": 30}
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection: object, _: object) -> None:
        # Explicit BEGIN also makes DDL transactional (sqlite3 defaults do not).
        import sqlite3

        assert isinstance(connection, sqlite3.Connection)
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")

    @event.listens_for(engine, "begin")
    def begin(connection: object) -> None:
        from sqlalchemy import Connection

        assert isinstance(connection, Connection)
        mode = connection.get_execution_options().get("sqlite_begin_mode", "DEFERRED")
        connection.exec_driver_sql("BEGIN IMMEDIATE" if mode == "IMMEDIATE" else "BEGIN")

    return engine


def get_session(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    with factory() as session, session.begin():
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            # Serialize SQLite writers before authorization reads, avoiding lock upgrades.
            session.connection(execution_options={"sqlite_begin_mode": "IMMEDIATE"})
        yield session


# Teardown commits before sending the response. Failures roll back the entire use case.
DatabaseSession = Annotated[Session, Depends(get_session, scope="function")]
