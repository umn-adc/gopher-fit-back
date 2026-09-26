"""Domain errors have no dependency on HTTP; main.py maps them to responses."""


class InvalidInput(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class AuthenticationFailed(Exception):
    pass


class StorageFailure(Exception):
    pass


class Unavailable(Exception):
    pass
