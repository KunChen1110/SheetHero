"""Base LLM client for stages."""


class BaseLLMClient:
    """Shared LLM client configuration."""

    def __init__(self, client, deployment: str):
        self.client = client
        self.deployment = deployment
