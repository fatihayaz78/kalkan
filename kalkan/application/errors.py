"""Application errors; the API layer maps them to HTTP status codes."""


class KalkanError(Exception):
    """Base class."""


class InvalidRequest(KalkanError):
    pass


class PayloadTooLarge(KalkanError):
    pass


class NotFound(KalkanError):
    pass


class Conflict(KalkanError):
    pass
