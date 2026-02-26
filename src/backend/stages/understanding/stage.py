"""Initial analysis and context generation stage for SheetHero."""

import re
import time
import random
from typing import Optional
from openai import RateLimitError

from ...log.logger_registry import LoggerRegistry
from ..base.stage import Stage
from ...prompt.prompt_builder import PromptBuilder

logger = LoggerRegistry.setup_logger(__name__)


class UnderstandingStage(Stage):
    """
    Module responsible for generating initial analysis and understanding from Excel context and user questions.
    """

    def __init__(self,
                 client,
                 deployment: str,
                 progress_logger=None,
                 prompt_profile: str = "online_rich"):
        """Initialize the UnderstandingStage."""

        self.client = client
        self.deployment = deployment
        self.progress_logger = progress_logger
        self.prompt_builder = PromptBuilder(profile=prompt_profile)

    def run(self, user_question: str, spreadsheet_context: str,
            session_context_understanding: Optional[str] = None) -> str:
        """
        Generate comprehensive understanding of the user's question in context.

        Combines Excel data context with the user's question to create an analysis plan that guides the execution module.
        """
        logger.info("Starting understanding analysis")
        if self.progress_logger:
            self.progress_logger.log("[UNDERSTANDING] start", to_terminal=False)

        # Build prompt and get LLM response
        session_context = (session_context_understanding or "").strip()
        if session_context and not self._context_is_relevant(user_question, session_context):
            session_context = ""
        messages = self._create_multimodal_prompt(
            user_question,
            spreadsheet_context,
            session_context
        )
    
        understanding_output = self._get_llm_response(messages)
        understanding_output = self._sanitize_understanding_output(
            understanding_output,
            user_question
        )
        if self.progress_logger:
            self.progress_logger.log_raw(
                "\n".join(["### [UNDERSTANDING OUTPUT]", understanding_output or ""])
            )

        logger.info("Understanding analysis completed")
        if self.progress_logger:
            self.progress_logger.log("[UNDERSTANDING] completed", to_terminal=False)
        return understanding_output

    def _sanitize_understanding_output(self, text: str, user_question: str) -> str:
        """Keep offline understanding concise and machine-usable for downstream stages."""
        cleaned = (text or "").strip()
        if not cleaned:
            cleaned = "### 1. Sheet Summary\n- No understanding output generated."

        # Remove long code snippets that tend to pollute offline planning.
        cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)

        forbidden_terms = (
            "pd.read_excel",
            "pd.excelfile",
            "pd.read_csv",
            "pd.read_table",
            "to_excel",
            "openpyxl",
        )
        kept_lines = []
        for line in cleaned.splitlines():
            lower = line.lower()
            if any(term in lower for term in forbidden_terms):
                continue
            kept_lines.append(line.rstrip())
        cleaned = "\n".join(kept_lines).strip()

        return self._ensure_output_contract(cleaned, user_question)

    @staticmethod
    def _parse_contract_flag(text: str, key: str) -> Optional[bool]:
        # Accept both plain and markdown-emphasized keys:
        # requires_detailed_table: YES
        # **requires_detailed_table**: YES
        pattern = rf"(?:\*\*)?\s*{re.escape(key)}\s*(?:\*\*)?\s*:\s*(YES|NO|TRUE|FALSE)"
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            return None
        return m.group(1).strip().upper() in {"YES", "TRUE"}

    @staticmethod
    def _infer_contract_from_question(user_question: str) -> dict:
        q = (user_question or "").lower()
        detail_terms = (
            "merge", "combine", "join", "table", "rows", "list", "new spreadsheet",
            "output", "export"
        )
        highlight_terms = ("highlight", "red", "color", "most", "maximum", "max")
        summary_terms = (
            "average", "avg", "total", "sum", "count", "minimum", "maximum", "metric"
        )
        need_detail = any(t in q for t in detail_terms)
        need_highlight = any(t in q for t in highlight_terms)
        need_summary = any(t in q for t in summary_terms)
        return {
            "requires_detailed_table": need_detail,
            "requires_highlight": need_highlight,
            "requires_summary_metrics": need_summary,
        }

    def _ensure_output_contract(self, text: str, user_question: str) -> str:
        """Normalize output contract for offline reliability.

        In offline mode we prefer deterministic intent extraction from the user
        question over LLM-written flags, because weak models often output
        contradictory contracts (e.g. scalar question but requires_highlight=YES).
        """
        current = {
            "requires_detailed_table": self._parse_contract_flag(text, "requires_detailed_table"),
            "requires_highlight": self._parse_contract_flag(text, "requires_highlight"),
            "requires_summary_metrics": self._parse_contract_flag(text, "requires_summary_metrics"),
        }
        inferred = self._infer_contract_from_question(user_question)
        # Offline-strict: inferred intent is authoritative to prevent noisy flags.
        final_flags = dict(inferred)

        reason_parts = []
        if final_flags["requires_detailed_table"]:
            reason_parts.append("detailed table required")
        if final_flags["requires_highlight"]:
            reason_parts.append("highlight required")
        if final_flags["requires_summary_metrics"]:
            reason_parts.append("summary metrics required")
        if not reason_parts:
            reason_parts.append("scalar output is sufficient")

        contract_block = (
            "\n\n### 3. Output Contract (MANDATORY, machine-readable)\n"
            f"requires_detailed_table: {'YES' if final_flags['requires_detailed_table'] else 'NO'}\n"
            f"requires_highlight: {'YES' if final_flags['requires_highlight'] else 'NO'}\n"
            f"requires_summary_metrics: {'YES' if final_flags['requires_summary_metrics'] else 'NO'}\n"
            f"contract_reason: {', '.join(reason_parts)}."
        )
        # Remove any existing contract block emitted by LLM to avoid duplicates/conflicts.
        cleaned = re.sub(
            r"\n*###\s*3\.\s*Output Contract\s*\(MANDATORY,\s*machine-readable\)\s*[\s\S]*$",
            "",
            text.rstrip(),
            flags=re.IGNORECASE,
        ).rstrip()
        return (cleaned + contract_block).strip()

    def enhance(self, understanding_output: str, last_validation: dict) -> str:
        """Refine understanding output based on validation feedback."""
        if not last_validation:
            return understanding_output
        if not last_validation.get("improvement_feedback"):
            return understanding_output
        if self.progress_logger:
            self.progress_logger.log("[UNDERSTANDING] enhance from validation", to_terminal=False)

        prompt_text = self.prompt_builder.build_enhanced_understanding_prompt(
            understanding_output,
            last_validation
        )
        messages = [{"role": "user", "content": prompt_text}]
        return self._get_llm_response(messages)

    def _create_multimodal_prompt(self, user_question: str,
                                  excel_context_understanding: str,
                                  session_context_understanding: str) -> list:
        """Build prompt combining user question with Excel context."""
        prompt_text = self.prompt_builder.build_understanding_prompt(
            user_question,
            excel_context_understanding,
            session_context_understanding
        )
        return [{"role": "user", "content": prompt_text}]

    def _context_is_relevant(self, user_question: str, session_context_understanding: str) -> bool:
        if not session_context_understanding:
            return False
        prompt_text = self.prompt_builder.build_understanding_context_match_prompt(
            user_question,
            session_context_understanding
        )
        messages = [{"role": "user", "content": prompt_text}]
        response = self._get_llm_response(messages)
        parsed = self._parse_yes_no(response or "")
        if parsed is None:
            return False
        return parsed

    @staticmethod
    def _parse_yes_no(text: str) -> Optional[bool]:
        upper = (text or "").strip().upper()
        if upper.startswith("YES"):
            return True
        if upper.startswith("NO"):
            return False
        return None

    def _get_llm_response(self, messages: list, max_retries: int = 5, base_delay: float = 1.0) -> str:
        """
        Get LLM response with exponential backoff retry for rate limits.
        Retries up to max_retries times, with increasing wait times between attempts.
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=messages,
                )
                return response.choices[0].message.content

            except RateLimitError as e:
                last_exception = e
                logger.warning(f"Rate limit hit, attempt {attempt + 1}/{max_retries}: {str(e)}")

                # Extract wait time from error message if available
                wait_time = self._extract_wait_time_from_error(str(e))

                if attempt < max_retries - 1:
                    if wait_time:
                        delay = wait_time + random.uniform(1, 3)
                        logger.info(f"Waiting {delay:.1f} seconds as suggested by API")
                    else:
                        delay = 10
                        logger.info(f"Waiting {delay:.1f} seconds")

                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed due to rate limiting")
                    break

            except Exception as e:
                last_exception = e
                logger.error(f"API error, attempt {attempt + 1}/{max_retries}: {str(e)}")

                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Waiting {delay:.1f} seconds before retry")
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed")
                    break

        if last_exception:
            raise last_exception

    def _extract_wait_time_from_error(self, error_message: str) -> Optional[int]:
        """
        Parse retry wait time from rate limit error messages.
        Looks for patterns like "Try again in X seconds" or "Retry after X seconds".
        """
        try:
            # Look for patterns like "Try again in X seconds"
            match = re.search(r'try again in (\d+) seconds?', error_message.lower())
            if match:
                return int(match.group(1))

            # Look for other patterns like "Retry after X seconds"
            match = re.search(r'retry after (\d+) seconds?', error_message.lower())
            if match:
                return int(match.group(1))

            return None
        except:
            return None
