"""Parse validation LLM responses into structured results."""

import json
import re
from typing import Any, Dict

from ...log.logger_registry import LoggerRegistry
from ..base.response_parser import BaseResponseParser

logger = LoggerRegistry.setup_logger(__name__)


class ValidationResponseParser(BaseResponseParser):
    """Extract structured validation data from LLM response text."""

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "passed", "pass", "yes", "1"}
        if isinstance(value, (int, float)):
            return bool(value)
        return False

    @staticmethod
    def _extract_json_payload(validation_text: str) -> Dict[str, Any]:
        candidates = [validation_text.strip()]

        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", validation_text, re.IGNORECASE)
        if fenced:
            candidates.append(fenced.group(1).strip())

        obj_match = re.search(r"\{[\s\S]*\}", validation_text)
        if obj_match:
            candidates.append(obj_match.group(0).strip())

        for candidate in candidates:
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue

        return {}

    def parse(self, validation_text: str) -> Dict[str, Any]:
        try:
            text = validation_text or ""
            result = {
                "validation_passed": False,
                "confidence_score": 0.0,
                "issues_found": [],
                "improvement_feedback": "",
                "final_assessment": "",
                "verified_answer": "",
                "requires_reexecution": False
            }

            parsed_json = self._extract_json_payload(validation_text)
            if parsed_json:
                if "validation_passed" in parsed_json:
                    result["validation_passed"] = self._coerce_bool(
                        parsed_json.get("validation_passed")
                    )
                if "confidence_score" in parsed_json:
                    try:
                        result["confidence_score"] = float(parsed_json.get("confidence_score", 0.0))
                    except (TypeError, ValueError):
                        result["confidence_score"] = 0.0
                if isinstance(parsed_json.get("issues_found"), list):
                    result["issues_found"] = [
                        str(issue).strip() for issue in parsed_json["issues_found"] if str(issue).strip()
                    ]
                if "improvement_feedback" in parsed_json:
                    feedback = parsed_json.get("improvement_feedback")
                    if isinstance(feedback, list):
                        result["improvement_feedback"] = "\n".join(
                            str(item).strip() for item in feedback if str(item).strip()
                        )
                    else:
                        result["improvement_feedback"] = str(feedback or "").strip()
                if "final_assessment" in parsed_json:
                    result["final_assessment"] = str(parsed_json.get("final_assessment") or "").strip()

                return result

            # Fallback: tolerate markdown key-value style like
            # "1. **validation_passed**: true"
            parsed_from_kv = False
            kv_has_validation_flag = False

            kv_bool = re.search(
                r"(?:^|\n)[ \t]*(?:\d+\.[ \t]*)?(?:\*\*)?validation_passed(?:\*\*)?[ \t]*:[ \t]*([^\n]+)",
                text,
                re.IGNORECASE,
            )
            if kv_bool:
                bool_raw = kv_bool.group(1).strip()
                if bool_raw and bool_raw != "**":
                    result["validation_passed"] = self._coerce_bool(bool_raw)
                    parsed_from_kv = True
                    kv_has_validation_flag = True

            kv_conf = re.search(
                r"(?:^|\n)[ \t]*(?:\d+\.[ \t]*)?(?:\*\*)?confidence_score(?:\*\*)?[ \t]*:[ \t]*([0-9]*\.?[0-9]+)",
                text,
                re.IGNORECASE,
            )
            if kv_conf:
                result["confidence_score"] = float(kv_conf.group(1))
                parsed_from_kv = True

            kv_issues = re.search(
                r"(?:^|\n)[ \t]*(?:\d+\.[ \t]*)?(?:\*\*)?issues_found(?:\*\*)?[ \t]*:[ \t]*([^\n]+)",
                text,
                re.IGNORECASE,
            )
            if kv_issues:
                issues_raw = kv_issues.group(1).strip()
                if issues_raw.lower().strip() in {
                    "[]", "none", "none.", "none identified", "none identified."
                }:
                    result["issues_found"] = []
                    parsed_from_kv = True
                elif issues_raw:
                    if issues_raw != "**":
                        # Keep as a single issue line when non-empty plain text is returned.
                        result["issues_found"] = [issues_raw]
                        parsed_from_kv = True

            kv_feedback = re.search(
                r"(?:^|\n)[ \t]*(?:\d+\.[ \t]*)?(?:\*\*)?improvement_feedback(?:\*\*)?[ \t]*:[ \t]*([^\n]+)",
                text,
                re.IGNORECASE,
            )
            if kv_feedback:
                feedback_raw = kv_feedback.group(1).strip()
                if feedback_raw and feedback_raw != "**":
                    result["improvement_feedback"] = feedback_raw
                    parsed_from_kv = True

            kv_assessment = re.search(
                r"(?:^|\n)[ \t]*(?:\d+\.[ \t]*)?(?:\*\*)?final_assessment(?:\*\*)?[ \t]*:[ \t]*([^\n]+)",
                text,
                re.IGNORECASE,
            )
            if kv_assessment:
                assessment_raw = kv_assessment.group(1).strip()
                if assessment_raw and assessment_raw != "**":
                    result["final_assessment"] = assessment_raw
                    parsed_from_kv = True

            # Return early only when KV text includes an explicit pass/fail flag.
            # Otherwise keep parsing structured headings like
            # "VALIDATION_STATUS: PASSED" below.
            if parsed_from_kv and kv_has_validation_flag:
                return result

            validation_match = re.search(
                r'(\*\*)?VALIDATION_STATUS:(\*\*)?\s*\[?(PASSED|FAILED)\]?',
                text,
                re.IGNORECASE
            )
            if validation_match:
                result["validation_passed"] = (
                    validation_match.group(3).upper() == "PASSED"
                )

            confidence_match = re.search(
                r'(\*\*)?CONFIDENCE_SCORE:(\*\*)?\s*\[?([0-9]*\.?[0-9]+)\]?',
                text
            )
            if confidence_match:
                result["confidence_score"] = float(confidence_match.group(3))

            # 3) Offline format fallback: validation_passed / confidence_score / ...
            bool_match = re.search(r"validation_passed\s*[:=]\s*(true|false)", text, re.IGNORECASE)
            if bool_match:
                result["validation_passed"] = bool_match.group(1).lower() == "true"
            cs_match = re.search(r"confidence_score\s*[:=]\s*([0-9]*\.?[0-9]+)", text, re.IGNORECASE)
            if cs_match:
                result["confidence_score"] = float(cs_match.group(1))

            issues_section = re.search(
                r'(\*\*)?ISSUES_FOUND:(\*\*)?(.*?)(\*\*)?IMPROVEMENT_FEEDBACK:(\*\*)?',
                text,
                re.DOTALL
            )
            if issues_section:
                issues_text = issues_section.group(3).strip()
                issues = [
                    line.strip('- ').strip()
                    for line in issues_text.split('\n')
                    if line.strip().startswith('-')
                ]
                def _is_none_issue(s: str) -> bool:
                    normalized = s.strip().lower().rstrip(".! ")
                    return normalized in {"none", "none identified"}
                result["issues_found"] = [
                    issue for issue in issues
                    if issue and not _is_none_issue(issue)
                ]
            elif not result["issues_found"]:
                issues_key_section = re.search(
                    r"issues_found\s*[:=]\s*(.*?)(?:improvement_feedback|final_assessment|$)",
                    text,
                    re.IGNORECASE | re.DOTALL
                )
                if issues_key_section:
                    issues_text = issues_key_section.group(1).strip()
                    parsed_issues = []
                    # bullet-style
                    for line in issues_text.splitlines():
                        line = line.strip()
                        if line.startswith("- "):
                            parsed_issues.append(line[2:].strip())
                    if not parsed_issues and issues_text and issues_text.lower() not in {"[]", "none", "none identified.", "none identified"}:
                        parsed_issues = [issues_text]
                    result["issues_found"] = [i for i in parsed_issues if i]

            feedback_section = re.search(
                r'(\*\*)?IMPROVEMENT_FEEDBACK:(\*\*)?(.*?)(\*\*)?FINAL_ASSESSMENT:(\*\*)?',
                text,
                re.DOTALL
            )
            if feedback_section:
                result["improvement_feedback"] = feedback_section.group(3).strip()
            elif not result["improvement_feedback"]:
                fb_match = re.search(
                    r"improvement_feedback\s*[:=]\s*(.*?)(?:final_assessment|$)",
                    text,
                    re.IGNORECASE | re.DOTALL
                )
                if fb_match:
                    result["improvement_feedback"] = fb_match.group(1).strip()

            assessment_section = re.search(
                r'(\*\*)?FINAL_ASSESSMENT:(\*\*)?(.*?)$',
                text,
                re.DOTALL
            )
            if assessment_section:
                result["final_assessment"] = assessment_section.group(3).strip()
            elif not result["final_assessment"]:
                ass_match = re.search(
                    r"final_assessment\s*[:=]\s*(.*?)$",
                    text,
                    re.IGNORECASE | re.DOTALL
                )
                if ass_match:
                    result["final_assessment"] = ass_match.group(1).strip()

            return result

        except Exception as e:
            logger.error(f"Error parsing validation response: {str(e)}")
            return {
                "validation_passed": False,
                "confidence_score": 0.0,
                "issues_found": [f"Failed to parse validation response: {str(e)}"],
                "improvement_feedback": "Manual review required due to parsing error",
                "final_assessment": "Parsing error occurred during validation",
                "verified_answer": "",
                "requires_reexecution": False
            }

    @staticmethod
    def _try_parse_json_object(text: str) -> Dict[str, Any] | None:
        if not text:
            return None
        candidates = []
        fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if fenced:
            candidates.append(fenced.group(1))
        plain = re.search(r"(\{.*\})", text, re.DOTALL)
        if plain:
            candidates.append(plain.group(1))
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
        return None

    @staticmethod
    def _merge_from_json(result: Dict[str, Any], obj: Dict[str, Any]) -> None:
        if "validation_passed" in obj:
            result["validation_passed"] = bool(obj.get("validation_passed"))
        if "confidence_score" in obj:
            try:
                result["confidence_score"] = float(obj.get("confidence_score"))
            except Exception:
                pass
        if "issues_found" in obj:
            raw = obj.get("issues_found")
            if isinstance(raw, list):
                result["issues_found"] = [str(i).strip() for i in raw if str(i).strip()]
            elif isinstance(raw, str) and raw.strip():
                if raw.strip().lower() not in {"none", "none identified", "none identified."}:
                    result["issues_found"] = [raw.strip()]
        if "improvement_feedback" in obj:
            feedback = obj.get("improvement_feedback")
            if isinstance(feedback, list):
                result["improvement_feedback"] = "\n".join(str(i) for i in feedback if str(i).strip())
            elif feedback is not None:
                result["improvement_feedback"] = str(feedback).strip()
        if "final_assessment" in obj and obj.get("final_assessment") is not None:
            result["final_assessment"] = str(obj.get("final_assessment")).strip()
