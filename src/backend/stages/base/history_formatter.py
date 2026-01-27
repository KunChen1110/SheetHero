"""Base history formatter interface."""


class BaseHistoryFormatter:
    """Formats conversation history for downstream use."""

    def format(self, conversation_history: list):
        raise NotImplementedError
