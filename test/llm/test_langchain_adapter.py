import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.llm.langchain_adapter import LangChainChatClient


class FakeAIMessage:
    content = "adapter response"


class FakeChatModel:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def invoke(self, messages):
        self.messages = messages
        return FakeAIMessage()


def test_langchain_chat_client_exposes_openai_compatible_create_shape():
    client = LangChainChatClient(
        api_key="test-key",
        base_url="http://localhost:11434/v1",
        chat_model_factory=FakeChatModel,
    )

    response = client.chat.completions.create(
        model="qwen3:8b",
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=32,
    )

    assert response.choices[0].message.content == "adapter response"
