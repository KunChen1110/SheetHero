"""Conversation history formatting for execution results."""

from ...base.history_formatter import BaseHistoryFormatter


class ExecutionHistory(BaseHistoryFormatter):
    """Formats conversation history into dicts for downstream consumers."""

    @staticmethod
    def format_history(conversation_history: list) -> list:
        formatted_history = []
        for msg in conversation_history:
            if hasattr(msg, 'dict'):
                formatted_history.append(msg.dict())
            elif isinstance(msg, dict):
                formatted_history.append(msg)
            else:
                formatted_history.append({
                    "role": getattr(msg, 'role', 'unknown'),
                    "content": getattr(msg, 'content', str(msg))
                })
        return formatted_history
