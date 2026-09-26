"""Online migrations only: adoption needs to inspect and back up the database."""

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import ForeignKeyConstraint, LargeBinary, Text
from sqlalchemy.engine import make_url

from app.core.database import Base, create_database_engine
from app.features.auth import models as auth_models  # noqa: F401
from app.features.nutrition import models as nutrition_models  # noqa: F401
from app.features.operations import models as operations_models  # noqa: F401
from app.features.profile import models as profile_models  # noqa: F401
from app.features.social import models as social_models  # noqa: F401
from app.features.workouts import models as workout_models  # noqa: F401

load_dotenv()
config = context.config
url = config.attributes.get("database_url") or os.environ.get(
    "DATABASE_URL", config.get_main_option("sqlalchemy.url")
)


def backup_database() -> None:
    database = make_url(url).database
    if not database or database == ":memory:" or not Path(database).exists():
        return
    backup = Path(database + ".pre-python.bak")
    if backup.exists():
        if not backup.is_file():
            raise RuntimeError(f"Backup path is not a regular file: {backup}")
        return
    # Publish only a complete snapshot; interrupted backups cannot occupy the final path.
    descriptor, temporary_name = tempfile.mkstemp(prefix=backup.name + ".", dir=backup.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with (
            closing(sqlite3.connect(database)) as source,
            closing(sqlite3.connect(temporary)) as target,
        ):
            source.backup(target)
        with temporary.open("rb") as snapshot:
            os.fsync(snapshot.fileno())
        # An atomic hard link cannot overwrite a snapshot from another migration process.
        os.link(temporary, backup)
    finally:
        temporary.unlink(missing_ok=True)


if context.is_offline_mode():
    raise RuntimeError("Use online migrations; legacy adoption requires schema inspection")

backup_database()
engine = create_database_engine(url)
with engine.connect().execution_options(sqlite_begin_mode="IMMEDIATE") as connection:

    def include_object(schema_object, name, kind, reflected, compare_to):
        if kind == "table" and name == "schema_migrations" and reflected:
            return False
        # SQLAlchemy loses ON DELETE when reflecting the Go table's inline FKs.
        # Suppress a false rebuild only when SQLite's actual FK matches our model.
        if (
            isinstance(schema_object, ForeignKeyConstraint)
            and schema_object.table.name == "personal_records"
        ):
            columns = [element.parent.name for element in schema_object.elements]
            expected = next(
                (
                    constraint
                    for constraint in Base.metadata.tables[
                        "personal_records"
                    ].foreign_key_constraints
                    if [element.parent.name for element in constraint.elements] == columns
                ),
                None,
            )
            if expected is not None and len(columns) == 1:
                target = list(expected.elements)[0].column
                for row in connection.exec_driver_sql(
                    "PRAGMA foreign_key_list(personal_records)"
                ).mappings():
                    if (
                        row["from"] == columns[0]
                        and row["table"] == target.table.name
                        and row["to"] == target.name
                        and row["on_delete"] == (expected.ondelete or "NO ACTION")
                        and row["on_update"] == (expected.onupdate or "NO ACTION")
                    ):
                        return False
        return True

    def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
        # Both TEXT and BLOB password storage are deliberately supported in place.
        if (
            metadata_column.table.name == "users"
            and metadata_column.name == "password"
            and isinstance(inspected_type, Text)
            and isinstance(metadata_type, LargeBinary)
        ):
            return False
        return None

    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        transactional_ddl=True,
        compare_type=compare_type,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
