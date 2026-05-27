"""LangChain-backed OpenAI-compatible chat client facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from openai import OpenAI


@dataclass
class _Message:
    content: str


@dataclass
class _Choice:
    message: _Message


@dataclass
class _ChatCompletion:
    choices: list[_Choice]


class _LangChainChatCompletions:
    def __init__(
        self,
        api_key: str,
        base_url: Optional[str],
        timeout: Optional[int],
        max_retries: int,
        chat_model_factory: Optional[Callable[..., Any]] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.chat_model_factory = chat_model_factory

    def create(self, *, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> _ChatCompletion:
        chat_model = self._build_chat_model(model, kwargs)
        lc_messages = self._to_langchain_messages(messages)
        response = chat_model.invoke(lc_messages)
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = "".join(str(part) for part in content)
        return _ChatCompletion(choices=[_Choice(message=_Message(content=str(content or "")))])

    def _build_chat_model(self, model: str, kwargs: dict[str, Any]):
        factory = self.chat_model_factory
        if factory is None:
            try:
                from langchain_openai import ChatOpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "LangChain chat backend is enabled but `langchain-openai` is not installed."
                ) from exc
            factory = ChatOpenAI

        model_kwargs: dict[str, Any] = {
            "model": model,
            "api_key": self.api_key,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }
        if self.base_url:
            model_kwargs["base_url"] = self.base_url
        if "max_tokens" in kwargs and kwargs["max_tokens"] is not None:
            model_kwargs["max_tokens"] = kwargs["max_tokens"]
        return factory(**model_kwargs)

    @staticmethod
    def _to_langchain_messages(messages: list[dict[str, Any]]) -> list[Any]:
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        except ImportError:
            return messages

        converted: list[Any] = []
        for message in messages:
            role = (message.get("role") or "user").lower()
            content = message.get("content") or ""
            if role == "system":
                converted.append(SystemMessage(content=content))
            elif role == "assistant":
                converted.append(AIMessage(content=content))
            else:
                converted.append(HumanMessage(content=content))
        return converted


class _LangChainChat:
    def __init__(self, completions: _LangChainChatCompletions):
        self.completions = completions


class LangChainChatClient:
    """Small facade exposing `chat.completions.create(...)` for existing code.

    Existing SheetHero stages expect an OpenAI-style client. This adapter lets us
    use LangChain chat models without rewriting every stage at once.
    """

    provider = "langchain"

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: int = 0,
        chat_model_factory: Optional[Callable[..., Any]] = None,
    ):
        self.chat = _LangChainChat(
            _LangChainChatCompletions(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
                max_retries=max(0, int(max_retries)),
                chat_model_factory=chat_model_factory,
            )
        )


def build_langchain_or_openai_client(
    *,
    api_key: str,
    base_url: Optional[str],
    timeout: Optional[int],
    max_retries: int,
    prefer_langchain: bool = True,
) -> Any:
    """Build the project LLM client.

    LangChain is preferred when installed. If the optional dependency is absent,
    we keep the previous OpenAI SDK path so local development still works before
    dependencies are refreshed.
    """

    if prefer_langchain:
        try:
            import langchain_openai  # noqa: F401
            import langchain_core  # noqa: F401
            return LangChainChatClient(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
                max_retries=max_retries,
            )
        except ImportError:
            pass

    client_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "timeout": timeout,
        "max_retries": max(0, int(max_retries)),
    }
    if base_url:
        client_kwargs["base_url"] = base_url
    return OpenAI(**client_kwargs)
