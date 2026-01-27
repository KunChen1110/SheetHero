"""Base action interface for domain environments."""


class Action:
    """Base class for domain actions."""

    def __init__(self, name: str, payload: dict | None = None):
        self.name = name
        self.payload = payload or {}
