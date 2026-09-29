"""OpenAPI declarations for the error statuses an operation can actually return.

main.py attaches the shared ErrorResponse body to every declared 4xx/5xx status.
"""

from typing import Any

Responses = dict[int | str, dict[str, Any]]

DESCRIPTIONS = {
    400: "Invalid input",
    401: "Missing, invalid, expired or revoked access token",
    404: "Not found or not owned by the caller",
    409: "Conflicting change",
    429: "Rate limit exceeded",
    500: "Database or stored-data failure",
    503: "Account recovery is not configured",
}


def errors(*statuses: int | tuple[int, str]) -> Responses:
    """Declare statuses, optionally as (status, description) for a specific meaning."""
    responses: Responses = {}
    for status in statuses:
        code, description = status if isinstance(status, tuple) else (status, DESCRIPTIONS[status])
        responses[code] = {"description": description}
        if code == 429:
            responses[code]["headers"] = {
                "Retry-After": {
                    "description": "Seconds until the next window",
                    "schema": {"type": "integer"},
                }
            }
    return responses
