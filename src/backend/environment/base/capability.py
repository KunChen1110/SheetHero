"""Base capability interface for environment tools."""

from typing import Any, Dict, List


class ToolCapability:
    """Base class for tool capabilities exposed to the agent."""

    def list_tools(self) -> List[str]:
        raise NotImplementedError

    def execute(self, tool_call: Dict[str, Any]) -> Any:
        raise NotImplementedError
