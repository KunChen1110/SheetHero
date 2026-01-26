"""Token cost helpers for Excel context building."""

import tiktoken


def calculate_token_cost_line(text: str, model: str = "gpt-4") -> int:
    """
    Calculate token cost of text for AI context management.

    Prevents exceeding model context limits and controls costs.
    Uses tiktoken for accurate counting based on model-specific encodings.
    """
    try:
        model_encodings = {
            "gpt-4": "cl100k_base",
            "gpt-4-turbo": "cl100k_base",
            "gpt-4o": "o200k_base",
            "gpt-3.5-turbo": "cl100k_base",
            "gpt-5-nano-2025-08-07": "o200k_base",
            "text-embedding-ada-002": "cl100k_base",
        }

        encoding_name = model_encodings.get(model, "cl100k_base")
        encoding = tiktoken.get_encoding(encoding_name)

        tokens = encoding.encode(text)
        return len(tokens)

    except Exception:
        char_count = len(text)
        token_count = max(1, int(char_count / 3.5))
        return token_count
