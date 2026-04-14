"""Base class for stages."""


class Stage:
    """Base stage interface."""

    def run(self, *args, **kwargs):
        raise NotImplementedError
