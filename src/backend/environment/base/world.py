"""Base world interface for domain environments."""


class World:
    """Base class for domain worlds."""

    def step(self, action):
        raise NotImplementedError
