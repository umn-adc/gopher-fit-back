"""The migration rehearsal works on a copy and never writes the source database."""

import hashlib
import sqlite3

import pytest

from scripts.rehearse_migration import main
from tests.conftest import migrate
from tests.test_migrations import legacy_database, snapshot


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_rehearsal_upgrades_a_copy_and_reports_counts(tmp_path, capsys):
    source = tmp_path / "legacy.db"
    before = legacy_database(source)
    original, modified = digest(source), source.stat().st_mtime_ns
    workdir = tmp_path / "rehearsal"
    main([str(source), "--workdir", str(workdir)])
    output = capsys.readouterr().out

    assert digest(source) == original and source.stat().st_mtime_ns == modified
    assert not (tmp_path / "legacy.db.pre-python.bak").exists()
    assert "Revision:             none (not yet adopted by Alembic) -> 0007_health_sync" in (output)
    assert "no schema differences" in output and "foreign_key_check: no violations" in output
    rows = {
        line.split()[0]: line.split()[1:]
        for line in output.splitlines()
        if line and line.split()[0] in {"users", "workout_item", "favorite_meals"}
    }
    assert rows == {
        "users": ["2", "2"],
        "workout_item": ["10", "10"],
        "favorite_meals": ["-", "0"],
    }
    with sqlite3.connect(workdir / "rehearsal.db") as copy:
        assert copy.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0007_health_sync",
        )
        upgraded = snapshot(copy)
        assert {table: upgraded[table] for table in before} == before
    with sqlite3.connect(workdir / "pre-upgrade.sqlite3") as backup:
        assert snapshot(backup) == before


def test_rehearsal_of_a_current_database_is_a_no_op_upgrade(tmp_path, capsys):
    source = tmp_path / "current.db"
    migrate(source)
    original = digest(source)
    main([str(source), "--workdir", str(tmp_path / "work")])
    assert "0007_health_sync -> 0007_health_sync" in capsys.readouterr().out
    assert digest(source) == original


def test_rehearsal_refuses_to_reuse_a_work_directory(tmp_path):
    source = tmp_path / "legacy.db"
    legacy_database(source)
    main([str(source), "--workdir", str(tmp_path / "work")])
    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        main([str(source), "--workdir", str(tmp_path / "work")])
    with pytest.raises(SystemExit, match="does not exist"):
        main([str(tmp_path / "missing.db"), "--workdir", str(tmp_path / "other")])


def test_failed_upgrade_reports_and_leaves_the_source_untouched(tmp_path):
    source = tmp_path / "orphan.db"
    legacy_database(source)
    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO workouts VALUES (99, 99, 'Orphan', 1)")
    original = digest(source)
    with pytest.raises(SystemExit, match="Rehearsal failed: .*foreign-key check failed"):
        main([str(source), "--workdir", str(tmp_path / "work")])
    assert digest(source) == original
