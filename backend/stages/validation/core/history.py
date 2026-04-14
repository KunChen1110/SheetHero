"""Conversation history formatting for validation prompts."""

from ...base.history_formatter import BaseHistoryFormatter


class ValidationHistory(BaseHistoryFormatter):
    """Format execution conversation history for validation."""

    @staticmethod
    def _message_role(msg) -> str:
        if isinstance(msg, dict):
            return msg.get("role", "unknown")
        return getattr(msg, "role", "unknown")

    @staticmethod
    def _message_content(msg) -> str:
        if isinstance(msg, dict):
            return msg.get("content", "")
        return getattr(msg, "content", "")

    def format(self, conversation_history: list) -> str:
        if not conversation_history:
            return "No conversation history available."

        formatted_parts = []
        turn_count = 0

        for i, msg in enumerate(conversation_history):
            role = self._message_role(msg)
            content = self._message_content(msg)

            if i == 0 and role == "system":
                continue
            if i == 1 and role == "user":
                continue

            if role == "assistant":
                turn_count += 1
                formatted_parts.append(f"\n**TURN {turn_count} - AGENT RESPONSE:**")

                if "```python" in content:
                    parts = content.split("```python")
                    if len(parts) > 1:
                        if parts[0].strip():
                            formatted_parts.append(
                                f"**Thoughts:** {parts[0].strip()}"
                            )

                        code_part = parts[1].split("```")[0]
                        formatted_parts.append("**Code Executed:**")
                        formatted_parts.append(
                            f"```python\n{code_part.strip()}\n```"
                        )

                        remaining = "```".join(parts[1].split("```")[1:])
                        if remaining.strip():
                            formatted_parts.append(
                                f"**Additional Thoughts:** {remaining.strip()}"
                            )
                    else:
                        formatted_parts.append(f"**Content:** {content}")
                else:
                    if "Final Answer:" in content:
                        formatted_parts.append(f"**Final Answer Provided:** {content}")
                    else:
                        formatted_parts.append(f"**Thoughts:** {content}")

            elif role == "user":
                if "Code execution result:" in content:
                    formatted_parts.append("**Code Execution Result:**")
                    result_content = content.replace(
                        "Code execution result:", ""
                    ).strip()
                    formatted_parts.append(f"```\n{result_content}\n```")
                elif "Code execution error:" in content:
                    formatted_parts.append("**Code Execution Error:**")
                    error_content = content.replace(
                        "Code execution error:", ""
                    ).strip()
                    formatted_parts.append(f"```\n{error_content}\n```")
                else:
                    formatted_parts.append(f"**User Feedback:** {content}")

        return "\n".join(formatted_parts)
