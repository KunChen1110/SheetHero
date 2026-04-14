"""Initial analysis and context generation stage for SheetHero."""

import re
from typing import Optional

from ...log.logger_registry import LoggerRegistry
from ...skills import (
    detect_skill,
    select_helper,
    build_skill_hint,
    build_compact_skill_workflow,
    build_fallback_strategy,
)
from ..base.stage import Stage
from ..base.llm_utils import call_llm
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

        # Detect the primary skill only; composition happens inside the chosen
        # skill through shared helpers, not by injecting multiple skill tracks.
        skill_hint = self._build_skill_hint(user_question)

        # Build prompt and get LLM response
        session_context = (session_context_understanding or "").strip()
        if session_context and not self._context_is_relevant(user_question, session_context):
            session_context = ""
        messages = self._create_multimodal_prompt(
            user_question,
            spreadsheet_context,
            session_context,
            skill_hint=skill_hint,
        )

        # Offline models can burn tokens on hidden reasoning before producing
        # usable output. Give understanding enough room, but keep the stage
        # LLM-first instead of bypassing it with a fixed scaffold.
        llm_kwargs = {}
        if self.prompt_builder.profile == "offline_strict":
            llm_kwargs["max_tokens"] = 3000
        try:
            understanding_output = call_llm(self.client, self.deployment, messages, **llm_kwargs)
            if not understanding_output.strip():
                logger.warning("Understanding LLM returned empty response; retrying with compact prompt.")
                retry_messages = self._create_compact_retry_prompt(
                    user_question,
                    spreadsheet_context,
                    skill_hint=skill_hint,
                )
                understanding_output = call_llm(
                    self.client,
                    self.deployment,
                    retry_messages,
                    **llm_kwargs,
                )
        except Exception as exc:
            logger.warning("Understanding LLM call failed; keeping downstream guidance minimal: %s", exc)
            understanding_output = (
                "### 1. Sheet Summary\n"
                "- Understanding generation failed; downstream stages must inspect the runtime schema directly.\n"
            )
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

    def _build_skill_hint(self, user_question: str) -> str:
        skill = detect_skill(user_question)
        if skill is None:
            return ""
        helper = select_helper(skill, user_question)
        if helper is None:
            return ""
        if self.prompt_builder.profile == "offline_strict":
            return build_compact_skill_workflow(skill, helper)
        return build_skill_hint(skill, helper)

    def _create_compact_retry_prompt(
        self,
        user_question: str,
        spreadsheet_context: str,
        skill_hint: str = "",
    ) -> list[dict]:
        context_lines = self._extract_context_summary_lines(spreadsheet_context)
        if not context_lines:
            context_lines = ["- Workbook context available."]
        skill_block = f"\nPrimary skill hint:\n{skill_hint}\n" if skill_hint else ""
        prompt_text = (
            "Return a short planning summary only.\n"
            "Use this structure exactly:\n"
            "### 1. Sheet Summary\n"
            "- ...\n"
            "### 2. Execution Plan\n"
            "- ...\n"
            "### 3. Output Contract\n"
            "- requires_detailed_table: YES/NO\n"
            "- requires_summary_metrics: YES/NO\n"
            "- requires_highlight: YES/NO\n\n"
            f"User Question:\n{user_question}\n\n"
            f"Workbook Context:\n{chr(10).join(context_lines)}\n"
            f"{skill_block}"
            "Ground the plan in the visible schema. Do not output code."
        )
        return [{"role": "user", "content": prompt_text}]

    @staticmethod
    def _extract_context_summary_lines(spreadsheet_context: str, max_lines: int = 8) -> list[str]:
        collected: list[str] = []
        for raw_line in (spreadsheet_context or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("📁 **File:"):
                cleaned = line.replace("📁 **File:", "").replace("**", "").strip()
                collected.append(f"- File visible: {cleaned}")
            elif line.startswith("**📄 Sheet:"):
                cleaned = line.replace("**📄 Sheet:", "").replace("**", "").strip()
                collected.append(f"- Sheet visible: {cleaned}")
            elif line.startswith("- Candidate headers:"):
                collected.append(line)
            if len(collected) >= max_lines:
                break
        return collected

    def _sanitize_understanding_output(self, text: str, user_question: str) -> str:
        """Keep offline understanding concise and machine-usable for downstream stages."""
        cleaned = (text or "").strip()
        if not cleaned:
            cleaned = "### 1. Sheet Summary\n- No understanding output generated."

        # Local models such as Qwen may leak hidden reasoning blocks.
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"^\s*\w*<think>\s*", "", cleaned, flags=re.IGNORECASE)

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

        def has_term(term: str) -> bool:
            escaped = re.escape(term.lower()).replace(r"\ ", r"\s+")
            pattern = rf"(?<!\w){escaped}(?!\w)"
            return re.search(pattern, q, flags=re.IGNORECASE) is not None

        detail_terms = (
            "merge", "combine", "join", "concatenate",
            "detailed table", "full table", "all rows", "list all",
            "row by row", "each row",
            "output a table", "following format",
            "schedule", "scheduling", "start time", "end time",
            "new excel sheet", "new spreadsheet", "new sheet",
            "fill any missing", "fill missing", "complete data", "complete file",
            "correlation matrix", "matrix", "4×4 table", "4x4 table",
            "contains cycle", "cycle", "graph id", "output an excel file",
            "| task id |", "| task name |", "| priority |", "| start time |", "| end time |", "| time |",
        )
        highlight_terms = ("highlight", "red")
        explicit_summary_terms = (
            "average", "avg", "total", "sum", "count", "minimum", "maximum", "min", "max"
        )
        summary_terms = (
            "metric", "coefficient", "correlation", "regression", "weight", "weights"
        )
        need_detail = any(has_term(t) for t in detail_terms) or "line chart" in q or "sort the regions" in q or "sorted by" in q
        need_highlight = any(has_term(t) for t in highlight_terms)
        is_target_feature_correlation = (
            "correlation matrix" not in q
            and (
                "correlation coefficient" in q
                or (
                    "correlation" in q
                    and any(marker in q for marker in ("survival", "other factors", "feature"))
                )
            )
        )
        is_regression_weights_output = (
            "regression" in q
            and any(marker in q for marker in ("weight", "weights", "coefficient", "coefficients"))
        )
        need_summary = (
            any(has_term(t) for t in summary_terms)
            or any(has_term(t) for t in explicit_summary_terms)
        )
        if is_target_feature_correlation and not any(has_term(t) for t in explicit_summary_terms):
            need_summary = False
        if is_regression_weights_output and not any(has_term(t) for t in explicit_summary_terms):
            need_summary = False
        if "correlation matrix" in q and not any(has_term(t) for t in explicit_summary_terms):
            need_summary = False
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
            r"\n*###\s*3\.\s*Output Contract[\s\S]*$",
            "",
            text.rstrip(),
            flags=re.IGNORECASE,
        ).rstrip()
        return (cleaned + contract_block).strip()

    def enhance(self, understanding_output: str, last_validation: dict,
                user_question: str = "") -> str:
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
        enhanced = call_llm(self.client, self.deployment, messages)
        return self._sanitize_understanding_output(enhanced, user_question)

    def _create_multimodal_prompt(self, user_question: str,
                                  excel_context_understanding: str,
                                  session_context_understanding: str,
                                  skill_hint: str = "") -> list:
        """Build prompt combining user question with Excel context."""
        context_text = excel_context_understanding
        is_offline = self.prompt_builder.profile == "offline_strict"
        if is_offline:
            context_lines = self._extract_context_summary_lines(
                excel_context_understanding,
                max_lines=8,
            )
            context_text = "\n".join(context_lines) if context_lines else "Workbook context available."
        prompt_text = self.prompt_builder.build_understanding_prompt(
            user_question,
            context_text,
            session_context_understanding
        )
        if skill_hint:
            prompt_text += f"\n\n{skill_hint}"
        else:
            # No skill matched — inject signal-aware fallback guidance so the
            # LLM always gets schema grounding rules and relevant hints.
            prompt_text += f"\n\n{build_fallback_strategy(user_question)}"
        if is_offline:
            prompt_text += "\n\nKeep your response under 15 lines. Be concise."
        return [{"role": "user", "content": prompt_text}]

    def _context_is_relevant(self, user_question: str, session_context_understanding: str) -> bool:
        if not session_context_understanding:
            return False
        prompt_text = self.prompt_builder.build_understanding_context_match_prompt(
            user_question,
            session_context_understanding
        )
        messages = [{"role": "user", "content": prompt_text}]
        response = call_llm(self.client, self.deployment, messages)
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
