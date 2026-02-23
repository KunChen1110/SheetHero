"""Validation runtime for execution results."""

import re
from typing import Any, Dict

from ...log.logger_registry import LoggerRegistry
from ..base.runtime import StageRuntime
from ...prompt.prompt_builder import PromptBuilder
from .history import ValidationHistory
from .llm_client import ValidationLLMClient
from .parser import ValidationResponseParser

logger = LoggerRegistry.setup_logger(__name__)


class ValidationRuntime(StageRuntime):
    """Runs validation steps to assess execution results."""

    def __init__(self, client, deployment: str, excel_context_understanding: str,
                 progress_log_file=None, prompt_profile: str = "online_rich"):
        super().__init__(progress_log_file)
        self.excel_context_understanding = excel_context_understanding
        self.history_formatter = ValidationHistory()
        self.llm_client = ValidationLLMClient(client, deployment)
        self.parser = ValidationResponseParser()
        self.prompt_builder = PromptBuilder(profile=prompt_profile)

    @staticmethod
    def _looks_like_file_path(s: str) -> bool:
        """True if s looks like a file path (e.g. ends with .xlsx or starts with / or contains \\)."""
        if not s or not isinstance(s, str):
            return False
        s = s.strip()
        if ".xlsx" in s or ".xls" in s or s.startswith("/") or "\\" in s or s.startswith("C:"):
            return True
        return False

    @staticmethod
    def _parse_output_contract_flag(understanding_output: str, key: str) -> bool | None:
        if not understanding_output:
            return None
        pattern = rf"(?:\*\*)?\s*{re.escape(key)}\s*(?:\*\*)?\s*:\s*(YES|NO|TRUE|FALSE)"
        m = re.search(pattern, understanding_output, flags=re.IGNORECASE)
        if not m:
            return None
        return m.group(1).strip().upper() in {"YES", "TRUE"}

    @staticmethod
    def _extract_rows_written(text: str) -> list[int]:
        if not text:
            return []
        out = []
        for m in re.findall(r"Wrote\s+(\d+)\s+rows\s+to", text, flags=re.IGNORECASE):
            try:
                out.append(int(m))
            except Exception:
                continue
        return out

    @staticmethod
    def _extract_highlight_rows(text: str) -> list[int]:
        if not text:
            return []
        all_rows: list[int] = []
        blocks = re.findall(r"Highlighted row\(s\)\s*\[([^\]]*)\]", text, flags=re.IGNORECASE)
        for raw in blocks:
            for token in re.findall(r"-?\d+", raw):
                try:
                    all_rows.append(int(token))
                except Exception:
                    continue
        return all_rows

    def run(self, execution_result: Dict[str, Any], user_question: str,
            understanding_output: str) -> Dict[str, Any]:
        logger.info("Starting validation on execution results")

        conversation_history = execution_result.get("conversation_history", [])
        conversation_history_text = self.history_formatter.format(conversation_history)

        prompt_text = self.prompt_builder.build_validation_prompt(
            user_query=user_question,
            excel_context_understanding=self.excel_context_understanding,
            execution_context=understanding_output,
            execution_success=execution_result.get("success", False),
            total_turns=execution_result.get("total_turns", 0),
            final_answer=execution_result.get("answer", "No answer provided"),
            execution_summary=execution_result.get("execution_summary", {}),
            conversation_history_text=conversation_history_text
        )
        messages = [{"role": "user", "content": prompt_text}]

        try:
            validation_analysis = self.llm_client.get_response(messages)
            self._log_to_file(
                f"\n**Validation Analysis:**\n```\n{validation_analysis}\n```\n"
            )

            validation_result = self.parser.parse(validation_analysis)

            # Rule-based hard checks to reduce offline false positives.
            hard_issues = []
            run_success = bool(execution_result.get("success", False))
            if not run_success:
                hard_issues.append("Execution result indicates failure (`success=false`).")

            final_answer = execution_result.get("answer", "") or ""
            steps = execution_result.get("execution_summary", {}).get("execution_steps", [])
            all_results = " ".join(str(s.get("result") or "") for s in steps)

            # If final answer is file path, execution stdout must contain save evidence.
            if final_answer and self._looks_like_file_path(final_answer):
                if "Workbook saved to:" not in all_results:
                    hard_issues.append(
                        "Final answer is a file path but no 'Workbook saved to:' line found in execution output. "
                        "Execution must use save_workbook_to(output_path) and produce save confirmation."
                    )
                    logger.warning("Validation overridden: path answer without save confirmation in stdout")

            rows_written = self._extract_rows_written(all_results)
            max_rows = max(rows_written) if rows_written else 0
            highlighted_rows = self._extract_highlight_rows(all_results)
            lower_results = all_results.lower()

            need_detail = self._parse_output_contract_flag(understanding_output, "requires_detailed_table")
            need_highlight = self._parse_output_contract_flag(understanding_output, "requires_highlight")
            need_summary = self._parse_output_contract_flag(understanding_output, "requires_summary_metrics")

            if need_detail is True and max_rows < 6:
                hard_issues.append(
                    "Output contract requires detailed table, but write evidence is too small "
                    f"(max rows written = {max_rows})."
                )

            if need_highlight is True:
                if "highlighted row(s)" not in lower_results:
                    hard_issues.append("Output contract requires highlight, but no highlight evidence was found.")
                elif max_rows > 0 and highlighted_rows:
                    invalid = [r for r in highlighted_rows if r < 2 or r > max_rows + 2]
                    if invalid:
                        hard_issues.append(
                            "Highlight rows appear out of expected table range: "
                            + ", ".join(str(v) for v in invalid[:5])
                        )

            if need_summary is True:
                has_summary_signal = ("added summary row" in lower_results) or (len(rows_written) >= 2)
                if not has_summary_signal:
                    hard_issues.append("Output contract requires summary metrics, but summary write evidence is missing.")

            if validation_result.get("validation_passed") and validation_result.get("issues_found"):
                hard_issues.append("Validator marked PASSED but still reported issues_found.")

            if hard_issues:
                validation_result["validation_passed"] = False
                merged_issues = list(validation_result.get("issues_found") or [])
                merged_issues.extend(hard_issues)
                validation_result["issues_found"] = merged_issues
                feedback = (validation_result.get("improvement_feedback") or "").strip()
                if not feedback:
                    validation_result["improvement_feedback"] = (
                        "Fix rule-based validation issues first: contract alignment, output shape, and save evidence."
                    )

            logger.info(
                f"Validation completed. Confidence: {validation_result['confidence_score']:.2f}"
            )
            logger.info(
                f"Validation: {'PASSED' if validation_result['validation_passed'] else 'FAILED'}"
            )

            if validation_result['validation_passed']:
                logger.info("Answer validated - ready for final output")
                validation_result['verified_answer'] = execution_result.get("answer", "")
                validation_result['requires_reexecution'] = False
            else:
                logger.warning("Issues found - recommending re-execution")
                validation_result['requires_reexecution'] = True

            return validation_result

        except Exception as e:
            logger.error(f"Error during validation: {str(e)}")
            return {
                "validation_passed": False,
                "confidence_score": 0.0,
                "issues_found": [f"Validation process failed: {str(e)}"],
                "improvement_feedback": (
                    "Unable to provide feedback due to validation error. "
                    "Please review the execution manually."
                ),
                "final_assessment": "Unable to validate due to validation error",
                "verified_answer": "",
                "requires_reexecution": False
            }
