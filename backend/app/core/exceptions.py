class DomainError(Exception):
    """Base for known, expected application errors — maps to a specific HTTP status."""
    status_code = 400


class UpstreamDataError(DomainError):
    """FortyGuard returned no usable data (empty features/locations)."""
    status_code = 502


class PermissionDeniedError(DomainError):
    status_code = 403

class SiteNotFoundError(DomainError):
    status_code = 404

