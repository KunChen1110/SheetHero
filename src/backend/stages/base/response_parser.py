"""Base response parser interface."""


class BaseResponseParser:
    """Parses model output into structured results."""

    def parse(self, content: str):
        raise NotImplementedError
