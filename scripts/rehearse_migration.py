"""Rehearse `alembic upgrade head` on a copy of a database; the source is only read.

Steps: copy SOURCE (read-only, SQLite backup API) to WORKDIR/rehearsal.db, snapshot
that copy to WORKDIR/pre-upgrade.sqlite3, upgrade the copy, then run `alembic check`,
PRAGMA integrity_check and foreign_key_check, and print row counts per table.

    uv run python -m scripts.rehearse_migration /srv/gopher/data/gopherfit.db \\
        --workdir /srv/gopher/rehearsal

Stop writers first, or rehearse from a verified backup, so the copy is current.
"""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from alembic import command
from alembic.config import Config

from scripts.backup import check_database, snapshot

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def row_counts(path: Path) -> dict[str, int]:
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            for table in tables
        }


def revision(path: Path) -> str:
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        has_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        ).fetchone()
        if not has_table:
            return "none (not yet adopted by Alembic)"
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        return str(row[0]) if row else "none"


def rehearse(source: Path, workdir: Path) -> list[str]:
    """Run the rehearsal and return the report lines; raise on any failed step."""
    source = source.resolve()
    if not source.is_file():
        raise ValueError(f"Source database does not exist: {source}")
    workdir = workdir.resolve()
    copy = workdir / "rehearsal.db"
    backup = workdir / "pre-upgrade.sqlite3"
    if source in (copy, backup):
        raise ValueError("The work directory must not contain the source database")
    for path in (copy, backup):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite {path}; use a new work directory")
    snapshot(source, copy)
    snapshot(copy, backup)
    before_revision, before = revision(copy), row_counts(copy)

    config = Config(str(ALEMBIC_INI))
    # env.py prefers this attribute over DATABASE_URL/.env, so only the copy is opened.
    config.attributes["database_url"] = f"sqlite:///{copy}"
    command.upgrade(config, "head")
    command.check(config)
    with closing(sqlite3.connect(copy)) as connection:
        check_database(connection)
    after = row_counts(copy)

    width = max(len(name) for name in after | before)
    lines = [
        f"Source (read only):   {source}",
        f"Upgraded copy:        {copy}",
        f"Pre-upgrade snapshot: {backup}",
        f"Revision:             {before_revision} -> {revision(copy)}",
        "alembic check:        no schema differences from the models",
        "integrity_check:      ok; foreign_key_check: no violations",
        "",
        f"{'table':<{width}}  {'before':>8}  {'after':>8}",
    ]
    for table in sorted(before | after):
        old = str(before[table]) if table in before else "-"
        lines.append(f"{table:<{width}}  {old:>8}  {after.get(table, 0):>8}")
    lines += [
        "",
        "Existing rows are preserved except personal_records, which revision 0003",
        "rebuilds empty (historical lifts have no known unit). New tables start empty.",
    ]
    return lines


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("source", type=Path, help="Database to copy; never written")
    parser.add_argument(
        "--workdir", type=Path, required=True, help="New directory for the copy and snapshot"
    )
    args = parser.parse_args(argv)
    try:
        lines = rehearse(args.source, args.workdir)
    except Exception as error:
        raise SystemExit(f"Rehearsal failed: {type(error).__name__}: {error}") from error
    print("\n".join(lines))


if __name__ == "__main__":
    main()
