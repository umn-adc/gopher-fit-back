"""Consistent SQLite snapshots and restore-to-new-file, without starting the API."""

import argparse
import hashlib
import os
import sqlite3
import tempfile
import time
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


def database_path(url: str) -> Path:
    parsed = make_url(url)
    if parsed.drivername != "sqlite" or not parsed.database or parsed.database == ":memory:":
        raise ValueError("An on-disk sqlite:/// URL is required")
    if parsed.query:
        raise ValueError("SQLite backup URLs must not contain query parameters")
    path = Path(parsed.database).resolve()
    if not path.is_file():
        raise ValueError("Source database does not exist")
    return path


def check_database(connection: sqlite3.Connection) -> None:
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("Database integrity check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("Database foreign-key check failed")


def snapshot(
    source: Path, destination: Path, timeout: float = 60, *, revoke_auth: bool = False
) -> None:
    """Publish a verified mode-0600 file atomically; never overwrite a destination."""
    if not source.is_file():
        raise ValueError("Source database does not exist")
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary_name = tempfile.mkstemp(prefix=".snapshot-", dir=destination.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    deadline = time.monotonic() + timeout

    def progress(status: int, remaining: int, total: int) -> None:
        if time.monotonic() > deadline:
            raise TimeoutError("Backup timed out; no snapshot published")

    try:
        with (
            closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as origin,
            closing(sqlite3.connect(temporary)) as target,
        ):
            origin.backup(target, pages=256, progress=progress, sleep=0.05)
            target.execute("PRAGMA journal_mode=DELETE")
            if revoke_auth:
                tables = {
                    row[0]
                    for row in target.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                with target:
                    now = int(time.time())
                    if "auth_sessions" in tables:
                        target.execute("UPDATE auth_sessions SET revoked_at=?", (now,))
                    if "recovery_tokens" in tables:
                        target.execute("UPDATE recovery_tokens SET used_at=?", (now,))
                    if "recovery_addresses" in tables:
                        target.execute("UPDATE recovery_addresses SET pending_email=NULL")
            check_database(target)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.link(temporary, destination)
        if hasattr(os, "O_DIRECTORY"):
            directory_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
        Path(str(temporary) + "-wal").unlink(missing_ok=True)
        Path(str(temporary) + "-shm").unlink(missing_ok=True)


def backup(url: str, directory: Path, keep: int = 7) -> Path:
    if keep < 1:
        raise ValueError("Retention must be at least one snapshot")
    source = database_path(url)
    identity = hashlib.sha256(str(source).encode()).hexdigest()[:12]
    prefix = f"gopher-{identity}-"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    destination = directory.resolve() / f"{prefix}{stamp}-{uuid.uuid4().hex}.sqlite3"
    snapshot(source, destination)
    candidates = sorted(
        (
            path
            for path in destination.parent.glob(prefix + "*.sqlite3")
            if path.is_file() and not path.is_symlink()
        ),
        reverse=True,
    )
    for old in candidates[keep:]:
        old.unlink()
    return destination


def restore(source: Path, destination: Path) -> None:
    if any(Path(str(destination) + suffix).exists() for suffix in ("", "-wal", "-shm")):
        raise FileExistsError("Restore requires a new path without SQLite sidecar files")
    snapshot(source, destination, revoke_auth=True)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    save = commands.add_parser("create")
    save.add_argument(
        "--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./gopherfit.db")
    )
    save.add_argument(
        "--directory", type=Path, default=Path(os.getenv("BACKUP_DIRECTORY", "./backups"))
    )
    save.add_argument("--keep", type=int, default=int(os.getenv("BACKUP_RETENTION", "7")))
    recover = commands.add_parser("restore")
    recover.add_argument("snapshot", type=Path)
    recover.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command == "create":
        print(backup(args.database_url, args.directory, args.keep))
    else:
        restore(args.snapshot, args.destination)
        print(f"Verified restore created at {args.destination}")


if __name__ == "__main__":
    main()
