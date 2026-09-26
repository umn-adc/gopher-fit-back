"""Export the API contract without connecting to a database or using deployment secrets."""

import argparse
import json
from pathlib import Path

from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    app = create_app(
        Settings.model_construct(
            # Schema-only configuration ignores deployment environment and .env secrets.
            jwt_secret=SecretStr("openapi-generation-only-not-a-deployment-secret"),
            database_url="sqlite:///:memory:",
            recovery_enabled=False,
            metrics_token=None,
            cors_origins=[],
        )
    )
    content = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    target = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
    if args.check:
        if not target.is_file() or target.read_text() != content:
            raise SystemExit("OpenAPI is stale: run uv run python -m scripts.export_openapi")
    else:
        target.write_text(content)


if __name__ == "__main__":
    main()
