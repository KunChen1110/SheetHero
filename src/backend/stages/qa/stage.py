"""Quality assurance stage (LLM-assisted matching + cleaning action)."""

from copy import deepcopy
import re
from typing import Any, Dict, Optional

from ...prompt.prompt_builder import PromptBuilder
from ...log.logger_registry import LoggerRegistry
from ..base.stage import Stage
from ..base.llm_utils import call_llm
from .policy_plan import CleaningPolicyPlan, QAIssueGroup

logger = LoggerRegistry.setup_logger(__name__)


class QualityAssuranceStage(Stage):
    """QA stage for multi-turn clarification."""

    def __init__(self, client, deployment: str, progress_logger=None,
                 prompt_profile: str = "online_rich"):
        self.client = client
        self.deployment = deployment
        self.progress_logger = progress_logger
        self.prompt_builder = PromptBuilder(profile=prompt_profile)
        self._is_offline = prompt_profile == "offline_strict"
        self.quality_table = []
        self.original_question = ""
        self.unresolved_problems = []
        self.current_problem = None
        self.answers = []
        self.cleaning_actions = []
        self.cleaning_policy_plans = []
        self.interpretation_policies = []
        self.max_qa_rounds = 30
        self.qa_rounds = 0
        self.last_mismatch = ""
        self._last_structured_decision: Dict[str, str] = {}

    def reset(self) -> None:
        """Reset all QA runtime state for a fresh clarification flow."""
        self.quality_table = []
        self.original_question = ""
        self.unresolved_problems = []
        self.current_problem = None
        self.answers = []
        self.cleaning_actions = []
        self.cleaning_policy_plans = []
        self.interpretation_policies = []
        self.qa_rounds = 0
        self.last_mismatch = ""
        self._last_structured_decision = {}

    def start(self, question_list: Optional[list], original_question: str) -> None:
        self.reset()
        filtered_questions = self._filter_format_questions(question_list or [])
        self.quality_table = self._group_policy_questions(filtered_questions)
        self.original_question = original_question
        self.unresolved_problems = []
        for idx, item in enumerate(self.quality_table):
            if isinstance(item, dict):
                problem = deepcopy(item)
                problem.setdefault("id", idx)
                problem.setdefault("description", self._problem_description(item))
                problem.setdefault("question", "")
                problem.setdefault("details_markdown", "")
            else:
                problem = {
                    "id": idx,
                    "description": self._problem_description(item),
                    "question": "",
                    "details_markdown": "",
                }
            self.unresolved_problems.append(problem)
        self._log_progress(
            f"[QA] Started with {len(self.unresolved_problems)} issue(s) to clarify."
        )

    def next_question_payload(self) -> Optional[Dict[str, str]]:
        if not self.unresolved_problems and self.current_problem is None:
            return None
        if self.qa_rounds >= self.max_qa_rounds:
            self._log_progress("[QA] Reached max QA rounds. Stopping questions.")
            self.current_problem = None
            return None

        if self.current_problem is None:
            self.current_problem = self.unresolved_problems.pop(0)
            self.qa_rounds += 1

        description = str(self.current_problem.get("description") or "").strip()
        direct_question = str(self.current_problem.get("question") or "").strip()
        details_markdown = str(self.current_problem.get("details_markdown") or "").strip()
        self._log_progress(f"[QA] Question about: {description}")

        if direct_question:
            return {
                "message": direct_question,
                "details_markdown": details_markdown,
            }

        prompt_text = self.prompt_builder.build_qa_question_prompt(
            self._format_quality_table(self.quality_table),
            description
        )
        messages = [{"role": "user", "content": prompt_text}]
        llm_kwargs = {}
        if self._is_offline:
            llm_kwargs["max_tokens"] = 256
        try:
            content = call_llm(self.client, self.deployment, messages, **llm_kwargs)
        except Exception:
            content = ""
        question = content.strip() or "Please clarify your preferences for data cleaning."
        return {
            "message": self._ensure_qa_scope(question),
            "details_markdown": details_markdown,
        }

    def next_question(self) -> Optional[str]:
        payload = self.next_question_payload()
        if not payload:
            return None
        return payload.get("message")

    def consume_user_reply(self, reply: str) -> None:
        if self.current_problem is None:
            return
        self._last_structured_decision = {}
        matched, action, feedback = self._match_reply(self.current_problem, reply)
        if not matched:
            self.last_mismatch = feedback or "Please answer the question directly."
            self.qa_rounds += 1
            self._log_progress(f"[QA] Reply mismatch: {self.last_mismatch}")
            return

        self.last_mismatch = ""
        self.answers.append({
            "problem_id": self.current_problem.get("id"),
            "problem": self.current_problem.get("description"),
            "problem_payload": deepcopy(self.current_problem),
            "reply": reply,
            "action": action or "NO_OP",
            "policy": self._build_interpretation_policy(self.current_problem, reply, action or "NO_OP"),
        })
        self._log_progress(
            f"[QA] Reply received for: {self.current_problem.get('description')}"
        )
        self.current_problem = None

    def finalize_decision(self) -> None:
        last_action = {}
        self.cleaning_policy_plans = []
        for item in self.answers:
            problem = item.get("problem")
            problem_payload = item.get("problem_payload") or {}
            action = item.get("action")
            policy = item.get("policy")
            policy_plan = self._build_cleaning_policy_plan(
                problem_payload,
                str(item.get("reply") or ""),
                action or "NO_OP",
            )
            if problem and action and action != "NO_OP":
                last_action[problem] = action
            if policy:
                self.interpretation_policies.append(str(policy))
            if policy_plan is not None:
                self.cleaning_policy_plans.append(policy_plan.to_dict())
        self.cleaning_actions = list(last_action.values())
        self._log_progress(
            f"[QA] actions={self._truncate(self.cleaning_actions)}"
        )
        if self.interpretation_policies:
            self._log_progress(
                f"[QA] policies={self._truncate(self.interpretation_policies)}"
            )

    def export_cleaning_actions(self) -> list:
        return self.cleaning_actions or []

    def export_cleaning_policy_plans(self) -> list:
        return [dict(plan) for plan in (self.cleaning_policy_plans or [])]

    def clear_cleaning_actions(self) -> None:
        self.cleaning_actions = []
        self.cleaning_policy_plans = []
        self.interpretation_policies = []

    def export_interpretation_policies(self) -> list:
        return self.interpretation_policies or []

    def get_last_mismatch(self) -> str:
        return self.last_mismatch

    def clear_last_mismatch(self) -> None:
        self.last_mismatch = ""


    @staticmethod
    def _format_quality_table(quality_table: list) -> str:
        if not quality_table:
            return "(none)"
        lines = []
        for item in quality_table:
            desc = item.get("description") if isinstance(item, dict) else str(item)
            lines.append(f"- {desc}")
        return "\n".join(lines)

    @staticmethod
    def _problem_description(problem: Any) -> str:
        if isinstance(problem, dict):
            return problem.get("description", str(problem))
        return str(problem)

    @staticmethod
    def _normalize_reply(reply: str) -> str:
        return " ".join((reply or "").strip().lower().split())

    @staticmethod
    def _normalize_option_token(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())
        return normalized

    @classmethod
    def _reply_polarity(cls, reply: str) -> Optional[bool]:
        normalized = cls._normalize_reply(reply)
        if not normalized:
            return None

        positive_markers = (
            "yes",
            "yeah",
            "yep",
            "correct",
            "do that",
            "go ahead",
            "use the latest available year",
            "use the latest year",
            "state that assumption",
            "normalize",
            "standardize",
            "convert",
        )
        negative_markers = (
            "no",
            "nope",
            "do not",
            "don't",
            "dont",
            "keep as is",
            "leave as is",
            "leave it as is",
        )

        has_positive = any(marker in normalized for marker in positive_markers)
        has_negative = any(marker in normalized for marker in negative_markers)
        if has_positive == has_negative:
            return None
        return has_positive

    @classmethod
    def _metadata_choice_options(cls, problem: Optional[Dict[str, Any]]) -> list[str]:
        metadata = (problem or {}).get("metadata") or {}
        issue_type = str((problem or {}).get("issue_type") or "")
        if issue_type == "duplicate_header":
            return [str(value).strip() for value in metadata.get("headers", []) if str(value).strip()]
        if issue_type == "missing_key_column":
            return [str(value).strip() for value in metadata.get("candidate_keys", []) if str(value).strip()]
        return []

    @classmethod
    def _ordinal_index_from_reply(cls, reply: str) -> Optional[int]:
        normalized = cls._normalize_reply(reply)
        if not normalized:
            return None
        ordinal_markers = (
            (0, ("first", "1st", "option 1", "option one", "the first one")),
            (1, ("second", "2nd", "option 2", "option two", "the second one")),
            (2, ("third", "3rd", "option 3", "option three", "the third one")),
        )
        for index, markers in ordinal_markers:
            if any(re.search(rf"\b{re.escape(marker)}\b", normalized) for marker in markers):
                return index
        return None

    @classmethod
    def _resolve_metadata_choice(cls, problem: Optional[Dict[str, Any]], reply: str) -> Optional[str]:
        options = cls._metadata_choice_options(problem)
        if not options:
            return None

        raw_reply = str(reply or "").strip()
        lowered_reply = raw_reply.lower()
        normalized_reply = cls._normalize_reply(reply)

        literal_matches = [option for option in options if option.lower() in lowered_reply]
        if len(literal_matches) == 1:
            return literal_matches[0]

        fuzzy_matches: list[str] = []
        for option in options:
            tokens = [token for token in re.split(r"[^a-z0-9]+", option.lower()) if token]
            if not tokens:
                continue
            pattern = r"\b" + r"[\s_\-./]*".join(re.escape(token) for token in tokens) + r"\b"
            if re.search(pattern, lowered_reply):
                fuzzy_matches.append(option)
                continue
            option_words = cls._normalize_reply(option)
            if option_words and re.search(rf"\b{re.escape(option_words)}\b", normalized_reply):
                fuzzy_matches.append(option)
        if len(fuzzy_matches) == 1:
            return fuzzy_matches[0]
        ordinal_index = cls._ordinal_index_from_reply(reply)
        if ordinal_index is not None and ordinal_index < len(options):
            return options[ordinal_index]
        return None

    @classmethod
    def _extract_question_options(cls, question: str) -> list[str]:
        quoted = [option.strip() for option in re.findall(r"`([^`]+)`", question or "") if option.strip()]
        if len(quoted) > 2 and re.search(r"\bor\b", question or "", flags=re.IGNORECASE):
            tail = quoted[-2:]
        else:
            tail = quoted
        unique: list[str] = []
        for option in tail:
            if option not in unique:
                unique.append(option)
        return unique

    @classmethod
    def _match_explicit_option(
        cls,
        question: str,
        reply: str,
        problem: Optional[Dict[str, Any]] = None,
    ) -> Optional[tuple[bool, str, str]]:
        options = cls._extract_question_options(question)
        if len(options) < 2:
            return None

        normalized_reply = cls._normalize_reply(reply)
        normalized_compact = cls._normalize_option_token(reply)
        if not normalized_reply and not normalized_compact:
            return None

        def _style_hint_matches(option: str) -> bool:
            option_has_space = bool(re.search(r"\s", option))
            option_has_hyphen = "-" in option
            option_has_underscore = "_" in option
            if option_has_space and any(
                marker in normalized_reply
                for marker in ("with a space", "with space", "spaced", "space-separated", "space separated")
            ):
                return True
            if (not option_has_space) and any(
                marker in normalized_reply
                for marker in ("without spaces", "without space", "no spaces", "no space", "compact", "no spacing")
            ):
                return True
            if option_has_hyphen and any(
                marker in normalized_reply
                for marker in ("with a hyphen", "hyphenated", "hyphen-separated", "hyphen separated")
            ):
                return True
            if option_has_underscore and any(
                marker in normalized_reply
                for marker in ("with an underscore", "underscored", "underscore-separated", "underscore separated")
            ):
                return True
            return False

        matched_option = None
        for option in options:
            normalized_option = cls._normalize_option_token(option)
            option_words = cls._normalize_reply(option)
            if not normalized_option:
                continue
            if normalized_option == normalized_compact:
                matched_option = option
                break
            if option_words and (
                re.search(rf"\b{re.escape(option_words)}\b", normalized_reply) is not None
                or normalized_option in normalized_compact
            ):
                matched_option = option
                break
            if _style_hint_matches(option):
                matched_option = option
                break

        ordinal_index = cls._ordinal_index_from_reply(reply)
        if matched_option is None and ordinal_index is not None and ordinal_index < len(options):
            matched_option = options[ordinal_index]

        if matched_option is None:
            return None

        metadata = (problem or {}).get("metadata") or {}
        issue_type = str((problem or {}).get("issue_type") or "")
        column_name = str(metadata.get("column") or "the column")
        sheet_key = str(metadata.get("sheet_key") or "the current sheet")
        if issue_type in {"format_inconsistency", "unit_or_time_format"}:
            return (
                True,
                f"Standardize `{column_name}` in `{sheet_key}` to `{matched_option}`.",
                "",
            )
        return True, matched_option, ""

    def _heuristic_match_reply(self, question: str, reply: str, problem: Optional[Dict[str, Any]] = None) -> Optional[tuple[bool, str, str]]:
        normalized_reply = self._normalize_reply(reply)
        if not normalized_reply:
            return False, "", "Please answer the question directly."

        issue_type = str((problem or {}).get("issue_type") or "")
        metadata = (problem or {}).get("metadata") or {}
        if issue_type == "missing_value_policy":
            if any(
                marker in normalized_reply
                for marker in (
                    "leave them blank",
                    "leave it blank",
                    "leave blank",
                    "leave as is",
                    "keep blank",
                    "keep them blank",
                    "keep missing",
                )
            ):
                return True, "NO_OP", ""
        if issue_type == "unit_or_time_format":
            formats = [str(value).strip() for value in metadata.get("formats", []) if str(value).strip()]
            if formats:
                chosen_format = None
                if any(marker in normalized_reply for marker in ("percentage", "percent")):
                    chosen_format = next((fmt for fmt in formats if "percent" in fmt), None)
                if chosen_format is None and "fraction" in normalized_reply:
                    chosen_format = next((fmt for fmt in formats if "fraction" in fmt), None)
                if chosen_format is None:
                    polarity = self._reply_polarity(reply)
                    if polarity is True:
                        chosen_format = formats[0]
                if chosen_format is not None:
                    sheet_key = str(metadata.get("sheet_key") or "current sheet")
                    column_name = str(metadata.get("column") or "value")
                    return (
                        True,
                        f"Standardize `{column_name}` in `{sheet_key}` to `{chosen_format}`.",
                        "",
                    )

        if issue_type == "missing_period_endpoint":
            if any(
                marker in normalized_reply
                for marker in ("interpolate", "shift", "exclude", "available requested years", "unavailable")
            ):
                return True, "NO_OP", ""
            polarity = self._reply_polarity(reply)
            if polarity is not None:
                return True, "NO_OP", ""

        if issue_type == "missing_value":
            if "depends on" in self._normalize_reply(question):
                if any(
                    marker in normalized_reply
                    for marker in (
                        "root task",
                        "no dependency",
                        "no dependencies",
                        "no prerequisite",
                        "leave it blank",
                        "leave blank",
                        "keep it blank",
                        "keep blank",
                    )
                ):
                    return True, "NO_OP", ""
            stripped = re.sub(r"[£$€¥]", "", (reply or "")).replace(",", "")
            normalized_stripped = self._normalize_reply(stripped)
            # Bare number: the entire reply is just a number ("0", "5.50").
            bare_match = re.fullmatch(r"\s*[-+]?\d+(?:\.\d+)?\s*", stripped)
            # Explicit action phrase: "treat as 0", "treat it as 0", "set to 200",
            # "fill with 0", etc. Handles optional pronoun/article between verb and "as/to".
            # Excludes ambiguous words like "is" / "equals" to avoid false positives.
            embedded_match = re.search(
                r"(?:treat(?:ed)?(?:\s+(?:it|them|this|that|the\s+\w+))?\s+as"
                r"|set\s+(?:it\s+)?to"
                r"|use"
                r"|fill\s+(?:it\s+)?with"
                r"|=)\s*([-+]?\d+(?:\.\d+)?)",
                stripped,
                flags=re.IGNORECASE,
            )
            numeric_str = None
            if bare_match:
                numeric_str = bare_match.group().strip()
            elif embedded_match:
                numeric_str = embedded_match.group(1)
            elif any(
                marker in normalized_stripped
                for marker in (
                    "0 spending",
                    "zero spending",
                    "0 value",
                    "zero value",
                    "0 amount",
                    "zero amount",
                    "0 cost",
                    "zero cost",
                    "0 pound",
                    "zero pound",
                    "0 pounds",
                    "zero pounds",
                )
            ):
                numeric_str = "0"
            elif (
                self._reply_polarity(reply) is True
                and any(
                    marker in normalized_stripped
                    for marker in ("missing value", "missing values", "blank", "empty")
                )
            ):
                numeric_str = "0"

            # Offline fallback: if the heuristics above didn't fire, try extracting
            # any standalone number mentioned anywhere in the reply (e.g. "use 0 for
            # missing entries", "I think 100 is appropriate").  Only used in offline
            # mode to avoid false positives when the cloud LLM can handle ambiguity.
            if numeric_str is None and self._is_offline:
                any_number = re.search(r"\b([-+]?\d+(?:\.\d+)?)\b", stripped)
                if any_number:
                    numeric_str = any_number.group(1)

            if numeric_str is not None:
                sheet_key = str(metadata.get("sheet_key") or "current sheet")
                column_name = str(metadata.get("column") or "value")
                excel_row = metadata.get("excel_row")
                row_text = f" at Excel row {excel_row}" if excel_row else ""
                return (
                    True,
                    f"Fill the missing value in `{column_name}`{row_text} in `{sheet_key}` with {numeric_str}.",
                    "",
                )

        metadata_choice = self._resolve_metadata_choice(problem, reply)
        if metadata_choice is not None:
            issue_type = str((problem or {}).get("issue_type") or "")
            if issue_type in {"duplicate_header", "missing_key_column"}:
                return True, "NO_OP", ""

        option_match = self._match_explicit_option(question, reply, problem)
        if option_match is not None:
            return option_match

        # Offline mode: for unresolved non-value issues, accept a substantive reply
        # as a policy decision, but only after issue-specific heuristics had a chance
        # to convert it into NO_OP or a concrete normalization action.
        if self._is_offline and issue_type != "missing_value":
            if len(normalized_reply.split()) > 5:
                return True, normalized_reply, ""

        return None

    def _build_interpretation_policy(self, problem: Dict[str, Any], reply: str, action: str) -> str:
        if action != "NO_OP":
            return ""
        normalized_reply = self._normalize_reply(reply)
        question_text = self._normalize_reply(
            str(problem.get("question") or problem.get("description") or "")
        )
        metadata = problem.get("metadata") or {}
        issue_type = str(problem.get("issue_type") or "")

        if issue_type == "missing_value" and "depends on" in question_text and (
            "root task" in normalized_reply
            or "root" in normalized_reply
            or "no prerequisite" in normalized_reply
            or "no dependency" in normalized_reply
            or "no dependencies" in normalized_reply
            or "does not depend on" in normalized_reply
            or "doesn't depend on" in normalized_reply
            or "depend on no other" in normalized_reply
            or "leave it blank" in normalized_reply
            or "leave blank" in normalized_reply
            or "keep it blank" in normalized_reply
            or "keep blank" in normalized_reply
        ):
            sheet_key = str(metadata.get("sheet_key") or "current sheet")
            column_name = str(metadata.get("column") or "Depends on")
            excel_row = metadata.get("excel_row")
            row_text = f" at Excel row {excel_row}" if excel_row else ""
            return (
                f"Interpret blank `{column_name}`{row_text} in `{sheet_key}` as meaning the task is a root task "
                "with no prerequisite dependency."
            )
        if issue_type == "missing_value_policy":
            sheet_key = str(metadata.get("sheet_key") or "current sheet")
            column_name = str(metadata.get("column") or "value")
            if any(
                marker in normalized_reply
                for marker in (
                    "leave them blank",
                    "leave it blank",
                    "leave blank",
                    "leave as is",
                    "keep blank",
                    "keep them blank",
                    "keep missing",
                )
            ):
                return f"Leave missing `{column_name}` values unchanged in `{sheet_key}`."
        chosen_option = self._resolve_metadata_choice(problem, reply)
        if issue_type == "missing_key_column" and chosen_option:
            sheet_key = str(metadata.get("sheet_key") or "current sheet")
            return (
                f"Use `{chosen_option}` as the matching key for sheet `{sheet_key}` during multi-file alignment."
            )
        if issue_type == "duplicate_header" and chosen_option:
            sheet_key = str(metadata.get("sheet_key") or "current sheet")
            return (
                f"Treat header `{chosen_option}` as the authoritative field in `{sheet_key}` when equivalent normalized headers compete."
            )
        if issue_type == "missing_period_endpoint":
            available_years = [
                int(value)
                for value in metadata.get("available_years", [])
                if str(value).strip()
            ]
            available_requested_years = [
                int(value)
                for value in metadata.get("available_requested_years", [])
                if str(value).strip()
            ]
            latest_available = max(available_years) if available_years else None
            requested_years = [
                str(value).strip()
                for value in metadata.get("requested_years", [])
                if str(value).strip()
            ]
            missing_years = sorted(
                {
                    int(value)
                    for value in requested_years
                    if str(value).strip().isdigit()
                }
                - set(available_years)
            )
            sheet_key = str(metadata.get("sheet_key") or "current sheet")
            if any(marker in normalized_reply for marker in ("interpolate", "interpolation")):
                missing_text = ", ".join(str(year) for year in missing_years) if missing_years else "missing years"
                return (
                    f"When requested years are unavailable in `{sheet_key}`, interpolate the missing years "
                    f"({missing_text}) from neighboring available years and state that assumption in the result."
                )
            if latest_available is None:
                return ""
            if any(
                marker in normalized_reply
                for marker in (
                    "no",
                    "nope",
                    "do not",
                    "don't",
                    "dont",
                    "not use",
                    "do not use",
                )
            ):
                requested_text = ", ".join(requested_years) if requested_years else "the requested years"
                return (
                    f"Do not substitute missing requested years ({requested_text}) in `{sheet_key}`; "
                    "state that the data is unavailable for the requested period."
                )
            if available_requested_years and any(
                marker in normalized_reply
                for marker in ("shift", "exclude", "available requested years", "2021", "2022", "2023", "2024")
            ):
                start_year = min(available_requested_years)
                end_year = max(available_requested_years)
                return (
                    f"When requested years are unavailable in `{sheet_key}`, restrict the analysis window to the available requested years "
                    f"`{start_year}`-`{end_year}` and state that adjustment in the result."
                )
            return (
                f"When requested years are unavailable in `{sheet_key}`, use the latest available year "
                f"`{latest_available}` instead and state that assumption in the result."
            )
        return ""

    @staticmethod
    def _groupable_missing_value_key(problem: Any) -> Optional[tuple[str, str, str]]:
        if not isinstance(problem, dict):
            return None
        if str(problem.get("issue_type") or "") != "missing_value":
            return None
        metadata = problem.get("metadata") or {}
        sheet_key = str(metadata.get("sheet_key") or "").strip()
        column = str(metadata.get("column") or "").strip()
        description = str(problem.get("description") or "").lower()
        question = str(problem.get("question") or "").lower()
        if not sheet_key or not column:
            return None
        if column.lower() == "depends on":
            return None
        if "depends on" in description or "depends on" in question:
            return None
        return (str(problem.get("issue_type") or ""), sheet_key, column)

    def _build_grouped_missing_value_problem(self, problems: list[Dict[str, Any]]) -> Dict[str, Any]:
        first = deepcopy(problems[0])
        metadata = deepcopy(first.get("metadata") or {})
        sheet_key = str(metadata.get("sheet_key") or "current sheet")
        column = str(metadata.get("column") or "value")
        affected_rows = [
            int(row)
            for row in (
                (problem.get("metadata") or {}).get("excel_row")
                for problem in problems
            )
            if row is not None
        ]
        issue_group = QAIssueGroup(
            issue_type="missing_value_policy",
            sheet_key=sheet_key,
            column=column,
            affected_rows=tuple(affected_rows),
        )
        metadata["affected_rows"] = list(issue_group.affected_rows)
        first["id"] = f"missing_value::{sheet_key}::{column}"
        first["issue_type"] = issue_group.issue_type
        first["description"] = f"Column `{column}` has multiple missing values."
        first["question"] = (
            f"For missing `{column}` values, should I leave them blank, fill a default value, or drop those rows?"
        )
        first["metadata"] = metadata
        return first

    def _group_policy_questions(self, question_list: list) -> list:
        grouped_problems: dict[tuple[str, str, str], list[Dict[str, Any]]] = {}
        for item in question_list:
            key = self._groupable_missing_value_key(item)
            if key is None:
                continue
            grouped_problems.setdefault(key, []).append(item)

        emitted_group_keys: set[tuple[str, str, str]] = set()
        output: list = []
        for item in question_list:
            key = self._groupable_missing_value_key(item)
            if key is None:
                output.append(item)
                continue
            group = grouped_problems.get(key, [])
            if len(group) <= 1:
                output.append(item)
                continue
            if key in emitted_group_keys:
                continue
            output.append(self._build_grouped_missing_value_problem(group))
            emitted_group_keys.add(key)
        return output

    @staticmethod
    def _build_cleaning_policy_plan(
        problem: Dict[str, Any],
        reply: str,
        action: str,
    ) -> Optional[CleaningPolicyPlan]:
        if not isinstance(problem, dict):
            return None
        issue_type = str(problem.get("issue_type") or "")
        metadata = problem.get("metadata") or {}
        normalized_reply = " ".join((reply or "").strip().lower().split())
        if issue_type == "missing_value_policy":
            if action == "NO_OP" and any(
                marker in normalized_reply
                for marker in (
                    "leave them blank",
                    "leave it blank",
                    "leave blank",
                    "leave as is",
                    "keep blank",
                    "keep them blank",
                    "keep missing",
                )
            ):
                return CleaningPolicyPlan(
                    policy_kind="missing_value",
                    sheet_key=str(metadata.get("sheet_key") or "current sheet"),
                    column=str(metadata.get("column") or "value"),
                    affected_rows=tuple(int(row) for row in metadata.get("affected_rows", []) if row is not None),
                    resolution="leave_blank",
                )
        return None

    def _match_reply(self, question_or_problem: Any, reply: str) -> tuple[bool, str, str]:
        if isinstance(question_or_problem, dict):
            problem = question_or_problem
            question = str(problem.get("question") or problem.get("description") or "")
        else:
            problem = None
            question = str(question_or_problem or "")

        heuristic = self._heuristic_match_reply(question, reply, problem)
        if heuristic is not None:
            return heuristic

        if self.client is None:
            return False, "", "Please answer the question directly."

        prompt_text = self.prompt_builder.build_qa_match_prompt(
            self._augment_question_with_problem_context(question, problem),
            reply,
        )
        messages = [{"role": "user", "content": prompt_text}]
        llm_kwargs = {}
        if self._is_offline:
            llm_kwargs["max_tokens"] = 256
        try:
            content = call_llm(self.client, self.deployment, messages, **llm_kwargs)
        except Exception:
            return False, "", "Unable to verify reply."

        decision = self._parse_match_action(content)
        self._last_structured_decision = decision
        match = bool(decision.get("match"))
        action = self._coerce_action_from_structured_decision(problem, decision)
        feedback = "" if match else self._build_match_feedback(problem, decision)
        return match, action, feedback

    @staticmethod
    def _parse_match_action(content: str) -> Dict[str, str]:
        decision: Dict[str, str] = {
            "match": "",
            "action": "",
            "decision_kind": "",
            "value": "",
            "selected_option": "",
            "policy_kind": "",
            "missing_slot": "",
        }
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            upper = line.upper()
            if upper.startswith("MATCH:") or upper.startswith("MATCH ="):
                parts = line.split(":", 1) if ":" in line else line.split("=", 1)
                if len(parts) == 2:
                    value = parts[1].strip().upper()
                    decision["match"] = "YES" if value == "YES" else "NO"
            if upper.startswith("DECISION_KIND:") or upper.startswith("DECISION_KIND ="):
                parts = line.split(":", 1) if ":" in line else line.split("=", 1)
                if len(parts) == 2:
                    decision["decision_kind"] = parts[1].strip()
            if upper.startswith("VALUE:") or upper.startswith("VALUE ="):
                parts = line.split(":", 1) if ":" in line else line.split("=", 1)
                if len(parts) == 2:
                    decision["value"] = parts[1].strip()
            if upper.startswith("SELECTED_OPTION:") or upper.startswith("SELECTED_OPTION ="):
                parts = line.split(":", 1) if ":" in line else line.split("=", 1)
                if len(parts) == 2:
                    decision["selected_option"] = parts[1].strip()
            if upper.startswith("POLICY_KIND:") or upper.startswith("POLICY_KIND ="):
                parts = line.split(":", 1) if ":" in line else line.split("=", 1)
                if len(parts) == 2:
                    decision["policy_kind"] = parts[1].strip()
            if upper.startswith("MISSING_SLOT:") or upper.startswith("MISSING_SLOT ="):
                parts = line.split(":", 1) if ":" in line else line.split("=", 1)
                if len(parts) == 2:
                    decision["missing_slot"] = parts[1].strip()
            if upper.startswith("ACTION:") or upper.startswith("ACTION ="):
                parts = line.split(":", 1) if ":" in line else line.split("=", 1)
                if len(parts) == 2:
                    decision["action"] = parts[1].strip()
        action = decision["action"].strip().lower()
        if decision["match"] == "YES" and action in {"", "none", "no_op", "no action", "ignore", "keep", "keep as-is", "as-is"}:
            decision["action"] = "NO_OP" if action in {"none", "no_op", "no action", "ignore", "keep", "keep as-is", "as-is"} else ""
        return decision

    @classmethod
    def _augment_question_with_problem_context(
        cls,
        question: str,
        problem: Optional[Dict[str, Any]],
    ) -> str:
        if not problem:
            return question
        metadata = problem.get("metadata") or {}
        metadata_lines = [f"- {key}: {value}" for key, value in metadata.items()]
        context_lines = [
            question,
            "",
            "Problem Context:",
            f"- issue_type: {problem.get('issue_type', '')}",
            f"- description: {problem.get('description', '')}",
        ]
        if metadata_lines:
            context_lines.append("- metadata:")
            context_lines.extend(metadata_lines)
        return "\n".join(context_lines).strip()

    @classmethod
    def _coerce_action_from_structured_decision(
        cls,
        problem: Optional[Dict[str, Any]],
        decision: Dict[str, str],
    ) -> str:
        action = str(decision.get("action") or "").strip()
        if action:
            return action
        if not problem:
            return ""
        issue_type = str(problem.get("issue_type") or "")
        metadata = problem.get("metadata") or {}
        decision_kind = cls._normalize_reply(decision.get("decision_kind", "").replace("_", " "))
        if decision_kind in {"no op", "no_op", "no change", "keep", "keep as is"}:
            return "NO_OP"
        if issue_type == "missing_value" and decision_kind == "fill value":
            numeric_str = str(decision.get("value") or "").strip()
            if numeric_str:
                sheet_key = str(metadata.get("sheet_key") or "current sheet")
                column_name = str(metadata.get("column") or "value")
                excel_row = metadata.get("excel_row")
                row_text = f" at Excel row {excel_row}" if excel_row else ""
                return (
                    f"Fill the missing value in `{column_name}`{row_text} in `{sheet_key}` with {numeric_str}."
                )
        return ""

    @classmethod
    def _build_match_feedback(
        cls,
        problem: Optional[Dict[str, Any]],
        decision: Dict[str, str],
    ) -> str:
        issue_type = str((problem or {}).get("issue_type") or "")
        missing_slot = str(decision.get("missing_slot") or "").strip()
        if issue_type == "missing_value":
            if missing_slot:
                return f"I couldn't identify the fill value yet. Missing: {missing_slot}."
            return "I couldn't identify what value you want to use for the missing cell."
        if missing_slot:
            return f"I couldn't determine the requested decision yet. Missing: {missing_slot}."
        return "Please answer the question directly."

    def _ensure_qa_scope(self, question: str) -> str:
        original = str(self.current_problem.get("description", "")).strip()
        if not original:
            return question
        original_lower = original.lower()
        question_lower = question.lower()
        forbidden = {"drop", "remove", "delete", "discard", "ignore"}
        if not any(term in original_lower for term in forbidden):
            if any(term in question_lower for term in forbidden):
                return original
        if ("format" in original_lower or "standard" in original_lower or "normalize" in original_lower):
            if any(term in question_lower for term in {"drop", "remove", "keep", "ignore"}):
                return original
        return question

    @staticmethod
    def _filter_format_questions(question_list: list) -> list:
        if not question_list:
            return []
        keywords = {"time", "times", "day", "days", "date", "dates"}
        email_keywords = {"email", "e-mail"}
        email_format_terms = {
            "format", "casing", "case", "separator", "token", "whitespace", "spacing", "trim"
        }
        filtered = []
        for item in question_list:
            if isinstance(item, dict) and item.get("source") == "router_evidence":
                filtered.append(item)
                continue
            if isinstance(item, dict):
                description = str(item.get("description", "")).strip()
            else:
                description = str(item).strip()
            desc_lower = description.lower()
            if "format" in desc_lower and "inconsist" in desc_lower:
                if any(keyword in desc_lower for keyword in keywords):
                    continue
            if any(keyword in desc_lower for keyword in email_keywords):
                if any(term in desc_lower for term in email_format_terms):
                    continue
            filtered.append(item)
        return filtered

    def _log_progress(self, message: str) -> None:
        if self.progress_logger is None:
            logger.info(message)
            return
        self.progress_logger.log(message, to_terminal=False)

    @staticmethod
    def _truncate(value: Any, limit: int = 300) -> str:
        text = str(value)
        if len(text) <= limit:
            return text
        return text[:limit] + "..."
