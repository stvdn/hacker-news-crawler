"""Failures shared by the service and infrastructure adapters."""


class UpstreamError(Exception):
    """The source could not supply a complete snapshot."""


class UpstreamTimeoutError(UpstreamError):
    """The upstream request exceeded its timeout."""


class UpstreamHTTPError(UpstreamError):
    """An upstream transport or HTTP status failure."""


class UpstreamParsingError(UpstreamError):
    """The source HTML did not contain 30 valid entries."""


class PersistenceError(Exception):
    """The usage recorder could not complete a write."""
