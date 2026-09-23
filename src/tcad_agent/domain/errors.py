"""Domain-specific errors surfaced at typed boundaries."""


class DomainError(ValueError):
    """Base error for invalid scientific input."""


class UnitError(DomainError):
    """A quantity is absent, malformed, or dimensionally incompatible."""

